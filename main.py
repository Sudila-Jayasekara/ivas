"""
Main Application Entrypoint

This file initializes the FastAPI application, configures middleware,
sets up the application lifespan (database connection and shutdown),
and includes all the API routers. The flow of a request starts here
and is routed to the appropriate endpoint defined in app/api/routes.
"""

import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db, close_db
from app.middleware.request_logger import RequestLoggerMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.mock import router as mock_router
from app.api.routes.grading_criteria import router as grading_criteria_router
from app.api.routes.questions import router as questions_router
from app.api.routes.assessments import router as assessments_router
from app.api.routes.students import router as students_router
from app.api.routes.instructors import router as instructors_router
from app.api.routes.llm import router as llm_router
from app.api.routes.voice import router as voice_router

# --- logging ---

logging.basicConfig(
    level=logging.DEBUG if settings.app_debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# --- lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting %s (env=%s, debug=%s)",
        settings.app_name,
        settings.app_env,
        settings.app_debug,
    )
    await init_db()
    yield
    await close_db()
    logger.info("Shutdown complete")


# --- app ---

app = FastAPI(
    title=settings.app_name,
    description="Intelligent Viva Assessment System – unified API",
    version="1.0.0",
    lifespan=lifespan,
)

# --- middleware ---

app.add_middleware(RequestLoggerMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- routes ---

app.include_router(health_router)
app.include_router(mock_router)
app.include_router(llm_router)

# All v1 routes
app.include_router(grading_criteria_router, prefix="/api/v1")
app.include_router(questions_router, prefix="/api/v1")
app.include_router(assessments_router, prefix="/api/v1")
app.include_router(voice_router, prefix="/api/v1")
app.include_router(students_router, prefix="/api/v1")
app.include_router(instructors_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.app_debug,
    )
