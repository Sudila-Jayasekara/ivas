package domain

import "time"

// What IVAS receives from Lab Activity Service
type LabTaskCompletedEvent struct {
	StudentID      string    `json:"student_id"`
	AssignmentID   string    `json:"assignment_id"`
	TaskID         string    `json:"task_id"`
	CourseID       string    `json:"course_id"`
	CompletionTime time.Time `json:"completion_time"`
	CodeSubmitted  string    `json:"code_submitted"` // The actual code student wrote
	Competencies   []string  `json:"competencies"`   // Which competencies this task covers
}
