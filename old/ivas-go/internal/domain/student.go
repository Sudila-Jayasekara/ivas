package domain

// What IVAS receives from Student Progress Service
type StudentProgress struct {
	StudentID        string             `json:"student_id"`
	CourseID         string             `json:"course_id"`
	CompetencyScores map[string]float64 `json:"competency_scores"` // {"loops": 0.75, "recursion": 0.6}
	PreviousAttempts int                `json:"previous_attempts"`
}
