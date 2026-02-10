package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/ivas/internal/api/router"
	"github.com/ivas/internal/application/service"
	"github.com/ivas/internal/config"
	"github.com/ivas/internal/domain/repository"
	"github.com/ivas/internal/infrastructure/client"
	"github.com/ivas/internal/infrastructure/database"
	"github.com/ivas/pkg/logger"
)

func main() {
	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		slog.Error("Failed to load configuration", "error", err)
		os.Exit(1)
	}

	// Setup logger
	logger.Setup(cfg.Log.Level, cfg.Log.Format)

	slog.Info("Starting application",
		"app", cfg.App.Name,
		"env", cfg.App.Env,
		"debug", cfg.App.Debug,
	)

	// Connect to database
	db, err := database.NewPostgresConnection(&cfg.Database, cfg.App.Debug)
	if err != nil {
		slog.Error("Failed to connect to database", "error", err)
		os.Exit(1)
	}

	// Run migrations
	if err := database.AutoMigrate(db); err != nil {
		slog.Error("Failed to run migrations", "error", err)
		os.Exit(1)
	}

	// Initialize repositories
	// userRepo := persistence.NewUserRepository(db)
	questionRepo := repository.NewQuestionRepository(db)
	rubricRepo := repository.NewRubricRepository(db)
	editHistoryRepo := repository.NewQuestionEditHistoryRepository(db)

	// Initialize clients
	aiClient := client.NewAIServiceClient(cfg.AI.URL, cfg.AI.Timeout)

	// Initialize services
	// userService := service.NewUserService(userRepo, cfg.JWT.Secret, cfg.JWT.ExpiryHours)
	questionService := service.NewQuestionService(questionRepo, rubricRepo, editHistoryRepo, aiClient)
	assessmentService := service.NewAssessmentService(db)

	// Setup router
	r := router.Setup(&router.Config{
		DB:                db,
		QuestionService:   questionService,
		AssessmentService: assessmentService,
		// UserService: input.UserService,
		Debug: cfg.App.Debug,
	})

	// Create HTTP server
	addr := fmt.Sprintf("%s:%s", cfg.Server.Host, cfg.Server.Port)
	srv := &http.Server{
		Addr:         addr,
		Handler:      r,
		ReadTimeout:  cfg.Server.ReadTimeout,
		WriteTimeout: cfg.Server.WriteTimeout,
		IdleTimeout:  cfg.Server.IdleTimeout,
	}

	// Start server in a goroutine
	go func() {
		slog.Info("Server starting", "address", addr)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			slog.Error("Server failed to start", "error", err)
			os.Exit(1)
		}
	}()

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	slog.Info("Shutting down server...")

	// Create shutdown context with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// Shutdown HTTP server
	if err := srv.Shutdown(ctx); err != nil {
		slog.Error("Server forced to shutdown", "error", err)
	}

	// Close database connection
	if err := database.Close(db); err != nil {
		slog.Error("Failed to close database connection", "error", err)
	}

	slog.Info("Server exited gracefully")
}
