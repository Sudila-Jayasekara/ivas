import json
import logging
from typing import Optional

import ollama
from ollama import Client

from app.config import settings
from app.schemas import (
    GenerateQuestionsRequest,
    GeneratedQuestion,
    RubricResponse,
)

logger = logging.getLogger(__name__)


class QuestionGenerator:
    """Generates assessment questions using Ollama LLM."""

    def __init__(self):
        self.client = Client(host=settings.ollama_host)
        self.model = settings.ollama_model

    def check_ollama_available(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            models = self.client.list()
            model_names = [m.model for m in models.models]
            return any(self.model in name for name in model_names)
        except Exception as e:
            logger.error(f"Ollama not available: {e}")
            return False

    def _build_prompt(self, request: GenerateQuestionsRequest, competency: str) -> str:
        """Build the prompt for question generation."""
        return f"""You are an expert programming instructor creating assessment questions.

Generate {request.num_questions_per_competency} unique viva voce (oral exam) questions for a programming assignment.

**Assignment Details:**
- Title: {request.title}
- Programming Language: {request.programming_language}
- Target Competency: {competency}
- Difficulty Range: {request.difficulty_range.min} to {request.difficulty_range.max} (scale 1-5)
- Learning Objectives: {', '.join(request.learning_objectives)}

**Requirements:**
1. Questions should test understanding of "{competency}" concept
2. Each question should have a different difficulty level within the range
3. Questions should be open-ended, suitable for verbal answers
4. Include expected key concepts the student should mention
5. Provide grading criteria

**Output Format (JSON array):**
```json
[
  {{
    "question_text": "Explain how...",
    "difficulty": 2,
    "expected_key_concepts": ["concept1", "concept2"],
    "grading_criteria": "Full marks if student explains...",
    "max_points": 10
  }}
]
```

Generate exactly {request.num_questions_per_competency} questions. Return ONLY valid JSON array, no other text."""

    def _parse_response(
        self, response_text: str, competency: str
    ) -> list[GeneratedQuestion]:
        """Parse LLM response into structured questions."""
        try:
            # Extract JSON from response
            text = response_text.strip()
            
            # Find JSON array in response
            start_idx = text.find("[")
            end_idx = text.rfind("]") + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.error(f"No JSON array found in response: {text[:200]}")
                return []
            
            json_str = text[start_idx:end_idx]
            questions_data = json.loads(json_str)
            
            questions = []
            for q in questions_data:
                questions.append(
                    GeneratedQuestion(
                        question_text=q.get("question_text", ""),
                        competency=competency,
                        difficulty=q.get("difficulty", 3),
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
            logger.error(f"Failed to parse JSON: {e}\nResponse: {response_text[:500]}")
            return []

    def generate_questions(
        self, request: GenerateQuestionsRequest
    ) -> list[GeneratedQuestion]:
        """Generate questions for all competencies."""
        all_questions = []
        
        for competency in request.competencies:
            logger.info(f"Generating questions for competency: {competency}")
            
            prompt = self._build_prompt(request, competency)
            
            try:
                response = self.client.generate(
                    model=self.model,
                    prompt=prompt,
                    options={
                        "temperature": 0.7,
                        "num_predict": 2000,
                    },
                )
                
                questions = self._parse_response(response.response, competency)
                all_questions.extend(questions)
                
                logger.info(
                    f"Generated {len(questions)} questions for {competency}"
                )
                
            except Exception as e:
                logger.error(f"Error generating questions for {competency}: {e}")
                continue
        
        return all_questions


# Singleton instance
question_generator = QuestionGenerator()
