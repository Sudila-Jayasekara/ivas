from pydantic import BaseModel


class DifficultyRange(BaseModel):
    min: int
    max: int


class AssignmentOut(BaseModel):
    assignment_id: str
    instructor_id: str
    course_id: str
    title: str
    competencies: list[str]
    learning_objectives: list[str]
    difficulty_range: DifficultyRange


class InstructorOut(BaseModel):
    id: str
    name: str
    email: str


class StudentOut(BaseModel):
    id: str
    name: str
    course_id: str


class CourseOut(BaseModel):
    id: str
    name: str
    programming_language: str
