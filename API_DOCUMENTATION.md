# IVAS — Complete API Documentation

> **Intelligent Viva Assessment System**
> Base URL: `http://localhost:8000`
> Version: 1.0.0

---

## Table of Contents

1. [Health Check](#1-health-check)
2. [Mock Data](#2-mock-data)
3. [LLM Provider Management](#3-llm-provider-management)
4. [Grading Criteria](#4-grading-criteria)
5. [Questions](#5-questions)
6. [Assessments](#6-assessments)
7. [Students](#7-students)
8. [Instructors](#8-instructors)
9. [Voice Biometrics](#9-voice-biometrics)
10. [Voice Assessment (WebSocket)](#10-voice-assessment-websocket)

---

## 1. Health Check

### 1.1 `GET /health`

Full system health check (database + LLM provider).

**Request:** None

**Response:**
```json
{
  "success": true,
  "message": "healthy",
  "data": {
    "status": "healthy",
    "services": {
      "database": "healthy",
      "llm": "healthy",
      "llm_provider": "gemini"
    }
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | `true` if all services healthy |
| `message` | `string` | `"healthy"` or `"unhealthy"` |
| `data.status` | `string` | Overall status |
| `data.services.database` | `string` | `"healthy"` / `"unhealthy"` |
| `data.services.llm` | `string` | `"healthy"` / `"unhealthy"` |
| `data.services.llm_provider` | `string` | Active LLM provider key |

---

### 1.2 `GET /ready`

Readiness probe (database only).

**Request:** None

**Response:**
```json
{
  "success": true,
  "message": "Service is ready"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | `true` if DB is reachable |
| `message` | `string` | Ready status message |

---

## 2. Mock Data

> Prefix: `/mock`
> Static/hardcoded data for frontend testing. No database interaction.

### 2.1 `GET /mock/assignments`

List all mock assignments.

**Request:** None

**Response:**
```json
{
  "data": [
    {
      "assignment_id": "assign-001",
      "instructor_id": "inst-001",
      "course_id": "course-001",
      "title": "Introduction to Loops",
      "competencies": ["loops", "iteration", "control-flow"],
      "learning_objectives": ["Understand for loops", "Apply while loops", "Choose appropriate loop type"],
      "difficulty_range": { "min": 1, "max": 3 }
    }
  ],
  "count": 2
}
```

| Field | Type | Description |
|-------|------|-------------|
| `data[].assignment_id` | `string` | Unique assignment ID |
| `data[].instructor_id` | `string` | Assigned instructor |
| `data[].course_id` | `string` | Parent course |
| `data[].title` | `string` | Assignment title |
| `data[].competencies` | `string[]` | Competency tags |
| `data[].learning_objectives` | `string[]` | Learning objectives |
| `data[].difficulty_range.min` | `int` | Minimum difficulty |
| `data[].difficulty_range.max` | `int` | Maximum difficulty |

---

### 2.2 `GET /mock/assignments/{assignment_id}`

Get a single mock assignment.

**Path Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `assignment_id` | `string` | Yes | e.g. `assign-001` |

**Response:** Same shape as a single item from `data[]` above.

**Error (not found):**
```json
{ "error": "assignment not found", "id": "assign-999" }
```

---

### 2.3 `GET /mock/instructors`

List all mock instructors.

**Response:**
```json
{
  "data": [
    { "id": "inst-001", "name": "Dr. Jane Smith", "email": "jane.smith@university.edu" }
  ],
  "count": 2
}
```

| Field | Type | Description |
|-------|------|-------------|
| `data[].id` | `string` | Instructor ID |
| `data[].name` | `string` | Full name |
| `data[].email` | `string` | Email address |

---

### 2.4 `GET /mock/instructors/{instructor_id}`

Get a single mock instructor.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `instructor_id` | `string` | Yes |

**Response:** Single `InstructorOut` object. Error if not found.

---

### 2.5 `GET /mock/courses`

List all mock courses.

**Response:**
```json
{
  "data": [
    { "id": "course-001", "name": "CS101 - Introduction to Programming", "programming_language": "Python" }
  ],
  "count": 2
}
```

| Field | Type | Description |
|-------|------|-------------|
| `data[].id` | `string` | Course ID |
| `data[].name` | `string` | Course name |
| `data[].programming_language` | `string` | Language used in the course |

---

### 2.6 `GET /mock/courses/{course_id}`

Get a single mock course.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `course_id` | `string` | Yes |

**Response:** Single `CourseOut` object. Error if not found.

---

### 2.7 `GET /mock/students`

List all mock students.

**Response:**
```json
{
  "data": [
    { "id": "stud-001", "name": "Alice Johnson", "course_id": "course-001" }
  ],
  "count": 3
}
```

| Field | Type | Description |
|-------|------|-------------|
| `data[].id` | `string` | Student ID |
| `data[].name` | `string` | Full name |
| `data[].course_id` | `string` | Enrolled course |

---

### 2.8 `GET /mock/students/{student_id}`

Get a single mock student.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `student_id` | `string` | Yes |

**Response:** Single `StudentOut` object. Error if not found.

---

### 2.9 `GET /mock/students/{student_id}/progress`

Get mock student progress.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `student_id` | `string` | Yes |

**Response:**
```json
{
  "student_id": "stud-001",
  "course_id": "course-789",
  "competency_scores": { "loops": 0.8, "arrays": 0.6, "recursion": 0.2 },
  "previous_attempts": 3
}
```

---

## 3. LLM Provider Management

> Prefix: `/llm`

### 3.1 `GET /llm/provider`

Get the current active LLM provider.

**Request:** None

**Response:**
```json
{
  "active_provider": "gemini",
  "provider_display": "Google Gemini",
  "supported_providers": ["ollama", "gemini"]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `active_provider` | `string` | Current provider key |
| `provider_display` | `string` | Human-readable name |
| `supported_providers` | `string[]` | All available providers |

---

### 3.2 `POST /llm/provider/switch`

Hot-swap the LLM provider at runtime (no restart).

**Request Body:**
```json
{
  "provider": "gemini"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `provider` | `string` | Yes | `"ollama"` or `"gemini"` |

**Response (200):**
```json
{
  "success": true,
  "data": {
    "active_provider": "gemini",
    "provider_display": "Google Gemini",
    "supported_providers": ["ollama", "gemini"]
  }
}
```

**Error (400):** Invalid provider name.

---

### 3.3 `GET /llm/provider/health`

Check if the current LLM provider is reachable.

**Request:** None

**Response:**
```json
{
  "success": true,
  "provider": "gemini",
  "status": "healthy"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Provider is reachable |
| `provider` | `string` | Active provider key |
| `status` | `string` | `"healthy"` / `"unhealthy"` |

---

## 4. Grading Criteria

> Prefix: `/api/v1`

### 4.1 `POST /api/v1/assignments/{assignment_id}/grading-criteria/generate`

AI-generate grading criteria from assignment text.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `assignment_id` | `string` | Yes |

**Request Body:**
```json
{
  "assignment_text": "Write a Python program that implements bubble sort...",
  "replace_existing": false,
  "num_criteria": 5
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `assignment_text` | `string` | **Yes** (min 1 char) | — | The full assignment text to analyze |
| `replace_existing` | `bool` | No | `false` | If `true`, deletes all existing criteria before generating. If `false`, appends (skipping duplicates) |
| `num_criteria` | `int` \| `null` | No | `null` | Exact number of criteria to generate (2–10). If omitted, AI decides based on complexity |

**Response (201):**
```json
{
  "assignment_id": "assign-001",
  "criteria_ids": ["crit-abc-123", "crit-def-456"],
  "total_generated": 2
}
```

| Field | Type | Description |
|-------|------|-------------|
| `assignment_id` | `string` | The assignment these criteria belong to |
| `criteria_ids` | `string[]` | IDs of newly created criteria |
| `total_generated` | `int` | Number of criteria generated |

**Error (502):** LLM generation failure.

---

### 4.2 `GET /api/v1/assignments/{assignment_id}/grading-criteria`

List all grading criteria for an assignment.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `assignment_id` | `string` | Yes |

**Response:**
```json
{
  "data": [
    {
      "id": "crit-abc-123",
      "assignment_id": "assign-001",
      "competency": "loops",
      "difficulty_level": 3,
      "level_label": "Intermediate",
      "level_description": "Can implement nested loops",
      "marking_criteria": "Student demonstrates...",
      "programming_language": "Python",
      "learning_objectives": ["Understand for loops", "Apply while loops"],
      "created_at": "2026-03-01T10:00:00Z",
      "updated_at": "2026-03-01T10:00:00Z"
    }
  ],
  "count": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `data[].id` | `string` | Criterion ID |
| `data[].assignment_id` | `string` | Parent assignment |
| `data[].competency` | `string` | Competency tag |
| `data[].difficulty_level` | `int` | 1–5 |
| `data[].level_label` | `string` | e.g. "Beginner", "Intermediate" |
| `data[].level_description` | `string` | What this level means |
| `data[].marking_criteria` | `string` | Detailed marking rubric |
| `data[].programming_language` | `string` | Language context |
| `data[].learning_objectives` | `string[]` | Associated learning objectives |
| `data[].created_at` | `datetime` | Creation timestamp |
| `data[].updated_at` | `datetime` | Last update timestamp |

---

### 4.3 `PATCH /api/v1/grading-criteria/{criteria_id}`

Update a single grading criterion. All fields are optional — only send what you want to change.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `criteria_id` | `string` | Yes |

**Request Body (all optional):**
```json
{
  "competency": "recursion",
  "difficulty_level": 4,
  "level_label": "Advanced",
  "level_description": "Can implement tail recursion",
  "marking_criteria": "Updated marking description...",
  "programming_language": "Python",
  "learning_objectives": ["Understand base cases"]
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `competency` | `string` | No | — |
| `difficulty_level` | `int` | No | 1–5 |
| `level_label` | `string` | No | — |
| `level_description` | `string` | No | — |
| `marking_criteria` | `string` | No | — |
| `programming_language` | `string` | No | — |
| `learning_objectives` | `string[]` | No | — |

**Response (200):** Updated `GradingCriteriaOut` object (same shape as list item above).

**Error (400):** No fields provided.
**Error (404):** Criterion not found.

---

## 5. Questions

> Prefix: `/api/v1`

### 5.1 `POST /api/v1/assignments/{assignment_id}/questions/generate`

AI-generate viva questions from saved grading criteria.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `assignment_id` | `string` | Yes |

**Query Parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `criteria_id` | `string` | No | `null` | Generate questions for a specific criterion only |
| `assignment_text` | `string` | No | `""` | Original assignment text for context-aware generation |
| `num_questions` | `int` | No | `null` | Exact number of questions per criterion (1–5). If omitted, AI decides |

**Response (201):**
```json
{
  "assignment_id": "assign-001",
  "question_ids": ["q-abc-123", "q-def-456"],
  "total_generated": 2
}
```

| Field | Type | Description |
|-------|------|-------------|
| `assignment_id` | `string` | The assignment these questions belong to |
| `question_ids` | `string[]` | IDs of newly created questions |
| `total_generated` | `int` | Count of generated questions |

**Error (400):** No grading criteria found / invalid input.

---

### 5.2 `GET /api/v1/assignments/{assignment_id}/questions`

List questions for an assignment with optional filtering.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `assignment_id` | `string` | Yes |

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | `string` | No | Filter by status (e.g. `"active"`) |
| `competency` | `string` | No | Filter by competency tag |

**Response:**
```json
{
  "data": [
    {
      "id": "q-abc-123",
      "assignment_id": "assign-001",
      "grading_criteria_id": "crit-abc-123",
      "question_text": "Explain the difference between for and while loops.",
      "competency": "loops",
      "difficulty": 2,
      "expected_answer": "A for loop iterates over a sequence...",
      "max_points": 10,
      "status": "active",
      "created_at": "2026-03-01T10:00:00Z",
      "updated_at": "2026-03-01T10:00:00Z"
    }
  ],
  "count": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `data[].id` | `string` | Question ID |
| `data[].assignment_id` | `string` | Parent assignment |
| `data[].grading_criteria_id` | `string` \| `null` | Linked grading criterion |
| `data[].question_text` | `string` | The question |
| `data[].competency` | `string` | Competency being assessed |
| `data[].difficulty` | `int` | Difficulty level |
| `data[].expected_answer` | `string` | Model answer |
| `data[].max_points` | `int` | Maximum score (default 10) |
| `data[].status` | `string` | Question status |
| `data[].created_at` | `datetime` | Created at |
| `data[].updated_at` | `datetime` | Updated at |

---

## 6. Assessments

> Prefix: `/api/v1/assessments`

### 6.1 `POST /api/v1/assessments/trigger`

Trigger (start) a new assessment session for a student.

**Request Body:**
```json
{
  "student_id": "stud-001",
  "assignment_id": "assign-001",
  "code_context": "def bubble_sort(arr):\n    ..."
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `student_id` | `string` | **Yes** | — | Student taking the assessment |
| `assignment_id` | `string` | **Yes** | — | Assignment being assessed |
| `code_context` | `string` | No | `""` | Student's code submission for context |

**Response (200):**
```json
{
  "session_id": "sess-uuid-123",
  "first_question": {
    "question_id": "q-abc-123",
    "question_instance_id": "qi-uuid-456",
    "question_text": "Explain how your bubble sort works.",
    "competency": "sorting",
    "difficulty": 2,
    "code_context": "",
    "hint": "",
    "is_follow_up": false,
    "question_type": "new"
  },
  "total_questions": 5,
  "status": "in_progress"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | `string` | Unique session identifier |
| `first_question` | `QuestionWithContext` \| `null` | First question to present |
| `first_question.question_id` | `string` | Template question ID |
| `first_question.question_instance_id` | `string` | Instance ID for this session |
| `first_question.question_text` | `string` | Question text |
| `first_question.competency` | `string` | Competency being tested |
| `first_question.difficulty` | `int` | Difficulty level |
| `first_question.code_context` | `string` | Code snippet context |
| `first_question.hint` | `string` | Optional hint |
| `first_question.is_follow_up` | `bool` | Whether this is a follow-up |
| `first_question.question_type` | `string` | `"new"` / `"follow_up"` / `"re_ask"` |
| `total_questions` | `int` | Total questions in the session |
| `status` | `string` | Session status |

---

### 6.2 `GET /api/v1/assessments/sessions/{session_id}`

Get full session details including questions and responses.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `session_id` | `string` | Yes |

**Response (200):**
```json
{
  "session": {
    "id": "sess-uuid-123",
    "student_id": "stud-001",
    "assignment_id": "assign-001",
    "status": "in_progress",
    "trigger_reason": "manual",
    "started_at": "2026-03-01T10:00:00Z",
    "completed_at": null,
    "code_context": "...",
    "final_score": null,
    "max_score": null,
    "competency_summary": null
  },
  "questions_asked": [
    {
      "id": "qi-uuid-456",
      "session_id": "sess-uuid-123",
      "question_id": "q-abc-123",
      "sequence_number": 1,
      "asked_at": "2026-03-01T10:00:01Z",
      "competency": "sorting",
      "difficulty": 2,
      "follow_up_depth": 0,
      "parent_instance_id": null,
      "follow_up_question_text": null
    }
  ],
  "responses": [
    {
      "id": "resp-uuid-789",
      "question_instance_id": "qi-uuid-456",
      "session_id": "sess-uuid-123",
      "student_id": "stud-001",
      "response_text": "Bubble sort compares adjacent elements...",
      "response_type": "text",
      "submitted_at": "2026-03-01T10:01:00Z",
      "response_time_seconds": 59,
      "evaluation_score": 8.0,
      "feedback_text": "Good explanation...",
      "detected_misconceptions": [],
      "input_classification": "valid_answer",
      "score_justification": "...",
      "voice_intent": null
    }
  ],
  "total_questions": 5,
  "answered_questions": 1
}
```

**Error (404):** Session not found.

---

### 6.3 `POST /api/v1/assessments/sessions/{session_id}/respond`

Submit a student's response to a question.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `session_id` | `string` | Yes |

**Request Body:**
```json
{
  "question_instance_id": "qi-uuid-456",
  "response_text": "Bubble sort compares adjacent elements and swaps them...",
  "response_type": "text"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `question_instance_id` | `string` | **Yes** | — | The specific question instance to answer |
| `response_text` | `string` | **Yes** | — | Student's answer |
| `response_type` | `string` | No | `""` | `"text"` or `"audio"` |

**Response (200):**
```json
{
  "response_id": "resp-uuid-789",
  "next_question": {
    "question_id": "q-def-456",
    "question_instance_id": "qi-uuid-999",
    "question_text": "What is the time complexity?",
    "competency": "complexity",
    "difficulty": 3,
    "code_context": "",
    "hint": "",
    "is_follow_up": false,
    "question_type": "new"
  },
  "is_complete": false,
  "message": "",
  "evaluation_score": 8.0,
  "feedback_text": "Good explanation of the comparison process.",
  "detected_misconceptions": [],
  "final_score": null,
  "max_score": null,
  "competency_summary": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `response_id` | `string` | Stored response ID |
| `next_question` | `QuestionWithContext` \| `null` | Next question (null if complete) |
| `is_complete` | `bool` | Whether the assessment is finished |
| `message` | `string` | Optional message |
| `evaluation_score` | `float` \| `null` | Score for this response |
| `feedback_text` | `string` \| `null` | LLM-generated feedback |
| `detected_misconceptions` | `string[]` \| `null` | Misconceptions detected |
| `final_score` | `float` \| `null` | Total score (only when `is_complete=true`) |
| `max_score` | `float` \| `null` | Maximum possible score |
| `competency_summary` | `dict[]` \| `null` | Per-competency breakdown |

**Error (404):** Session or question not found.
**Error (400):** Session not in progress.
**Error (409):** Response already submitted for this question.

---

### 6.4 `GET /api/v1/assessments/sessions/{session_id}/transcript`

Get the full conversation transcript for a session.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `session_id` | `string` | Yes |

**Response (200):**
```json
{
  "session_id": "sess-uuid-123",
  "student_id": "stud-001",
  "assignment_id": "assign-001",
  "status": "completed",
  "started_at": "2026-03-01T10:00:00Z",
  "completed_at": "2026-03-01T10:30:00Z",
  "code_context": "...",
  "exchanges": [
    {
      "question_text": "Explain how bubble sort works.",
      "competency": "sorting",
      "difficulty": 2,
      "student_answer": "Bubble sort compares...",
      "asked_at": "2026-03-01T10:00:01Z",
      "answered_at": "2026-03-01T10:01:00Z",
      "response_time_seconds": 59,
      "evaluation_score": 8.0,
      "feedback_text": "Good explanation...",
      "detected_misconceptions": [],
      "score_justification": "...",
      "voice_intent": null,
      "is_follow_up": false,
      "question_type": "new"
    }
  ],
  "final_score": 25.0,
  "max_score": 30.0,
  "competency_summary": [...]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `exchanges[].question_text` | `string` | Question asked |
| `exchanges[].competency` | `string` | Competency |
| `exchanges[].difficulty` | `int` | Difficulty |
| `exchanges[].student_answer` | `string` | Student's response |
| `exchanges[].asked_at` | `datetime` | When question was presented |
| `exchanges[].answered_at` | `datetime` \| `null` | When student answered |
| `exchanges[].response_time_seconds` | `int` | Time taken |
| `exchanges[].evaluation_score` | `float` \| `null` | Score |
| `exchanges[].feedback_text` | `string` \| `null` | LLM feedback |
| `exchanges[].detected_misconceptions` | `string[]` \| `null` | Misconceptions |
| `exchanges[].score_justification` | `string` \| `null` | Score reasoning |
| `exchanges[].voice_intent` | `string` \| `null` | Classified intent (voice sessions) |
| `exchanges[].is_follow_up` | `bool` | Whether it was a follow-up |
| `exchanges[].question_type` | `string` | `"new"` / `"follow_up"` / `"re_ask"` |

**Error (404):** Session not found.

---

### 6.5 `PUT /api/v1/assessments/sessions/{session_id}/abandon`

Abandon (cancel) an in-progress session.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `session_id` | `string` | Yes |

**Request Body:** None

**Response (200):**
```json
{ "message": "Session abandoned successfully" }
```

**Error (404):** Session not found.
**Error (400):** Session is not in a state that can be abandoned.

---

### 6.6 `POST /api/v1/assessments/sessions/{session_id}/hint`

Request a hint for the current question. May apply a scoring penalty.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `session_id` | `string` | Yes |

**Request Body:**
```json
{
  "session_id": "sess-uuid-123",
  "question_instance_id": "qi-uuid-456"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | `string` | **Yes** | Session ID |
| `question_instance_id` | `string` | **Yes** | The question to get a hint for |

**Response (200):**
```json
{
  "hint_text": "Think about how adjacent elements are compared...",
  "penalty_applied": true,
  "total_hints_used": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `hint_text` | `string` | The hint |
| `penalty_applied` | `bool` | Whether a scoring penalty was applied |
| `total_hints_used` | `int` | Total hints used in this session |

**Error (404):** Session or question not found.

---

### 6.7 `PUT /api/v1/assessments/sessions/{session_id}/pause`

Pause an in-progress session.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `session_id` | `string` | Yes |

**Request Body:**
```json
{
  "session_id": "sess-uuid-123",
  "reason": "Student needs a break"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | `string` | **Yes** | Session ID |
| `reason` | `string` \| `null` | No | Reason for pausing |

**Response (200):**
```json
{
  "status": "paused",
  "message": "Session paused"
}
```

**Error (400):** Session cannot be paused (not in progress).

---

### 6.8 `PUT /api/v1/assessments/sessions/{session_id}/resume`

Resume a paused session.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `session_id` | `string` | Yes |

**Request Body:** None

**Response (200):**
```json
{
  "status": "in_progress",
  "message": "Session resumed"
}
```

**Error (400):** Session cannot be resumed (not paused).

---

## 7. Students

> Prefix: `/api/v1/students`

### 7.1 `GET /api/v1/students/{student_id}/sessions`

Get all assessment sessions for a student.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `student_id` | `string` | Yes |

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | `string` | No | Filter by session status (e.g. `"completed"`, `"in_progress"`) |

**Response (200):**
```json
{
  "data": [
    {
      "session_id": "sess-uuid-123",
      "assignment_id": "assign-001",
      "status": "completed",
      "started_at": "2026-03-01T10:00:00Z",
      "completed_at": "2026-03-01T10:30:00Z",
      "questions_asked": 5,
      "responses_given": 5
    }
  ],
  "count": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `data[].session_id` | `string` | Session ID |
| `data[].assignment_id` | `string` | Assignment ID |
| `data[].status` | `string` | Session status |
| `data[].started_at` | `datetime` | Start time |
| `data[].completed_at` | `datetime` \| `null` | End time |
| `data[].questions_asked` | `int` | Questions presented |
| `data[].responses_given` | `int` | Responses submitted |

---

## 8. Instructors

> Prefix: `/api/v1/instructors`

### 8.1 `GET /api/v1/instructors/{instructor_id}/assessments`

Get assessment sessions across students with advanced filtering.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `instructor_id` | `string` | Yes |

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `assignment_ids` | `string` | No | Comma-separated list of assignment IDs |
| `assignment_id` | `string` | No | Single assignment ID filter |
| `student_id` | `string` | No | Filter by student |
| `status` | `string` | No | Filter by session status |
| `start_date` | `string` | No | ISO 8601 date (e.g. `"2026-03-01"`) |
| `end_date` | `string` | No | ISO 8601 date |

**Response (200):**
```json
{
  "data": [
    {
      "session_id": "sess-uuid-123",
      "student_id": "stud-001",
      "assignment_id": "assign-001",
      "status": "completed",
      "started_at": "2026-03-01T10:00:00Z",
      "completed_at": "2026-03-01T10:30:00Z",
      "questions_asked": 5,
      "responses_given": 5
    }
  ],
  "count": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `data[].session_id` | `string` | Session ID |
| `data[].student_id` | `string` | Student ID |
| `data[].assignment_id` | `string` | Assignment ID |
| `data[].status` | `string` | Session status |
| `data[].started_at` | `datetime` | Start time |
| `data[].completed_at` | `datetime` \| `null` | Completion time |
| `data[].questions_asked` | `int` | Questions presented |
| `data[].responses_given` | `int` | Responses submitted |

---

## 9. Voice Biometrics

> Prefix: `/api/v1/voice-biometrics`

### 9.1 `POST /api/v1/voice-biometrics/enroll`

Enroll a student's voiceprint from audio samples. Requires minimum 3 samples for a reliable voiceprint. Replaces any existing voiceprint.

**Request Body:**
```json
{
  "student_id": "stud-001",
  "audio_samples": [
    "<base64-encoded-wav-1>",
    "<base64-encoded-wav-2>",
    "<base64-encoded-wav-3>"
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `student_id` | `string` | **Yes** | Student to enroll |
| `audio_samples` | `string[]` | **Yes** (min 1) | Base64-encoded WAV audio clips (3–10 sec each) |

**Response (200):**
```json
{
  "student_id": "stud-001",
  "voiceprint_id": "vp-uuid-123",
  "sample_count": 3,
  "status": "enrolled",
  "message": "Voiceprint enrolled with 3 samples."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `student_id` | `string` | Student ID |
| `voiceprint_id` | `string` | Created voiceprint ID |
| `sample_count` | `int` | Number of samples processed |
| `status` | `string` | `"enrolled"` or `"needs_more_samples"` |
| `message` | `string` | Human-readable status |

**Error (400):** Invalid audio sample.

---

### 9.2 `POST /api/v1/voice-biometrics/enroll/sample`

Add a single audio sample to an existing (or new) enrollment. Useful for incremental enrollment.

**Request Body:**
```json
{
  "student_id": "stud-001",
  "audio_sample": "<base64-encoded-wav>"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `student_id` | `string` | **Yes** | Student ID |
| `audio_sample` | `string` | **Yes** | Base64-encoded WAV audio |

**Response (200):**
```json
{
  "student_id": "stud-001",
  "voiceprint_id": "vp-uuid-123",
  "sample_count": 2,
  "status": "needs_more_samples",
  "message": "Sample added (2/3 needed)."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `student_id` | `string` | Student ID |
| `voiceprint_id` | `string` | Voiceprint ID |
| `sample_count` | `int` | Total samples so far |
| `status` | `string` | `"enrolled"` or `"needs_more_samples"` |
| `message` | `string` | Progress message |

**Error (400):** Invalid audio.

---

### 9.3 `POST /api/v1/voice-biometrics/verify`

One-shot speaker verification against enrolled voiceprint.

**Request Body:**
```json
{
  "student_id": "stud-001",
  "session_id": "sess-uuid-123",
  "audio_data": "<base64-encoded-wav>"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `student_id` | `string` | **Yes** | Student to verify |
| `session_id` | `string` | **Yes** | Current assessment session |
| `audio_data` | `string` | **Yes** | Base64-encoded WAV audio to verify |

**Response (200):**
```json
{
  "student_id": "stud-001",
  "passed": true,
  "similarity_score": 0.8732,
  "threshold": 0.75,
  "message": "Voice verified — identity confirmed."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `student_id` | `string` | Student ID |
| `passed` | `bool` | Whether verification passed |
| `similarity_score` | `float` | Cosine similarity score (0–1) |
| `threshold` | `float` | Minimum threshold for pass |
| `message` | `string` | Result message |

**Error (404):** No enrolled voiceprint for student.
**Error (400):** Invalid audio data.

---

### 9.4 `GET /api/v1/voice-biometrics/enrollment-status/{student_id}`

Check whether a student has an active voiceprint enrollment.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `student_id` | `string` | Yes |

**Response (200):**
```json
{
  "student_id": "stud-001",
  "is_enrolled": true,
  "sample_count": 3,
  "created_at": "2026-03-01T09:00:00Z",
  "updated_at": "2026-03-01T09:05:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `student_id` | `string` | Student ID |
| `is_enrolled` | `bool` | Has active voiceprint |
| `sample_count` | `int` | Number of enrolled samples (0 if not enrolled) |
| `created_at` | `datetime` \| `null` | Voiceprint creation time |
| `updated_at` | `datetime` \| `null` | Last update time |

---

### 9.5 `GET /api/v1/voice-biometrics/session-summary/{session_id}`

Get the voice verification audit trail for an assessment session.

**Path Parameters:**

| Param | Type | Required |
|-------|------|----------|
| `session_id` | `string` | Yes |

**Response (200):**
```json
{
  "session_id": "sess-uuid-123",
  "total_checks": 10,
  "passed_checks": 9,
  "failed_checks": 1,
  "average_similarity": 0.8521,
  "is_flagged": false,
  "checks": [
    {
      "checked_at": "2026-03-01T10:01:00Z",
      "similarity_score": 0.8732,
      "passed": true,
      "consecutive_failures": 0
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | `string` | Session ID |
| `total_checks` | `int` | Total verification checks |
| `passed_checks` | `int` | Checks that passed |
| `failed_checks` | `int` | Checks that failed |
| `average_similarity` | `float` | Average similarity score |
| `is_flagged` | `bool` | `true` if 3+ consecutive failures occurred |
| `checks[].checked_at` | `string` | ISO timestamp |
| `checks[].similarity_score` | `float` | Similarity score |
| `checks[].passed` | `bool` | Pass/fail |
| `checks[].consecutive_failures` | `int` | Consecutive failure count at that point |

---

### 9.6 `POST /api/v1/voice-biometrics/re-enroll`

Deactivate existing voiceprint and re-enroll with new samples.

**Request Body:**
```json
{
  "student_id": "stud-001",
  "audio_samples": [
    "<base64-encoded-wav-1>",
    "<base64-encoded-wav-2>",
    "<base64-encoded-wav-3>"
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `student_id` | `string` | **Yes** | Student to re-enroll |
| `audio_samples` | `string[]` | **Yes** (min 1) | New base64-encoded WAV samples |

**Response (200):** Same as `POST /enroll` response.

---

## 10. Voice Assessment (WebSocket)

> `WS /api/v1/assessments/sessions/{session_id}/voice`

Real-time conversational voice assessment over WebSocket. STT and TTS are handled in the browser via Web Speech API. The server uses LLM-based intent classification (never regex).

### Connection

```
ws://localhost:8000/api/v1/assessments/sessions/{session_id}/voice
```

| Param | Type | Description |
|-------|------|-------------|
| `session_id` | `string` | Active assessment session ID |

---

### Client → Server Messages

#### `start_session`

Sent once after connecting. Provides the first question context and triggers voiceprint loading.

```json
{
  "type": "start_session",
  "question_instance_id": "qi-uuid-456",
  "question_text": "Explain how bubble sort works."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `string` | **Yes** | `"start_session"` |
| `question_instance_id` | `string` | **Yes** | First question instance ID |
| `question_text` | `string` | **Yes** | First question text |

---

#### `message` / `submit_answer`

Any student speech. Both types are treated identically — the LLM classifies the intent.

```json
{
  "type": "message",
  "text": "Bubble sort compares adjacent elements...",
  "question_instance_id": "qi-uuid-456",
  "audio_data": "<base64-encoded-wav>"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `string` | **Yes** | `"message"` or `"submit_answer"` |
| `text` | `string` | **Yes** | Student's speech text (from browser STT) |
| `question_instance_id` | `string` | No | Current question instance (tracked server-side too) |
| `audio_data` | `string` | No | Base64-encoded WAV for voice biometric verification |

---

### Server → Client Messages

#### `instructor_response`

Conversational response (clarification, repeat, topic question, greeting, error recovery).

```json
{
  "type": "instructor_response",
  "message": "Could you elaborate on the comparison step?",
  "intent": "clarification_request",
  "repeat_question": null,
  "audio_b64": "<base64-encoded-tts-audio>"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | `string` | `"instructor_response"` |
| `message` | `string` | Response text |
| `intent` | `string` | Classified intent: `"clarification_request"`, `"repeat_request"`, `"topic_question"`, `"greeting"`, `"duplicate"`, `"waiting"`, `"error_recovery"` |
| `repeat_question` | `string` \| `null` | Original question text (only for repeat requests) |
| `audio_b64` | `string` \| `null` | TTS audio (base64) |

---

#### `evaluation`

LLM evaluation result for an actual answer attempt.

```json
{
  "type": "evaluation",
  "score": 7.5,
  "feedback": "Good explanation of the basic mechanism...",
  "misconceptions": ["Confused swap with assignment"],
  "audio_b64": "<base64-encoded-tts-audio>"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | `string` | `"evaluation"` |
| `score` | `float` | Score for this answer |
| `feedback` | `string` | LLM feedback text |
| `misconceptions` | `string[]` | Detected misconceptions |
| `audio_b64` | `string` \| `null` | TTS audio of feedback |

---

#### `next_question`

Next question to present (browser speaks it via speechSynthesis).

```json
{
  "type": "next_question",
  "question_instance_id": "qi-uuid-789",
  "question_text": "What is the time complexity of bubble sort?",
  "competency": "complexity",
  "difficulty": 3,
  "is_follow_up": false,
  "audio_b64": "<base64-encoded-tts-audio>"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | `string` | `"next_question"` |
| `question_instance_id` | `string` | Instance ID for tracking |
| `question_text` | `string` | Question text |
| `competency` | `string` | Competency being tested |
| `difficulty` | `int` | Difficulty level |
| `is_follow_up` | `bool` | Whether it's a follow-up question |
| `audio_b64` | `string` \| `null` | TTS audio of the question |

---

#### `session_complete`

Assessment is finished.

```json
{
  "type": "session_complete",
  "final_score": 25.0,
  "max_score": 30.0,
  "message": "Assessment complete. Well done!",
  "competency_summary": [
    { "competency": "sorting", "score": 15, "max": 20 },
    { "competency": "complexity", "score": 10, "max": 10 }
  ],
  "audio_b64": "<base64-encoded-tts-audio>"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | `string` | `"session_complete"` |
| `final_score` | `float` | Total score achieved |
| `max_score` | `float` | Maximum possible score |
| `message` | `string` | Completion message |
| `competency_summary` | `dict[]` | Per-competency breakdown |
| `audio_b64` | `string` \| `null` | TTS audio |

---

#### `voice_verification`

Voice biometric verification result (sent after each audio check).

```json
{
  "type": "voice_verification",
  "passed": true,
  "similarity": 0.8732,
  "message": "Identity verified.",
  "consecutive_failures": 0
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | `string` | `"voice_verification"` |
| `passed` | `bool` | Verification result |
| `similarity` | `float` | Cosine similarity score |
| `message` | `string` | Result message |
| `consecutive_failures` | `int` | Streak of failures (resets on pass) |

---

#### `voice_verification_warning`

Sent when consecutive failures reach threshold (3+). Session is flagged.

```json
{
  "type": "voice_verification_warning",
  "message": "Warning: Voice biometric verification has failed multiple times...",
  "consecutive_failures": 3,
  "audio_b64": "<base64-encoded-tts-audio>"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | `string` | `"voice_verification_warning"` |
| `message` | `string` | Warning text |
| `consecutive_failures` | `int` | Failure count |
| `audio_b64` | `string` \| `null` | TTS audio of warning |

---

#### `error`

Non-fatal error (client can retry).

```json
{
  "type": "error",
  "message": "No speech detected. Please try again."
}
```

---

## Summary Table

| # | Method | Path | Description |
|---|--------|------|-------------|
| 1 | `GET` | `/health` | Full system health check |
| 2 | `GET` | `/ready` | Readiness probe |
| 3 | `GET` | `/mock/assignments` | List mock assignments |
| 4 | `GET` | `/mock/assignments/{id}` | Get mock assignment |
| 5 | `GET` | `/mock/instructors` | List mock instructors |
| 6 | `GET` | `/mock/instructors/{id}` | Get mock instructor |
| 7 | `GET` | `/mock/courses` | List mock courses |
| 8 | `GET` | `/mock/courses/{id}` | Get mock course |
| 9 | `GET` | `/mock/students` | List mock students |
| 10 | `GET` | `/mock/students/{id}` | Get mock student |
| 11 | `GET` | `/mock/students/{id}/progress` | Get mock student progress |
| 12 | `GET` | `/llm/provider` | Get active LLM provider |
| 13 | `POST` | `/llm/provider/switch` | Switch LLM provider |
| 14 | `GET` | `/llm/provider/health` | Check LLM provider health |
| 15 | `POST` | `/api/v1/assignments/{id}/grading-criteria/generate` | AI-generate grading criteria |
| 16 | `GET` | `/api/v1/assignments/{id}/grading-criteria` | List grading criteria |
| 17 | `PATCH` | `/api/v1/grading-criteria/{id}` | Update a grading criterion |
| 18 | `POST` | `/api/v1/assignments/{id}/questions/generate` | AI-generate questions |
| 19 | `GET` | `/api/v1/assignments/{id}/questions` | List questions |
| 20 | `POST` | `/api/v1/assessments/trigger` | Start assessment session |
| 21 | `GET` | `/api/v1/assessments/sessions/{id}` | Get session details |
| 22 | `POST` | `/api/v1/assessments/sessions/{id}/respond` | Submit response |
| 23 | `GET` | `/api/v1/assessments/sessions/{id}/transcript` | Get transcript |
| 24 | `PUT` | `/api/v1/assessments/sessions/{id}/abandon` | Abandon session |
| 25 | `POST` | `/api/v1/assessments/sessions/{id}/hint` | Request a hint |
| 26 | `PUT` | `/api/v1/assessments/sessions/{id}/pause` | Pause session |
| 27 | `PUT` | `/api/v1/assessments/sessions/{id}/resume` | Resume session |
| 28 | `GET` | `/api/v1/students/{id}/sessions` | Get student's sessions |
| 29 | `GET` | `/api/v1/instructors/{id}/assessments` | Get instructor's assessments |
| 30 | `POST` | `/api/v1/voice-biometrics/enroll` | Enroll voiceprint |
| 31 | `POST` | `/api/v1/voice-biometrics/enroll/sample` | Add enrollment sample |
| 32 | `POST` | `/api/v1/voice-biometrics/verify` | Verify speaker |
| 33 | `GET` | `/api/v1/voice-biometrics/enrollment-status/{id}` | Check enrollment status |
| 34 | `GET` | `/api/v1/voice-biometrics/session-summary/{id}` | Session verification audit |
| 35 | `POST` | `/api/v1/voice-biometrics/re-enroll` | Re-enroll voiceprint |
| 36 | `WS` | `/api/v1/assessments/sessions/{id}/voice` | Real-time voice assessment |
