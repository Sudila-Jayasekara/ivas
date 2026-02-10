package middleware

// import (
// 	"errors"
// 	"log/slog"
// 	"net/http"
// 	"runtime/debug"

// 	"github.com/gin-gonic/gin"
// 	"github.com/ivas/internal/application/service"
// 	"github.com/ivas/pkg/response"
// )

// // AppError represents a custom application error
// type AppError struct {
// 	Code    int    `json:"code"`
// 	Message string `json:"message"`
// 	Details string `json:"details,omitempty"`
// }

// // ErrorHandler is the global error handling middleware
// func ErrorHandler() gin.HandlerFunc {
// 	return func(c *gin.Context) {
// 		defer func() {
// 			if r := recover(); r != nil {
// 				slog.Error("Panic recovered",
// 					"error", r,
// 					"stack", string(debug.Stack()),
// 					"path", c.Request.URL.Path,
// 					"method", c.Request.Method,
// 				)
// 				response.InternalServerError(c, "An unexpected error occurred")
// 				c.Abort()
// 			}
// 		}()

// 		c.Next()

// 		// Handle errors after request processing
// 		if len(c.Errors) > 0 {
// 			err := c.Errors.Last().Err
// 			handleError(c, err)
// 		}
// 	}
// }

// // handleError handles specific error types and returns appropriate responses
// func handleError(c *gin.Context, err error) {
// 	switch {
// 	case errors.Is(err, service.ErrUserNotFound):
// 		response.NotFound(c, "User not found")
// 	case errors.Is(err, service.ErrEmailAlreadyExists):
// 		response.BadRequest(c, "Email already exists", nil)
// 	case errors.Is(err, service.ErrInvalidCredentials):
// 		response.Unauthorized(c, "Invalid email or password")
// 	case errors.Is(err, service.ErrInvalidToken):
// 		response.Unauthorized(c, "Invalid or expired token")
// 	default:
// 		slog.Error("Unhandled error", "error", err, "path", c.Request.URL.Path)
// 		response.InternalServerError(c, "An unexpected error occurred")
// 	}
// }

// // NotFound handles 404 errors for unknown routes
// func NotFound() gin.HandlerFunc {
// 	return func(c *gin.Context) {
// 		response.Error(c, http.StatusNotFound, "Route not found", nil)
// 	}
// }

// // MethodNotAllowed handles 405 errors
// func MethodNotAllowed() gin.HandlerFunc {
// 	return func(c *gin.Context) {
// 		response.Error(c, http.StatusMethodNotAllowed, "Method not allowed", nil)
// 	}
// }
