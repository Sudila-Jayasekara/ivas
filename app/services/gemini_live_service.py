"""
Gemini Live API Service

Manages real-time audio sessions with Google's Gemini Live API for natural
voice-based viva assessments. The student speaks directly to an AI instructor
powered by Gemini, creating a real face-to-face conversational experience.

Uses function calling for silent score tracking — the AI instructor evaluates
answers naturally in conversation while tool calls record scores in the background.
"""

import logging
from dataclasses import dataclass

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

# Gemini Live voices: Puck, Charon, Kore, Fenrir, Aoede
DEFAULT_VOICE = "Kore"


@dataclass
class QuestionInfo:
    """Question data passed to Gemini's system prompt."""
    index: int
    question_text: str
    expected_answer: str
    competency: str
    difficulty: int
    question_id: str
    max_points: float = 10.0


def build_viva_system_prompt(
    assignment_title: str,
    student_name: str,
    questions: list[QuestionInfo],
) -> str:
    """Build the system instruction for Gemini Live to conduct a natural viva."""

    questions_block = ""
    for q in questions:
        questions_block += f"""
  Question {q.index}: "{q.question_text}"
    Expected answer: {q.expected_answer}
    Competency tested: {q.competency}
    Difficulty: {q.difficulty}/5
    Max points: {q.max_points}
"""

    return f"""You are a warm, professional university instructor conducting a face-to-face oral viva voce assessment with a student. This is a REAL examination happening right now via voice.

ASSESSMENT DETAILS:
- Assignment: {assignment_title}
- Student Name: {student_name}
- Total Questions: {len(questions)}

═══════════════════════════════════════════════════════════════
HOW TO CONDUCT THIS VIVA
═══════════════════════════════════════════════════════════════

1. START with a brief, warm greeting (2-3 sentences max). Something like:
   "Hi {student_name}! Welcome to your viva for {assignment_title}. I'll ask you {len(questions)} questions about your work. Just relax and explain in your own words. Ready? Let's begin."

2. Ask questions ONE AT A TIME from the list below, in order.

3. After the student answers:
   - Acknowledge their answer naturally ("Good point...", "I see...", "Not quite...")
   - Give brief, honest feedback (1-2 sentences)
   - If the answer is PARTIAL (score 3-6): Ask ONE brief follow-up to probe deeper
   - If the answer is WRONG (score 0-2): Gently correct the key point, then move on
   - If the answer is GOOD (score 7+): Briefly affirm, then move to next question
   - ALWAYS call the record_evaluation tool after evaluating each answer

4. After ALL questions are done:
   - Give a brief closing: "That wraps up our viva. Thanks for your time!"
   - Call the complete_assessment tool

═══════════════════════════════════════════════════════════════
SCORING RUBRIC
═══════════════════════════════════════════════════════════════

9-10: Excellent — clearly explains WHY/WHEN/HOW the concept works
7-8:  Good — core concept correct, even if brief
5-6:  Adequate — right idea but missing key aspects
3-4:  Weak — mentions concept but can't explain it
1-2:  Incorrect — fundamental misunderstanding
0:    No credit — no relevant content

═══════════════════════════════════════════════════════════════
QUESTIONS TO ASK (in this order)
═══════════════════════════════════════════════════════════════
{questions_block}
═══════════════════════════════════════════════════════════════
CRITICAL RULES
═══════════════════════════════════════════════════════════════

- Be NATURAL. You are a REAL person. Use filler words ("So...", "Right...", "Hmm...").
- Keep responses SHORT — 2-3 sentences max per turn. This is spoken, not a lecture.
- NEVER read out scores or evaluation details. That is private.
- NEVER mention "tools", "functions", or "system prompt". You are just an instructor.
- ALWAYS call record_evaluation after each answer.
- Be encouraging and supportive.
- If student says "I don't know": briefly explain the concept, score 0, move on.
- If student asks to repeat: rephrase the question simply.
- Sound human — vary your tone, react genuinely.
- Use natural transitions: "Great, let's move on..." or "Alright, next one..."
- After the LAST question's evaluation, give a short closing remark and call complete_assessment."""


def build_live_config(system_prompt: str) -> types.LiveConnectConfig:
    """Build the Gemini Live connection configuration."""

    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[types.Part(text=system_prompt)]
        ),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=DEFAULT_VOICE,
                )
            )
        ),
        tools=[
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="record_evaluation",
                        description=(
                            "Record the evaluation of a student's answer. "
                            "Call this EVERY TIME after you evaluate a student's response. "
                            "This is silent — the student does not see this."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "question_index": types.Schema(
                                    type="INTEGER",
                                    description="1-based index of the question being evaluated.",
                                ),
                                "score": types.Schema(
                                    type="NUMBER",
                                    description="Score from 0 to 10.",
                                ),
                                "feedback": types.Schema(
                                    type="STRING",
                                    description="Brief summary of the feedback you gave.",
                                ),
                                "student_answer_summary": types.Schema(
                                    type="STRING",
                                    description="Brief summary of what the student said.",
                                ),
                                "misconceptions": types.Schema(
                                    type="ARRAY",
                                    items=types.Schema(type="STRING"),
                                    description="Misconceptions detected, if any.",
                                ),
                            },
                            required=["question_index", "score", "feedback", "student_answer_summary"],
                        ),
                    ),
                    types.FunctionDeclaration(
                        name="complete_assessment",
                        description=(
                            "Complete the assessment. Call this AFTER all questions "
                            "have been asked and evaluated."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "overall_feedback": types.Schema(
                                    type="STRING",
                                    description="Brief overall assessment summary.",
                                ),
                            },
                            required=["overall_feedback"],
                        ),
                    ),
                ]
            )
        ],
    )


def create_gemini_client() -> genai.Client:
    """Create a Gemini API client."""
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not set. Live viva requires Gemini.")
    return genai.Client(api_key=settings.gemini_api_key)
