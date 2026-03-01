"""
Evaluation Service

Evaluates a student's response against the expected answer and grading criteria
using the LLM. Returns a score, feedback text, and any detected misconceptions.
"""

import json
import logging
from dataclasses import dataclass

from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    score: float  # 0.0 – 10.0
    feedback: str
    misconceptions: list[str]
    competency_scores: dict[str, float]  # competency -> score


# Fixed max points for all questions — ensures fairness
MAX_POINTS = 10


class EvaluationService:
    """Sends student response + question context to LLM for evaluation."""

    @staticmethod
    def _build_prompt(
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

PURPOSE OF THIS VIVA:
- The goal is to check whether the student truly UNDERSTANDS the concept — not whether they can write code.
- We want to know: Can they explain WHY something works? Can they relate it to real-world problems?
- This is NOT a code review. Even if code context is provided, focus on the student's understanding of the IDEA.

SPEECH-TO-TEXT NOTE:
The student answered by SPEAKING into a microphone and their speech was converted to text. This means:
- There WILL be transcription errors, garbled words, and mispronounced technical terms
- Focus on the MEANING and INTENT of what they said, not exact wording
- If they clearly understand the concept but the transcription is messy, give credit
- Technical terms may be misspelled or wrong (e.g. "struck" instead of "struct", "dubble" instead of "double")
- Filler words, repetitions, and awkward phrasing are NORMAL for spoken answers
- Be GENEROUS with partial credit — this is a beginner student speaking, not writing

QUESTION: {question_text}
EXPECTED CONCEPTUAL ANSWER: {expected_answer}
STUDENT'S SPOKEN ANSWER (speech-to-text, may contain transcription errors): {student_answer}
{code_section}
COMPETENCY BEING ASSESSED: {competency}
DIFFICULTY: {difficulty}/5
MAX POINTS: {max_points}

EVALUATION RULES (focus on CONCEPTUAL UNDERSTANDING):
1. Score from 0.0 to {max_points}.0 based on how well the student UNDERSTANDS the concept.
2. Award high marks if the student can explain the concept in their own words, relate it to real-world use, or describe WHY it matters — even if their wording is imperfect.
3. Award partial credit if they show partial understanding (e.g. they know WHAT a struct is but not WHY you'd use one).
4. Do NOT penalise for inability to recite exact syntax or code. This is about understanding, not memorisation.
5. Provide SHORT, encouraging feedback (1-2 sentences). Mention what they understood correctly first.
6. Identify misconceptions ONLY if the student showed clearly WRONG conceptual understanding (not just poor wording or transcription errors).
7. Be FAIR to beginners — partial credit for partial understanding.

OUTPUT FORMAT (JSON object only, no other text):
{{
  "score": 7.5,
  "feedback": "You showed good understanding of X. To strengthen your answer, think about why Y matters in practice...",
  "misconceptions": ["confused iteration with recursion"],
  "competency_scores": {{"{competency}": 7.5}}
}}

Return ONLY valid JSON.""".strip()

    @staticmethod
    def _parse_response(raw: str, competency: str, max_points: int = MAX_POINTS) -> EvaluationResult:
        """Parse LLM JSON response into EvaluationResult."""
        try:
            text = raw.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end == 0:
                logger.error("No JSON object in evaluation response: %s", text[:200])
                return EvaluationResult(
                    score=0.0,
                    feedback="Evaluation could not be completed.",
                    misconceptions=[],
                    competency_scores={competency: 0.0},
                )

            data = json.loads(text[start:end])

            score = float(data.get("score", 0))
            score = max(0.0, min(float(max_points), score))

            feedback = str(data.get("feedback", ""))
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
            )

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.error("Failed to parse evaluation response: %s\n%s", e, raw[:500])
            return EvaluationResult(
                score=0.0,
                feedback="Evaluation could not be completed.",
                misconceptions=[],
                competency_scores={competency: 0.0},
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
        """Evaluate a single student response via LLM. Synchronous (LLM call is sync)."""
        prompt = self._build_prompt(
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
                temperature=0.3,
                max_output_tokens=1000,
                num_predict=1000,
            )
            return self._parse_response(raw, competency, max_points)

        except Exception as e:
            logger.error("LLM evaluation failed: %s", e, exc_info=True)
            return EvaluationResult(
                score=0.0,
                feedback="Evaluation could not be completed due to a system error.",
                misconceptions=[],
                competency_scores={competency: 0.0},
            )

    # ------------------------------------------------------------------
    # Socratic follow-up generation
    # ------------------------------------------------------------------

    def is_partial_understanding(self, score: float, max_points: float) -> bool:
        """Return True if the score indicates partial understanding (30-70% range)."""
        if max_points <= 0:
            return False
        pct = score / max_points
        return 0.3 <= pct <= 0.7

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

        prompt = f"""You are a Socratic tutor conducting a viva to check CONCEPTUAL UNDERSTANDING. The student gave a partially correct answer and you need to ask ONE short follow-up question to guide them toward deeper understanding.

PURPOSE: We are checking if the student truly understands the concept — not their code or syntax knowledge.

ORIGINAL QUESTION: {question_text}
STUDENT'S ANSWER: {student_answer}
EVALUATION FEEDBACK: {feedback}
{misconception_section}{code_section}
COMPETENCY: {competency}

RULES:
1. Ask exactly ONE concise follow-up question (1-2 sentences).
2. The question should probe CONCEPTUAL understanding — ask WHY something works, WHEN you'd use it, or HOW it relates to a real-world scenario.
3. Do NOT ask them to write or recite code.
4. Do NOT reveal the answer — help them think through the concept.
5. Keep it conversational and encouraging.
6. Good follow-ups: "Why would that matter in a real program?" / "Can you think of a situation where that wouldn't work?"

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
