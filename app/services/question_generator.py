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
ASSIGNMENT REFERENCE — FOR CONTEXT ONLY
═══════════════════════════════════════════════════════════════

The student completed THIS assignment. The assignment uses a SCENARIO
(e.g. mountains, students, books) as a vehicle for teaching programming.
You MAY reference the scenario to make questions feel familiar, but the
question MUST test the TECHNICAL PROGRAMMING COMPETENCY, not domain knowledge.

GOOD: "In your mountain program, why did you use an array instead of separate variables?"
  → Tests: arrays (technical)
BAD: "Why do we need to save the heights of mountains?"
  → Tests: mountains (domain)

ASSIGNMENT:
\"\"\"
{assignment_text}
\"\"\"
"""

        return f"""You are an expert instructor creating oral viva questions for BEGINNER students.

PURPOSE: These questions check whether the student UNDERSTANDS what they did in their
assignment and WHY their code works. Questions must be SPECIFIC to the assignment — 
not generic programming philosophy.

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
QUESTION QUALITY — SPECIFIC, NOT VAGUE
═══════════════════════════════════════════════════════════════

Questions MUST be SPECIFIC to the assignment. They should reference what the
student ACTUALLY DID — the data they worked with, the steps their program takes,
the output it produces. NEVER ask generic "why does this concept exist?" questions.

GOOD questions (specific, grounded in the assignment):
- "Your program reads 10 numbers — where do those numbers go after reading them?"
- "After sorting the heights, how does your program pick just the top 3?"
- "What would happen if two mountains had the same height in your program?"
- "If you added an 11th mountain, what would you need to change?"

BAD questions (vague, philosophical — NEVER generate these):
- "Why do programs need to get information from the user?" ← too obvious, no depth
- "What is the main purpose of reading input?" ← generic, not specific to assignment
- "Imagine you're building a program. Why might you need a number?" ← philosophical
- "Why would you use an array?" ← generic, not grounded in what they did

The difference: GOOD questions make the student think about THEIR specific program.
BAD questions sound like textbook definitions anyone could answer without doing the assignment.

Do NOT:
- Ask students to write, recite, or describe code syntax
- Ask "what is the output of this code?"
- Ask about syntax details (semicolons, brackets, etc.)
- Test memorisation of function names or data type names
- Ask generic "why does X exist in programming?" questions

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
  → Ask the student to recall a SPECIFIC fact about their program.
  → Reference something concrete from the assignment.
  → Example: "In your program, where do the 10 numbers go after you read them?"
  → Example: "How many numbers does your program read from the user?"

Level 2 — "Understand":
  → Ask the student to EXPLAIN a specific decision in their program.
  → Example: "Why did your program need to store all 10 heights instead of just reading one at a time?"
  → Example: "After sorting, why are the top 3 heights at the end of the array?"

Level 3 — "Apply":
  → Ask how a specific part of their program works step by step.
  → Example: "Walk me through how your program finds the 3 largest heights."
  → Example: "What would your program do if the user entered a negative number?"

Level 4 — "Analyse":
  → Ask to compare approaches or identify trade-offs in their solution.
  → Example: "Could you find the top 3 heights without sorting? What would be different?"
  → Example: "What's the difference between sorting all 10 and just picking the 3 biggest?"

Level 5 — "Evaluate & Create":
  → Ask the student to critique or propose improvements to their program.
  → Example: "If the assignment asked for the top 5 instead of top 3, what would you change?"
  → Example: "What would break in your program if two mountains had the same height?"

CRITICAL RULES:
1. The question MUST be about "{competency}" specifically.
2. The question MUST use the action verbs for "{level_label}" level ONLY.
3. Maximum 30 words in the question — SHORT and DIRECT.
4. The expected_answer must be a CONCEPTUAL explanation (not code) that a BEGINNER student would say in 1-3 spoken sentences (under 60 words). Use everyday language.
5. Do NOT ask multi-part questions. ONE question, ONE thing to answer.
6. Do NOT require code syntax in the answer. Accept conceptual explanations.
7. All questions are scored out of 10 points — do NOT include max_points in output.
8. Questions MUST test the TECHNICAL COMPETENCY — NOT domain knowledge. The question should test programming skills, not facts about mountains/students/etc.
9. Do NOT use forced or unrelated analogies (NO apples, fruits, baskets, cookies, pizza, etc.).
10. {overlap_rule}
11. LOGICAL COHERENCE: The question MUST logically relate to the actual code the student wrote and make total sense. Do NOT generate "stupid" or nonsensical questions.
12. STRICT EXPECTED ANSWER MATCH: The expected answer MUST completely and accurately answer the question. Later upon evaluation, the model will strictly compare the student's spoken response against this expected answer.

OUTPUT FORMAT ({output_count_note}, no other text):
[
  {{
    "question_text": "Your short question here (under 30 words)",
    "expected_answer": "Brief expected response (under 60 words)..."
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