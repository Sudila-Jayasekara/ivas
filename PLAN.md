# IVAS 2-Week Code-Red Plan

---

## WEEK 1 — Core Intelligence

### Day 1-2: LLM Answer Evaluation + Scoring

✅ 1. Add `evaluation_score`, `feedback_text`, `detected_misconceptions` fields to `StudentResponse` model

✅ 2. Build an evaluation prompt (question + expected answer + rubric + student answer → LLM returns score + feedback JSON)

✅ 3. Call evaluation in `submit_response()` — score every answer as it comes in

✅ 4. Return score + feedback in `SubmitResponseResponse` to the student

✅ 5. Populate `response_competency_links` table with per-competency scores

---

### Day 3: Adaptive Question Selection

⚠️ 6. Replace static ascending-difficulty selection with adaptive logic — if last score high → increase difficulty, if low → decrease or stay
> Questions are sorted by difficulty ascending but there is no dynamic adjustment based on the student's score. Needs real branching logic.

❌ 7. Use competency coverage — pick next question from least-covered competency

❌ 8. Make `max_questions` configurable per assignment (not hardcoded 3)

---

### Day 4-5: Socratic Follow-up Questions

✅ 9. Add `follow_up_depth` and `parent_instance_id` fields to `AssessmentQuestionInstance` model

✅ 10. After evaluating a response, if partial understanding detected → generate a Socratic follow-up via LLM instead of moving to next bank question

✅ 11. Cap follow-ups at max 1-2 per question then move on

✅ 12. Store follow-ups as question instances linked to the parent so transcript stays clean

---

### Day 6: Misconception Detection

❌ 13. Create `misconceptions` table (`id`, `assignment_id`, `competency`, `misconception_text`, `frequency`, `student_ids`)
> Misconceptions are detected and stored per-response as JSONB but there is no dedicated aggregation table.

⚠️ 14. Extract misconceptions from evaluation responses and aggregate into the table
> LLM detects and stores misconceptions per response. Aggregation into a shared table with frequency tracking is not implemented.

❌ 15. Add `GET /assignments/{id}/misconceptions` endpoint for instructors

---

## WEEK 2 — Voice, Analytics, Polish

### Day 7-8: Voice Input via Gemini Live Audio API

✅ 16. Add a WebSocket endpoint `WS /assessments/sessions/{session_id}/voice` for real-time audio streaming

✅ 17. Integrate Gemini Live Audio API for speech-to-text (student speaks → transcription)

✅ 18. Pipe transcribed text into `submit_response()` flow (set `response_type="audio"`, save `transcript_text`)

✅ 19. Optionally use Gemini audio to read questions aloud (text-to-speech back over WebSocket)

---

### Day 9-10: Instructor Analytics Endpoints

❌ 20. `GET /assignments/{id}/analytics` — class-wide stats: avg score by competency, difficulty distribution, completion rates

❌ 21. `GET /assignments/{id}/analytics/competency-heatmap` — competency × student score matrix

❌ 22. `GET /assignments/{id}/analytics/at-risk-students` — students below threshold in any competency

❌ 23. `GET /students/{id}/progress` — real per-student competency progress over time (replace mock)

❌ 24. `GET /assignments/{id}/analytics/misconceptions` — top misconceptions with frequency + affected students

---

### Day 11: Session Completion Summary + Student Feedback

❌ 25. When session completes, generate a final LLM summary: overall score, strengths, weaknesses, misconceptions, study recommendations
> Session completion only runs numeric score aggregation. No LLM narrative summary is generated.

⚠️ 26. Add `final_score`, `summary_feedback` fields to `AssessmentSession`
> `final_score` and `max_score` exist. `summary_feedback` field does not exist yet.

⚠️ 27. Return full feedback in session details and transcript endpoints
> Structured `competency_summary` is returned. No LLM-generated narrative feedback is returned anywhere.

---

### Day 12: Question Approval Workflow + Quality

❌ 28. Change question generation to save as draft (not auto-approve)
> Questions are created with `status="approved"` immediately on generation.

❌ 29. Add `PATCH /questions/{id}` — edit question text, expected answer, difficulty

❌ 30. Add `PATCH /questions/{id}/approve` and `PATCH /questions/{id}/reject` endpoints

❌ 31. Add question effectiveness tracking (avg score, discrimination index) updated after each session

---

### Day 13-14: Integration Testing + Hardening

❌ 32. End-to-end test: generate criteria → generate questions → approve → trigger assessment → answer with voice → get adaptive questions → Socratic follow-ups → completion with feedback

⚠️ 33. Add basic error handling, rate limiting on LLM calls, request validation
> Per-service error handling exists. No rate limiting on LLM calls.

❌ 34. Data export: `GET /assignments/{id}/export` — CSV/JSON dump of all session data for LMS integration

---

## Progress

✅ Done — 13 of 34
⚠️ Partial — 4 of 34
❌ Not started — 17 of 34
