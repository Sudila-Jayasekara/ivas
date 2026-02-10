package repository

import (
	"github.com/ivas/internal/domain/entity"
	"gorm.io/gorm"
)

// RubricRepository handles rubric database operations
type RubricRepository struct {
	db *gorm.DB
}

// NewRubricRepository creates a new rubric repository
func NewRubricRepository(db *gorm.DB) *RubricRepository {
	return &RubricRepository{db: db}
}

// Create creates a new rubric
func (r *RubricRepository) Create(rubric *entity.Rubric) error {
	return r.db.Create(rubric).Error
}

// CreateBatch creates multiple rubrics
func (r *RubricRepository) CreateBatch(rubrics []entity.Rubric) error {
	return r.db.Create(&rubrics).Error
}

// FindByQuestionID finds rubric by question ID
func (r *RubricRepository) FindByQuestionID(questionID string) (*entity.Rubric, error) {
	var rubric entity.Rubric
	err := r.db.First(&rubric, "question_id = ?", questionID).Error
	if err != nil {
		return nil, err
	}
	return &rubric, nil
}

// Update updates a rubric
func (r *RubricRepository) Update(rubric *entity.Rubric) error {
	return r.db.Save(rubric).Error
}
