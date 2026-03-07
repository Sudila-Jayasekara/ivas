"""
Evaluation Service — LLM Layer Architecture

Three-layer LLM pipeline for evaluating student responses:

  Layer 1 — Input Guard (real-time):
      LLM decides the next instructor ACTION based on the student's response:
        - evaluate:        Student is attempting → proceed to Layer 2
        - teach_and_skip:  No conceptual content → LLM teaches + move on
        - warn_and_reask:  Abusive content → LLM-generated warning + re-ask

  Layer 2 — Quick Evaluation (real-time):
      Scores the response and produces brief feedback + justification.
      Needed in real-time for branching logic (follow-up / re-ask / next).

  Layer 3 — Deep Analysis (background):
      Generates detailed score justification, thorough misconception analysis,
      and competency depth assessment. Written to DB asynchronously.
"""

import json
import logging
from dataclasses import dataclass, field

from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


# ── Data classes ──────────────────────────────────────────────────────

@dataclass
class InputGuardResult:
    action: str      # "evaluate" | "teach_and_skip" | "explain_and_reask" | "clarify_relevance" | "warn_and_reask"
    reason: str      # Brief LLM explanation
    warning: str = ""           # LLM-generated warning (only for warn_and_reask)
    explanation: str = ""       # LLM-generated explanation (for explain_and_reask / clarify_relevance)


@dataclass
class EvaluationResult:
    score: float  # 0.0 – 10.0
    feedback: str
    misconceptions: list[str]
    competency_scores: dict[str, float]
    justification: str = ""  # LLM's reasoning for the given score
    next_action: str = "advance"  # "advance" | "follow_up" | "re_ask"


@dataclass
class DeepAnalysisResult:
    justification: str           # Detailed score justification
    misconceptions: list[str]    # Thorough misconception list
    understanding_level: str     # "none" | "surface" | "partial" | "solid" | "deep"
    suggestions: list[str]       # Specific study/improvement suggestions


# Fixed max points for all questions — ensures fairness
MAX_POINTS = 10


class EvaluationService:
    """Three-layer LLM evaluation pipeline."""

    # ==================================================================
    # LAYER 1 — Input Guard  (real-time, fast)
    # ==================================================================

    @staticmethod
    def _build_guard_prompt(student_answer: str, question_text: str, conversation_history: str = "") -> str:
        history_block = ""
        if conversation_history:
            history_block = f"\n{conversation_history}\n"

        return f"""You are a REAL human instructor conducting an oral viva exam. You care about your student and want to help them learn while fairly assessing their understanding.

SPEECH-TO-TEXT NOTE: The student spoke into a microphone. There WILL be transcription errors — interpret garbled words by sound/context. Focus on MEANING and INTENT.

QUESTION ASKED: {question_text}

STUDENT SAID: "{student_answer}"
{history_block}
Decide the NEXT ACTION based on what the student actually MEANT:

═══════════════════════════════════════════════════════════════
⚠️ MOST IMPORTANT RULE — DEFAULT TO "evaluate"
═══════════════════════════════════════════════════════════════
When in doubt, ALWAYS choose "evaluate".
It is FAR better to evaluate a confused/messy answer (and give it a low score with helpful feedback)
than to refuse to evaluate a genuine attempt.

A student saying something WRONG or UNCLEAR about the topic IS an answer attempt — NOT a request for help.
Fragmented sentences, garbled speech, or poorly articulated ideas are STILL answer attempts if they
contain ANY words related to the topic being asked about.

═══════════════════════════════════════════════════════════════

1. "evaluate": The student is genuinely ATTEMPTING to answer the question with conceptual content — even if wrong, vague, partial, fragmented, or poorly worded. Choose this if there are ANY topic-related words or ideas in the response.
   Examples that MUST be "evaluate":
   - "Loop check condition if true it repeat" → EVALUATE (talking about loops!)
   - "we use for loop set variable check condition" → EVALUATE (describing loop mechanics!)
   - "array is like memory address shelf number" → EVALUATE (discussing arrays!)
   - "two loops one for x axis one for y axis" → EVALUATE (explaining nested loops!)
   - Any response mentioning technical terms related to the question → EVALUATE

2. "teach_and_skip": The student has absolutely NO conceptual content to evaluate. This includes:
   - Explicitly doesn't know ("I don't know", "no idea")
   - Wants to skip ("can we skip?", "next question")
   - Deflections with zero technical content ("because I'm lazy", "I just do")
   - Bare affirmations with NO reasoning ("yes", "I think so", "maybe")
   - Empty acknowledgements ("ok", "sure", "right")
   ⚠️ CRITICAL: A deflection like "because I'm lazy" is NOT an attempt to answer. Do NOT evaluate it.

3. "explain_and_reask": ONLY when the student is EXPLICITLY asking YOU a question or requesting help. They must be directing a question or request AT YOU. This includes:
   - Asking for clarification ("can you explain?", "what do you mean?", "I don't understand the question")
   - Asking to redo ("can I try again?", "let me redo this")
   - Asking for a hint ("can you give me a hint?")
   ⚠️ CRITICAL: This is ONLY for when the student is asking YOU something. If the student is ANSWERING (even badly), choose "evaluate" instead. A messy, fragmented, or wrong answer is NOT a request for help — it is an answer attempt.

4. "clarify_relevance": The student is questioning WHY this topic is being asked — they don't see the connection to their assignment.
   - "Why are you asking about this?"
   - "What does this have to do with my code?"

5. "warn_and_reask": The student is being abusive, offensive, or deliberately disruptive. Generate a firm but professional warning.

DECISION CHECKLIST (follow in order):
1. Does the response contain ANY words related to the topic/question? → "evaluate"
2. Is the student explicitly asking YOU a question or requesting help? → "explain_and_reask"
3. Is the student questioning why the topic matters? → "clarify_relevance"
4. Is the response abusive or offensive? → "warn_and_reask"
5. Is there zero content at all? → "teach_and_skip"

Return ONLY valid JSON:
For evaluate/teach_and_skip: {{"action": "<action>", "reason": "brief explanation"}}
For explain_and_reask: {{"action": "explain_and_reask", "reason": "brief explanation", "explanation": "Your kind, simple re-explanation of what the question is asking, in 1-2 sentences"}}
For clarify_relevance: {{"action": "clarify_relevance", "reason": "brief explanation", "explanation": "Your brief explanation of WHY this topic is relevant to their assignment, in 1-2 sentences"}}
For warn_and_reask: {{"action": "warn_and_reask", "reason": "brief explanation", "warning": "Your firm but professional warning"}}""".strip()

    VALID_GUARD_ACTIONS = ("evaluate", "teach_and_skip", "explain_and_reask", "clarify_relevance", "warn_and_reask")

    @staticmethod
    def _parse_guard_response(raw: str) -> InputGuardResult:
        try:
            text = raw.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end == 0:
                return InputGuardResult(action="evaluate", reason="parse_fallback")
            data = json.loads(text[start:end])
            action = str(data.get("action", "evaluate")).lower().strip()
            if action not in EvaluationService.VALID_GUARD_ACTIONS:
                action = "evaluate"
            reason = str(data.get("reason", ""))
            warning = str(data.get("warning", ""))
            explanation = str(data.get("explanation", ""))
            return InputGuardResult(action=action, reason=reason, warning=warning, explanation=explanation)
        except (json.JSONDecodeError, ValueError, TypeError):
            return InputGuardResult(action="evaluate", reason="parse_fallback")

    def classify_input(self, student_answer: str, question_text: str, conversation_history: str = "") -> InputGuardResult:
        """Layer 1: Classify student input via LLM. Fast, small prompt. Synchronous."""
        if not student_answer or not student_answer.strip():
            return InputGuardResult(action="teach_and_skip", reason="empty input")

        try:
            raw = llm_service.generate(
                prompt=self._build_guard_prompt(student_answer, question_text, conversation_history),
                temperature=0.1,
                max_output_tokens=150,
                num_predict=150,
            )
            result = self._parse_guard_response(raw)
            logger.debug("Input guard: action=%s — %s", result.action, result.reason)
            return result
        except Exception as e:
            logger.error("Input guard LLM failed: %s", e)
            return InputGuardResult(action="evaluate", reason="guard_error_fallback")

    # ==================================================================
    # LAYER 2 — Quick Evaluation  (real-time)
    # ==================================================================

    @staticmethod
    def _build_evaluation_prompt(
        question_text: str,
        expected_answer: str,
        student_answer: str,
        competency: str,
        difficulty: int,
        max_points: int,
        code_context: str = "",
    ) -> str:
        code_section = ""
        if code_context:
            code_section = f"\nBACKGROUND (student's code for reference only — do NOT evaluate the code itself):\n{code_context}\n"

        return f"""You are a REAL human instructor conducting an oral viva to assess a BEGINNER student's CONCEPTUAL UNDERSTANDING of a TECHNICAL PROGRAMMING CONCEPT.

PURPOSE: Check whether the student truly UNDERSTANDS the TECHNICAL CONCEPT
being tested — WHY it exists, WHEN to use it, and HOW it works.
This is NOT about whether the student can describe their program's behavior.
Focus on their understanding of the CONCEPT, not the scenario.

SPEECH-TO-TEXT NOTE:
The student spoke into a microphone and speech was converted to text.
- There WILL be transcription errors and garbled words
- Focus on MEANING and INTENT, not exact wording
- Technical terms may be misspelled or garbled by speech recognition
- Be lenient with TRANSCRIPTION quality, but STRICT with conceptual accuracy

QUESTION: {question_text}
EXPECTED CONCEPTUAL ANSWER: {expected_answer}
STUDENT'S SPOKEN ANSWER: {student_answer}
{code_section}
TECHNICAL CONCEPT BEING TESTED: {competency}
DIFFICULTY: {difficulty}/5
MAX POINTS: {max_points}

═══════════════════════════════════════════════════════════════
SCORING RUBRIC — BASED ON CONCEPT UNDERSTANDING
═══════════════════════════════════════════════════════════════

Score based on how well the student understands the PROGRAMMING CONCEPT —
not how well they describe the assignment scenario or what their program does.

9-10 (EXCELLENT): Clearly explains WHY/WHEN/HOW the concept works in their own words.
7-8 (GOOD): Core concept is correct, even if brief or simply stated.
5-6 (ADEQUATE): Right general idea but missing key aspects of WHY or HOW.
3-4 (WEAK): Mentions the concept but can't explain WHY it's used or HOW it works.
1-2 (INCORRECT): Fundamental misunderstanding — confuses concepts or states something wrong.
0 (NO CREDIT): Non-answers, abuse, or zero conceptual content.

═══════════════════════════════════════════════════════════════
SCORING RULES:
═══════════════════════════════════════════════════════════════

1. COMPARE against the EXPECTED ANSWER. If the student captures the same CONCEPT, reward them (7-10).
2. Describing what the program does WITHOUT explaining the concept = 3-5 max.
3. Do NOT penalize for short answers, informal language, speech-to-text garbling, or inability to recite code syntax. If the concept is right in 5 words, that's still 9-10.
4. VAGUE answers ("it's easy", "it makes things work") without WHY/HOW = 1-3.
5. VALID BUT SUBOPTIMAL approach that works correctly = 5-6 minimum.
6. BEGINNER LENIENCY: For difficulty {difficulty}/5, if they show they're on the right track conceptually, be generous.
7. FOLLOW-UP CONSISTENCY: Score based on how well they answered THIS specific question. A precise, correct response to a follow-up should score 7+ regardless of what might be "missing" from the broader topic.

═══════════════════════════════════════════════════════════════
FEEDBACK RULES — SOUND LIKE A REAL PERSON:
═══════════════════════════════════════════════════════════════

1. Be HONEST and SPECIFIC. If wrong, say so clearly but kindly.
2. NEVER say "You correctly identified..." when the answer is wrong.
3. For WRONG: State what's incorrect, then guide toward the right concept.
4. For PARTIALLY CORRECT: Acknowledge what's right, state what's missing.
5. For GOOD: Confirm understanding briefly.
6. Keep to 1-3 sentences.
7. ⚠️ VARY YOUR LANGUAGE — never repeat opening phrases. Use natural reactions:
   - "You're on the right track — ..."
   - "Exactly right! ..."
   - "Close! The key thing you're missing is..."
   - "I see what you mean, but..."
   - "Not quite — here's the thing..."
8. Keep feedback language-agnostic unless the programming language is specified. Accept answers that are conceptually valid across languages.

═══════════════════════════════════════════════════════════════
MISCONCEPTION DETECTION (be thorough):
═══════════════════════════════════════════════════════════════

Flag a misconception whenever the student:
- States something factually wrong
- Confuses two concepts
- Has inverted understanding
- Misattributes properties
- Shows misunderstanding that would cause errors

If ANY misconception is present, it MUST be listed.

═══════════════════════════════════════════════════════════════
NEXT ACTION ROUTING:
═══════════════════════════════════════════════════════════════

Based on the student's answer, decide the BEST NEXT ACTION for the conversation:
- "advance": Use this if the student has demonstrated sufficient understanding (score 7+). You MUST advance if the score is 7 or higher.
- "follow_up": Use this ONLY if the student shows PARTIAL or SURFACE understanding (score 3-6) and a specific Socratic follow-up question would help them. Do NOT follow up if the score is 7+.
- "re_ask": Use this if the student's answer was too vague or incorrect (score 0-2), but they made a genuine attempt and might clarify if asked again.

═══════════════════════════════════════════════════════════════
JUSTIFICATION (required):
═══════════════════════════════════════════════════════════════

Provide a brief justification explaining WHY you gave this score. Compare what the student said vs what was expected.

OUTPUT FORMAT (JSON only):
{{
  "score": <number 0 to {max_points}>,
  "feedback": "Honest feedback to show the student...",
  "misconceptions": ["specific misconception if any"],
  "justification": "I gave X/{max_points} because the student [did/didn't]...",
  "competency_scores": {{"{competency}": <same as score>}},
  "next_action": "advance"
}}

Return ONLY valid JSON.""".strip()

    @staticmethod
    def _parse_evaluation_response(raw: str, competency: str, max_points: int = MAX_POINTS) -> EvaluationResult:
        """Parse LLM JSON into EvaluationResult."""
        try:
            text = raw.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end == 0:
                logger.error("No JSON in evaluation response: %s", text[:200])
                return EvaluationResult(
                    score=0.0, feedback="Evaluation could not be completed.",
                    misconceptions=[], competency_scores={competency: 0.0},
                    justification="parse_error",
                )
            data = json.loads(text[start:end])

            score = float(data.get("score", 0))
            score = max(0.0, min(float(max_points), score))

            feedback = str(data.get("feedback", ""))
            justification = str(data.get("justification", ""))

            misconceptions = data.get("misconceptions", [])
            if not isinstance(misconceptions, list):
                misconceptions = []
            misconceptions = [str(m) for m in misconceptions if m]

            competency_scores = data.get("competency_scores", {})
            if not isinstance(competency_scores, dict):
                competency_scores = {competency: score}

            action = str(data.get("next_action", "advance")).lower().strip()
            if action not in ("advance", "follow_up", "re_ask"):
                action = "advance"

            return EvaluationResult(
                score=score,
                feedback=feedback,
                misconceptions=misconceptions,
                competency_scores=competency_scores,
                justification=justification,
                next_action=action,
            )
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.error("Failed to parse evaluation: %s\n%s", e, raw[:500])
            return EvaluationResult(
                score=0.0, feedback="Evaluation could not be completed.",
                misconceptions=[], competency_scores={competency: 0.0},
                justification="parse_error",
            )

    def evaluate(
        self,
        question_text: str,
        expected_answer: str,
        student_answer: str,
        competency: str,
        difficulty: int,
        max_points: int = MAX_POINTS,
        code_context: str = "",
    ) -> EvaluationResult:
        """Layer 2: Evaluate a student response. Synchronous."""
        prompt = self._build_evaluation_prompt(
            question_text=question_text,
            expected_answer=expected_answer,
            student_answer=student_answer,
            competency=competency,
            difficulty=difficulty,
            max_points=max_points,
            code_context=code_context,
        )
        try:
            raw = llm_service.generate(
                prompt=prompt,
                temperature=0.2,
                max_output_tokens=1000,
                num_predict=1000,
            )
            return self._parse_evaluation_response(raw, competency, max_points)
        except Exception as e:
            logger.error("LLM evaluation failed: %s", e, exc_info=True)
            return EvaluationResult(
                score=0.0,
                feedback="Evaluation could not be completed due to a system error.",
                misconceptions=[],
                competency_scores={competency: 0.0},
                justification="llm_error",
            )

    # ==================================================================
    # LAYER 3 — Deep Analysis  (background, async)
    # ==================================================================

    @staticmethod
    def _build_deep_analysis_prompt(
        question_text: str,
        expected_answer: str,
        student_answer: str,
        competency: str,
        difficulty: int,
        score: float,
        max_points: int,
        feedback: str,
    ) -> str:
        return f"""You are an educational assessment analyst. A student was asked an oral viva question and given a score. Provide a DEEP ANALYSIS of their response for instructor review.

QUESTION: {question_text}
EXPECTED ANSWER: {expected_answer}
STUDENT'S ANSWER (speech-to-text): {student_answer}
COMPETENCY: {competency}
DIFFICULTY: {difficulty}/5
SCORE GIVEN: {score}/{max_points}
INITIAL FEEDBACK: {feedback}

IMPORTANT: Focus your analysis on the student's understanding of the PROGRAMMING CONCEPT ({competency}), not their knowledge of the assignment's scenario or domain.

Provide analysis:

1. JUSTIFICATION: Why is the score of {score}/{max_points} appropriate? What did the student get right vs wrong about the CONCEPT?

2. MISCONCEPTIONS: List ALL conceptual misconceptions about the PROGRAMMING CONCEPT. Be thorough. If none, say so.

3. UNDERSTANDING LEVEL: Rate as: "none", "surface", "partial", "solid", "deep"
   - none: No relevant understanding
   - surface: Can name/recall but cannot explain
   - partial: Some correct ideas mixed with gaps or errors
   - solid: Core concept understood, minor gaps
   - deep: Thorough understanding with reasoning ability

4. SUGGESTIONS: 2-3 specific, actionable learning suggestions about the PROGRAMMING CONCEPT.

OUTPUT FORMAT (JSON only):
{{
  "justification": "Detailed explanation...",
  "misconceptions": ["misconception 1"],
  "understanding_level": "partial",
  "suggestions": ["Study X...", "Practice Y..."]
}}

Return ONLY valid JSON.""".strip()

    @staticmethod
    def _parse_deep_analysis(raw: str) -> DeepAnalysisResult:
        try:
            text = raw.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end == 0:
                return DeepAnalysisResult(
                    justification="Analysis could not be completed.",
                    misconceptions=[], understanding_level="unknown", suggestions=[],
                )
            data = json.loads(text[start:end])
            return DeepAnalysisResult(
                justification=str(data.get("justification", "")),
                misconceptions=[str(m) for m in data.get("misconceptions", []) if m],
                understanding_level=str(data.get("understanding_level", "unknown")),
                suggestions=[str(s) for s in data.get("suggestions", []) if s],
            )
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.error("Failed to parse deep analysis: %s", e)
            return DeepAnalysisResult(
                justification="Analysis parse error.",
                misconceptions=[], understanding_level="unknown", suggestions=[],
            )

    def deep_analyze(
        self,
        question_text: str,
        expected_answer: str,
        student_answer: str,
        competency: str,
        difficulty: int,
        score: float,
        max_points: int,
        feedback: str,
    ) -> DeepAnalysisResult:
        """Layer 3: Deep analysis. Synchronous — call via asyncio.to_thread in background task."""
        prompt = self._build_deep_analysis_prompt(
            question_text=question_text,
            expected_answer=expected_answer,
            student_answer=student_answer,
            competency=competency,
            difficulty=difficulty,
            score=score,
            max_points=max_points,
            feedback=feedback,
        )
        try:
            raw = llm_service.generate(
                prompt=prompt,
                temperature=0.3,
                max_output_tokens=1500,
                num_predict=1500,
            )
            return self._parse_deep_analysis(raw)
        except Exception as e:
            logger.error("Deep analysis failed: %s", e, exc_info=True)
            return DeepAnalysisResult(
                justification="Deep analysis could not be completed.",
                misconceptions=[], understanding_level="unknown", suggestions=[],
            )

    # ==================================================================
    # Teaching hint for non-answers (real-time)
    # ==================================================================

    def generate_teaching_hint(
        self,
        question_text: str,
        expected_answer: str,
        competency: str,
        conversation_history: str = "",
    ) -> str:
        """Generate a brief, kind teaching explanation when the student doesn't know.

        Instead of forcing the student to answer, we teach the concept and move on.
        Returns the teaching feedback text.
        """
        history_block = ""
        if conversation_history:
            history_block = f"\n{conversation_history}\n"

        prompt = f"""You are a kind, real human tutor during an oral viva. The student can't answer this question. Briefly teach the concept so they learn, then we move on.

QUESTION THAT WAS ASKED: {question_text}
COMPETENCY (the programming concept): {competency}
{history_block}
NOTE — The expected answer is shown for YOUR reference only to understand what concept to teach:
EXPECTED ANSWER: {expected_answer}

RULES:
1. Start warmly ("No worries!", "That's okay!", "Don't stress!") — never shame them. VARY your opening — don't always use the same phrase.
2. Give a CONCEPTUAL NUDGE in 1-2 simple sentences — help them understand the KEY IDEA. Do NOT repeat or paraphrase the expected answer. Instead, give them a simplified mental model or analogy.
3. Do NOT give away the complete answer, specific details, or technical terminology from the expected answer. Focus on the ONE core idea.
4. End with encouragement like "Let's move on to the next question."
5. Keep it SHORT — max 3 sentences total.
6. Do NOT ask any questions — this is a teaching moment, not a quiz.
7. If conversation history shows previous explanations, build on them — don't repeat.
8. Sound like a real person, not a textbook. Use simple everyday language.

Return ONLY the teaching text, nothing else.""".strip()

        try:
            raw = llm_service.generate(
                prompt=prompt,
                temperature=0.4,
                max_output_tokens=300,
                num_predict=300,
            )
            text = raw.strip().strip('"').strip("'")
            if text:
                return text
        except Exception as e:
            logger.error("Teaching hint generation failed: %s", e)

        # Minimal fallback — only used if the LLM call itself fails
        return "That's okay! Let's move on to the next question and keep learning."

    # ==================================================================
    # Socratic follow-up (real-time)
    # ==================================================================

    def generate_follow_up(
        self,
        question_text: str,
        student_answer: str,
        feedback: str,
        competency: str,
        score: float = 5.0,
        max_score: int = 10,
        difficulty: int = 1,
        misconceptions: list[str] | None = None,
        code_context: str = "",
        conversation_history: str = "",
        expected_answer: str = "",
        justification: str = "",
    ) -> str | None:
        """Generate a single Socratic follow-up question via LLM.

        The follow-up scaffolds based on the student's score:
        - Low scores (0-4): simpler, more basic follow-up
        - Medium scores (5-6): targets the specific gap
        - High scores (7-8): can probe slightly deeper

        Returns the follow-up question text, or None on failure.
        """
        misconception_section = ""
        if misconceptions:
            misconception_section = (
                f"\nDETECTED MISCONCEPTIONS: {', '.join(misconceptions)}\n"
            )

        code_section = ""
        if code_context:
            code_section = f"\nBACKGROUND (student's code for reference only):\n{code_context}\n"

        history_block = ""
        if conversation_history:
            history_block = f"\n{conversation_history}\n"

        expected_section = ""
        if expected_answer:
            expected_section = f"\nEXPECTED CONCEPTUAL ANSWER: {expected_answer}\n"

        justification_section = ""
        if justification:
            justification_section = f"\nSCORE JUSTIFICATION (why the student lost marks): {justification}\n"

        prompt = f"""You are a Socratic tutor during an oral viva. The student answered a question and you need to ask ONE follow-up to help them understand the PROGRAMMING CONCEPT better.

ORIGINAL QUESTION: {question_text}
STUDENT'S ANSWER: {student_answer}
STUDENT'S SCORE: {score}/{max_score}
EVALUATION FEEDBACK: {feedback}
{expected_section}{justification_section}{misconception_section}{code_section}{history_block}
PROGRAMMING CONCEPT BEING TESTED: {competency}
DIFFICULTY LEVEL: {difficulty}/5

═══════════════════════════════════════════════════════════════
⚠️ MOST IMPORTANT RULE: DIFFICULTY MUST STAY THE SAME OR GO DOWN
═══════════════════════════════════════════════════════════════

The original question was difficulty {difficulty}/5. Your follow-up MUST be
at difficulty {difficulty}/5 or LOWER. NEVER ask something harder.

The student scored {score}/{max_score}. A student who scored that low needs
a SIMPLER question, not a harder one.

═══════════════════════════════════════════════════════════════
SCAFFOLDING BY SCORE — FOLLOW THESE EXAMPLES:
═══════════════════════════════════════════════════════════════

IF SCORE WAS LOW (0-4) — student is STRUGGLING, ask something BASIC:
  Original: "Why did you use a for loop here?"
  BAD follow-up: "What's the time complexity of your loop?" (too advanced!)
  BAD follow-up: "How would you optimize this with recursion?" (way too hard!)
  GOOD follow-up: "What does a loop do in general?" (basic recall)
  GOOD follow-up: "What would happen if you didn't use a loop?" (simple reasoning)

  Original: "Why store data in an array instead of separate variables?"
  BAD follow-up: "Explain how array memory allocation works" (too advanced!)
  GOOD follow-up: "What is an array?" (basic recall)
  GOOD follow-up: "If you had 100 values, would you want 100 variable names?" (guides thinking)

IF SCORE WAS MEDIUM (5-6) — student has partial understanding, target the GAP:
  Compare the student's answer to the expected answer. Find the ONE thing they missed.
  Original: "Why use a for loop?" Student said "to repeat code" but missed "when you know how many times"
  GOOD follow-up: "How does the loop know when to stop?" (targets the specific gap)

═══════════════════════════════════════════════════════════════
GENERAL RULES:
═══════════════════════════════════════════════════════════════
1. Ask exactly ONE concise question (1-2 sentences max, under 25 words).
2. Focus on the PROGRAMMING CONCEPT — not the assignment scenario or domain.
3. Do NOT ask them to write or recite code.
4. Do NOT reveal the answer — guide their thinking.
5. Keep it conversational and encouraging.
6. Do NOT use forced analogies (NO apples, fruits, cookies, pizza).
7. If a misconception was detected, gently challenge it.
8. If conversation history shows previous follow-ups, ask about a DIFFERENT aspect.

Return ONLY the follow-up question text, nothing else.""".strip()

        try:
            raw = llm_service.generate(
                prompt=prompt,
                temperature=0.5,
                max_output_tokens=300,
                num_predict=300,
            )
            text = raw.strip().strip('"').strip("'")
            if text:
                return text
            return None
        except Exception as e:
            logger.error("Follow-up generation failed: %s", e, exc_info=True)
            return None

    # ==================================================================
    # Relevance explanation (for clarify_relevance action)
    # ==================================================================

    def generate_relevance_explanation(
        self,
        question_text: str,
        competency: str,
        assignment_context: str = "",
    ) -> str:
        """Explain WHY a topic/competency is relevant to the student's assignment.

        Used when the student questions why they're being asked about a topic.
        Returns explanation text.
        """
        context_block = ""
        if assignment_context:
            context_block = f"\nASSIGNMENT CONTEXT: {assignment_context}\n"

        prompt = f"""You are a kind instructor during an oral viva. The student just asked why you're asking about this topic — they don't see the connection to their assignment.

QUESTION BEING ASKED: {question_text}
TECHNICAL CONCEPT: {competency}
{context_block}
Your job: Briefly explain WHY this concept matters for their work. Be encouraging and make the connection clear.

RULES:
1. Keep it to 1-2 sentences.
2. Be specific — explain the actual connection (e.g. "This specific construct is how you handle this technical process — without it, you'd have to manage the data manually!")
3. Sound like a real person, not a textbook.
4. End with something encouraging that leads back to the question.
5. Do NOT lecture or be condescending.

Return ONLY the explanation text, nothing else.""".strip()

        try:
            raw = llm_service.generate(
                prompt=prompt,
                temperature=0.4,
                max_output_tokens=200,
                num_predict=200,
            )
            text = raw.strip().strip('"').strip("'")
            if text:
                return text
        except Exception as e:
            logger.error("Relevance explanation failed: %s", e)

        return f"Great question! {competency} is closely related to how your code works. Let me ask the question again."

    # ==================================================================
    # Question re-explanation (for explain_and_reask action)
    # ==================================================================

    def generate_question_explanation(
        self,
        question_text: str,
        expected_answer: str,
        competency: str,
        difficulty: int = 1,
        conversation_history: str = "",
    ) -> str:
        """Re-explain a question more simply when the student asks for clarification.

        Returns the explanation text.
        """
        history_block = ""
        if conversation_history:
            history_block = f"\n{conversation_history}\n"

        prompt = f"""You are a kind instructor during an oral viva. The student is asking you to explain or clarify the question. They WANT to try answering but need help understanding what you're asking.

ORIGINAL QUESTION: {question_text}
PROGRAMMING CONCEPT: {competency}
DIFFICULTY LEVEL: {difficulty}/5
{history_block}
Your job: Re-explain the question in SIMPLER words so the student can understand and attempt an answer. Match your explanation complexity to difficulty level {difficulty}/5 — for lower levels use very simple everyday language, for higher levels you can use slightly more technical terms.

RULES:
1. Start with something warm like "Sure!" or "Of course!" — show you're happy to help.
2. Rephrase the question in simpler, more concrete language (1-2 sentences).
3. You can give a small hint about what KIND of answer you're looking for, but do NOT reveal the answer itself.
4. End by encouraging them to try: "Give it your best shot!" or similar.
5. Keep it SHORT — max 3 sentences.
6. Sound like a real person having a conversation.

Return ONLY the explanation text, nothing else.""".strip()

        try:
            raw = llm_service.generate(
                prompt=prompt,
                temperature=0.4,
                max_output_tokens=250,
                num_predict=250,
            )
            text = raw.strip().strip('"').strip("'")
            if text:
                return text
        except Exception as e:
            logger.error("Question explanation failed: %s", e)

        return "Sure! Let me put it differently. Think about the core concept and give it your best shot!"


# Singleton
evaluation_service = EvaluationService()
