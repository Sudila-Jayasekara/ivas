"""
Grading Criteria Service

Business logic for generating, retrieving, and updating grading criteria.
API 1: Lecturer posts assignment text → AI extracts competencies, difficulty
       levels, marking criteria, programming language, and learning objectives.
API 2: Lecturer reviews the criteria.
API 3: Lecturer edits individual criteria rows.
"""

import asyncio
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grading_criteria import GradingCriteria
from app.repositories.grading_criteria_repository import GradingCriteriaRepository
from app.schemas.grading_criteria import GradingCriteriaAI
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class GradingCriteriaService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = GradingCriteriaRepository(session)

    # ------------------------------------------------------------------
    # Generate (API 1)
    # ------------------------------------------------------------------

    async def generate(self, assignment_id: str, assignment_text: str, replace_existing: bool = False) -> dict:
        """Send assignment text to AI, parse response, persist criteria rows."""
        logger.info("Generating grading criteria for assignment=%s (replace=%s)", assignment_id, replace_existing)

        prompt = self._build_prompt(assignment_text)

        try:
            response_text = await asyncio.to_thread(
                llm_service.generate,
                prompt,
                temperature=0.4,
                num_predict=4000,
                max_output_tokens=4000,
                top_p=0.9,
            )
        except Exception as e:
            logger.error("LLM call failed for grading criteria: %s", e, exc_info=True)
            raise RuntimeError("LLM generation failed") from e

        parsed = self._parse_response(response_text)
        if not parsed:
            raise ValueError("AI returned no usable grading criteria")

        programming_language = parsed["programming_language"]
        learning_objectives = parsed["learning_objectives"]
        criteria_items: list[GradingCriteriaAI] = parsed["criteria"]

        if replace_existing:
            await self.repo.delete_by_assignment_id(assignment_id)
        else:
            # Find existing competency+difficulty combos to skip duplicates
            existing = await self.repo.find_by_assignment_id(assignment_id)
            existing_keys = {
                (c.competency, c.difficulty_level) for c in existing
            }
            criteria_items = [
                item for item in criteria_items
                if (item.competency, item.difficulty_level) not in existing_keys
            ]

        criteria_ids: list[str] = []
        for item in criteria_items:
            row = GradingCriteria(
                assignment_id=assignment_id,
                competency=item.competency,
                difficulty_level=item.difficulty_level,
                level_label=item.level_label,
                level_description=item.level_description,
                marking_criteria=item.marking_criteria,
                programming_language=programming_language,
                learning_objectives=learning_objectives,
            )
            try:
                row = await self.repo.create(row)
                criteria_ids.append(row.id)
            except Exception as e:
                logger.error("Failed to save grading criteria row: %s", e)
                continue

        logger.info(
            "Grading criteria stored: assignment=%s total=%d",
            assignment_id,
            len(criteria_ids),
        )
        return {"criteria_ids": criteria_ids, "total_generated": len(criteria_ids)}

    # ------------------------------------------------------------------
    # Read (API 2)
    # ------------------------------------------------------------------

    async def get_by_assignment(self, assignment_id: str) -> list[GradingCriteria]:
        return await self.repo.find_by_assignment_id(assignment_id)

    async def get_by_id(self, criteria_id: str) -> GradingCriteria | None:
        return await self.repo.find_by_id(criteria_id)

    # ------------------------------------------------------------------
    # Update (API 3)
    # ------------------------------------------------------------------

    async def update(self, criteria_id: str, updates: dict) -> GradingCriteria | None:
        row = await self.repo.find_by_id(criteria_id)
        if not row:
            return None

        for field, value in updates.items():
            if value is not None and hasattr(row, field):
                setattr(row, field, value)

        return await self.repo.update(row)

    # ------------------------------------------------------------------
    # Prompt
    # ------------------------------------------------------------------

    @staticmethod
    def _build_prompt(assignment_text: str) -> str:
        return f"""You are an expert university lecturer designing an ORAL VIVA assessment. Analyse the following assignment text and produce grading criteria that can ONLY be assessed through spoken conversation — no written answers, no live coding.

ASSIGNMENT TEXT:
\"\"\"
{assignment_text}
\"\"\"

From the assignment text above you must extract:
1. The programming language used (e.g. "Python", "Java", "C++").
2. A list of learning objectives the assignment addresses.
3. A set of oral-viva grading criteria covering different competencies and Bloom's taxonomy levels.

Each criterion must be designed so that an assessor can probe student understanding purely through verbal questions and conversation. Do NOT produce criteria that require the student to write code, run programs, or submit text. Everything must be testable by asking the student to EXPLAIN, JUSTIFY, DESCRIBE, or DISCUSS verbally.

═══════════════════════════════════════════════════════════════
BLOOM'S TAXONOMY — MANDATORY RULES (follow these EXACTLY)
═══════════════════════════════════════════════════════════════

You MUST map each criterion to ONE of the following Bloom's levels.
Use the EXACT difficulty_level integer AND the EXACT level_label string shown below.
Use ONLY the action verbs listed for that level — both in level_description and marking_criteria.

┌─────────────────┬────────────────────┬──────────────────────────────────────────────────────────────────┐
│ difficulty_level │ level_label        │ Permitted action verbs & what to assess                         │
├─────────────────┼────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 1               │ "Remember"         │ DEFINE, LIST, RECALL, NAME, IDENTIFY, STATE                     │
│                 │                    │ Student recalls facts, terms, definitions from memory.           │
│                 │                    │ Example Q: "Can you list the data types in C++?"                 │
│                 │                    │ Example Q: "What is the syntax for declaring a function?"        │
├─────────────────┼────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 2               │ "Understand"       │ EXPLAIN, DESCRIBE, SUMMARISE, PARAPHRASE, COMPARE, CONTRAST     │
│                 │                    │ Student demonstrates comprehension by explaining concepts        │
│                 │                    │ IN THEIR OWN WORDS. No application to new scenarios.             │
│                 │                    │ Example Q: "Explain why functions are useful in programming."     │
│                 │                    │ Example Q: "Describe the difference between pass-by-value and    │
│                 │                    │  pass-by-reference."                                             │
├─────────────────┼────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 3               │ "Apply"            │ DEMONSTRATE, SOLVE, USE, IMPLEMENT (verbally), CALCULATE        │
│                 │                    │ Student applies knowledge to a SPECIFIC NEW SCENARIO verbally.   │
│                 │                    │ The question MUST present a concrete scenario and ask the        │
│                 │                    │ student to walk through their approach step-by-step.             │
│                 │                    │ Example Q: "Given a radius of 5, walk me through how your        │
│                 │                    │  function calculates the area."                                  │
│                 │                    │ Example Q: "If the user enters -3 as input, what would happen    │
│                 │                    │  in your program and how would you handle it?"                   │
├─────────────────┼────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 4               │ "Analyse"          │ ANALYSE, DIFFERENTIATE, COMPARE, CONTRAST, EXAMINE, DECONSTRUCT │
│                 │                    │ Student breaks down a problem into parts, identifies             │
│                 │                    │ relationships, or compares alternatives with reasoning.          │
│                 │                    │ The question MUST ask WHY or HOW alternatives differ.            │
│                 │                    │ Example Q: "Why did you use pass-by-reference here instead of    │
│                 │                    │  pass-by-value? What would change if you switched?"              │
│                 │                    │ Example Q: "Compare using a single monolithic function vs.       │
│                 │                    │  decomposing into multiple functions. What are the trade-offs?"  │
├─────────────────┼────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 5               │ "Evaluate & Create"│ EVALUATE, JUSTIFY, CRITIQUE, DESIGN, PROPOSE, HYPOTHESISE      │
│                 │                    │ Student makes judgements, defends design decisions, or           │
│                 │                    │ proposes new solutions to complex/novel situations.              │
│                 │                    │ The question MUST require critical thinking and justification.   │
│                 │                    │ Example Q: "If you had to redesign this program to handle 1000   │
│                 │                    │  shapes, what would you change and why?"                         │
│                 │                    │ Example Q: "Critique your error handling strategy. What are its  │
│                 │                    │  weaknesses and how would you improve it?"                       │
└─────────────────┴────────────────────┴──────────────────────────────────────────────────────────────────┘

IMPORTANT CONSTRAINTS:
- Every criterion's level_description must contain 2-4 example VERBAL QUESTIONS using ONLY the action verbs for that level.
- Do NOT use "Describe" or "Explain" verbs in Apply/Analyse/Evaluate levels — those belong to Understand.
- Do NOT use "Walk me through" or scenario-based questions at the Understand level — those belong to Apply.
- The marking_criteria must describe what assessors LISTEN FOR at the specific Bloom's level, not generic pass/fail.
- Generate a good spread across difficulty levels (aim for at least 2-3 different levels).
- Every criterion must be assessable purely through verbal dialogue.

For each grading criterion provide:
- competency: the skill or knowledge area being probed
- difficulty_level: integer 1-5 as per the table above
- level_label: EXACT string from the table above
- level_description: 2-4 example VERBAL QUESTIONS using the correct Bloom's verbs
- marking_criteria: specific observable indicators the assessor LISTENS FOR

NOTE: All questions are scored out of a FIXED 10 points. Do NOT include max_points in criteria.

OUTPUT FORMAT (JSON only, no other text):
{{
  "programming_language": "C++",
  "learning_objectives": ["objective 1", "objective 2"],
  "criteria": [
    {{
      "competency": "...",
      "difficulty_level": 2,
      "level_label": "Understand",
      "level_description": "Explain why ... / Describe how ... / Summarise ...",
      "marking_criteria": "Full marks: student clearly explains... Partial: student mentions but cannot elaborate... No marks: student cannot answer."
    }}
  ]
}}

Return ONLY valid JSON. Generate a comprehensive set of criteria covering all key competencies and multiple Bloom's levels relevant to the assignment.""".strip()

    # ------------------------------------------------------------------
    # Parse
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(response_text: str) -> dict | None:
        try:
            text = response_text.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end == 0:
                logger.error("No JSON object found in LLM response: %s", text[:300])
                return None

            data = json.loads(text[start:end])

            programming_language = data.get("programming_language", "Unknown")
            learning_objectives = data.get("learning_objectives", [])
            raw_criteria = data.get("criteria", [])

            criteria: list[GradingCriteriaAI] = []

            # Valid Bloom's level labels — enforce consistency
            VALID_LABELS = {
                1: "Remember",
                2: "Understand",
                3: "Apply",
                4: "Analyse",
                5: "Evaluate & Create",
            }

            for c in raw_criteria:
                try:
                    # LLM may return level_description as a list of viva questions;
                    # join into a single string so the schema validation passes.
                    if isinstance(c.get("level_description"), list):
                        c["level_description"] = " / ".join(c["level_description"])
                    # Enforce correct Bloom's level_label based on difficulty_level
                    difficulty = c.get("difficulty_level", 1)
                    c["level_label"] = VALID_LABELS.get(difficulty, "Understand")
                    # Remove max_points if LLM included it — it's always fixed at 10
                    c.pop("max_points", None)
                    criteria.append(GradingCriteriaAI(**c))
                except Exception as e:
                    logger.warning("Skipping invalid criterion: %s — %s", c, e)
                    continue

            if not criteria:
                return None

            return {
                "programming_language": programming_language,
                "learning_objectives": learning_objectives,
                "criteria": criteria,
            }
        except json.JSONDecodeError as e:
            logger.error("JSON parse error: %s\nResponse: %s", e, response_text[:500])
            return None
        except Exception as e:
            logger.error("Error parsing grading criteria response: %s", e)
            return None
