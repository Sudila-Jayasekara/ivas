"""
Question Generator Service

Constructs detailed prompts and coordinates with the LLMService to generate
programming questions and rubrics based on competencies and difficulty levels.
Flow: Receives generation parameters from QuestionService, builds a strict prompt
to enforce uniqueness and format, sends it to the LLM, and parses the JSON response
into `GeneratedQuestionAI` schemas.
"""

import json
import logging

from app.config import settings
from app.schemas.question import GeneratedQuestionAI, RubricResponse
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class QuestionGenerator:
    """Generates assessment questions using configured LLM provider (Ollama or Gemini)."""

    def __init__(self) -> None:
        # Uses the centralised llm_service — no own provider instance
        logger.info("QuestionGenerator initialized (provider: %s)", llm_service.provider_name)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def check_ollama_available(self) -> bool:
        """Check if LLM provider is available. Kept for backward compatibility."""
        return self.check_llm_available()

    def check_llm_available(self) -> bool:
        """Check if the configured LLM provider is available."""
        try:
            return llm_service.check_availability()
        except Exception as e:
            logger.error("LLM provider %s not available: %s", llm_service.provider_name, e)
            return False

    # ------------------------------------------------------------------
    # Prompt
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        title: str,
        programming_language: str,
        competency: str,
        difficulty_min: int,
        difficulty_max: int,
        learning_objectives: list[str],
        num_questions: int,
        all_competencies: list[str] | None = None,
        previously_generated: list[dict] | None = None,
    ) -> str:

        objectives = ", ".join(learning_objectives)

        # Competency-specific focus areas to ensure distinct questions
        competency_focus = self._get_competency_focus(competency, all_competencies)

        # Per-level definitions with concrete examples
        level_definitions = {
            1: {
                "description": "Basic recall and identification. Student recalls a definition or identifies a single concept.",
                "cognitive_level": "Remember (Bloom's Level 1)",
                "question_starters": "What is..., Define..., Identify..., Name...",
                "example": f'What is a loop in {programming_language}? Why do programmers use loops instead of repeating code?',
                "NOT_allowed": "Comparisons, trade-offs, multi-step reasoning, scenario analysis",
            },
            2: {
                "description": "Basic comparison or simple explanation. Compare two BASIC concepts or explain simple behavior.",
                "cognitive_level": "Understand (Bloom's Level 2)",
                "question_starters": "Compare..., Explain the difference..., What happens when..., Describe...",
                "example": f'What is the difference between a for loop and a while loop in {programming_language}? When is each used?',
                "NOT_allowed": "Trade-off analysis, design decisions, debugging complex scenarios, advanced concepts (iterators, generators, protocols)",
            },
            3: {
                "description": "Trade-offs, intermediate analysis, choosing between approaches. May involve intermediate concepts.",
                "cognitive_level": "Apply + Analyze (Bloom's Levels 3-4)",
                "question_starters": "When would you choose..., What are the trade-offs..., Compare the advantages and disadvantages...",
                "example": f'When would you choose a while loop over a for loop? What are the trade-offs in terms of readability and control?',
                "NOT_allowed": "Simple definitions, basic comparisons without analysis, complex system design",
            },
            4: {
                "description": "Complex scenarios requiring multi-step reasoning, debugging, or combining multiple concepts.",
                "cognitive_level": "Analyze + Evaluate (Bloom's Levels 4-5)",
                "question_starters": "Given this scenario..., How would you debug..., What would happen if..., Analyze...",
                "example": f'A student writes a loop that runs indefinitely. What are the possible causes? How would you systematically diagnose and fix this?',
                "NOT_allowed": "Simple recall, basic comparisons",
            },
            5: {
                "description": "Advanced design, critical analysis, edge cases, system-level reasoning. Requires expertise.",
                "cognitive_level": "Evaluate + Create (Bloom's Levels 5-6)",
                "question_starters": "Design..., Critique..., What edge cases..., How would you architect...",
                "example": f'Design an approach to handle early termination in nested loops without using goto or exceptions. What are the implications for code maintainability?',
                "NOT_allowed": "Anything that doesn't require deep expertise and design thinking",
            },
        }

        # Build difficulty level descriptions for requested range
        difficulty_section = "DIFFICULTY LEVELS (your questions MUST use these levels):\n\n"
        for level in range(difficulty_min, difficulty_max + 1):
            defn = level_definitions[level]
            difficulty_section += f"""Level {level}: {defn['description']}
  Cognitive: {defn['cognitive_level']}
  Question starters: {defn['question_starters']}
  Example: {defn['example']}
  NOT allowed: {defn['NOT_allowed']}

"""

        # Question type diversity requirements
        question_types = [
            "Definition/Identification - Ask what something is and why it exists",
            "Comparison - Compare two concepts (must be appropriate for difficulty level)",
            "Scenario/Application - Given a situation, what approach and why",
            "Consequence/Prediction - What happens if X? Explain the behavior",
            "Trade-off Analysis - Advantages/disadvantages, when to choose what",
            "Debugging/Problem - What could cause X problem? How to fix?",
        ]
        
        types_str = "\n".join(f"  • {t}" for t in question_types)
        diversity_section = f"""
QUESTION TYPE DIVERSITY (MANDATORY):
{types_str}

RULES:
- Each question MUST be a DIFFERENT type from the list above
- If generating {num_questions} questions, use {num_questions} DIFFERENT types
- Do NOT generate multiple comparison questions
- Do NOT generate multiple scenario questions
- VARIETY IS MANDATORY
"""

        # Deduplication section
        dedup_section = ""
        if previously_generated:
            prev_list = []
            for i, pq in enumerate(previously_generated, 1):
                prev_list.append(f'  {i}. [{pq["competency"]}, L{pq["difficulty"]}] "{pq["question_text"]}"')
            
            dedup_section = f"""
{'='*70}
CRITICAL: AVOID DUPLICATES - ALREADY GENERATED QUESTIONS
{'='*70}
The following questions have ALREADY been generated.
You MUST generate COMPLETELY DIFFERENT questions.

Already Generated:
{chr(10).join(prev_list)}

FORBIDDEN:
- Do NOT ask about the same concept pair (e.g., if "for vs while" is above, DON'T ask it again)
- Do NOT use the same scenario (e.g., if "empty files" is above, choose different scenario)
- Do NOT rephrase existing questions
- If a topic is covered above, choose a DIFFERENT aspect of {competency}

REQUIRED:
- Your questions must cover NEW ground
- Choose different sub-topics within {competency}
- Use different question types
- Test different aspects of the competency
{'='*70}

"""

        # Forbidden topics (technically problematic questions)
        forbidden_section = """
FORBIDDEN TOPICS (DO NOT GENERATE):
❌ Memory usage differences between for/while loops (no real difference in Python)
❌ "Simple vs complex iteration" (not a technical distinction)
❌ "Advantages of iterator over for loop" (for loops USE iterators in Python)
❌ Any question based on false technical premises
❌ Questions too vague to answer clearly
❌ Questions requiring code writing, drawing, or diagrams
"""

        # Rubric requirements
        rubric_section = """
RUBRIC REQUIREMENTS:
✓ Be SPECIFIC about what concepts must be mentioned
✓ Define what earns full credit vs partial credit
✓ Avoid vague phrases: "demonstrate understanding", "provide valid reason"
✓ For comparisons: specify which aspects to compare (syntax? use cases? performance?)
✓ For scenarios: specify what decision and what reasoning
✓ Example GOOD rubric: "Full marks if student: (1) explains X concept, (2) identifies Y situation, (3) justifies choice with Z reasoning"
✓ Example BAD rubric: "Student should demonstrate understanding" (too vague)
"""

        # Main prompt
        prompt = f"""You are an expert programming instructor creating oral viva questions.

TASK: Generate {num_questions} UNIQUE viva voce question(s) for "{competency}".

{'='*70}
ASSIGNMENT CONTEXT
{'='*70}
Title: {title}
Language: {programming_language}
Target Competency: {competency}
Learning Objectives: {objectives}
Difficulty Range: Level {difficulty_min} to {difficulty_max}

{'='*70}
COMPETENCY FOCUS - READ CAREFULLY
{'='*70}
{competency_focus}

{'='*70}
{difficulty_section}
{'='*70}
{diversity_section}
{'='*70}
{dedup_section}
{'='*70}
{forbidden_section}
{'='*70}
{rubric_section}
{'='*70}

CRITICAL RULES:
1. Questions MUST be about "{competency}" specifically
2. Questions MUST test UNDERSTANDING, not syntax or code writing
3. Questions MUST be answerable VOCALLY (no code, no diagrams, no writing)
4. Each question MUST have difficulty between {difficulty_min} and {difficulty_max}
5. Each question MUST be a DIFFERENT type (no duplicate types)
6. Questions MUST be UNIQUE (no duplicates of previously generated questions)
7. Difficulty MUST match cognitive complexity (not just topic complexity)
8. Ask WHY and WHEN, not HOW TO write code
9. Grading criteria MUST be specific and actionable

DIFFICULTY CALIBRATION CHECKLIST:
- Level 1: Can student recall/identify? → Just needs to remember
- Level 2: Can student explain/compare basics? → Needs to understand
- Level 3: Can student analyze trade-offs? → Needs to apply knowledge
- Level 4: Can student solve complex problems? → Needs multi-step reasoning
- Level 5: Can student design solutions? → Needs expertise

BAD EXAMPLES (DO NOT GENERATE):
❌ "Explain how to write a for loop" (asks for syntax)
❌ "Show the code for..." (asks for code)
❌ "Draw a diagram of..." (not vocal)
❌ Same question rephrased (duplicate)
❌ Advanced topic (iterators) rated as Level 1-2 (wrong difficulty)

GOOD EXAMPLES (GENERATE LIKE THESE):
✓ "Why do we use loops instead of repeating code?" (Level 1 - recall purpose)
✓ "Compare for and while loops. When is each appropriate?" (Level 2 - basic comparison)
✓ "What are the trade-offs between break and return in loops?" (Level 3 - analysis)

OUTPUT FORMAT (JSON array):
[
  {{
    "question_text": "Your question about {competency} here",
    "difficulty": {difficulty_min},
    "expected_key_concepts": ["concept1", "concept2", "concept3"],
    "grading_criteria": "SPECIFIC criteria: Full marks if student (1)..., (2)..., (3)... Partial credit if...",
    "max_points": 10
  }}
]

FINAL CHECKLIST (verify before returning):
□ Is the question about "{competency}"? (not some other topic)
□ Is difficulty {difficulty_min}-{difficulty_max}? (not outside range)
□ Does difficulty match cognitive complexity? (not just topic difficulty)
□ Is each question a DIFFERENT type? (no duplicate types)
□ Are questions UNIQUE? (no overlap with previous questions)
□ Can questions be answered VOCALLY? (no code/diagrams needed)
□ Are grading criteria SPECIFIC? (not vague)
□ Are all {num_questions} questions generated?

Generate exactly {num_questions} question(s).
Return ONLY valid JSON array, no other text.
"""

        return prompt.strip()

    def _get_competency_focus(self, competency: str, all_competencies: list[str] | None) -> str:
        """Generate competency-specific focus areas to ensure distinct questions."""
        
        # Define what each competency should focus on
        competency_guides = {
            "loops": """
Focus on LOOP CONSTRUCTS themselves:
  • Purpose of loops (DRY principle, automation)
  • Loop types: for, while, do-while
  • When to choose for vs while
  • Loop termination conditions
  • Infinite loops and how to avoid them
  
AVOID (these belong to other competencies):
  • Generic iteration patterns → belongs to "iteration"
  • Break/continue/return → belongs to "control-flow"
  • Iterators/generators → belongs to "iteration"
""",
            "iteration": """
Focus on ITERATION PATTERNS and techniques:
  • Different ways to iterate (direct, enumerate, range, zip)
  • Iterators vs iterables
  • Generators and lazy evaluation
  • List comprehensions vs loops
  • When to use each iteration pattern
  
AVOID (these belong to other competencies):
  • Basic for/while loop syntax → belongs to "loops"
  • Control flow statements → belongs to "control-flow"
""",
            "control-flow": """
Focus on CONTROL FLOW STATEMENTS and logic:
  • Conditional statements (if/else)
  • Control flow in loops: break, continue, pass
  • Early returns vs nested conditionals
  • Short-circuit evaluation
  • Program flow and execution order
  
AVOID (these belong to other competencies):
  • Loop types themselves → belongs to "loops"
  • Iteration patterns → belongs to "iteration"
""",
            "functions": """
Focus on FUNCTIONS as reusable code blocks:
  • Purpose of functions (abstraction, reusability)
  • Function definition and calling
  • Return values vs side effects
  • Function composition
  
AVOID:
  • Parameter details → belongs to "parameters"
  • Variable visibility → belongs to "scope"
""",
            "scope": """
Focus on VARIABLE VISIBILITY and lifetime:
  • Local vs global scope
  • LEGB rule (Local, Enclosing, Global, Built-in)
  • Variable shadowing
  • Scope and nested functions
  • Lifetime of variables
""",
            "parameters": """
Focus on FUNCTION PARAMETERS and arguments:
  • Positional vs keyword arguments
  • Default parameters
  • *args and **kwargs
  • Mutable vs immutable arguments
  • Pass by reference vs pass by value concepts
""",
        }
        
        focus = competency_guides.get(competency.lower(), f"""
Your questions must focus specifically on "{competency}".
Ensure questions test understanding of this competency, not tangentially related topics.
""")
        
        # Add boundary information if multiple competencies
        if all_competencies and len(all_competencies) > 1:
            others = [c for c in all_competencies if c != competency]
            if others:
                others_str = ", ".join(f'"{c}"' for c in others)
                focus += f"""
OTHER COMPETENCIES being tested separately: {others_str}
→ Your questions for "{competency}" must NOT overlap with these other areas
→ Choose aspects of "{competency}" that are DISTINCT from {others_str}
→ If uncertain, ask: "Does this question fit better under a different competency?"
"""
        
        return focus

    # ------------------------------------------------------------------
    # Parse
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(
        response_text: str,
        competency: str,
        difficulty_min: int,
        difficulty_max: int,
    ) -> list[GeneratedQuestionAI]:
        try:
            text = response_text.strip()
            start_idx = text.find("[")
            end_idx = text.rfind("]") + 1
            if start_idx == -1 or end_idx == 0:
                logger.error("No JSON array found in response: %s", text[:200])
                return []

            questions_data = json.loads(text[start_idx:end_idx])
            questions: list[GeneratedQuestionAI] = []
            
            for q in questions_data:
                # Clamp difficulty to the requested range
                raw_difficulty = q.get("difficulty", difficulty_min)
                clamped_difficulty = max(difficulty_min, min(difficulty_max, raw_difficulty))
                
                if raw_difficulty != clamped_difficulty:
                    logger.warning(
                        "AI returned difficulty %d for competency '%s', clamped to %d (range %d-%d)",
                        raw_difficulty, competency, clamped_difficulty, difficulty_min, difficulty_max,
                    )

                question_text = q.get("question_text", "").strip()
                if not question_text:
                    logger.warning("Skipping empty question for competency '%s'", competency)
                    continue

                questions.append(
                    GeneratedQuestionAI(
                        question_text=question_text,
                        competency=competency,
                        difficulty=clamped_difficulty,
                        expected_key_concepts=q.get("expected_key_concepts", []),
                        rubric=RubricResponse(
                            expected_key_concepts=q.get("expected_key_concepts", []),
                            grading_criteria=q.get("grading_criteria", ""),
                            max_points=q.get("max_points", 10),
                        ),
                    )
                )
            
            return questions
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON: %s\nResponse: %s", e, response_text[:500])
            return []
        except Exception as e:
            logger.error("Error parsing response: %s", e)
            return []

    # ------------------------------------------------------------------
    # Generate
    # ------------------------------------------------------------------

    def generate_questions(
        self,
        *,
        title: str,
        competencies: list[str],
        learning_objectives: list[str],
        difficulty_min: int,
        difficulty_max: int,
        num_questions_per_competency: int,
        programming_language: str,
        existing_questions: list[dict] | None = None,
    ) -> list[GeneratedQuestionAI]:
        all_questions: list[GeneratedQuestionAI] = []

        for competency in competencies:
            logger.info("Generating %d questions for competency: %s", num_questions_per_competency, competency)

            # Build summary of previously generated questions for deduplication
            # Includes: (1) existing questions from DB, (2) questions generated in this session
            previously_generated = list(existing_questions) if existing_questions else []
            previously_generated.extend(
                {
                    "competency": q.competency,
                    "difficulty": q.difficulty,
                    "question_text": q.question_text,
                }
                for q in all_questions
            )

            prompt = self._build_prompt(
                title=title,
                programming_language=programming_language,
                competency=competency,
                difficulty_min=difficulty_min,
                difficulty_max=difficulty_max,
                learning_objectives=learning_objectives,
                num_questions=num_questions_per_competency,
                all_competencies=competencies,
                previously_generated=previously_generated if previously_generated else None,
            )
            
            try:
                logger.debug("Sending prompt to %s for competency: %s", llm_service.provider_name, competency)
                response_text = llm_service.generate(
                    prompt=prompt,
                    temperature=0.8,  # Slightly higher for more variety
                    num_predict=2500,  # More tokens for detailed rubrics
                    max_output_tokens=2500,  # For Gemini compatibility
                    top_p=0.9,
                )
                
                questions = self._parse_response(
                    response_text, competency, difficulty_min, difficulty_max
                )
                
                if len(questions) < num_questions_per_competency:
                    logger.warning(
                        "Only generated %d/%d questions for %s",
                        len(questions), num_questions_per_competency, competency
                    )
                
                all_questions.extend(questions)
                logger.info("Successfully generated %d questions for %s", len(questions), competency)
                
            except Exception as e:
                logger.error("Error generating questions for %s: %s", competency, e, exc_info=True)
                continue

        return all_questions


# Singleton
question_generator = QuestionGenerator()