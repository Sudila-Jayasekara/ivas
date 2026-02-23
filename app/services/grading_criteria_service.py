"""
Grading Criteria Service

Business logic for generating, retrieving, and updating grading criteria.
API 1: Lecturer posts assignment text → AI extracts competencies, difficulty
       levels, marking criteria, programming language, and learning objectives.
API 2: Lecturer reviews the criteria.
API 3: Lecturer edits individual criteria rows.
"""

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

    async def generate(self, assignment_id: str, assignment_text: str) -> dict:
        """Send assignment text to AI, parse response, persist criteria rows."""
        logger.info("Generating grading criteria for assignment=%s", assignment_id)

        prompt = self._build_prompt(assignment_text)

        try:
            response_text = llm_service.generate(
                prompt=prompt,
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

        # Clear previous criteria for this assignment (regenerate)
        await self.repo.delete_by_assignment_id(assignment_id)

        criteria_ids: list[str] = []
        for item in criteria_items:
            row = GradingCriteria(
                assignment_id=assignment_id,
                competency=item.competency,
                difficulty_level=item.difficulty_level,
                level_label=item.level_label,
                level_description=item.level_description,
                marking_criteria=item.marking_criteria,
                max_points=item.max_points,
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
        return f"""You are an expert university lecturer. Analyse the following assignment text and extract grading criteria.

ASSIGNMENT TEXT:
\"\"\"
{assignment_text}
\"\"\"

From the assignment text above, you must extract:
1. The programming language used (e.g. "Python", "Java", "C++").
2. A list of learning objectives the assignment addresses.
3. A set of grading criteria covering different competencies and Bloom's taxonomy levels.

For each grading criterion provide:
- competency: the skill or knowledge area (e.g. "Data Structures", "Error Handling")
- difficulty_level: integer 1-5 (1=Remember, 2=Understand, 3=Apply, 4=Analyse, 5=Evaluate/Create)
- level_label: Bloom's taxonomy label (e.g. "Remember & Understand", "Apply", "Analyse", "Evaluate & Create")
- level_description: what this level tests in the context of the assignment
- marking_criteria: specific criteria for grading at this level
- max_points: suggested point value (integer)

OUTPUT FORMAT (JSON only, no other text):
{{
  "programming_language": "Python",
  "learning_objectives": ["objective 1", "objective 2"],
  "criteria": [
    {{
      "competency": "...",
      "difficulty_level": 1,
      "level_label": "...",
      "level_description": "...",
      "marking_criteria": "...",
      "max_points": 10
    }}
  ]
}}

Return ONLY valid JSON. Generate a comprehensive set of criteria covering all competencies and difficulty levels relevant to the assignment.""".strip()

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
            for c in raw_criteria:
                try:
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
