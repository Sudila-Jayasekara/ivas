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
    action: str      # "evaluate" | "teach_and_skip" | "warn_and_reask"
    reason: str      # Brief LLM explanation
    warning: str = ""  # LLM-generated warning (only for warn_and_reask)


@dataclass
class EvaluationResult:
    score: float  # 0.0 – 10.0
    feedback: str
    misconceptions: list[str]
    competency_scores: dict[str, float]
    justification: str = ""  # LLM's reasoning for the given score


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

        return f"""You are an instructor deciding what to do next in an oral assessment.

SPEECH-TO-TEXT NOTE: The student spoke into a microphone. There WILL be transcription errors — interpret garbled words by sound/context (e.g. "arrival" might mean "array will", "struck" might mean "struct"). Focus on MEANING and INTENT.

QUESTION: {question_text}

STUDENT SAID: "{student_answer}"
{history_block}
Decide the NEXT ACTION:

- "evaluate": The student is attempting to answer — even if wrong, vague, partial, or poorly worded. Any effort to address the topic should be evaluated.

- "teach_and_skip": The student provided NO conceptual content to evaluate. They may be unsure, confused, explicitly don't know, want to skip, gave an empty acknowledgement, or simply have nothing to say about this topic. There is nothing meaningful to score — teach them the concept and move on.

- "warn_and_reask": The student is being abusive, offensive, or deliberately disruptive. Generate a firm but professional warning.

GUIDANCE:
- If the student says ANYTHING related to the topic (even incorrect), choose "evaluate"
- If there is no conceptual content at all, choose "teach_and_skip" — never force a student to re-answer when they have nothing to offer
- Only choose "warn_and_reask" for genuinely abusive or offensive content
- Speech-to-text may garble words — be generous in interpretation
- If the conversation history shows the student has been struggling or confused, prefer "teach_and_skip" over forcing more attempts

Return ONLY valid JSON:
For evaluate/teach_and_skip: {{"action": "<action>", "reason": "brief explanation"}}
For warn_and_reask: {{"action": "warn_and_reask", "reason": "brief explanation", "warning": "Your firm but professional warning to the student"}}""".strip()

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
            if action not in ("evaluate", "teach_and_skip", "warn_and_reask"):
                action = "evaluate"
            reason = str(data.get("reason", ""))
            warning = str(data.get("warning", ""))
            return InputGuardResult(action=action, reason=reason, warning=warning)
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

        return f"""You are an expert instructor conducting an oral viva to assess a BEGINNER student's CONCEPTUAL UNDERSTANDING.

PURPOSE: Check whether the student truly UNDERSTANDS the concept — not whether they can write code.
This is NOT a code review. Focus on the IDEA, not syntax.

SPEECH-TO-TEXT NOTE:
The student spoke into a microphone and speech was converted to text.
- There WILL be transcription errors and garbled words
- Focus on MEANING and INTENT, not exact wording
- Technical terms may be misspelled (e.g. "struck" for "struct")
- Be lenient with TRANSCRIPTION quality, but STRICT with conceptual accuracy

QUESTION: {question_text}
EXPECTED CONCEPTUAL ANSWER: {expected_answer}
STUDENT'S SPOKEN ANSWER: {student_answer}
{code_section}
COMPETENCY: {competency}
DIFFICULTY: {difficulty}/5
MAX POINTS: {max_points}

═══════════════════════════════════════════════════════════════
SCORING RUBRIC (apply STRICTLY):
═══════════════════════════════════════════════════════════════

9-10 (EXCELLENT): Explains the concept accurately and thoroughly. Clear understanding of WHY/HOW. May reason beyond basics.

7-8 (GOOD): Core concept is correct. Main idea right but missing depth. Answer clearly addresses the question.

5-6 (ADEQUATE): Some relevant understanding but notable gaps. General area right but cannot explain WHY/HOW, OR mixes correct and incorrect ideas.

3-4 (WEAK): Minimal understanding. Mostly vague ("it's easy", "it's helpful") without explaining WHY or HOW. Touches the topic but misses the main point.

1-2 (INCORRECT): Answer is factually wrong, contradicts the expected answer, or shows fundamental misunderstanding.

0 (NO CREDIT): Non-answers, abuse, or zero content.

═══════════════════════════════════════════════════════════════
MANDATORY SCORING RULES:
═══════════════════════════════════════════════════════════════

1. COMPARE against the EXPECTED ANSWER. If the student CONTRADICTS it, score 1-2 max.

2. Do NOT fabricate positive interpretations. Wrong is wrong. Do NOT say "You correctly identified..." for a wrong answer.

3. VAGUE answers ("it's easy", "it's good", "we can use it") without WHY/HOW: 3-4 max.

4. Bare agreement/disagreement without reasoning: 0-1.

5. SHORT answers (under 15 meaningful words): max 5/{max_points} unless every word shows precise understanding.

6. DIFFICULTY SCALING: At difficulty 4-5, expect analysis/comparison/reasoning. Surface-level answers at high difficulty score 2-3 lower than at difficulty 1-2.

7. PARROTING ("because you said...", "you told me..."): max 5/{max_points}.

8. WRONG + CONFIDENT scores LOWER than UNCERTAIN + RIGHT DIRECTION.

9. Do NOT penalise for inability to recite code syntax — but the concept must be correct.

═══════════════════════════════════════════════════════════════
FEEDBACK RULES:
═══════════════════════════════════════════════════════════════

1. Be HONEST and SPECIFIC. If wrong, say so clearly but kindly.
2. NEVER say "You correctly identified..." when the answer is wrong.
3. For WRONG: State what's incorrect, then guide toward the right concept.
4. For PARTIALLY CORRECT: Acknowledge what's right, state what's missing.
5. For GOOD: Confirm understanding and suggest how to deepen it.
6. Keep to 1-3 sentences.

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
JUSTIFICATION (required):
═══════════════════════════════════════════════════════════════

Provide a brief justification explaining WHY you gave this score. Compare what the student said vs what was expected.

OUTPUT FORMAT (JSON only):
{{
  "score": <number 0 to {max_points}>,
  "feedback": "Honest feedback to show the student...",
  "misconceptions": ["specific misconception if any"],
  "justification": "I gave X/{max_points} because the student [did/didn't]...",
  "competency_scores": {{"{competency}": <same as score>}}
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

            return EvaluationResult(
                score=score,
                feedback=feedback,
                misconceptions=misconceptions,
                competency_scores=competency_scores,
                justification=justification,
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

Provide analysis:

1. JUSTIFICATION: Why is the score of {score}/{max_points} appropriate? What did the student get right vs wrong vs the expected answer?

2. MISCONCEPTIONS: List ALL conceptual misconceptions the student demonstrated. Be thorough. If none, say so.

3. UNDERSTANDING LEVEL: Rate as: "none", "surface", "partial", "solid", "deep"
   - none: No relevant understanding
   - surface: Can name/recall but cannot explain
   - partial: Some correct ideas mixed with gaps or errors
   - solid: Core concept understood, minor gaps
   - deep: Thorough understanding with reasoning ability

4. SUGGESTIONS: 2-3 specific, actionable learning suggestions.

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

        prompt = f"""You are a kind tutor during an oral viva. The student said they don't know the answer. Your job is to BRIEFLY TEACH the concept so they learn from this moment, then we move on to the next question.

QUESTION THAT WAS ASKED: {question_text}
EXPECTED ANSWER: {expected_answer}
COMPETENCY: {competency}
{history_block}
RULES:
1. Start with something warm like "No worries!" or "That's okay!" — never shame them.
2. Explain the core concept in 2-3 simple sentences, suitable for a beginner.
3. Use the expected answer as your guide but rephrase it in plain, conversational language.
4. Do NOT just dump the expected answer verbatim — teach it naturally.
5. End with a brief encouraging note like "Let's move on to the next question."
6. Keep it SHORT — max 4 sentences total.
7. Do NOT ask any questions — this is a teaching moment, not a quiz.
8. If conversation history shows previous explanations, build on them — don't repeat the same explanation.

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

    def is_partial_understanding(self, score: float, max_points: float) -> bool:
        """Return True if score indicates partial understanding (30-70% range)."""
        if max_points <= 0:
            return False
        pct = score / max_points
        return 0.3 <= pct < 0.7

    def generate_follow_up(
        self,
        question_text: str,
        student_answer: str,
        feedback: str,
        competency: str,
        misconceptions: list[str] | None = None,
        code_context: str = "",
        conversation_history: str = "",
    ) -> str | None:
        """Generate a single Socratic follow-up question via LLM.

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

        prompt = f"""You are a Socratic tutor during an oral viva checking CONCEPTUAL UNDERSTANDING. The student gave a partially correct answer. Ask ONE follow-up question to guide deeper understanding.

ORIGINAL QUESTION: {question_text}
STUDENT'S ANSWER: {student_answer}
EVALUATION FEEDBACK: {feedback}
{misconception_section}{code_section}{history_block}
COMPETENCY: {competency}

RULES:
1. Ask exactly ONE concise follow-up question (1-2 sentences).
2. Probe CONCEPTUAL understanding — ask WHY, WHEN, or HOW.
3. Do NOT ask them to write or recite code.
4. Do NOT reveal the answer — guide their thinking.
5. Keep it conversational and encouraging.
6. Do NOT use forced analogies (NO apples, fruits, baskets, cookies). Stay in the assignment domain.
7. If a misconception was detected, design the question to challenge that specific misconception.
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


# Singleton
evaluation_service = EvaluationService()
