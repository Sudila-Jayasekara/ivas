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

    async def generate(self, assignment_id: str, assignment_text: str, replace_existing: bool = False, *, num_criteria: int | None = None) -> dict:
        """Send assignment text to AI, parse response, persist criteria rows."""
        logger.info("Generating grading criteria for assignment=%s (replace=%s, num_criteria=%s)", assignment_id, replace_existing, num_criteria)

        prompt = self._build_prompt(assignment_text, num_criteria=num_criteria)

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
    def _build_prompt(assignment_text: str, *, num_criteria: int | None = None) -> str:
        # Build the criteria count instruction dynamically
        if num_criteria is not None:
            count_instruction = f"""Generate EXACTLY {num_criteria} criteria. You MUST produce exactly {num_criteria} — no more, no less.
Each criterion must target a DIFFERENT technical competency from the assignment.
Map each criterion to a different Bloom's level (use levels 1-5 as needed; if {num_criteria} < 5, pick the most relevant levels; if {num_criteria} > 5, you may reuse levels for different competencies)."""
        else:
            count_instruction = """Decide HOW MANY criteria to generate based on the assignment's complexity and the number of distinct technical competencies it covers.
- Simple assignments (1-2 concepts): generate 3 criteria
- Medium assignments (3-4 concepts): generate 4-5 criteria
- Complex assignments (5+ concepts): generate 5-6 criteria
You MUST cover ALL key technical competencies in the assignment — do not leave any out.
Map each criterion to a Bloom's level (1-5). Use as many different levels as appropriate."""

        return f"""You are an expert university lecturer designing an ORAL VIVA assessment for BEGINNER students.
The students will answer questions by SPEAKING into a microphone (speech-to-text).

Analyse the following assignment text and produce grading criteria that:
- Can ONLY be assessed through spoken conversation
- Are appropriate for BEGINNER-level students
- Lead to SHORT, SIMPLE questions answerable in 1-3 spoken sentences
- Do NOT require reciting code syntax, writing code, or giving long technical explanations

ASSIGNMENT TEXT:
\"\"\"
{assignment_text}
\"\"\"

From the assignment text above you must extract:
1. The programming language used (e.g. "Python", "Java", "C++").
2. A list of learning objectives the assignment addresses.
3. A set of oral-viva grading criteria covering different competencies and Bloom's taxonomy levels.

Each criterion must be designed so an assessor can probe student understanding purely through
simple verbal questions. Students are BEGINNERS answering by VOICE — keep everything simple.

═══════════════════════════════════════════════════════════════
EXTRACT TECHNICAL COMPETENCIES — NOT DOMAIN KNOWLEDGE
═══════════════════════════════════════════════════════════════

The assignment uses a SCENARIO (e.g. mountain heights, student grades, library books)
as a vehicle for teaching PROGRAMMING CONCEPTS. Your job is to identify the
TECHNICAL/PROGRAMMING competencies the assignment teaches — NOT domain knowledge.

The competency field MUST name a TECHNICAL PROGRAMMING SKILL, not the scenario.

GOOD competencies (technical):
- "Using arrays to store multiple values"
- "Sorting data to find specific values"
- "Reading input from the user"
- "Comparing values to find the largest"
- "Formatting program output"

BAD competencies (domain-specific — NEVER do this):
- "Purpose of storing mountain heights"      ← about mountains, not programming
- "Understanding data organisation"          ← too vague, not technical
- "Analysing the need for ordering"          ← about the problem, not the skill
- "Evaluating output clarity"               ← too abstract

Questions CAN use the assignment's scenario for context (e.g. "In your mountain
program, why did you use an array?"), but the COMPETENCY being tested must always
be a technical programming concept (e.g. "Using arrays to store multiple values").

═══════════════════════════════════════════════════════════════
VOICE-FIRST DESIGN — CRITICAL CONSTRAINTS
═══════════════════════════════════════════════════════════════

- Students answer by SPEAKING (speech-to-text may garble technical terms)
- Every question derived from these criteria must be answerable in 1-3 SHORT sentences
- Do NOT create criteria that require students to recite exact code syntax
- Do NOT create criteria requiring long multi-step explanations
- PREFER criteria that test conceptual understanding over syntax knowledge
- Each criterion should lead to ONE focused question, not multi-part questions
- Think: "Can a beginner explain this in 15 seconds of speaking?"

═══════════════════════════════════════════════════════════════
CONCEPTUAL UNDERSTANDING — NO SYNTAX RECALL
═══════════════════════════════════════════════════════════════

Competencies must test UNDERSTANDING of programming concepts, NOT recall of:
- Language keywords (int, float, void, etc.)
- Syntax rules (semicolons, brackets, etc.)
- Data type names or function signatures
- Method names or API details
- Domain facts (mountain heights, student scores, etc.)

GOOD: competency = "Using arrays to store multiple values"
      question = "Your program stores 10 heights — why use an array instead of 10 separate variables?"
BAD:  competency = "Purpose of storing mountain heights"
      question = "Why do programs need input from users?"

The GOOD question is specific to what the student DID. The BAD question is generic philosophy.

═══════════════════════════════════════════════════════════════
BLOOM'S TAXONOMY — MANDATORY RULES (follow these EXACTLY)
═══════════════════════════════════════════════════════════════

Map each criterion to ONE of the following Bloom's levels.
Use the EXACT difficulty_level integer AND the EXACT level_label string shown below.

┌─────────────────┬────────────────────┬──────────────────────────────────────────────────────────────────┐
│ difficulty_level │ level_label        │ Permitted action verbs & what to assess                         │
├─────────────────┼────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 1               │ "Remember"         │ DEFINE, NAME, RECALL, STATE                                     │
│                 │                    │ Student recalls a SPECIFIC fact about their program.             │
│                 │                    │ Example Q: "In your program, where do the 10 numbers go?"        │
│                 │                    │ Example Q: "How many values does your program read?"             │
├─────────────────┼────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 2               │ "Understand"       │ EXPLAIN, DESCRIBE, SUMMARISE                                    │
│                 │                    │ Student explains a specific decision in their program.           │
│                 │                    │ Example Q: "Why store all 10 heights instead of one at a time?"  │
│                 │                    │ Example Q: "After sorting, why are the largest values at the end?"│
├─────────────────┼────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 3               │ "Apply"            │ DEMONSTRATE (verbally), SOLVE, USE                              │
│                 │                    │ Student describes how a part of their program works.             │
│                 │                    │ Example Q: "Walk me through how your program finds the top 3."   │
│                 │                    │ Example Q: "What would happen if someone entered a negative number?"│
├─────────────────┼────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 4               │ "Analyse"          │ COMPARE, DIFFERENTIATE, EXPLAIN WHY                             │
│                 │                    │ Student compares approaches or identifies trade-offs.            │
│                 │                    │ Example Q: "Could you find the top 3 without sorting?"           │
│                 │                    │ Example Q: "What's different about sorting all 10 vs picking top 3?"│
├─────────────────┼────────────────────┼──────────────────────────────────────────────────────────────────┤
│ 5               │ "Evaluate & Create"│ EVALUATE, JUSTIFY, SUGGEST                                     │
│                 │                    │ Student critiques or proposes improvements.                      │
│                 │                    │ Example Q: "If the task asked for top 5 instead of 3, what changes?"│
│                 │                    │ Example Q: "What breaks if two mountains have the same height?"  │
└─────────────────┴────────────────────┴──────────────────────────────────────────────────────────────────┘

IMPORTANT CONSTRAINTS:
- {count_instruction}
- Every criterion's level_description must contain 2-3 example VERBAL QUESTIONS that are SHORT (under 25 words each).
- The competency MUST be a TECHNICAL PROGRAMMING SKILL — never a domain-specific concept.
- Questions MAY reference the assignment's scenario for familiarity, but the skill tested must be technical.
- The marking_criteria must describe what the assessor LISTENS FOR — keep it beginner-appropriate.
- Each criterion must target a DIFFERENT technical competency from the assignment.
- Every criterion must be assessable through 1-2 simple spoken sentences from the student.

For each grading criterion provide:
- competency: the skill or knowledge area being probed (keep it simple and focused)
- difficulty_level: integer 1-5 as per the table above
- level_label: EXACT string from the table above
- level_description: 2-3 example SHORT VERBAL QUESTIONS (under 25 words each) using the correct Bloom's verbs
- marking_criteria: specific observable indicators the assessor LISTENS FOR in a short spoken answer

NOTE: All questions are scored out of a FIXED 10 points. Do NOT include max_points in criteria.

OUTPUT FORMAT (JSON only, no other text):
{{{{
  "programming_language": "C++",
  "learning_objectives": ["objective 1", "objective 2"],
  "criteria": [
    {{{{
      "competency": "...",
      "difficulty_level": 2,
      "level_label": "Understand",
      "level_description": "Explain what ... / Describe why ...",
      "marking_criteria": "Full marks: student clearly explains... Partial: mentions but cannot elaborate... No marks: cannot answer."
    }}}}
  ]
}}}}

Return ONLY valid JSON. Cover ALL key technical competencies from the assignment.""".strip()

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

            # Enforce exactly one criterion per Bloom's level (5 total).
            # If LLM generated duplicates for a level, keep only the first.
            seen_levels: set[int] = set()
            deduped: list[GradingCriteriaAI] = []
            for c in criteria:
                if c.difficulty_level not in seen_levels:
                    seen_levels.add(c.difficulty_level)
                    deduped.append(c)
            criteria = deduped

            if len(criteria) != 5:
                logger.warning(
                    "Expected 5 criteria (one per Bloom's level), got %d (levels: %s)",
                    len(criteria),
                    sorted(seen_levels),
                )

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
