from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.grading_criteria import GradingCriteria
from app.models.question import Question
from app.schemas.mock import AssignmentOut, DifficultyRange

class AssignmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_assignments(self) -> list[AssignmentOut]:
        """
        Aggregate unique assignment_ids from grading_criteria and questions.
        For now, we group by assignment_id.
        """
        # Get unique assignment IDs from GradingCriteria
        stmt = select(GradingCriteria.assignment_id).distinct()
        result = await self.session.execute(stmt)
        assignment_ids = [r[0] for r in result.all()]

        assignments = []
        for aid in assignment_ids:
            # For each, let's aggregate some metadata
            # Competencies
            c_stmt = select(GradingCriteria.competency).where(GradingCriteria.assignment_id == aid).distinct()
            c_result = await self.session.execute(c_stmt)
            competencies = [r[0] for r in c_result.all()]

            # Learning objectives (merged)
            lo_stmt = select(GradingCriteria.learning_objectives).where(GradingCriteria.assignment_id == aid)
            lo_result = await self.session.execute(lo_stmt)
            all_lo = []
            for row in lo_result.all():
                all_lo.extend(row[0])
            unique_lo = list(set(all_lo))

            # Difficulty range
            d_stmt = select(func.min(GradingCriteria.difficulty_level), func.max(GradingCriteria.difficulty_level)).where(GradingCriteria.assignment_id == aid)
            d_result = await self.session.execute(d_stmt)
            d_min, d_max = d_result.one()

            assignments.append(AssignmentOut(
                assignment_id=aid,
                instructor_id="inst-001", # Placeholder
                course_id="course-001",    # Placeholder
                title=aid,                 # Placeholder: use ID as title for now
                competencies=competencies,
                learning_objectives=unique_lo,
                difficulty_range=DifficultyRange(min=d_min or 1, max=d_max or 5)
            ))
        
        return assignments

    async def get_assignment(self, assignment_id: str) -> AssignmentOut | None:
        """Fetch details for a specific assignment_id."""
        # Basically the same as above but for one ID
        c_stmt = select(GradingCriteria.competency).where(GradingCriteria.assignment_id == assignment_id).distinct()
        c_result = await self.session.execute(c_stmt)
        competencies = [r[0] for r in c_result.all()]
        if not competencies:
            return None

        lo_stmt = select(GradingCriteria.learning_objectives).where(GradingCriteria.assignment_id == assignment_id)
        lo_result = await self.session.execute(lo_stmt)
        all_lo = []
        for row in lo_result.all():
            all_lo.extend(row[0])
        unique_lo = list(set(all_lo))

        d_stmt = select(func.min(GradingCriteria.difficulty_level), func.max(GradingCriteria.difficulty_level)).where(GradingCriteria.assignment_id == assignment_id)
        d_result = await self.session.execute(d_stmt)
        d_min, d_max = d_result.one()

        return AssignmentOut(
            assignment_id=assignment_id,
            instructor_id="inst-001",
            course_id="course-001",
            title=assignment_id,
            competencies=competencies,
            learning_objectives=unique_lo,
            difficulty_range=DifficultyRange(min=d_min or 1, max=d_max or 5)
        )
