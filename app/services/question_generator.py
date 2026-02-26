"""
Question Generator Service

Generates viva questions from saved GradingCriteria rows using the LLM.
Called by QuestionService (API 4).
"""

import json
import logging

from app.schemas.question import GeneratedQuestionAI
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class QuestionGenerator:
    """Generates assessment questions aligned to grading criteria using the configured LLM provider."""

    def __init__(self) -> None:
        logger.info("QuestionGenerator initialized (provider: %s)", llm_service.provider_name)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def check_llm_available(self) -> bool:
        try:
            return llm_service.check_availability()
        except Exception as e:
            logger.error("LLM provider %s not available: %s", llm_service.provider_name, e)
            return False

    # kept for backward compat
    check_ollama_available = check_llm_available

    # ------------------------------------------------------------------
    # Prompt
    # ------------------------------------------------------------------

    @staticmethod
    def _build_prompt(
        competency: str,
        difficulty_level: int,
        level_label: str,
        level_description: str,
        marking_criteria: str,
        programming_language: str,
        learning_objectives: list[str],
    ) -> str:
        objectives = ", ".join(learning_objectives)

        return f"""You are an expert programming instructor creating oral viva questions.

Generate exactly 1 viva voce question for the competency "{competency}" at difficulty level {difficulty_level} ({level_label}).

CONTEXT:
- Programming Language: {programming_language}
- Competency: {competency}
- Difficulty Level: {difficulty_level}/5 — {level_label}
- Level Description: {level_description}
- Marking Criteria: {marking_criteria}
- Learning Objectives: {objectives}

═══════════════════════════════════════════════════════════════
BLOOM'S TAXONOMY — MANDATORY QUESTION DESIGN RULES
═══════════════════════════════════════════════════════════════

The question MUST match the Bloom's level "{level_label}" (difficulty {difficulty_level}).
Follow these rules STRICTLY:

Level 1 — "Remember":
  → Ask the student to RECALL, DEFINE, LIST, NAME, or STATE facts/terms.
  → Questions should test memorisation of syntax, definitions, or terminology.
  → Do NOT ask "why" or "how" — only "what".
  → Example: "What is the syntax for declaring a struct in C++?"

Level 2 — "Understand":
  → Ask the student to EXPLAIN, DESCRIBE, SUMMARISE, COMPARE, or CONTRAST concepts.
  → The student must demonstrate comprehension IN THEIR OWN WORDS.
  → Do NOT present a new scenario to solve — that is Apply level.
  → Do NOT ask them to walk through steps — that is Apply level.
  → Example: "Explain why using functions improves code readability."

Level 3 — "Apply":
  → Present a SPECIFIC CONCRETE SCENARIO and ask the student to walk through
    how they would SOLVE, USE, IMPLEMENT, or CALCULATE using their knowledge.
  → The question MUST contain a scenario (e.g., "Given X...", "Imagine you have...").
  → The student must demonstrate they can USE their knowledge in a new situation.
  → Example: "Given a rectangle with length 5.5 and width 3.2, walk me through
    how your function would calculate and display the perimeter."

Level 4 — "Analyse":
  → Ask the student to ANALYSE, COMPARE alternatives, find TRADE-OFFS, or
    DIFFERENTIATE between approaches with reasoning.
  → The question MUST ask WHY one approach is better/worse or what the
    TRADE-OFFS are between alternatives.
  → Example: "Compare using pass-by-reference vs pass-by-value for this function.
    What are the trade-offs in terms of memory and side effects?"

Level 5 — "Evaluate & Create":
  → Ask the student to EVALUATE, JUSTIFY, CRITIQUE, DESIGN, or PROPOSE solutions.
  → The question MUST require critical thinking, judgment, or designing a new approach.
  → Example: "Critique your error handling approach. What weaknesses does it have,
    and how would you redesign it for a production system?"

CRITICAL RULES:
1. The question MUST be about "{competency}" specifically.
2. The question MUST use the action verbs for "{level_label}" level ONLY.
3. The question must be answerable verbally (no code writing or diagrams).
4. The expected_answer must describe what a strong student would say at this Bloom's level.
5. All questions are scored out of 10 points — do NOT include max_points in output.

OUTPUT FORMAT (JSON array with exactly 1 item, no other text):
[
  {{
    "question_text": "Your question here",
    "expected_answer": "Expected student response covering key points..."
  }}
]

Return ONLY valid JSON array.""".strip()

    # ------------------------------------------------------------------
    # Parse
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(
        response_text: str,
        competency: str,
        difficulty: int,
    ) -> list[GeneratedQuestionAI]:
        try:
            text = response_text.strip()
            start_idx = text.find("[")
            end_idx = text.rfind("]") + 1
            if start_idx == -1 or end_idx == 0:
                logger.error("No JSON array found in response: %s", text[:200])
                return []

            questions_data = json.loads(text[start_idx:end_idx])
            questions: list[GeneratedQuestionAI] = []

            for q in questions_data:
                question_text = q.get("question_text", "").strip()
                if not question_text:
                    logger.warning("Skipping empty question for competency '%s'", competency)
                    continue

                questions.append(
                    GeneratedQuestionAI(
                        question_text=question_text,
                        competency=competency,
                        difficulty=difficulty,
                        expected_answer=q.get("expected_answer", ""),
                        max_points=10,
                    )
                )

            return questions

        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON: %s\nResponse: %s", e, response_text[:500])
            return []
        except Exception as e:
            logger.error("Error parsing response: %s", e)
            return []

    # ------------------------------------------------------------------
    # Generate — takes a list of grading-criteria dicts
    # ------------------------------------------------------------------

    def generate_questions(
        self,
        *,
        criteria_rows: list[dict],
    ) -> list[GeneratedQuestionAI]:
        """
        Parameters
        ----------
        criteria_rows : list[dict]
            Each dict must contain: competency, difficulty_level, level_label,
            level_description, marking_criteria, programming_language,
            learning_objectives, max_points.  Optionally: criteria_id.

        Generates exactly one question per criteria row (one per competency).
        """
        all_questions: list[GeneratedQuestionAI] = []

        for cr in criteria_rows:
            competency = cr["competency"]
            difficulty = cr["difficulty_level"]
            criteria_id = cr.get("criteria_id")
            logger.info(
                "Generating 1 question for competency=%s difficulty=%d",
                competency, difficulty,
            )

            prompt = self._build_prompt(
                competency=competency,
                difficulty_level=difficulty,
                level_label=cr["level_label"],
                level_description=cr["level_description"],
                marking_criteria=cr["marking_criteria"],
                programming_language=cr["programming_language"],
                learning_objectives=cr["learning_objectives"],
            )

            try:
                response_text = llm_service.generate(
                    prompt=prompt,
                    temperature=0.8,
                    num_predict=2500,
                    max_output_tokens=2500,
                    top_p=0.9,
                )

                questions = self._parse_response(response_text, competency, difficulty)

                # Attach criteria_id; max_points is always 10
                for q in questions:
                    q.max_points = 10
                    if criteria_id:
                        q.grading_criteria_id = criteria_id

                if not questions:
                    logger.warning(
                        "Failed to generate question for %s@%d",
                        competency, difficulty,
                    )

                all_questions.extend(questions)
                logger.info(
                    "Successfully generated %d questions for %s@%d",
                    len(questions), competency, difficulty,
                )

            except Exception as e:
                logger.error(
                    "Error generating questions for %s@%d: %s",
                    competency, difficulty, e, exc_info=True,
                )
                continue

        return all_questions


# Singleton
question_generator = QuestionGenerator()