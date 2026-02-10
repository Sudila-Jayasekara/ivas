.PHONY: all build run test clean docker-up docker-down migrate

# Variables
APP_NAME := ivas
MAIN_PATH := ./cmd/api

# Build
all: build

build:
	@echo "Building..."
	@go build -o bin/$(APP_NAME) $(MAIN_PATH)

run:
	@echo "Running..."
	@go run $(MAIN_PATH)

# Development with hot reload (requires air: go install github.com/air-verse/air@latest)
dev:
	@air

# Testing
test:
	@echo "Running tests..."
	@go test -v ./...

test-coverage:
	@echo "Running tests with coverage..."
	@go test -v -coverprofile=coverage.out ./...
	@go tool cover -html=coverage.out -o coverage.html

# Linting (requires golangci-lint)
lint:
	@golangci-lint run ./...

# Clean
clean:
	@echo "Cleaning..."
	@rm -rf bin/
	@rm -f coverage.out coverage.html

# Docker
docker-up:
	@docker-compose up -d

docker-down:
	@docker-compose down

docker-build:
	@docker build -t $(APP_NAME) .

# Dependencies
deps:
	@echo "Installing dependencies..."
	@go mod download
	@go mod tidy

# Database migrations (for future use with migrate tool)
migrate-up:
	@echo "Running migrations..."
	@migrate -path ./migrations -database "postgresql://postgres:postgres@localhost:5432/ivas_db?sslmode=disable" up

migrate-down:
	@echo "Rolling back migrations..."
	@migrate -path ./migrations -database "postgresql://postgres:postgres@localhost:5432/ivas_db?sslmode=disable" down

# Generate swagger docs (requires swag: go install github.com/swaggo/swag/cmd/swag@latest)
swagger:
	@swag init -g $(MAIN_PATH)/main.go -o ./docs

# Help
help:
	@echo "Available commands:"
	@echo "  make build         - Build the application"
	@echo "  make run           - Run the application"
	@echo "  make dev           - Run with hot reload (requires air)"
	@echo "  make test          - Run tests"
	@echo "  make test-coverage - Run tests with coverage report"
	@echo "  make lint          - Run linter"
	@echo "  make clean         - Clean build artifacts"
	@echo "  make docker-up     - Start Docker containers"
	@echo "  make docker-down   - Stop Docker containers"
	@echo "  make deps          - Download dependencies"
