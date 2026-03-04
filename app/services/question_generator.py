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
        assignment_text: str = "",
        num_questions: int | None = None,
    ) -> str:
        objectives = ", ".join(learning_objectives)

        # Dynamic question count
        if num_questions is not None:
            count_instruction = f"Generate EXACTLY {num_questions} different viva voce questions"
            output_count_note = f"JSON array with exactly {num_questions} items"
            overlap_rule = f"The {num_questions} questions must test genuinely DIFFERENT aspects — if two questions would get the same answer, they are too similar."
        else:
            count_instruction = """Generate 1 to 3 viva voce questions (decide based on the competency's breadth:
- Narrow competency with one clear concept: 1 question
- Moderate competency with 2 aspects: 2 questions
- Broad competency covering multiple facets: 3 questions)
You MUST cover ALL important aspects of this competency. Do not skip any"""
            output_count_note = "JSON array with 1-3 items"
            overlap_rule = "Each question must test a genuinely DIFFERENT aspect — if two questions would get the same answer, they are too similar."

        assignment_section = ""
        if assignment_text:
            assignment_section = f"""
═══════════════════════════════════════════════════════════════
ASSIGNMENT CONTEXT — FOR LIGHT REFERENCE ONLY
═══════════════════════════════════════════════════════════════

The student completed this assignment. You MAY lightly reference the scenario
to make questions feel familiar, but the question MUST primarily test the
TECHNICAL CONCEPT "{competency}" — NOT the assignment's domain/scenario.

ASSIGNMENT:
\"\"\"
{assignment_text}
\"\"\"
"""

        return f"""You are an expert instructor creating oral viva questions for BEGINNER students.

PURPOSE: These questions check whether the student UNDERSTANDS the technical
CONCEPT behind what they did — WHY it works, WHEN to use it, and HOW it
behaves. You are NOT checking if they can describe what their program does.

{count_instruction} for the competency "{competency}" at difficulty level {difficulty_level} ({level_label}).
{assignment_section}
CONTEXT:
- Programming Language: {programming_language}
- Competency: {competency}
- Difficulty Level: {difficulty_level}/5 — {level_label}
- Level Description: {level_description}
- Marking Criteria: {marking_criteria}
- Learning Objectives: {objectives}

═══════════════════════════════════════════════════════════════
THE GOLDEN RULE — TEST THE PROGRAMMING CONCEPT, NOT THE SCENARIO
═══════════════════════════════════════════════════════════════

Every assignment uses a SCENARIO (e.g., students, grades, animals, games) to teach
a PROGRAMMING CONCEPT (loops, arrays, functions, etc.). Your questions MUST test
whether the student understands the CONCEPT — not the scenario.

Test: "Would this question still make sense if the scenario changed
but the same programming construct was used?" If YES → good. If NO → rewrite.

GOOD questions (name specific constructs):
- "Why did you use a for loop instead of writing the same code multiple times?"
  → Tests: understanding of loops / iteration
- "Why store the values in an array instead of separate variables?"
  → Tests: understanding of arrays / collections
- "What does your if-else condition check, and why is that check needed?"
  → Tests: understanding of conditional logic
- "Why did you put this code in a separate function?"
  → Tests: understanding of modular design
- "How does your loop know when to stop?"
  → Tests: understanding of loop termination

BAD questions (test the scenario or are too vague):
- "Why do you need to count the students?" (scenario-specific)
- "What does your program output?" (describes behavior, not concept)
- "Why is it important to track grades?" (domain knowledge)
- "What is the main purpose of this code?" (too generic)
- "Explain your approach" (too vague, no specific construct)

Do NOT ask questions that require knowledge of the assignment's specific
inputs, outputs, entities, or domain to answer. The student should be able
to answer based on their understanding of the PROGRAMMING CONCEPT alone.

═══════════════════════════════════════════════════════════════
EXPECTED ANSWERS — MUST EXPLAIN THE CONCEPT
═══════════════════════════════════════════════════════════════

The expected_answer MUST explain WHY/WHEN/HOW the programming concept works.
It should NOT describe what the student's specific program does.

GOOD expected answer (for "Why use a for loop instead of repeating code?"):
"A for loop lets you repeat the same instructions many times without writing
them out each time. It's useful when you know how many times you need to repeat."

BAD expected answer:
"The program reads 5 student names and stores them one by one."
(Describes program behavior, not the concept.)

═══════════════════════════════════════════════════════════════
VOICE-FIRST DESIGN — THIS IS A SPOKEN ASSESSMENT
═══════════════════════════════════════════════════════════════

Students answer by SPEAKING into a microphone. Speech-to-text converts
their voice to text. This means:
- Questions MUST be SHORT (1-2 sentences max, under 30 words)
- Questions MUST be simple and direct — one clear thing to answer
- Answers MUST be expressible in 1-3 SHORT spoken sentences
- Do NOT ask multi-part questions (no "and also" or "additionally")
- Do NOT require precise technical jargon that speech-to-text may garble
- Think: "Can a beginner answer this in 15 seconds of speaking?"
- Expected answers should use everyday language a beginner would naturally speak

═══════════════════════════════════════════════════════════════
BLOOM'S TAXONOMY — MANDATORY QUESTION DESIGN RULES
═══════════════════════════════════════════════════════════════

The question MUST match the Bloom's level "{level_label}" (difficulty {difficulty_level}).
Follow these rules STRICTLY:

Level 1 — "Remember":
  → Ask the student to identify or name the programming construct they used.
  → Example: "What type of loop did you use in your code?"
  → Example: "What data structure did you use to store the values?"

Level 2 — "Understand":
  → Ask the student to EXPLAIN WHY they used a specific construct.
  → Example: "Why did you use a for loop instead of writing the code out each time?"
  → Example: "Why store the data in an array instead of separate variables?"

Level 3 — "Apply":
  → Ask how the construct works step by step in a specific situation.
  → Example: "What happens when your loop reaches the last element?"
  → Example: "What would change if you used a while loop instead of a for loop?"

Level 4 — "Analyse":
  → Ask to compare constructs or identify trade-offs.
  → Example: "What's the difference between using a for loop and a while loop here?"
  → Example: "Could you solve this without using an array? What would be harder?"

Level 5 — "Evaluate & Create":
  → Ask the student to critique or extend their approach.
  → Example: "What would break in your code if the input had zero items?"
  → Example: "How would you change your approach if the data came from a file instead?"

CRITICAL RULES:
1. The question MUST be about "{competency}" specifically — the PROGRAMMING CONCEPT.
2. The question MUST match "{level_label}" level ONLY.
3. Maximum 30 words in the question — SHORT and DIRECT.
4. The expected_answer must explain the CONCEPT (not describe program behavior) in 1-3 spoken sentences (under 60 words).
5. Do NOT ask multi-part questions. ONE question, ONE thing to answer.
6. Do NOT require code syntax in the answer. Accept conceptual explanations.
7. All questions are scored out of 10 points — do NOT include max_points in output.
8. Questions MUST test the PROGRAMMING CONCEPT — NOT domain/scenario knowledge.
9. Do NOT use forced or unrelated analogies (NO apples, fruits, baskets, cookies, pizza, etc.).
10. {overlap_rule}
11. The question must make logical sense in the context of the concept being tested.
12. The expected answer must directly and correctly answer the question.

OUTPUT FORMAT ({output_count_note}, no other text):
[
  {{
    "question_text": "Your short question here (under 30 words)",
    "expected_answer": "Brief conceptual explanation (under 60 words)..."
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
        assignment_text: str = "",
        num_questions: int | None = None,
    ) -> list[GeneratedQuestionAI]:
        """
        Parameters
        ----------
        criteria_rows : list[dict]
            Each dict must contain: competency, difficulty_level, level_label,
            level_description, marking_criteria, programming_language,
            learning_objectives.  Optionally: criteria_id.
        assignment_text : str
            The original assignment text, used to keep questions in context.
        num_questions : int | None
            Optional: exact number of questions per criterion. If None, LLM decides.

        Generates questions for each criteria row. Count is dynamic.
        """
        all_questions: list[GeneratedQuestionAI] = []

        for cr in criteria_rows:
            competency = cr["competency"]
            difficulty = cr["difficulty_level"]
            criteria_id = cr.get("criteria_id")
            logger.info(
                "Generating questions for competency=%s difficulty=%d (num_questions=%s)",
                competency, difficulty, num_questions,
            )

            prompt = self._build_prompt(
                competency=competency,
                difficulty_level=difficulty,
                level_label=cr["level_label"],
                level_description=cr["level_description"],
                marking_criteria=cr["marking_criteria"],
                programming_language=cr["programming_language"],
                learning_objectives=cr["learning_objectives"],
                assignment_text=assignment_text,
                num_questions=num_questions,
            )

            try:
                response_text = llm_service.generate(
                    prompt=prompt,
                    temperature=0.5,
                    num_predict=1500,
                    max_output_tokens=1500,
                    top_p=0.85,
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