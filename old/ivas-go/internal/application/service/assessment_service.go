package service

import (
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/ivas/internal/domain"
	"github.com/ivas/internal/domain/entity"
	"gorm.io/gorm"
)

type AssessmentService struct {
	db *gorm.DB
}

func NewAssessmentService(db *gorm.DB) *AssessmentService {
	return &AssessmentService{db: db}
}

// TriggerAssessmentRequest defines the input for starting an assessment
type TriggerAssessmentRequest struct {
	StudentID    string   `json:"student_id" binding:"required"`
	AssignmentID string   `json:"assignment_id" binding:"required"`
	TaskID       string   `json:"task_id" binding:"required"`
	CodeContext  string   `json:"code_context"`
	Competencies []string `json:"competencies"`
}

// TriggerAssessmentResponse defines the output after starting an assessment
type TriggerAssessmentResponse struct {
	SessionID      string                      `json:"session_id"`
	FirstQuestion  *domain.QuestionWithContext `json:"first_question,omitempty"`
	TotalQuestions int                         `json:"total_questions"`
	Status         string                      `json:"status"`
}

// TriggerAssessment creates a new assessment session
func (s *AssessmentService) TriggerAssessment(req TriggerAssessmentRequest) (*TriggerAssessmentResponse, error) {
	// 1. Create AssessmentSession
	session := domain.AssessmentSession{
		ID:            uuid.New().String(),
		StudentID:     req.StudentID,
		AssignmentID:  req.AssignmentID,
		TaskID:        req.TaskID,
		Status:        "in_progress",
		TriggerReason: "task_completion",
		StartedAt:     time.Now(),
		CodeContext:   req.CodeContext,
	}

	if err := s.db.Create(&session).Error; err != nil {
		return nil, fmt.Errorf("failed to create assessment session: %w", err)
	}

	// 2. Select first question
	// For Phase 2, we just pick the first approved question for the assignment
	// that matches one of the competencies
	var question entity.Question
	query := s.db.Where("assignment_id = ? AND status = ?", req.AssignmentID, "approved")

	if len(req.Competencies) > 0 {
		// In a real implementation we would filter by competencies
		// query = query.Where("competencies && ?", pq.Array(req.Competencies))
		// For now simple check or just get any valid question
	}

	if err := query.Order("difficulty asc").First(&question).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			// No questions found, maybe complete session immediately or return empty
			return &TriggerAssessmentResponse{
				SessionID: session.ID,
				Status:    "completed", // No questions to ask
			}, nil
		}
		return nil, fmt.Errorf("failed to find questions: %w", err)
	}

	// 3. Create AssessmentQuestionInstance
	instance := domain.AssessmentQuestionInstance{
		ID:             uuid.New().String(),
		SessionID:      session.ID,
		QuestionID:     question.ID,
		SequenceNumber: 1,
		AskedAt:        time.Now(),
		Competency:     "", // Should come from question metadata
		Difficulty:     question.Difficulty,
	}

	if err := s.db.Create(&instance).Error; err != nil {
		return nil, fmt.Errorf("failed to create question instance: %w", err)
	}

	// 4. Return response
	firstQuestion := &domain.QuestionWithContext{
		QuestionID:         question.ID,
		QuestionInstanceID: instance.ID,
		QuestionText:       question.QuestionText,
		Competency:         "", // Fill from question
		Difficulty:         question.Difficulty,
		CodeContext:        req.CodeContext,
	}

	return &TriggerAssessmentResponse{
		SessionID:      session.ID,
		FirstQuestion:  firstQuestion,
		TotalQuestions: 1, // Placeholder
		Status:         "in_progress",
	}, nil
}

// SubmitResponseRequest defines the input for submitting an answer
type SubmitResponseRequest struct {
	SessionID          string `json:"session_id"`
	QuestionInstanceID string `json:"question_instance_id" binding:"required"`
	ResponseText       string `json:"response_text" binding:"required"`
	ResponseType       string `json:"response_type"` // "text" for now
}

// SubmitResponseResponse defines the output after submitting an answer
type SubmitResponseResponse struct {
	ResponseID   string                      `json:"response_id"`
	NextQuestion *domain.QuestionWithContext `json:"next_question,omitempty"` // nil if assessment complete
	IsComplete   bool                        `json:"is_complete"`
	Message      string                      `json:"message,omitempty"`
}

// SubmitResponse processes a student's answer and returns the next question or completion status
func (s *AssessmentService) SubmitResponse(req SubmitResponseRequest) (*SubmitResponseResponse, error) {
	// 1. Validate session exists and is "in_progress"
	var session domain.AssessmentSession
	if err := s.db.First(&session, "id = ?", req.SessionID).Error; err != nil {
		return nil, fmt.Errorf("session not found: %w", err)
	}

	if session.Status != "in_progress" {
		return nil, fmt.Errorf("session is not in progress")
	}

	// 2. Validate question instance belongs to session
	var instance domain.AssessmentQuestionInstance
	if err := s.db.First(&instance, "id = ? AND session_id = ?", req.QuestionInstanceID, req.SessionID).Error; err != nil {
		return nil, fmt.Errorf("invalid question instance: %w", err)
	}

	// 3. Store StudentResponse
	response := domain.StudentResponse{
		ID:                 uuid.New().String(),
		QuestionInstanceID: req.QuestionInstanceID,
		SessionID:          req.SessionID,
		StudentID:          session.StudentID,
		ResponseText:       req.ResponseText,
		ResponseType:       req.ResponseType,
		SubmittedAt:        time.Now(),
		// ResponseTimeSeconds: calculated from difference between now and instance.AskedAt
	}
	response.ResponseTimeSeconds = int(time.Since(instance.AskedAt).Seconds())

	if err := s.db.Create(&response).Error; err != nil {
		return nil, fmt.Errorf("failed to save response: %w", err)
	}

	// 4. Check if more questions needed
	// For Phase 2 simple logic: Ask 3 questions total
	var askedCount int64
	s.db.Model(&domain.AssessmentQuestionInstance{}).Where("session_id = ?", req.SessionID).Count(&askedCount)

	if askedCount >= 3 {
		// Mark session as completed
		now := time.Now()
		session.Status = "completed"
		session.CompletedAt = &now
		s.db.Save(&session)

		return &SubmitResponseResponse{
			ResponseID: response.ID,
			IsComplete: true,
			Message:    "Assessment completed",
		}, nil
	}

	// 5. Select next question
	// Create logic to pick next question (simplified)
	// Get questions already asked
	var askedQuestionIDs []string
	s.db.Model(&domain.AssessmentQuestionInstance{}).
		Where("session_id = ?", req.SessionID).
		Pluck("question_id", &askedQuestionIDs)

	var nextQuestion entity.Question
	err := s.db.Where("assignment_id = ? AND status = ?", session.AssignmentID, "approved").
		Where("id NOT IN ?", askedQuestionIDs).
		Order("difficulty asc").
		First(&nextQuestion).Error

	if err != nil {
		if err == gorm.ErrRecordNotFound {
			// No more questions available
			now := time.Now()
			session.Status = "completed"
			session.CompletedAt = &now
			s.db.Save(&session)

			return &SubmitResponseResponse{
				ResponseID: response.ID,
				IsComplete: true,
				Message:    "No more questions available. Assessment completed.",
			}, nil
		}
		return nil, fmt.Errorf("failed to find next question: %w", err)
	}

	// 6. Create new QuestionInstance
	newInstance := domain.AssessmentQuestionInstance{
		ID:             uuid.New().String(),
		SessionID:      session.ID,
		QuestionID:     nextQuestion.ID,
		SequenceNumber: int(askedCount) + 1,
		AskedAt:        time.Now(),
		Competency:     nextQuestion.Competency,
		Difficulty:     nextQuestion.Difficulty,
	}

	if err := s.db.Create(&newInstance).Error; err != nil {
		return nil, fmt.Errorf("failed to create next question instance: %w", err)
	}

	nextQWithContext := &domain.QuestionWithContext{
		QuestionID:         nextQuestion.ID,
		QuestionInstanceID: newInstance.ID,
		QuestionText:       nextQuestion.QuestionText,
		Competency:         nextQuestion.Competency,
		Difficulty:         nextQuestion.Difficulty,
		CodeContext:        session.CodeContext,
	}

	return &SubmitResponseResponse{
		ResponseID:   response.ID,
		NextQuestion: nextQWithContext,
		IsComplete:   false,
	}, nil
}

// ========================
// SESSION MANAGEMENT
// ========================

// SessionDetails contains full session information
type SessionDetails struct {
	Session           domain.AssessmentSession            `json:"session"`
	QuestionsAsked    []domain.AssessmentQuestionInstance `json:"questions_asked"`
	Responses         []domain.StudentResponse            `json:"responses"`
	TotalQuestions    int                                 `json:"total_questions"`
	AnsweredQuestions int                                 `json:"answered_questions"`
}

// GetSession retrieves a session with all its details
func (s *AssessmentService) GetSession(sessionID string) (*SessionDetails, error) {
	var session domain.AssessmentSession
	if err := s.db.First(&session, "id = ?", sessionID).Error; err != nil {
		return nil, fmt.Errorf("session not found: %w", err)
	}

	var questions []domain.AssessmentQuestionInstance
	s.db.Where("session_id = ?", sessionID).Order("sequence_number ASC").Find(&questions)

	var responses []domain.StudentResponse
	s.db.Where("session_id = ?", sessionID).Order("submitted_at ASC").Find(&responses)

	return &SessionDetails{
		Session:           session,
		QuestionsAsked:    questions,
		Responses:         responses,
		TotalQuestions:    len(questions),
		AnsweredQuestions: len(responses),
	}, nil
}

// StudentSessionSummary is a lightweight summary for listing sessions
type StudentSessionSummary struct {
	SessionID      string     `json:"session_id"`
	AssignmentID   string     `json:"assignment_id"`
	Status         string     `json:"status"`
	StartedAt      time.Time  `json:"started_at"`
	CompletedAt    *time.Time `json:"completed_at,omitempty"`
	QuestionsAsked int        `json:"questions_asked"`
	ResponsesGiven int        `json:"responses_given"`
}

// GetStudentSessions retrieves all assessment sessions for a student
func (s *AssessmentService) GetStudentSessions(studentID string, status *string) ([]StudentSessionSummary, error) {
	query := s.db.Model(&domain.AssessmentSession{}).Where("student_id = ?", studentID)

	if status != nil && *status != "" {
		query = query.Where("status = ?", *status)
	}

	var sessions []domain.AssessmentSession
	if err := query.Order("started_at DESC").Find(&sessions).Error; err != nil {
		return nil, fmt.Errorf("failed to fetch sessions: %w", err)
	}

	summaries := make([]StudentSessionSummary, 0, len(sessions))
	for _, sess := range sessions {
		var questionsAsked int64
		s.db.Model(&domain.AssessmentQuestionInstance{}).Where("session_id = ?", sess.ID).Count(&questionsAsked)

		var responsesGiven int64
		s.db.Model(&domain.StudentResponse{}).Where("session_id = ?", sess.ID).Count(&responsesGiven)

		summaries = append(summaries, StudentSessionSummary{
			SessionID:      sess.ID,
			AssignmentID:   sess.AssignmentID,
			Status:         sess.Status,
			StartedAt:      sess.StartedAt,
			CompletedAt:    sess.CompletedAt,
			QuestionsAsked: int(questionsAsked),
			ResponsesGiven: int(responsesGiven),
		})
	}

	return summaries, nil
}

// AbandonSession marks a session as abandoned
func (s *AssessmentService) AbandonSession(sessionID string) error {
	var session domain.AssessmentSession
	if err := s.db.First(&session, "id = ?", sessionID).Error; err != nil {
		return fmt.Errorf("session not found: %w", err)
	}

	if session.Status != "in_progress" {
		return fmt.Errorf("can only abandon in-progress sessions")
	}

	now := time.Now()
	session.Status = "abandoned"
	session.CompletedAt = &now

	return s.db.Save(&session).Error
}

// ========================
// INSTRUCTOR RETRIEVAL APIs
// ========================

// InstructorAssessmentFilter defines filters for instructor queries
type InstructorAssessmentFilter struct {
	AssignmentID *string
	StudentID    *string
	Status       *string
	StartDate    *time.Time
	EndDate      *time.Time
}

// InstructorAssessmentSummary provides assessment overview for instructors
type InstructorAssessmentSummary struct {
	SessionID      string     `json:"session_id"`
	StudentID      string     `json:"student_id"`
	AssignmentID   string     `json:"assignment_id"`
	TaskID         string     `json:"task_id"`
	Status         string     `json:"status"`
	StartedAt      time.Time  `json:"started_at"`
	CompletedAt    *time.Time `json:"completed_at,omitempty"`
	QuestionsAsked int        `json:"questions_asked"`
	ResponsesGiven int        `json:"responses_given"`
}

// GetInstructorAssessments retrieves assessments for instructor's assignments
func (s *AssessmentService) GetInstructorAssessments(assignmentIDs []string, filter InstructorAssessmentFilter) ([]InstructorAssessmentSummary, error) {
	query := s.db.Model(&domain.AssessmentSession{})

	if len(assignmentIDs) > 0 {
		query = query.Where("assignment_id IN ?", assignmentIDs)
	}

	if filter.AssignmentID != nil && *filter.AssignmentID != "" {
		query = query.Where("assignment_id = ?", *filter.AssignmentID)
	}
	if filter.StudentID != nil && *filter.StudentID != "" {
		query = query.Where("student_id = ?", *filter.StudentID)
	}
	if filter.Status != nil && *filter.Status != "" {
		query = query.Where("status = ?", *filter.Status)
	}
	if filter.StartDate != nil {
		query = query.Where("started_at >= ?", *filter.StartDate)
	}
	if filter.EndDate != nil {
		query = query.Where("started_at <= ?", *filter.EndDate)
	}

	var sessions []domain.AssessmentSession
	if err := query.Order("started_at DESC").Find(&sessions).Error; err != nil {
		return nil, fmt.Errorf("failed to fetch assessments: %w", err)
	}

	summaries := make([]InstructorAssessmentSummary, 0, len(sessions))
	for _, sess := range sessions {
		var questionsAsked int64
		s.db.Model(&domain.AssessmentQuestionInstance{}).Where("session_id = ?", sess.ID).Count(&questionsAsked)

		var responsesGiven int64
		s.db.Model(&domain.StudentResponse{}).Where("session_id = ?", sess.ID).Count(&responsesGiven)

		summaries = append(summaries, InstructorAssessmentSummary{
			SessionID:      sess.ID,
			StudentID:      sess.StudentID,
			AssignmentID:   sess.AssignmentID,
			TaskID:         sess.TaskID,
			Status:         sess.Status,
			StartedAt:      sess.StartedAt,
			CompletedAt:    sess.CompletedAt,
			QuestionsAsked: int(questionsAsked),
			ResponsesGiven: int(responsesGiven),
		})
	}

	return summaries, nil
}

// Exchange represents a single question-answer pair in a transcript
type Exchange struct {
	QuestionText  string    `json:"question_text"`
	Competency    string    `json:"competency"`
	Difficulty    int       `json:"difficulty"`
	StudentAnswer string    `json:"student_answer"`
	AskedAt       time.Time `json:"asked_at"`
	AnsweredAt    time.Time `json:"answered_at"`
	ResponseTime  int       `json:"response_time_seconds"`
}

// AssessmentTranscript provides full conversation transcript
type AssessmentTranscript struct {
	SessionID    string     `json:"session_id"`
	StudentID    string     `json:"student_id"`
	AssignmentID string     `json:"assignment_id"`
	Status       string     `json:"status"`
	StartedAt    time.Time  `json:"started_at"`
	CompletedAt  *time.Time `json:"completed_at,omitempty"`
	CodeContext  string     `json:"code_context,omitempty"`
	Exchanges    []Exchange `json:"exchanges"`
}

// GetAssessmentTranscript retrieves full conversation transcript for a session
func (s *AssessmentService) GetAssessmentTranscript(sessionID string) (*AssessmentTranscript, error) {
	var session domain.AssessmentSession
	if err := s.db.First(&session, "id = ?", sessionID).Error; err != nil {
		return nil, fmt.Errorf("session not found: %w", err)
	}

	// Get all question instances for this session
	var instances []domain.AssessmentQuestionInstance
	s.db.Where("session_id = ?", sessionID).Order("sequence_number ASC").Find(&instances)

	// Get all responses for this session
	var responses []domain.StudentResponse
	s.db.Where("session_id = ?", sessionID).Find(&responses)

	// Create a map of responses by question instance ID
	responseMap := make(map[string]domain.StudentResponse)
	for _, resp := range responses {
		responseMap[resp.QuestionInstanceID] = resp
	}

	// Build exchanges
	exchanges := make([]Exchange, 0, len(instances))
	for _, inst := range instances {
		// Get the actual question text
		var question entity.Question
		s.db.First(&question, "id = ?", inst.QuestionID)

		exchange := Exchange{
			QuestionText: question.QuestionText,
			Competency:   inst.Competency,
			Difficulty:   inst.Difficulty,
			AskedAt:      inst.AskedAt,
		}

		// Add response if exists
		if resp, ok := responseMap[inst.ID]; ok {
			exchange.StudentAnswer = resp.ResponseText
			exchange.AnsweredAt = resp.SubmittedAt
			exchange.ResponseTime = resp.ResponseTimeSeconds
		}

		exchanges = append(exchanges, exchange)
	}

	return &AssessmentTranscript{
		SessionID:    session.ID,
		StudentID:    session.StudentID,
		AssignmentID: session.AssignmentID,
		Status:       session.Status,
		StartedAt:    session.StartedAt,
		CompletedAt:  session.CompletedAt,
		CodeContext:  session.CodeContext,
		Exchanges:    exchanges,
	}, nil
}

// ========================
// ASSESSMENT FLOW CONFIG
// ========================

// AssessmentFlowConfig holds configurable assessment flow rules
type AssessmentFlowConfig struct {
	MinQuestionsPerSession int  `json:"min_questions_per_session"`
	MaxQuestionsPerSession int  `json:"max_questions_per_session"`
	RequireAllRequired     bool `json:"require_all_required"`
}

// DefaultFlowConfig returns default assessment flow configuration
func DefaultFlowConfig() AssessmentFlowConfig {
	return AssessmentFlowConfig{
		MinQuestionsPerSession: 3,
		MaxQuestionsPerSession: 5,
		RequireAllRequired:     true,
	}
}

// ShouldContinueAssessment determines if more questions should be asked
func (s *AssessmentService) ShouldContinueAssessment(sessionID string, config AssessmentFlowConfig) (bool, error) {
	var askedCount int64
	s.db.Model(&domain.AssessmentQuestionInstance{}).Where("session_id = ?", sessionID).Count(&askedCount)

	// Stop if max reached
	if int(askedCount) >= config.MaxQuestionsPerSession {
		return false, nil
	}

	// Continue if min not reached
	if int(askedCount) < config.MinQuestionsPerSession {
		return true, nil
	}

	// Check if required questions all asked (if configured)
	if config.RequireAllRequired {
		allAsked, err := s.allRequiredQuestionsAsked(sessionID)
		if err != nil {
			return false, err
		}
		if !allAsked {
			return true, nil
		}
	}

	return false, nil
}

// allRequiredQuestionsAsked checks if all required questions have been asked
func (s *AssessmentService) allRequiredQuestionsAsked(sessionID string) (bool, error) {
	// Get session to find assignment ID
	var session domain.AssessmentSession
	if err := s.db.First(&session, "id = ?", sessionID).Error; err != nil {
		return false, err
	}

	// Get all required questions for this assignment
	var requiredQuestions []entity.Question
	s.db.Where("assignment_id = ? AND status = ? AND question_type = ?",
		session.AssignmentID, "approved", "required").Find(&requiredQuestions)

	if len(requiredQuestions) == 0 {
		return true, nil
	}

	// Get asked question IDs
	var askedQuestionIDs []string
	s.db.Model(&domain.AssessmentQuestionInstance{}).
		Where("session_id = ?", sessionID).
		Pluck("question_id", &askedQuestionIDs)

	askedMap := make(map[string]bool)
	for _, id := range askedQuestionIDs {
		askedMap[id] = true
	}

	// Check if all required questions are in the asked list
	for _, q := range requiredQuestions {
		if !askedMap[q.ID] {
			return false, nil
		}
	}

	return true, nil
}

// ========================
// VALIDATION HELPERS
// ========================

// ValidateSessionOwnership verifies a student owns a session
func (s *AssessmentService) ValidateSessionOwnership(sessionID, studentID string) error {
	var session domain.AssessmentSession
	if err := s.db.First(&session, "id = ?", sessionID).Error; err != nil {
		return fmt.Errorf("session not found")
	}

	if session.StudentID != studentID {
		return fmt.Errorf("session does not belong to this student")
	}

	return nil
}

// CheckDuplicateResponse prevents answering the same question twice
func (s *AssessmentService) CheckDuplicateResponse(questionInstanceID string) error {
	var count int64
	s.db.Model(&domain.StudentResponse{}).Where("question_instance_id = ?", questionInstanceID).Count(&count)

	if count > 0 {
		return fmt.Errorf("response already submitted for this question")
	}

	return nil
}
