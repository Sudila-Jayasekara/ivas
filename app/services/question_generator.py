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

        # Per-level definitions: question style, allowed verbs, example, and forbidden patterns
        level_definitions = {
            1: {
                "label": "Level 1 — Basic Recall & Definitions",
                "description": (
                    "Simple, direct conceptual questions. "
                    "Student only needs to recall or identify a single concept."
                ),
                "allowed_verbs": "what, define, identify, name, list, state",
                "question_style": "Ask for a single definition, identification, or simple factual recall.",
                "good_example": f'"What is a {competency} in {programming_language}? Why does it exist?"',
                "bad_example": '"Compare X and Y" or "What are the trade-offs" (too complex for Level 1)',
                "forbidden": (
                    "Do NOT ask for comparisons, trade-offs, design decisions, "
                    "debugging, or multi-step reasoning."
                ),
            },
            2: {
                "label": "Level 2 — Basic Comparison & Explanation",
                "description": (
                    "Straightforward comparison or explanation of two related ideas. "
                    "Student explains a difference or describes what happens in a simple scenario."
                ),
                "allowed_verbs": "compare, explain, describe, differentiate, what happens when",
                "question_style": "Ask for a simple comparison between two concepts or a brief explanation of behaviour.",
                "good_example": f'"What is the difference between X and Y in {programming_language}?"',
                "bad_example": '"Analyze trade-offs" or "Design a solution" (too complex for Level 2)',
                "forbidden": (
                    "Do NOT ask for trade-off analysis, design decisions, debugging of complex code, "
                    "or multi-step reasoning."
                ),
            },
            3: {
                "label": "Level 3 — Trade-offs & Intermediate Analysis",
                "description": (
                    "Questions requiring the student to weigh pros and cons, "
                    "choose between approaches, or reason about when to use one technique over another."
                ),
                "allowed_verbs": "compare trade-offs, when would you, why choose, what are the pros and cons",
                "question_style": "Ask about trade-offs, choosing between approaches, or analysing a scenario.",
                "good_example": f'"When would you choose approach A over B for {competency}? What are the trade-offs?"',
                "bad_example": '"Define X" (too simple) or "Design a full system" (too complex)',
                "forbidden": (
                    "Do NOT ask basic definitions (Level 1-2) or complex system design / architecture (Level 4-5)."
                ),
            },
            4: {
                "label": "Level 4 — Complex Scenarios & Multi-step Reasoning",
                "description": (
                    "Questions involving a non-trivial scenario that requires combining multiple concepts, "
                    "debugging complex issues, or reasoning through several steps."
                ),
                "allowed_verbs": "analyze, debug, predict, evaluate, what would happen if, how would you handle",
                "question_style": "Present a complex scenario and ask the student to reason through it step-by-step.",
                "good_example": f'"Given this scenario involving {competency}, predict what happens and explain why."',
                "bad_example": '"What is X?" (too simple for Level 4)',
                "forbidden": (
                    "Do NOT ask simple recall or basic comparisons (Level 1-2)."
                ),
            },
            5: {
                "label": "Level 5 — Advanced Design & Critical Thinking",
                "description": (
                    "Questions demanding deep expertise: designing solutions under constraints, "
                    "critiquing designs, identifying subtle edge cases, or reasoning about system-level impact."
                ),
                "allowed_verbs": "design, architect, critique, optimize, what edge cases, how would you restructure",
                "question_style": "Ask the student to design, critique, or deeply analyze a sophisticated problem.",
                "good_example": f'"Design a robust approach to handle {competency} under these constraints. What edge cases must you consider?"',
                "bad_example": '"Explain the difference between X and Y" (too simple for Level 5)',
                "forbidden": (
                    "Do NOT ask basic recall, simple comparisons, or straightforward trade-offs (Level 1-3)."
                ),
            },
        }

        # Build per-level blocks for only the levels in the requested range
        level_blocks: list[str] = []
        for level in range(difficulty_min, difficulty_max + 1):
            defn = level_definitions[level]
            level_blocks.append(
                f"""{defn['label']}:
  Description : {defn['description']}
  Allowed verbs: {defn['allowed_verbs']}
  Question style: {defn['question_style']}
  GOOD example : {defn['good_example']}
  BAD example  : {defn['bad_example']}
  FORBIDDEN    : {defn['forbidden']}"""
            )

        difficulty_section = "\n\n".join(level_blocks)

        return f"""
You are an expert programming instructor creating oral viva questions to assess students' understanding of programming concepts.

Generate {num_questions} unique viva voce (oral exam) question(s) for a programming assignment.

CRITICAL REQUIREMENTS:
- Questions MUST test conceptual understanding, NOT syntax or code writing
- Ask WHY and WHEN, not HOW TO write code
- Questions should reveal whether student truly understands the concept
- Avoid memorization-based questions
- Every question MUST be specifically about the Target Competency: "{competency}"
- Do NOT generate questions about unrelated topics

═══════════════════════════════════════════
  DIFFICULTY CONSTRAINT — THIS IS MANDATORY
═══════════════════════════════════════════
Every question MUST have a difficulty value that is an integer between {difficulty_min} and {difficulty_max} (inclusive).
If a question's complexity does not fit within Level {difficulty_min}–{difficulty_max}, do NOT generate it — generate a simpler/harder alternative that fits.

ALLOWED DIFFICULTY LEVELS (only these):

{difficulty_section}

HARD RULES:
- difficulty field MUST be >= {difficulty_min} and <= {difficulty_max}
- If you are tempted to write a question that belongs to a level outside {difficulty_min}-{difficulty_max}, STOP and rewrite it
- Match the question style, allowed verbs, and constraints for the level you assign
═══════════════════════════════════════════

Assignment Details:
- Title: {title}
- Programming Language: {programming_language}
- Target Competency: {competency}
- Learning Objectives: {objectives}

COMPETENCY FOCUS:
- The question MUST directly test the student's understanding of "{competency}"
- "{competency}" means: the programming concept called "{competency}" — stay on topic
- The question should be clearly and obviously about "{competency}", not a tangentially related topic

BAD Examples (avoid these regardless of difficulty):
- "Explain how to write a for loop" (tests syntax, not understanding)
- "Show syntax for a while loop" (asks for code)
- "Write a function that does X" (asks for code)

Output Format (JSON array only):
[
  {{
    "question_text": "Your question here about {competency} in {programming_language}",
    "difficulty": {difficulty_min},
    "expected_key_concepts": ["concept1", "concept2", "concept3"],
    "grading_criteria": "What the student should demonstrate",
    "max_points": 10
  }}
]

FINAL CHECKLIST before returning:
1. Is every question about "{competency}"? If no, rewrite.
2. Is difficulty between {difficulty_min} and {difficulty_max}? If no, rewrite.
3. Does the question match the style/verbs for its difficulty level? If no, rewrite.

Generate exactly {num_questions} question(s).
Return ONLY valid JSON array.
""".strip()



    # ------------------------------------------------------------------
    # Parse
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(
        response_text: str,
        competency: str,
        difficulty_min: int,
        difficulty_max: int,
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
                # Clamp difficulty to the requested range
                raw_difficulty = q.get("difficulty", difficulty_min)
                clamped_difficulty = max(difficulty_min, min(difficulty_max, raw_difficulty))
                if raw_difficulty != clamped_difficulty:
                    logger.warning(
                        "AI returned difficulty %d for competency '%s', clamped to %d (range %d-%d)",
                        raw_difficulty, competency, clamped_difficulty, difficulty_min, difficulty_max,
                    )

                questions.append(
                    GeneratedQuestionAI(
                        question_text=q.get("question_text", ""),
                        competency=competency,
                        difficulty=clamped_difficulty,
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
                questions = self._parse_response(
                    response.response, competency, difficulty_min, difficulty_max
                )
                all_questions.extend(questions)
                logger.info("Generated %d questions for %s", len(questions), competency)
            except Exception as e:
                logger.error("Error generating questions for %s: %s", competency, e)
                continue

        return all_questions


# Singleton
question_generator = QuestionGenerator()
