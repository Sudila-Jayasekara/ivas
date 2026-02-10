package router

import (
	"github.com/gin-gonic/gin"
	"github.com/ivas/internal/api/handler"
	"github.com/ivas/internal/api/middleware"
	"github.com/ivas/internal/application/service"
	"gorm.io/gorm"
)

// Config holds the router configuration
type Config struct {
	DB *gorm.DB
	// UserService service.UserService
	QuestionService   *service.QuestionService
	AssessmentService *service.AssessmentService
	Debug             bool
}

// Setup initializes and returns the Gin router with all routes
func Setup(cfg *Config) *gin.Engine {
	// Set Gin mode
	if cfg.Debug {
		gin.SetMode(gin.DebugMode)
	} else {
		gin.SetMode(gin.ReleaseMode)
	}

	// Create router
	router := gin.New()

	// Apply global middleware
	router.Use(middleware.RequestLogger())
	// router.Use(middleware.ErrorHandler())
	router.Use(middleware.CORS())
	router.Use(gin.Recovery())

	// Handle 404 and 405
	// router.NoRoute(middleware.NotFound())
	// router.NoMethod(middleware.MethodNotAllowed())

	// Initialize handlers
	// Initialize handlers
	healthHandler := handler.NewHealthHandler(cfg.DB)
	mockHandler := handler.NewMockHandler()
	questionHandler := handler.NewQuestionHandler(cfg.QuestionService)
	assessmentHandler := handler.NewAssessmentHandler(cfg.AssessmentService)

	// Health check routes (no auth required)
	router.GET("/health", healthHandler.Health)
	router.GET("/ready", healthHandler.Ready)

	// Mock routes (simulate other services for testing)
	mock := router.Group("/mock")
	{
		mock.GET("/assignments", mockHandler.ListAssignments)
		mock.GET("/assignments/:id", mockHandler.GetAssignment)
		mock.GET("/instructors", mockHandler.ListInstructors)
		mock.GET("/instructors/:id", mockHandler.GetInstructor)
		mock.GET("/courses", mockHandler.ListCourses)
		mock.GET("/courses/:id", mockHandler.GetCourse)
		mock.GET("/students", mockHandler.ListStudents)
		mock.GET("/students/:id", mockHandler.GetStudent)
		mock.GET("/lab-tasks/:taskId", mockHandler.GetLabTask)
		mock.POST("/lab-tasks/complete", mockHandler.CompleteLabTask)
		mock.GET("/students/:id/progress", mockHandler.GetStudentProgress)
	}

	// API v1 routes
	v1 := router.Group("/api/v1")
	{
		// Questions routes
		// POST /api/v1/assignments/:id/generate-questions
		v1.POST("/assignments/:id/generate-questions", questionHandler.GenerateQuestions)
		v1.GET("/assignments/:id/questions", questionHandler.GetQuestions)

		questions := v1.Group("/questions")
		{
			questions.GET("/:id", questionHandler.GetQuestion)
			questions.GET("/:id/history", questionHandler.GetQuestionHistory)
			questions.PATCH("/:id", questionHandler.UpdateQuestion)
			questions.DELETE("/:id", questionHandler.DeleteQuestion)
			questions.PUT("/:id/approve", questionHandler.ApproveQuestion)
			questions.PUT("/:id/type", questionHandler.SetQuestionType)
		}

		// Assessment routes
		assessments := v1.Group("/assessments")
		{
			assessments.POST("/trigger", assessmentHandler.TriggerAssessment)
			assessments.GET("/sessions/:sessionId", assessmentHandler.GetSession)
			assessments.POST("/sessions/:sessionId/respond", assessmentHandler.SubmitResponse)
			assessments.GET("/sessions/:sessionId/transcript", assessmentHandler.GetAssessmentTranscript)
			assessments.PUT("/sessions/:sessionId/abandon", assessmentHandler.AbandonSession)
		}

		// Student routes
		students := v1.Group("/students")
		{
			students.GET("/:studentId/sessions", assessmentHandler.GetStudentSessions)
		}

		// Instructor routes
		instructors := v1.Group("/instructors")
		{
			instructors.GET("/:instructorId/assessments", assessmentHandler.GetInstructorAssessments)
		}
	}

	return router
}
