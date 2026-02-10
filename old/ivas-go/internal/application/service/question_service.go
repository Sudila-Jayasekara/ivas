package service

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"time"

	"github.com/ivas/internal/domain/entity"
	"github.com/ivas/internal/domain/repository"
	"github.com/ivas/internal/infrastructure/client"
	"github.com/lib/pq"
)

// QuestionService handles question business logic
type QuestionService struct {
	questionRepo    *repository.QuestionRepository
	rubricRepo      *repository.RubricRepository
	editHistoryRepo *repository.QuestionEditHistoryRepository
	aiClient        *client.AIServiceClient
}

// NewQuestionService creates a new question service
func NewQuestionService(
	questionRepo *repository.QuestionRepository,
	rubricRepo *repository.RubricRepository,
	editHistoryRepo *repository.QuestionEditHistoryRepository,
	aiClient *client.AIServiceClient,
) *QuestionService {
	return &QuestionService{
		questionRepo:    questionRepo,
		rubricRepo:      rubricRepo,
		editHistoryRepo: editHistoryRepo,
		aiClient:        aiClient,
	}
}

// GenerateQuestionsInput represents input for question generation
type GenerateQuestionsInput struct {
	AssignmentID              string
	Title                     string
	Competencies              []string
	LearningObjectives        []string
	DifficultyMin             int
	DifficultyMax             int
	NumQuestionsPerCompetency int
	ProgrammingLanguage       string
}

// GenerateQuestionsOutput represents output from question generation
type GenerateQuestionsOutput struct {
	QuestionIDs    []string
	TotalGenerated int
}

// GenerateQuestions generates questions using AI and stores them
func (s *QuestionService) GenerateQuestions(input GenerateQuestionsInput) (*GenerateQuestionsOutput, error) {
	slog.Info("Starting question generation",
		"assignment_id", input.AssignmentID,
		"competencies", input.Competencies,
	)

	// Call AI service
	aiReq := client.GenerateQuestionsRequest{
		AssignmentID: input.AssignmentID,
		Title:        input.Title,
		Competencies: input.Competencies,
		DifficultyRange: client.DifficultyRange{
			Min: input.DifficultyMin,
			Max: input.DifficultyMax,
		},
		LearningObjectives:        input.LearningObjectives,
		NumQuestionsPerCompetency: input.NumQuestionsPerCompetency,
		ProgrammingLanguage:       input.ProgrammingLanguage,
	}

	aiResp, err := s.aiClient.GenerateQuestions(aiReq)
	if err != nil {
		return nil, fmt.Errorf("AI service failed: %w", err)
	}

	// Store questions in database
	var questionIDs []string
	for _, q := range aiResp.Questions {
		question := &entity.Question{
			AssignmentID: input.AssignmentID,
			QuestionText: q.QuestionText,
			Competency:   q.Competency,
			Difficulty:   q.Difficulty,
			Source:       entity.QuestionSourceAIGenerated,
			Status:       entity.QuestionStatusDraft,
			QuestionType: entity.QuestionTypeRequired,
		}

		if err := s.questionRepo.Create(question); err != nil {
			slog.Error("Failed to create question", "error", err)
			continue
		}

		// Store rubric
		gradingCriteriaJSON, _ := json.Marshal(q.Rubric.GradingCriteria)
		rubric := &entity.Rubric{
			QuestionID:          question.ID,
			ExpectedKeyConcepts: pq.StringArray(q.ExpectedKeyConcepts),
			GradingCriteria:     string(gradingCriteriaJSON),
			MaxPoints:           q.Rubric.MaxPoints,
		}

		if err := s.rubricRepo.Create(rubric); err != nil {
			slog.Error("Failed to create rubric", "error", err, "question_id", question.ID)
		}

		questionIDs = append(questionIDs, question.ID)
	}

	slog.Info("Questions stored in database",
		"assignment_id", input.AssignmentID,
		"total_stored", len(questionIDs),
	)

	return &GenerateQuestionsOutput{
		QuestionIDs:    questionIDs,
		TotalGenerated: len(questionIDs),
	}, nil
}

// GetQuestionsByAssignment gets all questions for an assignment
func (s *QuestionService) GetQuestionsByAssignment(
	assignmentID string,
	status *string,
	competency *string,
	questionType *string,
) ([]entity.Question, error) {
	return s.questionRepo.FindByAssignmentIDWithFilters(assignmentID, status, competency, questionType)
}

// GetQuestion gets a single question by ID
func (s *QuestionService) GetQuestion(id string) (*entity.Question, error) {
	return s.questionRepo.FindByID(id)
}

// UpdateQuestionInput represents input for updating a question
type UpdateQuestionInput struct {
	QuestionID   string
	QuestionText *string
	Competency   *string
	Difficulty   *int
	ModifiedBy   string
}

// UpdateQuestion updates a question and logs the edit
func (s *QuestionService) UpdateQuestion(input UpdateQuestionInput) (*entity.Question, error) {
	question, err := s.questionRepo.FindByID(input.QuestionID)
	if err != nil {
		return nil, fmt.Errorf("question not found: %w", err)
	}

	// Track changes for history
	changes := make(map[string]interface{})

	if input.QuestionText != nil && *input.QuestionText != question.QuestionText {
		changes["question_text"] = map[string]string{
			"old": question.QuestionText,
			"new": *input.QuestionText,
		}
		question.QuestionText = *input.QuestionText
	}

	if input.Competency != nil && *input.Competency != question.Competency {
		changes["competency"] = map[string]string{
			"old": question.Competency,
			"new": *input.Competency,
		}
		question.Competency = *input.Competency
	}

	if input.Difficulty != nil && *input.Difficulty != question.Difficulty {
		changes["difficulty"] = map[string]int{
			"old": question.Difficulty,
			"new": *input.Difficulty,
		}
		question.Difficulty = *input.Difficulty
	}

	question.LastModifiedBy = input.ModifiedBy

	// Save question
	if err := s.questionRepo.Update(question); err != nil {
		return nil, fmt.Errorf("failed to update question: %w", err)
	}

	// Log edit history
	if len(changes) > 0 {
		changesJSON, _ := json.Marshal(changes)
		history := &entity.QuestionEditHistory{
			QuestionID:  question.ID,
			EditedBy:    input.ModifiedBy,
			ChangesJSON: string(changesJSON),
			Timestamp:   time.Now(),
		}
		if err := s.editHistoryRepo.Create(history); err != nil {
			slog.Error("Failed to log edit history", "error", err)
		}
	}

	return question, nil
}

// ApproveQuestion changes question status to approved
func (s *QuestionService) ApproveQuestion(id string, approvedBy string) error {
	question, err := s.questionRepo.FindByID(id)
	if err != nil {
		return fmt.Errorf("question not found: %w", err)
	}

	question.Status = entity.QuestionStatusApproved
	question.LastModifiedBy = approvedBy

	return s.questionRepo.Update(question)
}

// SetQuestionType sets question as required or adaptive
func (s *QuestionService) SetQuestionType(id string, qType entity.QuestionType) error {
	return s.questionRepo.UpdateType(id, qType)
}

// ArchiveQuestion soft deletes a question
func (s *QuestionService) ArchiveQuestion(id string) error {
	return s.questionRepo.SoftDelete(id)
}

// GetQuestionHistory gets edit history for a question
func (s *QuestionService) GetQuestionHistory(questionID string) ([]entity.QuestionEditHistory, error) {
	return s.editHistoryRepo.FindByQuestionID(questionID)
}
