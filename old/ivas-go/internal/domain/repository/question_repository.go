package repository

import (
	"github.com/ivas/internal/domain/entity"
	"gorm.io/gorm"
)

// QuestionRepository handles question database operations
type QuestionRepository struct {
	db *gorm.DB
}

// NewQuestionRepository creates a new question repository
func NewQuestionRepository(db *gorm.DB) *QuestionRepository {
	return &QuestionRepository{db: db}
}

// Create creates a new question
func (r *QuestionRepository) Create(question *entity.Question) error {
	return r.db.Create(question).Error
}

// CreateBatch creates multiple questions in a transaction
func (r *QuestionRepository) CreateBatch(questions []entity.Question) error {
	return r.db.Create(&questions).Error
}

// FindByID finds a question by ID
func (r *QuestionRepository) FindByID(id string) (*entity.Question, error) {
	var question entity.Question
	err := r.db.First(&question, "id = ?", id).Error
	if err != nil {
		return nil, err
	}
	return &question, nil
}

// FindByAssignmentID finds all questions for an assignment
func (r *QuestionRepository) FindByAssignmentID(assignmentID string) ([]entity.Question, error) {
	var questions []entity.Question
	err := r.db.Where("assignment_id = ?", assignmentID).Find(&questions).Error
	return questions, err
}

// FindByAssignmentIDWithFilters finds questions with optional filters
func (r *QuestionRepository) FindByAssignmentIDWithFilters(
	assignmentID string,
	status *string,
	competency *string,
	questionType *string,
) ([]entity.Question, error) {
	query := r.db.Where("assignment_id = ?", assignmentID)

	if status != nil && *status != "" {
		query = query.Where("status = ?", *status)
	}
	if competency != nil && *competency != "" {
		query = query.Where("competency = ?", *competency)
	}
	if questionType != nil && *questionType != "" {
		query = query.Where("question_type = ?", *questionType)
	}

	var questions []entity.Question
	err := query.Order("created_at DESC").Find(&questions).Error
	return questions, err
}

// Update updates a question
func (r *QuestionRepository) Update(question *entity.Question) error {
	return r.db.Save(question).Error
}

// UpdateStatus updates question status
func (r *QuestionRepository) UpdateStatus(id string, status entity.QuestionStatus) error {
	return r.db.Model(&entity.Question{}).Where("id = ?", id).Update("status", status).Error
}

// UpdateType updates question type
func (r *QuestionRepository) UpdateType(id string, qType entity.QuestionType) error {
	return r.db.Model(&entity.Question{}).Where("id = ?", id).Update("question_type", qType).Error
}

// SoftDelete archives a question (soft delete)
func (r *QuestionRepository) SoftDelete(id string) error {
	return r.UpdateStatus(id, entity.QuestionStatusArchived)
}
