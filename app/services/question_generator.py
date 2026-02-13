import json
import logging

from ollama import Client

from app.config import settings
from app.schemas.question import GeneratedQuestionAI, RubricResponse

logger = logging.getLogger(__name__)


class QuestionGenerator:
    """Generates assessment questions using Ollama LLM."""

    def __init__(self) -> None:
        self.client = Client(host=settings.ollama_host)
        self.model = settings.ollama_model

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def check_ollama_available(self) -> bool:
        try:
            models = self.client.list()
            model_names = [m.model for m in models.models]
            return any(self.model in name for name in model_names)
        except Exception as e:
            logger.error("Ollama not available: %s", e)
            return False

    # ------------------------------------------------------------------
    # Prompt
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        title: str,
        programming_language: str,
        competency: str,
        difficulty_min: int,
        difficulty_max: int,
        learning_objectives: list[str],
        num_questions: int,
    ) -> str:
        return f"""You are an expert programming instructor creating assessment questions.

Generate {num_questions} unique viva voce (oral exam) questions for a programming assignment.

**Assignment Details:**
- Title: {title}
- Programming Language: {programming_language}
- Target Competency: {competency}
- Difficulty Range: {difficulty_min} to {difficulty_max} (scale 1-5)
- Learning Objectives: {', '.join(learning_objectives)}

**Requirements:**
1. Questions should test understanding of "{competency}" concept
2. Each question should have a different difficulty level within the range
3. Questions should be open-ended, suitable for verbal answers
4. Include expected key concepts the student should mention
5. Provide grading criteria

**Output Format (JSON array):**
```json
[
  {{
    "question_text": "Explain how...",
    "difficulty": 2,
    "expected_key_concepts": ["concept1", "concept2"],
    "grading_criteria": "Full marks if student explains...",
    "max_points": 10
  }}
]
```

Generate exactly {num_questions} questions. Return ONLY valid JSON array, no other text."""

    # ------------------------------------------------------------------
    # Parse
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(
        response_text: str, competency: str
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
                questions.append(
                    GeneratedQuestionAI(
                        question_text=q.get("question_text", ""),
                        competency=competency,
                        difficulty=q.get("difficulty", 3),
                        expected_key_concepts=q.get("expected_key_concepts", []),
                        rubric=RubricResponse(
                            expected_key_concepts=q.get("expected_key_concepts", []),
                            grading_criteria=q.get("grading_criteria", ""),
                            max_points=q.get("max_points", 10),
                        ),
                    )
                )
            return questions
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON: %s\nResponse: %s", e, response_text[:500])
            return []

    # ------------------------------------------------------------------
    # Generate
    # ------------------------------------------------------------------

    def generate_questions(
        self,
        *,
        title: str,
        competencies: list[str],
        learning_objectives: list[str],
        difficulty_min: int,
        difficulty_max: int,
        num_questions_per_competency: int,
        programming_language: str,
    ) -> list[GeneratedQuestionAI]:
        all_questions: list[GeneratedQuestionAI] = []

        for competency in competencies:
            logger.info("Generating questions for competency: %s", competency)
            prompt = self._build_prompt(
                title=title,
                programming_language=programming_language,
                competency=competency,
                difficulty_min=difficulty_min,
                difficulty_max=difficulty_max,
                learning_objectives=learning_objectives,
                num_questions=num_questions_per_competency,
            )
            try:
                response = self.client.generate(
                    model=self.model,
                    prompt=prompt,
                    options={"temperature": 0.7, "num_predict": 2000},
                )
                questions = self._parse_response(response.response, competency)
                all_questions.extend(questions)
                logger.info("Generated %d questions for %s", len(questions), competency)
            except Exception as e:
                logger.error("Error generating questions for %s: %s", competency, e)
                continue

        return all_questions


# Singleton
question_generator = QuestionGenerator()
