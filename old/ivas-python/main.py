import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.schemas import (
    GenerateQuestionsRequest,
    GenerateQuestionsResponse,
    HealthResponse,
)
from app.services.question_generator import question_generator

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="AI-powered question generation service using Ollama",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    ollama_available = question_generator.check_ollama_available()
    return HealthResponse(
        status="healthy" if ollama_available else "degraded",
        service="ivas-ai",
        ollama_available=ollama_available,
    )


@app.post("/ai/generate-questions", response_model=GenerateQuestionsResponse)
async def generate_questions(request: GenerateQuestionsRequest):
    """Generate assessment questions using AI."""
    logger.info(
        f"Generating questions for assignment: {request.assignment_id}, "
        f"competencies: {request.competencies}"
    )
    
    # Check if Ollama is available
    if not question_generator.check_ollama_available():
        raise HTTPException(
            status_code=503,
            detail="Ollama service is not available. Please ensure Ollama is running.",
        )
    
    # Generate questions
    questions = question_generator.generate_questions(request)
    
    if not questions:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate questions. Please try again.",
        )
    
    return GenerateQuestionsResponse(
        assignment_id=request.assignment_id,
        questions=questions,
        total_generated=len(questions),
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
