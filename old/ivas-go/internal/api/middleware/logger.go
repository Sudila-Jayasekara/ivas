package middleware

import (
	"log/slog"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

// RequestLogger logs HTTP requests using slog
func RequestLogger() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Generate request ID
		requestID := uuid.New().String()
		c.Set("request_id", requestID)
		c.Header("X-Request-ID", requestID)

		// Start timer
		start := time.Now()
		path := c.Request.URL.Path
		raw := c.Request.URL.RawQuery

		// Process request
		c.Next()

		// Calculate latency
		latency := time.Since(start)

		// Build query string
		if raw != "" {
			path = path + "?" + raw
		}

		// Get status code and error
		statusCode := c.Writer.Status()
		errorMessage := c.Errors.ByType(gin.ErrorTypePrivate).String()

		// Determine log level based on status code
		logAttrs := []any{
			"request_id", requestID,
			"method", c.Request.Method,
			"path", path,
			"status", statusCode,
			"latency", latency.String(),
			"latency_ms", latency.Milliseconds(),
			"client_ip", c.ClientIP(),
			"user_agent", c.Request.UserAgent(),
		}

		if errorMessage != "" {
			logAttrs = append(logAttrs, "error", errorMessage)
		}

		// Check if user is authenticated
		if userID, exists := c.Get("user_id"); exists {
			logAttrs = append(logAttrs, "user_id", userID)
		}

		switch {
		case statusCode >= 500:
			slog.Error("Server error", logAttrs...)
		case statusCode >= 400:
			slog.Warn("Client error", logAttrs...)
		default:
			slog.Info("Request completed", logAttrs...)
		}
	}
}
