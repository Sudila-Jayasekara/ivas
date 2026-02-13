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

        objectives = ", ".join(learning_objectives)

        return f"""
You are an expert programming instructor creating oral viva questions to assess students' DEEP UNDERSTANDING of programming concepts.

Generate {num_questions} unique viva voce (oral exam) questions for a programming assignment.

CRITICAL REQUIREMENTS:
- Questions MUST test conceptual understanding, NOT syntax or code writing
- Ask WHY and WHEN, not HOW TO write code
- Questions should reveal whether student truly understands the concept
- Avoid memorization-based questions
- Focus on trade-offs, comparisons, real-world scenarios, and problem-solving

Assignment Details:
- Title: {title}
- Programming Language: {programming_language}
- Target Competency: {competency}
- Difficulty Range: {difficulty_min} to {difficulty_max} (scale 1-5)
- Learning Objectives: {objectives}

Question Types to Generate:
1. Comparison questions
2. Trade-off questions
3. Design questions
4. Debugging/Analysis
5. Real-world application

BAD Examples:
- Explain how to write a for loop
- Show syntax for a while loop
- Write a function that does X

GOOD Examples:
- Compare for loops and while loops. When use each?
- Trade-offs between iteration and recursion?
- Loop runs infinitely. Possible causes?

Output Format (JSON array only):
[
  {{
    "question_text": "Compare for loops and while loops in {programming_language}. When use each?",
    "difficulty": 2,
    "expected_key_concepts": ["iteration control", "termination", "use cases"],
    "grading_criteria": "Student explains differences, scenarios, trade-offs",
    "max_points": 10
  }}
]

Difficulty Guidelines:
- Level 1-2: Basic comparisons
- Level 3: Trade-offs
- Level 4-5: Complex scenarios

Generate exactly {num_questions} questions.
Return ONLY valid JSON array.
""".strip()



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
