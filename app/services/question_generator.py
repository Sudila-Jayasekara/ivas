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

        return f"""You are an expert instructor creating SIMPLE oral viva questions for BEGINNER students.

PURPOSE: This viva checks whether the student truly UNDERSTANDS the concepts — not whether
they can write code. We want to know: Do they understand WHY something works? Can they
relate it to real-world problems? Can they explain the concept in their own words?

Generate exactly 2 different viva voce questions for the competency "{competency}" at difficulty level {difficulty_level} ({level_label}).
The 2 questions must test DIFFERENT aspects of this competency. Do NOT repeat the same question with different wording.

CONTEXT:
- Programming Language: {programming_language}
- Competency: {competency}
- Difficulty Level: {difficulty_level}/5 — {level_label}
- Level Description: {level_description}
- Marking Criteria: {marking_criteria}
- Learning Objectives: {objectives}

═══════════════════════════════════════════════════════════════
CONCEPTUAL UNDERSTANDING — THIS IS WHAT WE'RE CHECKING
═══════════════════════════════════════════════════════════════

Questions MUST focus on CONCEPTUAL UNDERSTANDING:
- Ask WHY something exists or matters, not just WHAT it is
- Ask HOW a concept applies to real-world problems
- Ask students to EXPLAIN in their own words
- Ask for COMPARISONS between concepts (at higher levels)
- Ask WHEN you would use one approach over another

Do NOT:
- Ask students to write, recite, or describe code syntax
- Ask "what is the output of this code?"
- Ask about syntax details (semicolons, brackets, etc.)
- Test memorisation of function names or language-specific syntax

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
- AVOID questions needing lists of more than 3 items
- PREFER questions answerable with a conceptual explanation
- Think: "Can a beginner answer this in 15 seconds of speaking?"

═══════════════════════════════════════════════════════════════
BLOOM'S TAXONOMY — MANDATORY QUESTION DESIGN RULES
═══════════════════════════════════════════════════════════════

The question MUST match the Bloom's level "{level_label}" (difficulty {difficulty_level}).
Follow these rules STRICTLY:

Level 1 — "Remember":
  → Ask the student to RECALL or DEFINE a SINGLE concept/term.
  → Keep it to ONE simple thing to recall.
  → Example: "What is the purpose of a struct in {programming_language}?"
  → Example: "What does a variable do in a program?"

Level 2 — "Understand":
  → Ask the student to EXPLAIN or DESCRIBE ONE concept in their own words.
  → Example: "In your own words, why do we use functions in programming?"
  → Example: "Can you explain what a loop does and why it's useful?"

Level 3 — "Apply":
  → Give a SIMPLE, DIRECTLY RELEVANT scenario and ask how they'd use the concept.
  → The scenario MUST be a realistic programming situation (building an app, processing data, etc.).
  → Example: "If you were building a student record system, how would you organise the data?"
  → Example: "How would you use a loop to process a list of student grades?"

Level 4 — "Analyse":
  → Ask ONE comparison, trade-off, or "why would you choose" question.
  → Example: "Why might you use functions instead of putting all your logic in one place?"
  → Example: "What's the difference between using a struct and using separate variables?"

Level 5 — "Evaluate & Create":
  → Ask the student to make a judgment, critique, or propose an approach.
  → Example: "If you were designing a program for a library, how would you structure the data and why?"
  → Example: "What would go wrong if a program never checked for invalid input?"

CRITICAL RULES:
1. The question MUST be about "{competency}" specifically.
2. The question MUST use the action verbs for "{level_label}" level ONLY.
3. Maximum 30 words in the question — SHORT and DIRECT.
4. The expected_answer must be a CONCEPTUAL explanation (not code) that a BEGINNER student would say in 1-3 spoken sentences (under 60 words).
5. Do NOT ask multi-part questions. ONE question, ONE thing to answer.
6. Do NOT require code syntax in the answer. Accept conceptual explanations.
7. All questions are scored out of 10 points — do NOT include max_points in output.
8. Do NOT use forced or unrelated analogies (NO apples, fruits, baskets, cookies, pizza, etc.). If you use an example or scenario, it MUST be directly related to programming or the specific competency. Ask about the concept DIRECTLY — e.g. "Why would you use a variable?" NOT "Imagine you're collecting apples in baskets...".
9. Keep examples in the PROGRAMMING DOMAIN — use scenarios like building apps, processing data, managing records, etc.

OUTPUT FORMAT (JSON array with exactly 2 items, no other text):
[
  {{
    "question_text": "Your short question here (under 30 words)",
    "expected_answer": "Brief expected response (under 60 words)..."
  }},
  {{
    "question_text": "A different short question (under 30 words)",
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
    ) -> list[GeneratedQuestionAI]:
        """
        Parameters
        ----------
        criteria_rows : list[dict]
            Each dict must contain: competency, difficulty_level, level_label,
            level_description, marking_criteria, programming_language,
            learning_objectives, max_points.  Optionally: criteria_id.

        Generates exactly two questions per criteria row (one per competency).
        With 5 Bloom's levels × 2 questions each = 10 questions total.
        """
        all_questions: list[GeneratedQuestionAI] = []

        for cr in criteria_rows:
            competency = cr["competency"]
            difficulty = cr["difficulty_level"]
            criteria_id = cr.get("criteria_id")
            logger.info(
                "Generating 2 questions for competency=%s difficulty=%d",
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