package middleware

// import (
// 	"strings"

// 	"github.com/gin-gonic/gin"
// 	"github.com/ivas/internal/application/service"
// 	"github.com/ivas/pkg/response"
// )

// // Auth is JWT authentication middleware
// func Auth(userService service.UserService) gin.HandlerFunc {
// 	return func(c *gin.Context) {
// 		// Get authorization header
// 		authHeader := c.GetHeader("Authorization")
// 		if authHeader == "" {
// 			response.Unauthorized(c, "Authorization header is required")
// 			c.Abort()
// 			return
// 		}

// 		// Check Bearer token format
// 		parts := strings.SplitN(authHeader, " ", 2)
// 		if len(parts) != 2 || strings.ToLower(parts[0]) != "bearer" {
// 			response.Unauthorized(c, "Invalid authorization header format. Use: Bearer <token>")
// 			c.Abort()
// 			return
// 		}

// 		tokenString := parts[1]

// 		// Validate token
// 		claims, err := userService.ValidateToken(tokenString)
// 		if err != nil {
// 			response.Unauthorized(c, "Invalid or expired token")
// 			c.Abort()
// 			return
// 		}

// 		// Set user info in context for use in handlers
// 		c.Set("user_id", claims.UserID)
// 		c.Set("user_email", claims.Email)
// 		c.Set("user_role", claims.Role)

// 		c.Next()
// 	}
// }

// // RequireRole checks if the authenticated user has the required role
// func RequireRole(roles ...string) gin.HandlerFunc {
// 	return func(c *gin.Context) {
// 		userRole, exists := c.Get("user_role")
// 		if !exists {
// 			response.Unauthorized(c, "User not authenticated")
// 			c.Abort()
// 			return
// 		}

// 		roleStr, ok := userRole.(string)
// 		if !ok {
// 			response.Forbidden(c, "Invalid user role")
// 			c.Abort()
// 			return
// 		}

// 		// Check if user has one of the required roles
// 		for _, role := range roles {
// 			if roleStr == role {
// 				c.Next()
// 				return
// 			}
// 		}

// 		response.Forbidden(c, "Insufficient permissions")
// 		c.Abort()
// 	}
// }
