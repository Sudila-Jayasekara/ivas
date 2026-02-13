from datetime import datetime

from fastapi import APIRouter

from app.schemas.mock import AssignmentOut, CourseOut, DifficultyRange, InstructorOut, StudentOut

router = APIRouter(prefix="/mock", tags=["mock"])

# ---------- mock data ----------

MOCK_ASSIGNMENTS: dict[str, AssignmentOut] = {
    "assign-001": AssignmentOut(
        assignment_id="assign-001",
        instructor_id="inst-001",
        course_id="course-001",
        title="Introduction to Loops",
        competencies=["loops", "iteration", "control-flow"],
        learning_objectives=[
            "Understand for loops",
            "Apply while loops",
            "Choose appropriate loop type",
        ],
        difficulty_range=DifficultyRange(min=1, max=3),
    ),
    "assign-002": AssignmentOut(
        assignment_id="assign-002",
        instructor_id="inst-001",
        course_id="course-001",
        title="Recursion Fundamentals",
        competencies=["recursion", "problem-solving", "debugging"],
        learning_objectives=[
            "Understand base cases",
            "Implement recursive solutions",
            "Debug recursive functions",
        ],
        difficulty_range=DifficultyRange(min=2, max=4),
    ),
}

MOCK_INSTRUCTORS: dict[str, InstructorOut] = {
    "inst-001": InstructorOut(id="inst-001", name="Dr. Jane Smith", email="jane.smith@university.edu"),
    "inst-002": InstructorOut(id="inst-002", name="Prof. John Doe", email="john.doe@university.edu"),
}

MOCK_STUDENTS: dict[str, StudentOut] = {
    "stud-001": StudentOut(id="stud-001", name="Alice Johnson", course_id="course-001"),
    "stud-002": StudentOut(id="stud-002", name="Bob Williams", course_id="course-001"),
    "stud-003": StudentOut(id="stud-003", name="Charlie Brown", course_id="course-002"),
}

MOCK_COURSES: dict[str, CourseOut] = {
    "course-001": CourseOut(id="course-001", name="CS101 - Introduction to Programming", programming_language="Python"),
    "course-002": CourseOut(id="course-002", name="CS201 - Data Structures", programming_language="Java"),
}


# ---------- assignments ----------

@router.get("/assignments")
async def list_assignments():
    items = list(MOCK_ASSIGNMENTS.values())
    return {"data": items, "count": len(items)}


@router.get("/assignments/{assignment_id}")
async def get_assignment(assignment_id: str):
    a = MOCK_ASSIGNMENTS.get(assignment_id)
    if not a:
        return {"error": "assignment not found", "id": assignment_id}
    return a


# ---------- instructors ----------

@router.get("/instructors")
async def list_instructors():
    items = list(MOCK_INSTRUCTORS.values())
    return {"data": items, "count": len(items)}


@router.get("/instructors/{instructor_id}")
async def get_instructor(instructor_id: str):
    i = MOCK_INSTRUCTORS.get(instructor_id)
    if not i:
        return {"error": "instructor not found", "id": instructor_id}
    return i


# ---------- courses ----------

@router.get("/courses")
async def list_courses():
    items = list(MOCK_COURSES.values())
    return {"data": items, "count": len(items)}


@router.get("/courses/{course_id}")
async def get_course(course_id: str):
    c = MOCK_COURSES.get(course_id)
    if not c:
        return {"error": "course not found", "id": course_id}
    return c


# ---------- students ----------

@router.get("/students")
async def list_students():
    items = list(MOCK_STUDENTS.values())
    return {"data": items, "count": len(items)}


@router.get("/students/{student_id}")
async def get_student(student_id: str):
    s = MOCK_STUDENTS.get(student_id)
    if not s:
        return {"error": "student not found", "id": student_id}
    return s


@router.get("/students/{student_id}/progress")
async def get_student_progress(student_id: str):
    return {
        "student_id": student_id,
        "course_id": "course-789",
        "competency_scores": {"loops": 0.8, "arrays": 0.6, "recursion": 0.2},
        "previous_attempts": 3,
    }


# ---------- lab tasks ----------

@router.get("/lab-tasks/{task_id}")
async def get_lab_task(task_id: str):
    return {
        "student_id": "student-123",
        "assignment_id": "assignment-456",
        "task_id": task_id,
        "course_id": "course-789",
        "completion_time": datetime.utcnow().isoformat(),
        "code_submitted": 'def main():\n    print("Hello")',
        "competencies": ["loops", "arrays"],
    }


@router.post("/lab-tasks/complete")
async def complete_lab_task():
    return {"status": "completed", "message": "Task completion recorded"}
