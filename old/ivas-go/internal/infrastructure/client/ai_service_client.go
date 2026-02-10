package client

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"time"
)

// DifficultyRange represents difficulty min/max
type DifficultyRange struct {
	Min int `json:"min"`
	Max int `json:"max"`
}

// GenerateQuestionsRequest is the request to AI service
type GenerateQuestionsRequest struct {
	AssignmentID              string          `json:"assignment_id"`
	Title                     string          `json:"title"`
	Competencies              []string        `json:"competencies"`
	DifficultyRange           DifficultyRange `json:"difficulty_range"`
	LearningObjectives        []string        `json:"learning_objectives"`
	NumQuestionsPerCompetency int             `json:"num_questions_per_competency"`
	ProgrammingLanguage       string          `json:"programming_language"`
}

// RubricResponse represents rubric from AI
type RubricResponse struct {
	ExpectedKeyConcepts []string `json:"expected_key_concepts"`
	GradingCriteria     string   `json:"grading_criteria"`
	MaxPoints           int      `json:"max_points"`
}

// GeneratedQuestion represents a question from AI
type GeneratedQuestion struct {
	QuestionText        string         `json:"question_text"`
	Competency          string         `json:"competency"`
	Difficulty          int            `json:"difficulty"`
	ExpectedKeyConcepts []string       `json:"expected_key_concepts"`
	Rubric              RubricResponse `json:"rubric"`
}

// GenerateQuestionsResponse is the response from AI service
type GenerateQuestionsResponse struct {
	AssignmentID   string              `json:"assignment_id"`
	Questions      []GeneratedQuestion `json:"questions"`
	TotalGenerated int                 `json:"total_generated"`
}

// AIServiceClient handles communication with Python AI service
type AIServiceClient struct {
	BaseURL    string
	HTTPClient *http.Client
}

// NewAIServiceClient creates a new AI service client
func NewAIServiceClient(baseURL string, timeout time.Duration) *AIServiceClient {
	return &AIServiceClient{
		BaseURL: baseURL,
		HTTPClient: &http.Client{
			Timeout: timeout,
		},
	}
}

// HealthCheck checks if AI service is available
func (c *AIServiceClient) HealthCheck() error {
	resp, err := c.HTTPClient.Get(c.BaseURL + "/health")
	if err != nil {
		return fmt.Errorf("AI service health check failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("AI service unhealthy, status: %d", resp.StatusCode)
	}
	return nil
}

// GenerateQuestions calls AI service to generate questions
func (c *AIServiceClient) GenerateQuestions(req GenerateQuestionsRequest) (*GenerateQuestionsResponse, error) {
	slog.Info("Calling AI service to generate questions",
		"assignment_id", req.AssignmentID,
		"competencies", req.Competencies,
	)

	// Marshal request
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	// Make HTTP request
	httpReq, err := http.NewRequest("POST", c.BaseURL+"/ai/generate-questions", bytes.NewBuffer(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.HTTPClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("AI service request failed: %w", err)
	}
	defer resp.Body.Close()

	// Read response
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("AI service returned error: %s, body: %s", resp.Status, string(respBody))
	}

	// Parse response
	var result GenerateQuestionsResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	slog.Info("AI service generated questions",
		"assignment_id", req.AssignmentID,
		"total_generated", result.TotalGenerated,
	)

	return &result, nil
}
