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

ASSIGNMENT TEXT:
\"\"\"
{assignment_text}
\"\"\"

═══════════════════════════════════════════════════════════════
STEP 1 (MOST IMPORTANT): IDENTIFY THE PROGRAMMING CONSTRUCTS USED
═══════════════════════════════════════════════════════════════

Before generating ANY criteria, you MUST read the assignment and identify the
SPECIFIC PROGRAMMING CONSTRUCTS the student's code would use. Ignore the
assignment's scenario/story entirely — focus only on the CODE.

Look for constructs like:
- Loops (for, while, do-while) — why they're used, how they terminate
- Arrays / Lists — why store in a collection vs separate variables
- Conditionals (if/else, switch) — why branching is needed
- Functions / Methods — why modularize, parameters vs return values
- Classes / Structs — why group data and behavior together
- File I/O — why read/write external data
- String manipulation — how text is processed
- Nested structures — why loops inside loops, arrays of arrays, etc.
- Error handling — why validate input, what happens on bad data

The CRITERIA you generate must test whether the student understands THESE
PROGRAMMING CONSTRUCTS — not the assignment's scenario, story, or domain.

═══════════════════════════════════════════════════════════════
STEP 2: BUILD COMPETENCIES AROUND THE PROGRAMMING CONSTRUCTS
═══════════════════════════════════════════════════════════════

Each competency MUST name a SPECIFIC PROGRAMMING CONSTRUCT (e.g. "for loops",
"arrays", "if-else branching", "functions with parameters").

Ask yourself: "If I changed the assignment scenario but kept the same code
constructs, would this competency still apply?" If yes → good. If no → rewrite.

GOOD competencies (name specific constructs):
- "Understanding why a for loop is used instead of writing repetitive code"
- "Understanding why data is stored in an array instead of separate variables"
- "Understanding how if-else conditions control which code path executes"
- "Understanding why code is split into functions with parameters and return values"
- "Understanding how nested loops process multi-dimensional data"
- "Understanding why input validation prevents runtime errors"

BAD competencies (vague or scenario-focused — NEVER generate these):
- "Purpose of counting balls in the game" (scenario-specific)
- "Understanding how student grades are stored" (scenario-specific)
- "Explaining the calculation logic" (too vague, no construct named)
- "Understanding data organization" (too vague, no construct named)
- "Performing the sorting operation" (describes task, not concept)

═══════════════════════════════════════════════════════════════
WHAT MAKES A GOOD CRITERION — THE CONCEPT TEST
═══════════════════════════════════════════════════════════════

A good criterion checks: "Does the student understand WHY this programming concept
exists, WHEN to use it, and HOW it works?"

For technical CONTROL STRUCTURES, good criteria probe:
- Why do we need these structures instead of repetitive manual code?
- When would you use one specific structure over another available option?
- How does the structure determine its termination or continuation?
- What happens under technically invalid or edge-case conditions?

For DATA STRUCTURES, good criteria probe:
- Why store values in this specific structure instead of separate variables?
- How do you technically access or manipulate specific elements?
- What happens if technical boundaries or constraints are exceeded?

For CONDITIONAL LOGIC, good criteria probe:
- Why do programs need to make technical decisions?
- What is the difference between different types of branching logic?
- How does combining complex technical conditions work?

For MODULAR DESIGN, good criteria probe:
- Why break code into smaller modules instead of one large block?
- What is the technical difference between input parameters and output results?
- Why does a technical module need specified types or interfaces?

The questions CAN reference the assignment scenario for familiarity (e.g. "In your
program, why did you choose this specific approach?") but the CONCEPT being tested
must be the technical principle, not the scenario.

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
BLOOM'S TAXONOMY — MANDATORY RULES (follow these EXACTLY)
═══════════════════════════════════════════════════════════════

Map each criterion to ONE of the following Bloom's levels.
Use the EXACT difficulty_level integer AND the EXACT level_label string shown below.

Level 1 — "Remember":
  Student recalls a specific fact about the TECHNICAL CONCEPT used in their program.
  Example: "What technical construct did you choose for this specific task?"
  Example: "What are the technical properties of the approach you used?"

Level 2 — "Understand":
  Student explains WHY a specific technical decision was made.
  Example: "Why did you choose this technical approach instead of an alternative one?"
  Example: "Why was this specific technical structure needed for this requirement?"

Level 3 — "Apply":
  Student describes HOW a technical concept works step-by-step.
  Example: "Walk me through the technical steps that occur when this logic executes."
  Example: "What would technically change if this parameter or condition was modified?"

Level 4 — "Analyse":
  Student compares approaches or identifies trade-offs between technical choices.
  Example: "Could you solve this with a different technical method? What would be the trade-off?"
  Example: "What is the technical difference between these two potential implementation approaches?"

Level 5 — "Evaluate & Create":
  Student critiques or proposes improvements to their technical approach.
  Example: "If technical constraints changed in this specific way, how would your approach adapt?"
  Example: "What technical failure would occur if specific boundary checks were removed?"

IMPORTANT CONSTRAINTS:
- {count_instruction}
- Every criterion's level_description must contain 2-3 example VERBAL QUESTIONS that are SHORT (under 25 words each).
- The competency MUST name a TECHNICAL PROGRAMMING CONCEPT — never a domain/scenario concept.
- Questions MAY reference the assignment's scenario for familiarity, but the concept tested must be technical.
- The marking_criteria must describe what CONCEPTUAL UNDERSTANDING the assessor LISTENS FOR.
- Each criterion must target a DIFFERENT technical concept from the assignment.
- Every criterion must be assessable through 1-2 simple spoken sentences from the student.

From the assignment text you must also extract:
1. The programming language used (identify it from the assignment text).
2. A list of learning objectives — these should name TECHNICAL CONCEPTS, not scenario goals.

OUTPUT FORMAT (JSON only, no other text):
{{{{
  "programming_language": "<detected language>",
  "learning_objectives": ["objective 1", "objective 2"],
  "criteria": [
    {{{{
      "competency": "...",
      "difficulty_level": 2,
      "level_label": "Understand",
      "level_description": "Explain what ... / Describe why ...",
      "marking_criteria": "Full marks: student clearly explains the concept... Partial: mentions but cannot elaborate... No marks: cannot answer."
    }}}}
  ]
}}}}

Return ONLY valid JSON. Cover ALL key technical concepts from the assignment.""".strip()

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
