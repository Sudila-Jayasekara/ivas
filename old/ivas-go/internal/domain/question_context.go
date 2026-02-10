package domain

// Enhanced question presentation with code context
type QuestionWithContext struct {
	QuestionID         string `json:"question_id"`
	QuestionInstanceID string `json:"question_instance_id"`
	QuestionText       string `json:"question_text"`
	Competency         string `json:"competency"`
	Difficulty         int    `json:"difficulty"`
	CodeContext        string `json:"code_context"` // The student's code that triggered this
	Hint               string `json:"hint,omitempty"`
}
