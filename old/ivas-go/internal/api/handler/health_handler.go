package handler

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/ivas/internal/infrastructure/database"
	"github.com/ivas/pkg/response"
	"gorm.io/gorm"
)

// HealthHandler handles health check endpoints
type HealthHandler struct {
	db *gorm.DB
}

// NewHealthHandler creates a new health handler
func NewHealthHandler(db *gorm.DB) *HealthHandler {
	return &HealthHandler{db: db}
}

// HealthResponse represents the health check response
type HealthResponse struct {
	Status   string            `json:"status"`
	Services map[string]string `json:"services"`
}

// Health godoc
// @Summary Health check
// @Description Check if the API is healthy
// @Tags Health
// @Produce json
// @Success 200 {object} response.Response{data=HealthResponse}
// @Failure 503 {object} response.Response
// @Router /health [get]
func (h *HealthHandler) Health(c *gin.Context) {
	services := make(map[string]string)
	allHealthy := true

	// Check database
	if err := database.HealthCheck(h.db); err != nil {
		services["database"] = "unhealthy"
		allHealthy = false
	} else {
		services["database"] = "healthy"
	}

	status := "healthy"
	httpStatus := http.StatusOK

	if !allHealthy {
		status = "unhealthy"
		httpStatus = http.StatusServiceUnavailable
	}

	c.JSON(httpStatus, response.Response{
		Success: allHealthy,
		Message: status,
		Data: HealthResponse{
			Status:   status,
			Services: services,
		},
	})
}

// Ready godoc
// @Summary Readiness check
// @Description Check if the API is ready to accept requests
// @Tags Health
// @Produce json
// @Success 200 {object} response.Response
// @Failure 503 {object} response.Response
// @Router /ready [get]
func (h *HealthHandler) Ready(c *gin.Context) {
	// Check database connection
	if err := database.HealthCheck(h.db); err != nil {
		response.Error(c, http.StatusServiceUnavailable, "Service not ready", nil)
		return
	}

	response.OK(c, "Service is ready", nil)
}
