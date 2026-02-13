# Complete Updated User Stories - Implementation Order

## Phase 1: Foundation & Core Assessment Engine
*Build the basic infrastructure first*

### Epic 1.1: Assignment & Question Management

**US-001** [Instructor]  
As an Instructor, I want to create a lab assignment with defined learning objectives and competency areas (e.g., "loops," "debugging," "recursion") so that the system knows what concepts to assess.

**US-002** [Instructor]  
As an Instructor, I want to request AI-generated questions based on specific lab exercises and competency areas with difficulty levels (1-5 scale) so that I have a context-aware question pool without writing everything from scratch.

**US-003** [Instructor]  
As an Instructor, I want to review, edit, delete, and approve AI-generated questions before they're used in student assessments so that I maintain quality control.

**US-004** [Instructor]  
As an Instructor, I want to manually create custom questions with rubrics and tag them by competency and difficulty so that I can add specialized questions the AI might not generate.

**US-005** [Instructor]  
As an Instructor, I want to mark certain questions as "required" or "adaptive pool" so that I can ensure critical concepts are always tested while allowing flexibility for others.

---

## Phase 2: Student Assessment Experience
*Enable students to take assessments*

### Epic 2.1: Basic Assessment Flow

**US-006** [Student]  
As a Student, I want the assessment to trigger automatically when I complete a specific coding task in the lab so that the questions are relevant to the code I just wrote.

**US-007** [System]  
As the System, I want to identify optimal moments during laboratory sessions to trigger assessments (e.g., when student completes a coding task, shows confusion patterns, or achieves a milestone) so that assessments are contextually relevant.

**US-008** [Student]  
As a Student, I want to answer assessment questions using text input explaining my code and thought process so that I can demonstrate my understanding.

**US-009** [Student]  
As a Student, I want to see questions that are tagged to the specific lab exercise I completed so that the assessment feels relevant and contextual.

**US-010** [System]  
As the System, I want to record student responses with timestamps and link them to specific questions and competencies so that I can analyze performance data.

### Epic 2.2: Voice Interface

**US-011** [Student]  
As a Student, I want to answer assessment questions verbally using natural speech so that I can explain my thought process without typing, simulating a real oral exam.

**US-012** [Student]  
As a Student, I want my speech to be accurately transcribed and saved so that I can review what I said and the system can evaluate it correctly.

---

## Phase 3: Adaptive & Intelligent Assessment
*Make assessments personalized and interactive*

### Epic 3.1: Adaptive Difficulty

**US-013** [Student]  
As a Student, I want questions to adjust in difficulty based on my previous answers so that I am challenged appropriately according to my current understanding level.

**US-014** [System]  
As the System, I want to select the next question from the approved pool based on the student's performance pattern (correct/incorrect, completeness of explanation) so that each student gets a personalized assessment path.

### Epic 3.2: Socratic Dialogue

**US-015** [Student]  
As a Student, I want the AI to ask probing follow-up questions rather than just marking me 'wrong' immediately so that I have a chance to self-correct and demonstrate deeper understanding.

**US-016** [Student]  
As a Student, I want follow-up questions to be conversational and context-aware (referencing my previous answer) so that it feels like a real discussion with an instructor.

**US-017** [System]  
As the System, I want to generate Socratic follow-up questions in real-time based on student responses that show partial understanding or misconceptions so that students can clarify their thinking.

---

## Phase 4: Feedback & Misconception Detection
*Close the loop with students and identify knowledge gaps*

### Epic 4.1: Immediate Feedback

**US-018** [Student]  
As a Student, I want to receive immediate feedback on my explanations that explains my specific misconceptions and reasoning gaps (not just "correct/incorrect") so that I understand where my logic is flawed.

**US-019** [Student]  
As a Student, I want feedback that highlights specific misconceptions (e.g., "You confused iteration with recursion here") rather than just a score so that I know exactly what to review.

**US-020** [System]  
As the System, I want to evaluate student responses against the rubric and expected key concepts using AI so that feedback is instant and consistent.

### Epic 4.2: Misconception Identification

**US-021** [Student]  
As a Student, I want the system to detect when I hold misconceptions (e.g., confusing loops with recursion) and explain them to me so that I can correct my understanding immediately.

**US-022** [System]  
As the System, I want to identify common misconception patterns across student responses (e.g., "confusing variable scope," "misunderstanding pointer behavior") so that instructors can address these systematically.

---

## Phase 5: Instructor Analytics & Intervention
*Give instructors insights and control*

### Epic 5.1: Dashboards & Visualization

**US-023** [Instructor]  
As an Instructor, I want to view a competency dashboard that visualizes individual student understanding across different concepts (e.g., algorithms, debugging) and highlights students at risk so that I can quickly see who is mastering material and who needs intervention.

**US-024** [Instructor]  
As an Instructor, I want to see class-wide patterns of specific misconceptions highlighted (e.g., "60% of students confuse loops with recursion") so that I can address these in my next lecture with targeted examples.

**US-025** [Instructor]  
As an Instructor, I want to drill down into individual student assessment transcripts and see their response patterns over time so that I can understand their specific learning journey.

### Epic 5.2: Proactive Support

**US-026** [Instructor]  
As an Instructor, I want to receive alerts for students at risk of conceptual misunderstanding (e.g., consistently low scores in "debugging" competency) so that I can offer proactive help before exams.

**US-027** [Instructor]  
As an Instructor, I want to filter at-risk alerts by competency, difficulty level, or time period so that I can prioritize my intervention efforts.

---

## Phase 6: Scale & Automation
*Handle large classes efficiently*

### Epic 6.1: Concurrent Assessment

**US-028** [Instructor]  
As an Instructor, I want the system to concurrently assess hundreds of students without my direct intervention so that every student gets a personalized assessment even in large classes.

**US-029** [System]  
As the System, I want to queue and process multiple student assessments in parallel while maintaining response quality so that no student experiences delays.

### Epic 6.2: Question Pool Intelligence

**US-030** [Instructor]  
As an Instructor, I want the system to suggest updating the question pool based on usage patterns (e.g., "Question Q-045 has been answered correctly 95% of the time—consider increasing difficulty") so that assessments remain appropriately challenging.

---

## Phase 7: Advanced Features & Integration
*Nice-to-haves for enhanced experience*

### Epic 7.1: Student Self-Assessment

**US-031** [Student]  
As a Student, I want to see my competency progress over multiple assessments visualized in a personal dashboard so that I can track my own learning growth.

### Epic 7.2: Data Export & LMS Integration

**US-032** [Instructor]  
As an Instructor, I want to export assessment data (CSV/JSON) for external analysis or integration with LMS grade books so that I can use the data in my existing workflows.

**US-033** [System]  
As the System, I want to integrate with existing Learning Management Systems via RESTful APIs so that assessment data flows seamlessly into institutional platforms.

---

## Future Enhancements (Out of Scope for Initial Release)

**FE-001** [Student]  
As a Student, I want to request a practice assessment (not graded) on specific competencies so that I can prepare for real assessments.

**FE-002** [Instructor]  
As an Instructor, I want to collaborate with other instructors by sharing approved question pools so that we can maintain consistency across course sections.

**FE-003** [Instructor]  
As an Instructor, I want to version-control my question pools and revert to previous versions if needed so that I can experiment with changes safely.
