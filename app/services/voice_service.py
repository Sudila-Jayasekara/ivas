"""
Voice Service

Provides intent classification and conversational response generation
for voice-based assessments. Sits between the WebSocket route and the
assessment pipeline to detect whether the student is answering, asking
for clarification, requesting a repeat, or asking a topic question.

Only confirmed answer attempts are forwarded to the assessment pipeline.
Everything else gets a conversational instructor response.
"""

import json
import logging
from dataclasses import dataclass
from enum import Enum

from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class StudentIntent(str, Enum):
    ANSWER_ATTEMPT = "answer_attempt"
    CLARIFICATION_REQUEST = "clarification_request"
    REPEAT_REQUEST = "repeat_request"
    TOPIC_QUESTION = "topic_question"
    OFF_TOPIC = "off_topic"


@dataclass
class ClassificationResult:
    intent: StudentIntent
    confidence: float  # 0.0–1.0 (informational)


# ── Prompts ───────────────────────────────────────────────────────────

CLASSIFICATION_PROMPT = """You are classifying a student's speech during an oral programming exam.

CURRENT QUESTION BEING ASKED: {question_text}

STUDENT SAID: "{student_text}"

Classify the student's intent as exactly ONE of:
- answer_attempt: Student is trying to answer the current question (even partially or incorrectly)
- clarification_request: Student wants the question explained or clarified
- repeat_request: Student wants the question repeated or said again
- topic_question: Student is asking a related question about the topic
- off_topic: Student said something completely unrelated

Return ONLY valid JSON: {{"intent": "...", "confidence": 0.95}}"""

RESPONSE_PROMPTS = {
    StudentIntent.CLARIFICATION_REQUEST: """You are a friendly programming instructor during an oral exam.
The student asked for clarification on this question:

QUESTION: {question_text}
STUDENT SAID: "{student_text}"

Provide a brief clarification that helps them understand what is being asked WITHOUT revealing the answer.
Keep it to 2-3 sentences. Be encouraging.
Return ONLY your response text, nothing else.""",

    StudentIntent.TOPIC_QUESTION: """You are a friendly programming instructor during an oral exam.
The student asked a related question about the topic:

CURRENT ASSESSMENT QUESTION: {question_text}
STUDENT ASKED: "{student_text}"

Give a brief, helpful response (2-3 sentences). Guide their thinking without giving away the answer to the assessment question.
Then gently redirect them back to answering the assessment question.
Return ONLY your response text, nothing else.""",
}

# Patterns that can be detected without an LLM call
_REPEAT_KEYWORDS = [
    "repeat", "say that again", "come again", "what was the question",
    "can you repeat", "say again", "one more time", "didn't hear",
    "pardon", "sorry what", "tell me again", "ask again",
]


# ── Service ───────────────────────────────────────────────────────────

class VoiceService:
    """Intent classification and conversational response generation."""

    @staticmethod
    def _quick_classify(text: str) -> ClassificationResult | None:
        """Fast regex-based classification for obvious cases. Returns None to fall through to LLM."""
        lower = text.lower().strip()
        for pattern in _REPEAT_KEYWORDS:
            if pattern in lower:
                return ClassificationResult(
                    intent=StudentIntent.REPEAT_REQUEST, confidence=1.0
                )
        return None

    @staticmethod
    def _parse_classification(raw: str) -> ClassificationResult:
        """Parse LLM JSON classification. Falls back to ANSWER_ATTEMPT on any error."""
        try:
            text = raw.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end == 0:
                return ClassificationResult(
                    intent=StudentIntent.ANSWER_ATTEMPT, confidence=0.0
                )
            data = json.loads(text[start:end])
            intent = StudentIntent(data["intent"])
            confidence = float(data.get("confidence", 0.8))
            return ClassificationResult(intent=intent, confidence=confidence)
        except (json.JSONDecodeError, ValueError, KeyError):
            return ClassificationResult(
                intent=StudentIntent.ANSWER_ATTEMPT, confidence=0.0
            )

    def classify_intent(
        self, student_text: str, question_text: str
    ) -> ClassificationResult:
        """
        Classify student speech intent. SYNCHRONOUS — call via run_in_executor.

        Falls back to ANSWER_ATTEMPT if anything goes wrong.
        """
        # Try fast path first
        quick = self._quick_classify(student_text)
        if quick is not None:
            logger.debug("Quick classified as %s: %s", quick.intent, student_text[:80])
            return quick

        try:
            raw = llm_service.generate(
                prompt=CLASSIFICATION_PROMPT.format(
                    question_text=question_text,
                    student_text=student_text,
                ),
                temperature=0.1,
                max_output_tokens=100,
                num_predict=100,
            )
            result = self._parse_classification(raw)
            logger.debug(
                "LLM classified as %s (%.0f%%): %s",
                result.intent, result.confidence * 100, student_text[:80],
            )
            return result
        except Exception as e:
            logger.error("Intent classification failed: %s", e)
            return ClassificationResult(
                intent=StudentIntent.ANSWER_ATTEMPT, confidence=0.0
            )

    def generate_conversational_response(
        self,
        intent: StudentIntent,
        student_text: str,
        question_text: str,
    ) -> str:
        """
        Generate an instructor-like response for non-answer intents. SYNCHRONOUS.

        For REPEAT_REQUEST and OFF_TOPIC, returns canned responses (no LLM call).
        For CLARIFICATION_REQUEST and TOPIC_QUESTION, uses the LLM.
        """
        if intent == StudentIntent.REPEAT_REQUEST:
            return "Sure, let me repeat the question for you."

        if intent == StudentIntent.OFF_TOPIC:
            return (
                "Let's stay focused on the assessment. "
                "I'll repeat the current question for you."
            )

        template = RESPONSE_PROMPTS.get(intent)
        if not template:
            return "Let's continue with the assessment."

        try:
            raw = llm_service.generate(
                prompt=template.format(
                    question_text=question_text,
                    student_text=student_text,
                ),
                temperature=0.5,
                max_output_tokens=300,
                num_predict=300,
            )
            text = raw.strip().strip('"').strip("'")
            return text if text else "Let's continue with the current question."
        except Exception as e:
            logger.error("Conversational response generation failed: %s", e)
            return "Let me rephrase — please try to answer the current question."


# Singleton
voice_service = VoiceService()
