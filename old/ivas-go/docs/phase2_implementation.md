# IVAS Phase 2: Student Assessment Flow

## Implementation Complete ✅

### New Endpoints Added

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/assessments/sessions/:sessionId` | Get full session details |
| GET | `/api/v1/assessments/sessions/:sessionId/transcript` | Get question-answer transcript |
| PUT | `/api/v1/assessments/sessions/:sessionId/abandon` | Mark session as abandoned |
| GET | `/api/v1/students/:studentId/sessions` | Get all sessions for a student |
| GET | `/api/v1/instructors/:instructorId/assessments` | Get assessments for instructor |

### Existing Endpoints (Phase 1)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/assessments/trigger` | Start new assessment session |
| POST | `/api/v1/assessments/sessions/:sessionId/respond` | Submit response to question |

### Domain Models

```go
// Assessment Session
type AssessmentSession struct {
    ID            string
    StudentID     string
    AssignmentID  string
    TaskID        string
    Status        string     // "in_progress", "completed", "abandoned"
    TriggerReason string     // "task_completion", "milestone", "confusion_detected"
    StartedAt     time.Time
    CompletedAt   *time.Time
    CodeContext   string
}

// Question Instance (asked in a session)
type AssessmentQuestionInstance struct {
    ID             string
    SessionID      string
    QuestionID     string
    SequenceNumber int
    AskedAt        time.Time
    Competency     string
    Difficulty     int
}

// Student Response
type StudentResponse struct {
    ID                  string
    QuestionInstanceID  string
    SessionID           string
    StudentID           string
    ResponseText        string
    ResponseType        string    // "text" for now, "voice" future
    TranscriptText      string
    SubmittedAt         time.Time
    ResponseTimeSeconds int
}

// Response Competency Link
type ResponseCompetencyLink struct {
    ID         string
    ResponseID string
    Competency string
    QuestionID string
}
```

### Assessment Flow Configuration

```go
type AssessmentFlowConfig struct {
    MinQuestionsPerSession int  // Default: 3
    MaxQuestionsPerSession int  // Default: 5
    RequireAllRequired     bool // Default: true
}
```

### Test Files Created

**Bruno Collection:**
- `Assessments/Get Session.bru`
- `Assessments/Get Session Transcript.bru`
- `Assessments/Abandon Session.bru`
- `Students/Get Student Sessions.bru`
- `Instructors/Get Instructor Assessments.bru`

**Test Script:**
- `scripts/simulate_student_assessment.sh`

### Query Parameters

**GET /api/v1/students/:studentId/sessions**
- `status` (optional): Filter by session status

**GET /api/v1/instructors/:instructorId/assessments**
- `assignment_id` (optional): Filter by assignment
- `assignment_ids` (optional): Comma-separated list
- `student_id` (optional): Filter by student
- `status` (optional): Filter by status
- `start_date` (optional): ISO format date
- `end_date` (optional): ISO format date

### Validation & Error Handling

- ✅ Session exists before accepting responses
- ✅ Prevent duplicate responses to same question
- ✅ Validate student owns the session
- ✅ Proper HTTP status codes (400, 404, 409, 500)
- ✅ Sessions can only be abandoned when "in_progress"

### What's Next (Phase 3)

- [ ] Adaptive difficulty based on student performance
- [ ] Voice interface integration
- [ ] Socratic follow-up questions
- [ ] Session timeout after 30 min inactivity (background job)
