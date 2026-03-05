# IVAS Frontend Integration Prompt

> **Use this prompt with your Next.js project agent to integrate the IVAS (Intelligent Viva Assessment System) backend into the main monorepo's `apps/web` frontend.**

---

## System Context

We have a separate backend service called **IVAS** (Intelligent Viva Assessment System) that provides AI-powered oral viva assessments for students. The backend is a FastAPI service already running and deployed. We need to integrate it into our existing Next.js monorepo frontend at `apps/web/`.

**IVAS Backend Base URL:** Configure via environment variable `NEXT_PUBLIC_IVAS_API_URL` (e.g., `https://ivas.sudila.com` for production).

---

## What IVAS Does

IVAS is an intelligent, adaptive oral viva assessment system. It has two distinct user roles:

### Instructor Flow
1. **Generate Grading Criteria** — Instructor submits assignment text; AI extracts competencies, difficulty levels, marking rubrics, and learning objectives
2. **Review & Edit Criteria** — Instructor reviews AI-generated criteria and can edit them
3. **Generate Viva Questions** — AI generates viva questions aligned to each criterion (tests concepts, not scenario knowledge)
4. **Monitor Assessments** — View all student sessions, filter by assignment/student/status/date
5. **Review Transcripts** — Read full exchange history of any completed viva session

### Student Flow
1. **Trigger Assessment** — Student starts a viva session for a specific assignment
2. **Answer Questions** — Chat-based interface; up to 5 distinct questions per session
3. **Receive AI Feedback** — 3-layer LLM evaluation pipeline provides real-time scoring + feedback
4. **Adaptive Difficulty** — System adjusts question difficulty based on rolling performance
5. **Socratic Follow-ups** — If student partially understands (score 3-6), AI generates follow-up questions
6. **Session Completion** — Final score computed per competency with detailed breakdown

### Key Behavioral Details
- **Input Guard (Layer 1):** LLM classifies every student response as: `evaluate` (genuine attempt), `teach_and_skip` (student doesn't know), `explain_and_reask` (student needs help), `clarify_relevance` (student questions relevance), `warn_and_reask` (inappropriate content)
- **Quick Evaluation (Layer 2):** Scores 0-10, provides feedback, determines next action: `advance` (≥7), `follow_up` (3-6), `re_ask` (0-2)
- **Deep Analysis (Layer 3):** Runs async in background; provides understanding level, misconceptions, study suggestions
- **Exchange Limits:** Max 5 distinct questions, max 30 total exchanges, max 3 interactions per question chain, max 1 follow-up depth, max 1 re-ask per question

---

## OpenAPI Specification — Complete Endpoint Reference

### Health Endpoints
```
GET /health                    → { status, database, llm_provider }
GET /ready                     → { ready: boolean }
```

### Mock Data Endpoints (Development LMS Simulation)
```
GET /mock/assignments          → { data: Assignment[] }
GET /mock/assignments/:id      → Assignment
GET /mock/instructors          → { data: Instructor[] }
GET /mock/instructors/:id      → Instructor
GET /mock/courses              → { data: Course[] }
GET /mock/courses/:id          → Course
GET /mock/students             → { data: Student[] }
GET /mock/students/:id         → Student
GET /mock/students/:id/progress → StudentProgress
```

### LLM Provider Management
```
GET  /llm/provider             → ProviderInfo
POST /llm/provider/switch      → { provider: string }  →  { message, active_provider }
GET  /llm/provider/health      → { status, provider, reachable }
```

### Grading Criteria (Instructor)
```
POST /api/v1/assignments/:assignment_id/grading-criteria/generate
  Body: { assignment_text: string, replace_existing?: boolean, num_criteria?: number (2-10) }
  → 201: { assignment_id, criteria_ids: string[], total_generated: number }

GET  /api/v1/assignments/:assignment_id/grading-criteria
  → 200: { data: GradingCriteria[] }

PATCH /api/v1/grading-criteria/:criteria_id
  Body: { competency?, difficulty_level? (1-5), level_label?, level_description?, marking_criteria?, programming_language?, learning_objectives?: string[] }
  → 200: GradingCriteria
```

### Question Generation (Instructor)
```
POST /api/v1/assignments/:assignment_id/questions/generate
  Query: criteria_id?, assignment_text?, num_questions? (1-5)
  → 201: { assignment_id, question_ids: string[], total_generated: number }

GET  /api/v1/assignments/:assignment_id/questions
  Query: status?, competency?
  → 200: { data: Question[] }
```

### Assessment Sessions (Student + Instructor Review)
```
POST /api/v1/assessments/trigger
  Body: { student_id: string, assignment_id: string, code_context?: string }
  → 200: TriggerAssessmentResponse

GET  /api/v1/assessments/sessions/:session_id
  → 200: SessionDetailsOut

POST /api/v1/assessments/sessions/:session_id/respond
  Body: { question_instance_id: string, response_text: string, response_type?: string }
  → 200: SubmitResponseResponse

GET  /api/v1/assessments/sessions/:session_id/transcript
  → 200: AssessmentTranscriptOut

PUT  /api/v1/assessments/sessions/:session_id/abandon
  → 200: { message: string }
```

### Student Portal
```
GET /api/v1/students/:student_id/sessions
  Query: status?
  → 200: { data: StudentSessionSummary[], count: number }
```

### Instructor Portal
```
GET /api/v1/instructors/:instructor_id/assessments
  Query: assignment_ids?, assignment_id?, student_id?, status?, start_date?, end_date?
  → 200: { data: InstructorAssessmentSummary[], count: number }
```

---

## TypeScript Types to Create

Create a file at `apps/web/types/ivas.ts` (or integrate into existing types) with these exact types matching the backend schemas:

```typescript
// ============================================================
// Mock / LMS Types
// ============================================================

export interface DifficultyRange {
  min: number;
  max: number;
}

export interface IvasAssignment {
  assignment_id: string;
  instructor_id: string;
  course_id: string;
  title: string;
  competencies: string[];
  learning_objectives: string[];
  difficulty_range: DifficultyRange;
}

export interface IvasStudent {
  id: string;
  name: string;
  course_id: string;
}

export interface IvasCourse {
  id: string;
  name: string;
  programming_language: string;
}

export interface IvasInstructor {
  id: string;
  name: string;
  email: string;
}

// ============================================================
// Grading Criteria
// ============================================================

export interface GradingCriteria {
  id: string;
  assignment_id: string;
  competency: string;
  difficulty_level: number;
  level_label: string;
  level_description: string;
  marking_criteria: string;
  programming_language: string;
  learning_objectives: string[];
  created_at: string;
  updated_at: string;
}

export interface GenerateGradingCriteriaRequest {
  assignment_text: string;
  replace_existing?: boolean;
  num_criteria?: number; // 2-10
}

export interface GenerateGradingCriteriaResponse {
  assignment_id: string;
  criteria_ids: string[];
  total_generated: number;
}

export interface UpdateGradingCriteriaRequest {
  competency?: string;
  difficulty_level?: number; // 1-5
  level_label?: string;
  level_description?: string;
  marking_criteria?: string;
  programming_language?: string;
  learning_objectives?: string[];
}

// ============================================================
// Questions
// ============================================================

export interface IvasQuestion {
  id: string;
  assignment_id: string;
  criteria_id: string;
  question_text: string;
  expected_answer: string;
  competency: string;
  difficulty: number;
  max_points: number;
  status: string; // "draft" | "approved"
}

export interface GenerateQuestionsResponse {
  assignment_id: string;
  question_ids: string[];
  total_generated: number;
}

// ============================================================
// Assessment Session
// ============================================================

export interface QuestionWithContext {
  question_id: string;
  question_instance_id: string;
  question_text: string;
  competency: string;
  difficulty: number;
  code_context: string;
  hint: string;
  is_follow_up: boolean;
  question_type: "new" | "follow_up" | "re_ask";
}

export interface TriggerAssessmentRequest {
  student_id: string;
  assignment_id: string;
  code_context?: string;
}

export interface TriggerAssessmentResponse {
  session_id: string;
  first_question: QuestionWithContext | null;
  total_questions: number;
  status: string;
}

export interface SubmitResponseRequest {
  question_instance_id: string;
  response_text: string;
  response_type?: string;
}

export interface CompetencySummary {
  competency: string;
  score: number;
  max_score: number;
  questions_asked: number;
}

export interface SubmitResponseResponse {
  response_id: string;
  next_question: QuestionWithContext | null;
  is_complete: boolean;
  message: string;
  evaluation_score: number | null;
  feedback_text: string | null;
  detected_misconceptions: string[] | null;
  final_score: number | null;
  max_score: number | null;
  competency_summary: CompetencySummary[] | null;
}

// ============================================================
// Session Details
// ============================================================

export interface QuestionInstanceOut {
  id: string;
  session_id: string;
  question_id: string;
  sequence_number: number;
  asked_at: string;
  competency: string;
  difficulty: number;
  follow_up_depth: number;
  parent_instance_id: string | null;
  follow_up_question_text: string | null;
}

export interface StudentResponseOut {
  id: string;
  question_instance_id: string;
  session_id: string;
  student_id: string;
  response_text: string;
  response_type: string | null;
  submitted_at: string;
  response_time_seconds: number;
  evaluation_score: number | null;
  feedback_text: string | null;
  detected_misconceptions: string[] | null;
  input_classification: string | null; // "evaluate"|"teach_and_skip"|"explain_and_reask"|"clarify_relevance"|"warn_and_reask"
  score_justification: string | null;
  voice_intent: string | null;
}

export interface SessionOut {
  id: string;
  student_id: string;
  assignment_id: string;
  status: "in_progress" | "completed" | "abandoned";
  trigger_reason: string;
  started_at: string;
  completed_at: string | null;
  code_context: string | null;
  final_score: number | null;
  max_score: number | null;
  competency_summary: CompetencySummary[] | null;
}

export interface SessionDetailsOut {
  session: SessionOut;
  questions_asked: QuestionInstanceOut[];
  responses: StudentResponseOut[];
  total_questions: number;
  answered_questions: number;
}

// ============================================================
// Student & Instructor Summaries
// ============================================================

export interface StudentSessionSummary {
  session_id: string;
  assignment_id: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  questions_asked: number;
  responses_given: number;
}

export interface InstructorAssessmentSummary {
  session_id: string;
  student_id: string;
  assignment_id: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  questions_asked: number;
  responses_given: number;
}

// ============================================================
// Transcript
// ============================================================

export interface ExchangeOut {
  question_text: string;
  competency: string;
  difficulty: number;
  student_answer: string;
  asked_at: string;
  answered_at: string | null;
  response_time_seconds: number;
  evaluation_score: number | null;
  feedback_text: string | null;
  detected_misconceptions: string[] | null;
  score_justification: string | null;
  voice_intent: string | null;
  is_follow_up: boolean;
  question_type: "new" | "follow_up" | "re_ask";
}

export interface AssessmentTranscriptOut {
  session_id: string;
  student_id: string;
  assignment_id: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  code_context: string;
  exchanges: ExchangeOut[];
  final_score: number | null;
  max_score: number | null;
  competency_summary: CompetencySummary[] | null;
}

// ============================================================
// LLM Provider
// ============================================================

export interface ProviderInfo {
  active_provider: string;
  provider_display: string;
  supported_providers: string[];
}
```

---

## API Client to Create

Create `apps/web/lib/ivas-api.ts` — a typed API client for all IVAS endpoints:

```typescript
const IVAS_BASE_URL = process.env.NEXT_PUBLIC_IVAS_API_URL || 'https://ivas.sudila.com';

async function ivasRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${IVAS_BASE_URL}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || response.statusText);
  }

  if (response.status === 204) return {} as T;
  return response.json();
}

export const ivasApi = {
  // --- Health ---
  checkHealth: () => ivasRequest<any>('/health'),
  checkReady: () => ivasRequest<{ ready: boolean }>('/ready'),

  // --- Mock / LMS Data ---
  getAssignments: () => ivasRequest<{ data: IvasAssignment[] }>('/mock/assignments').then(r => r.data),
  getAssignment: (id: string) => ivasRequest<IvasAssignment>(`/mock/assignments/${encodeURIComponent(id)}`),
  getStudents: () => ivasRequest<{ data: IvasStudent[] }>('/mock/students').then(r => r.data),
  getStudent: (id: string) => ivasRequest<IvasStudent>(`/mock/students/${encodeURIComponent(id)}`),
  getStudentProgress: (id: string) => ivasRequest<any>(`/mock/students/${encodeURIComponent(id)}/progress`),
  getInstructors: () => ivasRequest<{ data: IvasInstructor[] }>('/mock/instructors').then(r => r.data),
  getInstructor: (id: string) => ivasRequest<IvasInstructor>(`/mock/instructors/${encodeURIComponent(id)}`),
  getCourses: () => ivasRequest<{ data: IvasCourse[] }>('/mock/courses').then(r => r.data),
  getCourse: (id: string) => ivasRequest<IvasCourse>(`/mock/courses/${encodeURIComponent(id)}`),

  // --- LLM Provider ---
  getProvider: () => ivasRequest<ProviderInfo>('/llm/provider'),
  switchProvider: (provider: string) =>
    ivasRequest<any>('/llm/provider/switch', { method: 'POST', body: JSON.stringify({ provider }) }),
  getProviderHealth: () => ivasRequest<any>('/llm/provider/health'),

  // --- Grading Criteria (Instructor) ---
  generateCriteria: (assignmentId: string, data: GenerateGradingCriteriaRequest) =>
    ivasRequest<GenerateGradingCriteriaResponse>(
      `/api/v1/assignments/${encodeURIComponent(assignmentId)}/grading-criteria/generate`,
      { method: 'POST', body: JSON.stringify(data) }
    ),
  getCriteria: (assignmentId: string) =>
    ivasRequest<{ data: GradingCriteria[] }>(
      `/api/v1/assignments/${encodeURIComponent(assignmentId)}/grading-criteria`
    ).then(r => r.data),
  updateCriteria: (criteriaId: string, data: UpdateGradingCriteriaRequest) =>
    ivasRequest<GradingCriteria>(
      `/api/v1/grading-criteria/${encodeURIComponent(criteriaId)}`,
      { method: 'PATCH', body: JSON.stringify(data) }
    ),

  // --- Questions (Instructor) ---
  generateQuestions: (
    assignmentId: string,
    params?: { criteria_id?: string; assignment_text?: string; num_questions?: number }
  ) => {
    const query = new URLSearchParams();
    if (params?.criteria_id) query.set('criteria_id', params.criteria_id);
    if (params?.assignment_text) query.set('assignment_text', params.assignment_text);
    if (params?.num_questions) query.set('num_questions', String(params.num_questions));
    const qs = query.toString();
    return ivasRequest<GenerateQuestionsResponse>(
      `/api/v1/assignments/${encodeURIComponent(assignmentId)}/questions/generate${qs ? `?${qs}` : ''}`,
      { method: 'POST' }
    );
  },
  getQuestions: (assignmentId: string, params?: { status?: string; competency?: string }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set('status', params.status);
    if (params?.competency) query.set('competency', params.competency);
    const qs = query.toString();
    return ivasRequest<{ data: IvasQuestion[] }>(
      `/api/v1/assignments/${encodeURIComponent(assignmentId)}/questions${qs ? `?${qs}` : ''}`
    ).then(r => r.data);
  },

  // --- Assessment Sessions ---
  triggerAssessment: (data: TriggerAssessmentRequest) =>
    ivasRequest<TriggerAssessmentResponse>('/api/v1/assessments/trigger', {
      method: 'POST', body: JSON.stringify(data),
    }),
  getSession: (sessionId: string) =>
    ivasRequest<SessionDetailsOut>(`/api/v1/assessments/sessions/${encodeURIComponent(sessionId)}`),
  submitResponse: (sessionId: string, data: SubmitResponseRequest) =>
    ivasRequest<SubmitResponseResponse>(
      `/api/v1/assessments/sessions/${encodeURIComponent(sessionId)}/respond`,
      { method: 'POST', body: JSON.stringify(data) }
    ),
  getTranscript: (sessionId: string) =>
    ivasRequest<AssessmentTranscriptOut>(
      `/api/v1/assessments/sessions/${encodeURIComponent(sessionId)}/transcript`
    ),
  abandonSession: (sessionId: string) =>
    ivasRequest<{ message: string }>(
      `/api/v1/assessments/sessions/${encodeURIComponent(sessionId)}/abandon`,
      { method: 'PUT' }
    ),

  // --- Student Portal ---
  getStudentSessions: (studentId: string, status?: string) => {
    const query = status ? `?status=${encodeURIComponent(status)}` : '';
    return ivasRequest<{ data: StudentSessionSummary[]; count: number }>(
      `/api/v1/students/${encodeURIComponent(studentId)}/sessions${query}`
    ).then(r => r.data);
  },

  // --- Instructor Portal ---
  getInstructorAssessments: (
    instructorId: string,
    params?: { assignment_ids?: string; assignment_id?: string; student_id?: string; status?: string; start_date?: string; end_date?: string }
  ) => {
    const query = new URLSearchParams();
    if (params?.assignment_ids) query.set('assignment_ids', params.assignment_ids);
    if (params?.assignment_id) query.set('assignment_id', params.assignment_id);
    if (params?.student_id) query.set('student_id', params.student_id);
    if (params?.status) query.set('status', params.status);
    if (params?.start_date) query.set('start_date', params.start_date);
    if (params?.end_date) query.set('end_date', params.end_date);
    const qs = query.toString();
    return ivasRequest<{ data: InstructorAssessmentSummary[]; count: number }>(
      `/api/v1/instructors/${encodeURIComponent(instructorId)}/assessments${qs ? `?${qs}` : ''}`
    ).then(r => r.data);
  },
};
```

**Note:** Import all the types from the types file at the top of the API client.

---

## Pages & Features to Implement

### IMPORTANT: Navigation Structure

Add an **"Assessments"** or **"Viva"** section to the existing sidebar/navigation. This should contain sub-navigation for both instructor and student views.

---

### Page 1: Instructor — Assignment Viva Setup (`/assessments/setup/[assignmentId]`)

**Purpose:** Instructor configures AI-generated grading criteria and questions for an assignment's viva.

**Layout:** Two-column — left panel for assignment info + actions, right panel for generated content.

**Left Panel:**
- Display assignment title and description (fetched from `/mock/assignments/:id`)
- Editable textarea for assignment text (used as input for AI generation)
- **Action Buttons:**
  1. **"Generate Grading Criteria"** — Calls `ivasApi.generateCriteria(assignmentId, { assignment_text, num_criteria: 5 })`
  2. **"Generate Questions"** — Calls `ivasApi.generateQuestions(assignmentId, { assignment_text, num_questions: 2 })` — disabled until criteria exist

**Right Panel:**
- **Grading Criteria Cards** — For each criterion, show:
  - Competency name, difficulty level badge, level label
  - Level description, marking criteria text
  - Programming language, learning objectives list
  - Edit button (inline edit or modal) → calls `ivasApi.updateCriteria()`
- **Generated Questions Section** — For each question, show:
  - Question text, expected answer (collapsible), difficulty badge, competency tag, status

**State Management:**
- Fetch criteria via `ivasApi.getCriteria(assignmentId)` on mount
- Fetch questions via `ivasApi.getQuestions(assignmentId)` on mount
- Show loading spinners during AI generation (can take 10-30s)
- Refresh data after generation completes

---

### Page 2: Instructor — Assessment Dashboard (`/assessments/dashboard`)

**Purpose:** Instructor monitors all viva sessions across their assignments.

**Features:**
- Fetch sessions via `ivasApi.getInstructorAssessments(instructorId, filters)`
- **Filters:** Assignment dropdown, Student search, Status (active/completed/abandoned), Date range
- **Table Columns:** Date, Session ID, Student Name, Assignment Title, Status Badge, Score (if completed), Actions
- **Status Badges:** Green = completed, Blue = in_progress, Gray = abandoned
- Click row → navigate to transcript/review page

**Score Display:** Show `final_score / max_score` and percentage for completed sessions.

---

### Page 3: Instructor — Session Review (`/assessments/review/[sessionId]`)

**Purpose:** Instructor reviews a completed (or in-progress) viva session.

**Top Section:**
- Session metadata: student name, assignment title, status, duration, final score
- Competency summary breakdown (if completed): progress bars per competency showing `score/max_score`

**Main Section — Transcript View:**
- Fetch via `ivasApi.getTranscript(sessionId)`
- Display each exchange chronologically:
  - **Question bubble** (left, assistant style): question_text, competency badge, difficulty badge, question_type indicator (new/follow_up/re_ask)
  - **Answer bubble** (right, user style): student_answer, response_time display
  - **Evaluation card** (below answer): evaluation_score/10 with color coding, feedback_text, detected_misconceptions (if any), score_justification
- Color-code scores: Red (0-3), Yellow (4-6), Green (7-10)
- Show follow-up chains visually (indent follow-ups under parent questions)

---

### Page 4: Student — My Assessments (`/assessments/my-sessions`)

**Purpose:** Student views their past and active viva sessions.

**Features:**
- Fetch via `ivasApi.getStudentSessions(studentId)`
- **Table/Card list:** Assignment title, Date, Status, Score (if completed), Action button
- Active sessions: "Continue" button → navigates to viva page
- Completed sessions: "View Results" → navigates to results page

---

### Page 5: Student — Viva Session (`/assessments/viva/[sessionId]`)

**Purpose:** The live, interactive viva examination chat interface. **This is the most critical page.**

**Session Header:**
- Session ID, status indicator (green pulse = active), assignment title
- Abandon button (with confirmation dialog) → calls `ivasApi.abandonSession()`
- Progress indicator: "Question X of Y" based on session details

**Chat Interface — CRITICAL IMPLEMENTATION DETAILS:**

The viva is NOT a simple chat. It follows a strict question-response-feedback loop:

1. **On Mount / Trigger:**
   - If new session: Call `ivasApi.triggerAssessment({ student_id, assignment_id })` → receive `first_question`
   - If resuming: Call `ivasApi.getSession(sessionId)` to get current state, then `ivasApi.getTranscript(sessionId)` to hydrate chat history

2. **Displaying Questions:**
   - Each `QuestionWithContext` from the API should render as an assistant message
   - Show the `question_text` as the message content
   - Show metadata: competency badge, difficulty indicator, hint (if provided)
   - If `is_follow_up` is true, show a "Follow-up" label
   - If `question_type` is "re_ask", show "Let's try this again" label

3. **Student Submits Response:**
   - Call `ivasApi.submitResponse(sessionId, { question_instance_id: currentQuestion.question_instance_id, response_text })`
   - The response returns `SubmitResponseResponse` which contains:
     - `evaluation_score` — Show score badge (0-10)
     - `feedback_text` — Show as assistant message (this is the AI's feedback to the student)
     - `detected_misconceptions` — Optionally show as subtle warning chips
     - `next_question` — If not null, this is the next question to display (could be a follow-up, re-ask, or new question)
     - `is_complete` — If true, session is over
     - `message` — System message (e.g., "All questions completed!")
     - `final_score`, `max_score`, `competency_summary` — Available when `is_complete` is true

4. **Message Flow Per Exchange:**
   ```
   [Assistant] Question text + metadata
   [User]      Student's typed answer
   [Assistant]  AI feedback + score badge
   [Assistant]  Next question (if any) OR completion message
   ```

5. **Session Completion:**
   - When `is_complete === true`, show a completion card:
     - Final score: `final_score / max_score`
     - Competency breakdown with progress bars
     - "View Full Results" button → navigate to results page
   - Disable the input area
   - Change status indicator to completed

6. **Handle Special Cases:**
   - If `feedback_text` contains teaching content (from `teach_and_skip` classification), show it styled differently (info box)
   - If `message` field has content, show as a system message (centered, subtle)
   - Handle 409 Conflict error (duplicate response) gracefully — show "Response already submitted"
   - Handle session not active (400) — show "Session ended" and disable input

**Input Area:**
- Textarea with placeholder "Type your answer..."
- Send button (disabled when empty or session not active)
- Enter to send, Shift+Enter for newline
- Disable during API call, show typing indicator

**State to Track:**
```typescript
const [session, setSession] = useState<SessionDetailsOut | null>(null);
const [currentQuestion, setCurrentQuestion] = useState<QuestionWithContext | null>(null);
const [messages, setMessages] = useState<ChatMessage[]>([]);
const [isComplete, setIsComplete] = useState(false);
const [sending, setSending] = useState(false);
```

Where `ChatMessage` is:
```typescript
interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  metadata?: {
    score?: number;
    competency?: string;
    difficulty?: number;
    questionType?: 'new' | 'follow_up' | 're_ask';
    isFeedback?: boolean;
    misconceptions?: string[];
  };
}
```

---

### Page 6: Student — Viva Results (`/assessments/results/[sessionId]`)

**Purpose:** Detailed results view after viva completion.

**Features:**
- Fetch via `ivasApi.getSession(sessionId)` + `ivasApi.getTranscript(sessionId)`
- **Score Header:** Large display of `final_score / max_score` with percentage
- **Competency Breakdown:** For each competency in `competency_summary`:
  - Competency name, score/max_score, progress bar with color coding
- **Exchange History:** Full transcript with:
  - Each question + student answer + AI feedback + score
  - Group by question chain (show follow-ups indented under parent)

---

### Page 7: Settings — LLM Provider (`/settings` or `/assessments/settings`)

**Purpose:** Admin/instructor configures the LLM provider powering IVAS.

**Features:**
- Fetch current provider via `ivasApi.getProvider()`
- Show supported providers as selectable cards/buttons
- Active provider highlighted
- Switch button → calls `ivasApi.switchProvider(providerName)`
- Health check display → calls `ivasApi.getProviderHealth()` — show "Connected" (green) or "Offline" (red)

---

## Key Implementation Notes

### 1. The Response Loop is NOT a Chat
Do **not** implement this as a free-form chat. The flow is strictly:
- Backend sends a question → student answers → backend evaluates and sends feedback + next question
- The `question_instance_id` from `QuestionWithContext` MUST be sent back with the student's response
- Track `currentQuestion` state and always send its `question_instance_id`

### 2. Handle the First Question from Trigger
When you call `triggerAssessment()`, the response includes `first_question`. Use this to display the first question immediately — don't make a separate call.

### 3. Transcript Hydration
When loading an existing session (e.g., page refresh during active session):
- Call `getSession()` to get current status and question instances
- Call `getTranscript()` to get full exchange history
- Map transcript `exchanges` to chat messages:
  - Each exchange has `question_text` (assistant) and `student_answer` (user) and `feedback_text` (assistant)
- Determine current question from session's `questions_asked` — the last one without a response is the current question

### 4. Loading States
AI generation can take 10-30 seconds. Show proper loading states:
- Spinning indicator with "AI is evaluating your response..." during `submitResponse`
- "Generating criteria..." during `generateCriteria`
- "Generating questions..." during `generateQuestions`

### 5. Error Handling
- 404: Session/resource not found → show "Not Found" page
- 409: Duplicate response → show toast "Response already submitted"
- 400: Session not active → disable input, show "Session has ended"
- 422: Validation error → show field-level errors
- Network errors → show retry option

### 6. Session Status Values
Backend uses `in_progress` (with underscore), not `active`. Map appropriately:
- `in_progress` → Show as "Active" / "Live" with green indicator
- `completed` → Show as "Completed" with checkmark
- `abandoned` → Show as "Abandoned" with gray indicator

### 7. Competency Summary Format
The `competency_summary` from the backend is an array of objects:
```json
[
  { "competency": "OOP Concepts", "score": 7.5, "max_score": 10, "questions_asked": 2 },
  { "competency": "Error Handling", "score": 5.0, "max_score": 10, "questions_asked": 1 }
]
```

### 8. Mock Data Note
The `/mock/*` endpoints simulate an LMS. In production, replace these calls with your actual LMS/academic service endpoints. The mock endpoints provide: assignments, students, instructors, courses. The actual IVAS functionality (criteria, questions, assessments) is real and persistent.

---

## Routing Summary

```
/assessments/setup/[assignmentId]    → Instructor: Configure criteria + questions
/assessments/dashboard               → Instructor: Monitor all sessions
/assessments/review/[sessionId]      → Instructor: Review transcript + scores
/assessments/my-sessions             → Student: View their sessions
/assessments/viva/[sessionId]        → Student: Live viva chat interface
/assessments/results/[sessionId]     → Student: View completed results
/settings                            → Admin: LLM provider configuration
```

---

## Environment Variable

Add to `.env.local`:
```
NEXT_PUBLIC_IVAS_API_URL=https://ivas.sudila.com
```

---

## Summary of Work

1. Create types file with all IVAS TypeScript interfaces
2. Create IVAS API client with all endpoints properly typed
3. Add IVAS navigation items to sidebar
4. Implement 7 pages as described above
5. The **Viva Session page** is the most complex — follow the question-response-feedback loop exactly as specified
6. Use proper loading states, error handling, and status mapping
7. Style consistently with the existing design system (Tailwind, same color patterns)
8. Replace `/mock/*` calls with real LMS data from your existing services where applicable
