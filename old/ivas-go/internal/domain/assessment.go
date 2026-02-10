package domain

import "time"

// Assessment Session table
type AssessmentSession struct {
	ID            string     `gorm:"primaryKey" json:"id"`
	StudentID     string     `gorm:"index" json:"student_id"`
	AssignmentID  string     `gorm:"index" json:"assignment_id"`
	TaskID        string     `json:"task_id"`
	Status        string     `json:"status"`         // "in_progress", "completed", "abandoned"
	TriggerReason string     `json:"trigger_reason"` // "task_completion", "milestone", "confusion_detected"
	StartedAt     time.Time  `json:"started_at"`
	CompletedAt   *time.Time `json:"completed_at"`
	CodeContext   string     `gorm:"type:text" json:"code_context"` // The code that triggered this
}

// Assessment Question Instance (questions asked in a session)
type AssessmentQuestionInstance struct {
	ID             string    `gorm:"primaryKey" json:"id"`
	SessionID      string    `gorm:"index" json:"session_id"`
	QuestionID     string    `gorm:"index" json:"question_id"` // Links to Question table
	SequenceNumber int       `json:"sequence_number"`          // Order in which question was asked
	AskedAt        time.Time `json:"asked_at"`
	Competency     string    `json:"competency"`
	Difficulty     int       `json:"difficulty"`
}

// Student Response table
type StudentResponse struct {
	ID                  string    `gorm:"primaryKey" json:"id"`
	QuestionInstanceID  string    `gorm:"index" json:"question_instance_id"`
	SessionID           string    `gorm:"index" json:"session_id"`
	StudentID           string    `gorm:"index" json:"student_id"`
	ResponseText        string    `gorm:"type:text" json:"response_text"`
	ResponseType        string    `json:"response_type"`                    // "text", "voice" (future)
	TranscriptText      string    `gorm:"type:text" json:"transcript_text"` // For voice responses
	SubmittedAt         time.Time `json:"submitted_at"`
	ResponseTimeSeconds int       `json:"response_time_seconds"` // Time taken to answer
}

// Competency Assessment Link (track which competency each response addresses)
type ResponseCompetencyLink struct {
	ID         string `gorm:"primaryKey" json:"id"`
	ResponseID string `gorm:"index" json:"response_id"`
	Competency string `gorm:"index" json:"competency"`
	QuestionID string `json:"question_id"`
}
