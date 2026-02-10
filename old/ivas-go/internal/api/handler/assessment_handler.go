package handler

import (
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/ivas/internal/application/service"
)

type AssessmentHandler struct {
	assessmentService *service.AssessmentService
}

func NewAssessmentHandler(assessmentService *service.AssessmentService) *AssessmentHandler {
	return &AssessmentHandler{
		assessmentService: assessmentService,
	}
}

// TriggerAssessment (POST /api/assessments/trigger)
func (h *AssessmentHandler) TriggerAssessment(c *gin.Context) {
	var req service.TriggerAssessmentRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	response, err := h.assessmentService.TriggerAssessment(req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, response)
}

// SubmitResponse (POST /api/assessments/sessions/:sessionId/respond)
func (h *AssessmentHandler) SubmitResponse(c *gin.Context) {
	sessionID := c.Param("sessionId")
	var req service.SubmitResponseRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	req.SessionID = sessionID // Set from path param

	// Check for duplicate response
	if err := h.assessmentService.CheckDuplicateResponse(req.QuestionInstanceID); err != nil {
		c.JSON(http.StatusConflict, gin.H{"error": err.Error()})
		return
	}

	response, err := h.assessmentService.SubmitResponse(req)
	if err != nil {
		if strings.Contains(err.Error(), "not found") {
			c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
			return
		}
		if strings.Contains(err.Error(), "not in progress") {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, response)
}

// ========================
// SESSION MANAGEMENT
// ========================

// GetSession (GET /api/assessments/sessions/:sessionId)
func (h *AssessmentHandler) GetSession(c *gin.Context) {
	sessionID := c.Param("sessionId")

	session, err := h.assessmentService.GetSession(sessionID)
	if err != nil {
		if strings.Contains(err.Error(), "not found") {
			c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, session)
}

// GetStudentSessions (GET /api/students/:studentId/sessions)
func (h *AssessmentHandler) GetStudentSessions(c *gin.Context) {
	studentID := c.Param("studentId")
	status := c.Query("status") // Optional filter

	var statusPtr *string
	if status != "" {
		statusPtr = &status
	}

	sessions, err := h.assessmentService.GetStudentSessions(studentID, statusPtr)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"data":  sessions,
		"count": len(sessions),
	})
}

// AbandonSession (PUT /api/assessments/sessions/:sessionId/abandon)
func (h *AssessmentHandler) AbandonSession(c *gin.Context) {
	sessionID := c.Param("sessionId")

	if err := h.assessmentService.AbandonSession(sessionID); err != nil {
		if strings.Contains(err.Error(), "not found") {
			c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
			return
		}
		if strings.Contains(err.Error(), "can only abandon") {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "Session abandoned successfully",
	})
}

// ========================
// INSTRUCTOR RETRIEVAL APIs
// ========================

// GetInstructorAssessmentsRequest defines query params for instructor assessments
type GetInstructorAssessmentsRequest struct {
	AssignmentIDs string `form:"assignment_ids"` // Comma-separated
	AssignmentID  string `form:"assignment_id"`
	StudentID     string `form:"student_id"`
	Status        string `form:"status"`
	StartDate     string `form:"start_date"` // ISO format
	EndDate       string `form:"end_date"`   // ISO format
}

// GetInstructorAssessments (GET /api/instructors/:instructorId/assessments)
func (h *AssessmentHandler) GetInstructorAssessments(c *gin.Context) {
	// instructorID := c.Param("instructorId") // Could be used for auth verification

	var req GetInstructorAssessmentsRequest
	if err := c.ShouldBindQuery(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Parse assignment IDs
	var assignmentIDs []string
	if req.AssignmentIDs != "" {
		assignmentIDs = strings.Split(req.AssignmentIDs, ",")
	}

	// Build filter
	filter := service.InstructorAssessmentFilter{}
	if req.AssignmentID != "" {
		filter.AssignmentID = &req.AssignmentID
	}
	if req.StudentID != "" {
		filter.StudentID = &req.StudentID
	}
	if req.Status != "" {
		filter.Status = &req.Status
	}
	if req.StartDate != "" {
		if t, err := time.Parse(time.RFC3339, req.StartDate); err == nil {
			filter.StartDate = &t
		}
	}
	if req.EndDate != "" {
		if t, err := time.Parse(time.RFC3339, req.EndDate); err == nil {
			filter.EndDate = &t
		}
	}

	assessments, err := h.assessmentService.GetInstructorAssessments(assignmentIDs, filter)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"data":  assessments,
		"count": len(assessments),
	})
}

// GetAssessmentTranscript (GET /api/assessments/sessions/:sessionId/transcript)
func (h *AssessmentHandler) GetAssessmentTranscript(c *gin.Context) {
	sessionID := c.Param("sessionId")

	transcript, err := h.assessmentService.GetAssessmentTranscript(sessionID)
	if err != nil {
		if strings.Contains(err.Error(), "not found") {
			c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, transcript)
}
