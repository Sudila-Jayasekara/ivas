.PHONY: run dev docker-up docker-down install lint clean

# Run the server
run:
	python main.py

# Run with auto-reload
dev:
	uvicorn main:app --host 0.0.0.0 --port 8080 --reload

# Install dependencies
install:
	pip install -r requirements.txt

# Install dev dependencies
install-dev:
	pip install -r requirements.txt
	pip install pytest pytest-asyncio httpx

# Docker
docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-build:
	docker build -t ivas .

# Lint
lint:
	ruff check .

# Clean
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Help
help:
	@echo "Available commands:"
	@echo "  make run          - Run the application"
	@echo "  make dev          - Run with hot reload"
	@echo "  make install      - Install dependencies"
	@echo "  make install-dev  - Install dev dependencies"
	@echo "  make docker-up    - Start Docker containers (postgres, pgadmin)"
	@echo "  make docker-down  - Stop Docker containers"
	@echo "  make docker-build - Build Docker image"
	@echo "  make lint         - Run linter"
	@echo "  make clean        - Clean __pycache__"
