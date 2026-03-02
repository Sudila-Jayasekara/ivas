"""
Evaluation Service — LLM Layer Architecture

Three-layer LLM pipeline for evaluating student responses:

  Layer 1 — Input Guard (real-time):
      Classifies the student's response as abuse / non_answer / genuine_attempt.
      Replaces all regex-based detection with a small, fast LLM call.

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
    classification: str  # "abuse" | "non_answer" | "genuine_attempt"
    reason: str          # Brief LLM explanation


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
    def _build_guard_prompt(student_answer: str, question_text: str) -> str:
        return f"""You are a content classifier for an oral assessment system. Your ONLY job is to classify the student's input.

QUESTION BEING ASKED: {question_text}

STUDENT SAID: "{student_answer}"

Classify as exactly ONE of:
- "genuine_attempt": The student is trying to answer the question, even if wrong, vague, partial, or poorly worded. ANY attempt to address the topic counts.
- "non_answer": The student gave NO conceptual content at all. Examples: "yes", "no", "I think so", "okay thank you", "I understand", "I don't know", "not sure", "pass", "next", "skip", "sounds good", "that makes sense". Key test: does the response contain ANY idea, concept, or explanation? If not, it's a non_answer.
- "abuse": Profanity, insults, threats, or deliberately offensive/disruptive content.

IMPORTANT DISTINCTIONS:
- "yes I think it's practical and easy" → genuine_attempt (states opinion about topic)
- "we can use string for store numbers" → genuine_attempt (wrong but attempting)
- "I think no" or "yes" with zero elaboration → non_answer
- "okay I understand thank you" → non_answer (acknowledgement, not an answer)
- "I don't want to write 20 statements" → genuine_attempt (opinion about approach)

Return ONLY valid JSON:
{{"classification": "genuine_attempt", "reason": "Student attempts to explain their understanding"}}""".strip()

    @staticmethod
    def _parse_guard_response(raw: str) -> InputGuardResult:
        try:
            text = raw.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end == 0:
                return InputGuardResult(classification="genuine_attempt", reason="parse_fallback")
            data = json.loads(text[start:end])
            classification = str(data.get("classification", "genuine_attempt")).lower().strip()
            if classification not in ("abuse", "non_answer", "genuine_attempt"):
                classification = "genuine_attempt"
            reason = str(data.get("reason", ""))
            return InputGuardResult(classification=classification, reason=reason)
        except (json.JSONDecodeError, ValueError, TypeError):
            return InputGuardResult(classification="genuine_attempt", reason="parse_fallback")

    def classify_input(self, student_answer: str, question_text: str) -> InputGuardResult:
        """Layer 1: Classify student input via LLM. Fast, small prompt. Synchronous."""
        if not student_answer or not student_answer.strip():
            return InputGuardResult(classification="non_answer", reason="empty input")

        try:
            raw = llm_service.generate(
                prompt=self._build_guard_prompt(student_answer, question_text),
                temperature=0.1,
                max_output_tokens=150,
                num_predict=150,
            )
            result = self._parse_guard_response(raw)
            logger.debug("Input guard: %s — %s", result.classification, result.reason)
            return result
        except Exception as e:
            logger.error("Input guard LLM failed: %s", e)
            return InputGuardResult(classification="genuine_attempt", reason="guard_error_fallback")

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

        prompt = f"""You are a Socratic tutor during an oral viva checking CONCEPTUAL UNDERSTANDING. The student gave a partially correct answer. Ask ONE follow-up question to guide deeper understanding.

ORIGINAL QUESTION: {question_text}
STUDENT'S ANSWER: {student_answer}
EVALUATION FEEDBACK: {feedback}
{misconception_section}{code_section}
COMPETENCY: {competency}

RULES:
1. Ask exactly ONE concise follow-up question (1-2 sentences).
2. Probe CONCEPTUAL understanding — ask WHY, WHEN, or HOW.
3. Do NOT ask them to write or recite code.
4. Do NOT reveal the answer — guide their thinking.
5. Keep it conversational and encouraging.
6. Do NOT use forced analogies (NO apples, fruits, baskets, cookies). Use programming examples.
7. If a misconception was detected, design the question to challenge that specific misconception.

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
