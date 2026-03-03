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
THE GOLDEN RULE — TEST THE CONCEPT, NOT THE SCENARIO
═══════════════════════════════════════════════════════════════

Every assignment uses a SCENARIO (e.g., real-world entities or behaviors) to teach
a TECHNICAL CONCEPT (the underlying programming principle). Your questions MUST
test whether the student understands the CONCEPT — not the scenario.

Ask yourself: "Would this question still make sense if the scenario changed
but the same programming concept was used?" If YES → good question.
If NO → you're testing the scenario, rewrite it.

GOOD questions (test the CONCEPT — survive scenario changes):
- "What is the primary technical reason for choosing this approach over an alternative?"
  → Tests: comparative technical understanding
- "How does this specific programming construct behave under edge-case conditions?"
  → Tests: understanding of technical mechanics
- "When is this particular technical solution necessary versus a simpler one?"
  → Tests: understanding of technical requirements
- "What are the fundamental principles governing this technical concept?"
  → Tests: conceptual understanding

BAD questions (test the SCENARIO — break if scenario changes):
- "Why do we need to count the specific items in this scenario?"
  → Tests: the scenario, not the technical concept
- "What does your program output when given these specific inputs?"
  → Tests: program behavior, not understanding
- "Why is it important to track these specific real-world values?"
  → Tests: domain knowledge, not programming skill
- "What is the main purpose of this code?"
  → Too generic, doesn't test any specific concept

The difference: GOOD questions have a definitive technical answer about
the programming concept. BAD questions are about the scenario or so generic
that anyone could answer without understanding the concept.

═══════════════════════════════════════════════════════════════
EXPECTED ANSWERS — MUST DEMONSTRATE CONCEPTUAL UNDERSTANDING
═══════════════════════════════════════════════════════════════

The expected_answer MUST be a conceptual explanation of the TECHNICAL CONCEPT.
It should show understanding of WHY/WHEN/HOW the concept works — not describe
what the student's specific program does.

GOOD expected answer (for "Why this approach over an alternative?"):
"This approach is more efficient because it handles [technical property] automatically, whereas the alternative would require manual [technical process]."

BAD expected answer:
"The program reads the specific inputs and stores them in the specified structure."
(This describes WHAT the program does, not WHY the concept was used.)

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
  → Ask the student to recall a fact about the TECHNICAL CONCEPT they used.
  → Example: "What specific technical construct did you use for this requirement?"
  → Example: "Which technical property is being utilized here?"

Level 2 — "Understand":
  → Ask the student to EXPLAIN WHY they chose a specific technical approach.
  → Example: "Why did you choose this technical approach instead of a simpler one?"
  → Example: "Why is this specific construct necessary for this task?"

Level 3 — "Apply":
  → Ask how the technical concept works step by step.
  → Example: "What happens technically when this construct reaches a specific state?"
  → Example: "What would the technical result be if we changed this parameter?"

Level 4 — "Analyse":
  → Ask to compare technical approaches or identify concept trade-offs.
  → Example: "Could you solve this using a different technical method? What would change?"
  → Example: "What is the technical trade-off between these two approaches?"

Level 5 — "Evaluate & Create":
  → Ask the student to critique or extend their technical approach.
  → Example: "If the technical constraints changed in this way, how would your approach adapt?"
  → Example: "What technical failure would occur if this specific boundary condition was met?"

CRITICAL RULES:
1. The question MUST be about "{competency}" specifically — the TECHNICAL CONCEPT.
2. The question MUST use the action verbs for "{level_label}" level ONLY.
3. Maximum 30 words in the question — SHORT and DIRECT.
4. The expected_answer must demonstrate CONCEPTUAL UNDERSTANDING (not describe program behavior) in 1-3 spoken sentences (under 60 words).
5. Do NOT ask multi-part questions. ONE question, ONE thing to answer.
6. Do NOT require code syntax in the answer. Accept conceptual explanations.
7. All questions are scored out of 10 points — do NOT include max_points in output.
8. Questions MUST test the TECHNICAL CONCEPT — NOT domain/scenario knowledge.
9. Do NOT use forced or unrelated analogies (NO apples, fruits, baskets, cookies, pizza, etc.).
10. {overlap_rule}
11. LOGICAL COHERENCE: The question must make sense in the context of the concept being tested.
12. STRICT EXPECTED ANSWER MATCH: The expected answer must be a correct conceptual explanation that directly answers the question.

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