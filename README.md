# IVAS – Intelligent Viva Assessment System

Unified Python backend (FastAPI + PostgreSQL + Ollama).

## Quick Start

```bash
# 1. Start PostgreSQL
docker compose up -d postgres

# 2. Ensure Ollama is running
ollama serve

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the server
python main.py
```

The API will be available at `http://localhost:8080`.

Docs at `http://localhost:8080/docs`.

## Project Structure

```
ivas/
├── main.py                     # Entry point
├── app/
│   ├── config.py               # Settings (env vars)
│   ├── database.py             # Async SQLAlchemy engine
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── assessment.py
│   │   └── question.py
│   ├── schemas/                # Pydantic request/response schemas
│   │   ├── assessment.py
│   │   ├── common.py
│   │   ├── mock.py
│   │   └── question.py
│   ├── repositories/           # Data access layer
│   │   ├── question_repository.py
│   │   ├── rubric_repository.py
│   │   └── edit_history_repository.py
│   ├── services/               # Business logic
│   │   ├── assessment_service.py
│   │   ├── question_service.py
│   │   └── question_generator.py  # Ollama AI
│   ├── api/
│   │   ├── deps.py             # Dependency injection
│   │   └── routes/
│   │       ├── health.py
│   │       ├── mock.py
│   │       ├── questions.py
│   │       ├── assessments.py
│   │       ├── students.py
│   │       └── instructors.py
│   └── middleware/
│       └── request_logger.py
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── requirements.txt
└── pyproject.toml
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (DB + Ollama) |
| GET | `/ready` | Readiness check |
| GET | `/mock/*` | Mock data (assignments, students, etc.) |
| POST | `/api/v1/assignments/{id}/generate-questions` | Generate AI questions |
| GET | `/api/v1/assignments/{id}/questions` | List questions |
| GET | `/api/v1/questions/{id}` | Get question |
| PATCH | `/api/v1/questions/{id}` | Update question |
| DELETE | `/api/v1/questions/{id}` | Archive question |
| PUT | `/api/v1/questions/{id}/approve` | Approve question |
| PUT | `/api/v1/questions/{id}/type` | Set question type |
| GET | `/api/v1/questions/{id}/history` | Edit history |
| POST | `/api/v1/assessments/trigger` | Start assessment |
| GET | `/api/v1/assessments/sessions/{id}` | Get session |
| POST | `/api/v1/assessments/sessions/{id}/respond` | Submit answer |
| GET | `/api/v1/assessments/sessions/{id}/transcript` | Transcript |
| PUT | `/api/v1/assessments/sessions/{id}/abandon` | Abandon session |
| GET | `/api/v1/students/{id}/sessions` | Student sessions |
| GET | `/api/v1/instructors/{id}/assessments` | Instructor view |

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed. All settings are loaded via `pydantic-settings`.
