package handler

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/ivas/internal/application/service"
	"github.com/ivas/internal/domain/entity"
)

// QuestionHandler handles question-related HTTP requests
type QuestionHandler struct {
	questionService *service.QuestionService
}

// NewQuestionHandler creates a new question handler
func NewQuestionHandler(questionService *service.QuestionService) *QuestionHandler {
	return &QuestionHandler{questionService: questionService}
}

// GenerateQuestionsRequest represents the request body
type GenerateQuestionsRequest struct {
	Title                     string   `json:"title" binding:"required"`
	Competencies              []string `json:"competencies" binding:"required"`
	LearningObjectives        []string `json:"learning_objectives" binding:"required"`
	DifficultyMin             int      `json:"difficulty_min" binding:"required,min=1,max=5"`
	DifficultyMax             int      `json:"difficulty_max" binding:"required,min=1,max=5"`
	NumQuestionsPerCompetency int      `json:"num_questions_per_competency"`
	ProgrammingLanguage       string   `json:"programming_language"`
}

// GenerateQuestions generates questions for an assignment
// POST /api/assignments/:id/generate-questions
func (h *QuestionHandler) GenerateQuestions(c *gin.Context) {
	assignmentID := c.Param("id")

	var req GenerateQuestionsRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Set defaults
	if req.NumQuestionsPerCompetency == 0 {
		req.NumQuestionsPerCompetency = 3
	}
	if req.ProgrammingLanguage == "" {
		req.ProgrammingLanguage = "Python"
	}

	input := service.GenerateQuestionsInput{
		AssignmentID:              assignmentID,
		Title:                     req.Title,
		Competencies:              req.Competencies,
		LearningObjectives:        req.LearningObjectives,
		DifficultyMin:             req.DifficultyMin,
		DifficultyMax:             req.DifficultyMax,
		NumQuestionsPerCompetency: req.NumQuestionsPerCompetency,
		ProgrammingLanguage:       req.ProgrammingLanguage,
	}

	output, err := h.questionService.GenerateQuestions(input)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, gin.H{
		"assignment_id":   assignmentID,
		"question_ids":    output.QuestionIDs,
		"total_generated": output.TotalGenerated,
	})
}

// GetQuestions gets all questions for an assignment
// GET /api/assignments/:id/questions
func (h *QuestionHandler) GetQuestions(c *gin.Context) {
	assignmentID := c.Param("id")

	// Optional filters
	status := c.Query("status")
	competency := c.Query("competency")
	questionType := c.Query("type")

	var statusPtr, competencyPtr, typePtr *string
	if status != "" {
		statusPtr = &status
	}
	if competency != "" {
		competencyPtr = &competency
	}
	if questionType != "" {
		typePtr = &questionType
	}

	questions, err := h.questionService.GetQuestionsByAssignment(assignmentID, statusPtr, competencyPtr, typePtr)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"data":  questions,
		"count": len(questions),
	})
}

// GetQuestion gets a single question
// GET /api/questions/:id
func (h *QuestionHandler) GetQuestion(c *gin.Context) {
	id := c.Param("id")

	question, err := h.questionService.GetQuestion(id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "question not found"})
		return
	}

	c.JSON(http.StatusOK, question)
}

// UpdateQuestionRequest represents the update request body
type UpdateQuestionRequest struct {
	QuestionText *string `json:"question_text"`
	Competency   *string `json:"competency"`
	Difficulty   *int    `json:"difficulty"`
	ModifiedBy   string  `json:"modified_by" binding:"required"`
}

// UpdateQuestion updates a question
// PATCH /api/questions/:id
func (h *QuestionHandler) UpdateQuestion(c *gin.Context) {
	id := c.Param("id")

	var req UpdateQuestionRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	input := service.UpdateQuestionInput{
		QuestionID:   id,
		QuestionText: req.QuestionText,
		Competency:   req.Competency,
		Difficulty:   req.Difficulty,
		ModifiedBy:   req.ModifiedBy,
	}

	question, err := h.questionService.UpdateQuestion(input)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, question)
}

// DeleteQuestion archives a question (soft delete)
// DELETE /api/questions/:id
func (h *QuestionHandler) DeleteQuestion(c *gin.Context) {
	id := c.Param("id")

	if err := h.questionService.ArchiveQuestion(id); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "question archived"})
}

// ApproveQuestionRequest represents the approve request body
type ApproveQuestionRequest struct {
	ApprovedBy string `json:"approved_by" binding:"required"`
}

// ApproveQuestion approves a question
// PUT /api/questions/:id/approve
func (h *QuestionHandler) ApproveQuestion(c *gin.Context) {
	id := c.Param("id")

	var req ApproveQuestionRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if err := h.questionService.ApproveQuestion(id, req.ApprovedBy); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "question approved"})
}

// SetQuestionTypeRequest represents the type update request
type SetQuestionTypeRequest struct {
	Type string `json:"type" binding:"required,oneof=required adaptive"`
}

// SetQuestionType sets question type
// PUT /api/questions/:id/type
func (h *QuestionHandler) SetQuestionType(c *gin.Context) {
	id := c.Param("id")

	var req SetQuestionTypeRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	qType := entity.QuestionType(req.Type)
	if err := h.questionService.SetQuestionType(id, qType); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "question type updated"})
}

// GetQuestionHistory gets edit history for a question
// GET /api/questions/:id/history
func (h *QuestionHandler) GetQuestionHistory(c *gin.Context) {
	id := c.Param("id")

	history, err := h.questionService.GetQuestionHistory(id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"data":  history,
		"count": len(history),
	})
}
