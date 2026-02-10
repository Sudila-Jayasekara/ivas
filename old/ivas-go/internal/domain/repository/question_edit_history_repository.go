package repository

import (
	"github.com/ivas/internal/domain/entity"
	"gorm.io/gorm"
)

// QuestionEditHistoryRepository handles edit history database operations
type QuestionEditHistoryRepository struct {
	db *gorm.DB
}

// NewQuestionEditHistoryRepository creates a new edit history repository
func NewQuestionEditHistoryRepository(db *gorm.DB) *QuestionEditHistoryRepository {
	return &QuestionEditHistoryRepository{db: db}
}

// Create creates a new edit history entry
func (r *QuestionEditHistoryRepository) Create(history *entity.QuestionEditHistory) error {
	return r.db.Create(history).Error
}

// FindByQuestionID finds all edit history for a question
func (r *QuestionEditHistoryRepository) FindByQuestionID(questionID string) ([]entity.QuestionEditHistory, error) {
	var history []entity.QuestionEditHistory
	err := r.db.Where("question_id = ?", questionID).Order("timestamp DESC").Find(&history).Error
	return history, err
}
