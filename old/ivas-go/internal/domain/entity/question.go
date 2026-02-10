package entity

import (
	"time"

	"github.com/lib/pq"
)

// QuestionSource indicates how the question was created
type QuestionSource string

const (
	QuestionSourceAIGenerated       QuestionSource = "ai_generated"
	QuestionSourceInstructorCreated QuestionSource = "instructor_created"
)

// QuestionStatus indicates the current state of the question
type QuestionStatus string

const (
	QuestionStatusDraft    QuestionStatus = "draft"
	QuestionStatusApproved QuestionStatus = "approved"
	QuestionStatusArchived QuestionStatus = "archived"
)

// QuestionType indicates if question is required or adaptive
type QuestionType string

const (
	QuestionTypeRequired QuestionType = "required"
	QuestionTypeAdaptive QuestionType = "adaptive"
)

// Question represents an assessment question
type Question struct {
	ID             string         `gorm:"primaryKey;type:uuid;default:gen_random_uuid()" json:"id"`
	AssignmentID   string         `gorm:"index;not null" json:"assignment_id"`
	QuestionText   string         `gorm:"type:text;not null" json:"question_text"`
	Competency     string         `gorm:"index;not null" json:"competency"`
	Difficulty     int            `gorm:"not null;check:difficulty >= 1 AND difficulty <= 5" json:"difficulty"`
	Source         QuestionSource `gorm:"type:varchar(50);not null" json:"source"`
	Status         QuestionStatus `gorm:"type:varchar(50);not null;default:'draft'" json:"status"`
	QuestionType   QuestionType   `gorm:"type:varchar(50);not null" json:"question_type"`
	LastModifiedBy string         `json:"last_modified_by,omitempty"`
	CreatedAt      time.Time      `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt      time.Time      `gorm:"autoUpdateTime" json:"updated_at"`
}

// Rubric contains expected answers and grading criteria for a question
type Rubric struct {
	ID                  string         `gorm:"primaryKey;type:uuid;default:gen_random_uuid()" json:"id"`
	QuestionID          string         `gorm:"index;not null" json:"question_id"`
	ExpectedKeyConcepts pq.StringArray `gorm:"type:text[]" json:"expected_key_concepts"`
	GradingCriteria     string         `gorm:"type:jsonb" json:"grading_criteria"`
	MaxPoints           int            `gorm:"not null" json:"max_points"`
	CreatedAt           time.Time      `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt           time.Time      `gorm:"autoUpdateTime" json:"updated_at"`

	// Relationship
	Question Question `gorm:"foreignKey:QuestionID" json:"-"`
}

// QuestionEditHistory tracks changes made to questions
type QuestionEditHistory struct {
	ID          string    `gorm:"primaryKey;type:uuid;default:gen_random_uuid()" json:"id"`
	QuestionID  string    `gorm:"index;not null" json:"question_id"`
	EditedBy    string    `gorm:"not null" json:"edited_by"`
	ChangesJSON string    `gorm:"type:jsonb" json:"changes_json"`
	Timestamp   time.Time `gorm:"autoCreateTime" json:"timestamp"`

	// Relationship
	Question Question `gorm:"foreignKey:QuestionID" json:"-"`
}
