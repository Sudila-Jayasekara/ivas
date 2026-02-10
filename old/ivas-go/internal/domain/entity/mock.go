package entity

// Mock data structures representing data IVAS receives from other services
// These will be replaced with actual service calls/events later

// DifficultyRange represents min/max difficulty levels
type DifficultyRange struct {
	Min int `json:"min"` // 1-5
	Max int `json:"max"` // 1-5
}

// AssignmentCreatedEvent represents data received from Assignment Service
type AssignmentCreatedEvent struct {
	AssignmentID       string          `json:"assignment_id"`
	InstructorID       string          `json:"instructor_id"`
	CourseID           string          `json:"course_id"`
	Title              string          `json:"title"`
	Competencies       []string        `json:"competencies"` // e.g., ["loops", "recursion", "debugging"]
	LearningObjectives []string        `json:"learning_objectives"`
	DifficultyRange    DifficultyRange `json:"difficulty_range"`
}

// Instructor represents data received from User Service
type Instructor struct {
	ID    string `json:"id"`
	Name  string `json:"name"`
	Email string `json:"email"`
}

// Student represents data received from User Service
type Student struct {
	ID       string `json:"id"`
	Name     string `json:"name"`
	CourseID string `json:"course_id"`
}

// Course represents data received from Course Service
type Course struct {
	ID                  string `json:"id"`
	Name                string `json:"name"`
	ProgrammingLanguage string `json:"programming_language"`
}
