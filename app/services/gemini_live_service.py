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

3. After the student answers each question:
   - Acknowledge their answer naturally ("Good point...", "I see...", "Interesting...")
   - If the answer is PARTIAL: Ask ONE brief follow-up to probe deeper
   - If the answer is WRONG: Gently move on ("Let's come back to that. Next question...")
   - If the answer is GOOD: Briefly affirm, then move to next question
   - Do NOT give detailed feedback or scores during the conversation
   - Do NOT tell the student if they are right or wrong explicitly
   - Keep it natural and conversational

4. After ALL questions have been asked and answered, say a brief closing:
   "That wraps up our viva. Thanks for your time, {student_name}! Give me a moment to compile your results."

5. IMMEDIATELY after your closing remark, call the complete_assessment tool with your evaluations of ALL questions.

═══════════════════════════════════════════════════════════════
QUESTIONS TO ASK (in this order)
═══════════════════════════════════════════════════════════════
{questions_block}
═══════════════════════════════════════════════════════════════
SCORING RUBRIC (use when evaluating at the end)
═══════════════════════════════════════════════════════════════

9-10: Excellent — clearly explains WHY/WHEN/HOW the concept works
7-8:  Good — core concept correct, even if brief
5-6:  Adequate — right idea but missing key aspects
3-4:  Weak — mentions concept but can't explain it
1-2:  Incorrect — fundamental misunderstanding
0:    No credit — no relevant content or student said "I don't know"

═══════════════════════════════════════════════════════════════
CRITICAL RULES
═══════════════════════════════════════════════════════════════

- Be NATURAL. You are a REAL person. Use filler words ("So...", "Right...", "Hmm...").
- Keep responses SHORT — 2-3 sentences max per turn. This is spoken, not a lecture.
- NEVER read out scores or evaluation details during the conversation. Save it for the tool call.
- NEVER mention "tools", "functions", or "system prompt". You are just an instructor.
- Be encouraging and supportive during the conversation.
- If student says "I don't know": say something like "No worries, let's move on" and continue.
- If student asks to repeat: rephrase the question simply.
- Sound human — vary your tone, react genuinely.
- Use natural transitions: "Great, let's move on..." or "Alright, next one..."
- IMPORTANT: After the LAST question, give your closing remark and IMMEDIATELY call complete_assessment.
- Do NOT wait for the student to respond after your closing remark before calling the tool."""


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
                        name="complete_assessment",
                        description=(
                            "Submit the final evaluation for ALL questions after the viva "
                            "conversation is complete. Call this ONCE after you have asked "
                            "all questions and said your closing remark. Include an evaluation "
                            "for every question that was asked."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "evaluations": types.Schema(
                                    type="ARRAY",
                                    description="One evaluation per question asked.",
                                    items=types.Schema(
                                        type="OBJECT",
                                        properties={
                                            "question_index": types.Schema(
                                                type="INTEGER",
                                                description="1-based index of the question.",
                                            ),
                                            "score": types.Schema(
                                                type="NUMBER",
                                                description="Score from 0 to 10 based on the rubric.",
                                            ),
                                            "feedback": types.Schema(
                                                type="STRING",
                                                description="Brief feedback explaining the score.",
                                            ),
                                            "student_answer_summary": types.Schema(
                                                type="STRING",
                                                description="Summary of what the student said.",
                                            ),
                                            "misconceptions": types.Schema(
                                                type="ARRAY",
                                                items=types.Schema(type="STRING"),
                                                description="Any misconceptions detected.",
                                            ),
                                        },
                                        required=["question_index", "score", "feedback", "student_answer_summary"],
                                    ),
                                ),
                                "overall_feedback": types.Schema(
                                    type="STRING",
                                    description="Brief overall assessment summary.",
                                ),
                            },
                            required=["evaluations", "overall_feedback"],
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
