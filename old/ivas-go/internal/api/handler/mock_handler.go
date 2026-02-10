package handler

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/ivas/internal/domain"
	"github.com/ivas/internal/domain/entity"
)

// MockHandler provides mock endpoints simulating other services
type MockHandler struct{}

// NewMockHandler creates a new mock handler
func NewMockHandler() *MockHandler {
	return &MockHandler{}
}

// ... existing code ...

// GetLabTask (GET /mock/lab-tasks/:taskId)
func (h *MockHandler) GetLabTask(c *gin.Context) {
	taskID := c.Param("taskId")

	// Return a static mock response
	c.JSON(http.StatusOK, domain.LabTaskCompletedEvent{
		StudentID:      "student-123",
		AssignmentID:   "assignment-456",
		TaskID:         taskID,
		CourseID:       "course-789",
		CompletionTime: time.Now(),
		CodeSubmitted:  "func main() { fmt.Println(\"Hello\") }",
		Competencies:   []string{"loops", "arrays"},
	})
}

// CompleteLabTask (POST /mock/lab-tasks/complete)
func (h *MockHandler) CompleteLabTask(c *gin.Context) {
	// Simulate receiving a webhook or trigger from the lab service
	// In a real scenario, this might forward to the assessment trigger endpoint
	// For now, we just acknowledge receipt
	c.JSON(http.StatusOK, gin.H{
		"status":  "completed",
		"message": "Task completion recorded",
	})
}

// GetStudentProgress (GET /mock/students/:id/progress)
func (h *MockHandler) GetStudentProgress(c *gin.Context) {
	studentID := c.Param("id")

	c.JSON(http.StatusOK, domain.StudentProgress{
		StudentID: studentID,
		CourseID:  "course-789",
		CompetencyScores: map[string]float64{
			"loops":     0.8,
			"arrays":    0.6,
			"recursion": 0.2,
		},
		PreviousAttempts: 3,
	})
}

// ListStudents returns all mock students
// GET /mock/students
func (h *MockHandler) ListStudents(c *gin.Context) {
	students := make([]entity.Student, 0, len(mockStudents))
	for _, s := range mockStudents {
		students = append(students, s)
	}
	c.JSON(http.StatusOK, gin.H{
		"data":  students,
		"count": len(students),
	})
}

// Hardcoded mock data for testing
var mockAssignments = map[string]entity.AssignmentCreatedEvent{
	"assign-001": {
		AssignmentID:       "assign-001",
		InstructorID:       "inst-001",
		CourseID:           "course-001",
		Title:              "Introduction to Loops",
		Competencies:       []string{"loops", "iteration", "control-flow"},
		LearningObjectives: []string{"Understand for loops", "Apply while loops", "Choose appropriate loop type"},
		DifficultyRange:    entity.DifficultyRange{Min: 1, Max: 3},
	},
	"assign-002": {
		AssignmentID:       "assign-002",
		InstructorID:       "inst-001",
		CourseID:           "course-001",
		Title:              "Recursion Fundamentals",
		Competencies:       []string{"recursion", "problem-solving", "debugging"},
		LearningObjectives: []string{"Understand base cases", "Implement recursive solutions", "Debug recursive functions"},
		DifficultyRange:    entity.DifficultyRange{Min: 2, Max: 4},
	},
}

var mockInstructors = map[string]entity.Instructor{
	"inst-001": {
		ID:    "inst-001",
		Name:  "Dr. Jane Smith",
		Email: "jane.smith@university.edu",
	},
	"inst-002": {
		ID:    "inst-002",
		Name:  "Prof. John Doe",
		Email: "john.doe@university.edu",
	},
}

var mockStudents = map[string]entity.Student{
	"stud-001": {
		ID:       "stud-001",
		Name:     "Alice Johnson",
		CourseID: "course-001",
	},
	"stud-002": {
		ID:       "stud-002",
		Name:     "Bob Williams",
		CourseID: "course-001",
	},
	"stud-003": {
		ID:       "stud-003",
		Name:     "Charlie Brown",
		CourseID: "course-002",
	},
}

var mockCourses = map[string]entity.Course{
	"course-001": {
		ID:                  "course-001",
		Name:                "CS101 - Introduction to Programming",
		ProgrammingLanguage: "Python",
	},
	"course-002": {
		ID:                  "course-002",
		Name:                "CS201 - Data Structures",
		ProgrammingLanguage: "Java",
	},
}

// GetAssignment returns mock assignment data
// GET /mock/assignments/:id
func (h *MockHandler) GetAssignment(c *gin.Context) {
	id := c.Param("id")

	assignment, exists := mockAssignments[id]
	if !exists {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "assignment not found",
			"id":    id,
		})
		return
	}

	c.JSON(http.StatusOK, assignment)
}

// GetInstructor returns mock instructor data
// GET /mock/instructors/:id
func (h *MockHandler) GetInstructor(c *gin.Context) {
	id := c.Param("id")

	instructor, exists := mockInstructors[id]
	if !exists {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "instructor not found",
			"id":    id,
		})
		return
	}

	c.JSON(http.StatusOK, instructor)
}

// GetCourse returns mock course data
// GET /mock/courses/:id
func (h *MockHandler) GetCourse(c *gin.Context) {
	id := c.Param("id")

	course, exists := mockCourses[id]
	if !exists {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "course not found",
			"id":    id,
		})
		return
	}

	c.JSON(http.StatusOK, course)
}

// ListAssignments returns all mock assignments
// GET /mock/assignments
func (h *MockHandler) ListAssignments(c *gin.Context) {
	assignments := make([]entity.AssignmentCreatedEvent, 0, len(mockAssignments))
	for _, a := range mockAssignments {
		assignments = append(assignments, a)
	}
	c.JSON(http.StatusOK, gin.H{
		"data":  assignments,
		"count": len(assignments),
	})
}

// ListInstructors returns all mock instructors
// GET /mock/instructors
func (h *MockHandler) ListInstructors(c *gin.Context) {
	instructors := make([]entity.Instructor, 0, len(mockInstructors))
	for _, i := range mockInstructors {
		instructors = append(instructors, i)
	}
	c.JSON(http.StatusOK, gin.H{
		"data":  instructors,
		"count": len(instructors),
	})
}

// ListCourses returns all mock courses
// GET /mock/courses
func (h *MockHandler) ListCourses(c *gin.Context) {
	courses := make([]entity.Course, 0, len(mockCourses))
	for _, course := range mockCourses {
		courses = append(courses, course)
	}
	c.JSON(http.StatusOK, gin.H{
		"data":  courses,
		"count": len(courses),
	})
}

// GetStudent returns mock student data
// GET /mock/students/:id
func (h *MockHandler) GetStudent(c *gin.Context) {
	id := c.Param("id")

	student, exists := mockStudents[id]
	if !exists {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "student not found",
			"id":    id,
		})
		return
	}

	c.JSON(http.StatusOK, student)
}
