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
            code_section = f"\nSTUDENT'S CODE CONTEXT:\n{code_context}\n"

        return f"""You are an expert programming instructor evaluating a student's oral viva response.

QUESTION: {question_text}
EXPECTED ANSWER: {expected_answer}
STUDENT'S ANSWER: {student_answer}
{code_section}
COMPETENCY: {competency}
DIFFICULTY: {difficulty}/5
MAX POINTS: {max_points}

EVALUATION RULES:
1. Score from 0.0 to {max_points}.0 based on correctness, completeness, and understanding.
2. Provide concise, constructive feedback (2-3 sentences) explaining the score.
3. Identify specific misconceptions if the student showed incorrect understanding (empty list if none).
4. Be fair — partial credit for partial understanding.

OUTPUT FORMAT (JSON object only, no other text):
{{
  "score": 7.5,
  "feedback": "Your explanation of X was correct but you missed Y...",
  "misconceptions": ["confused iteration with recursion"],
  "competency_scores": {{"{competency}": 7.5}}
}}

Return ONLY valid JSON.""".strip()

    @staticmethod
    def _parse_response(raw: str, competency: str, max_points: int) -> EvaluationResult:
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
        max_points: int = 10,
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


# Singleton
evaluation_service = EvaluationService()
