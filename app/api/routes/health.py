from fastapi import APIRouter

from app.database import health_check
from app.services.question_generator import question_generator

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    services: dict[str, str] = {}
    all_healthy = True

    db_ok = await health_check()
    services["database"] = "healthy" if db_ok else "unhealthy"
    if not db_ok:
        all_healthy = False

    ollama_ok = question_generator.check_ollama_available()
    services["ollama"] = "healthy" if ollama_ok else "unhealthy"
    if not ollama_ok:
        all_healthy = False

    status = "healthy" if all_healthy else "unhealthy"
    return {
        "success": all_healthy,
        "message": status,
        "data": {"status": status, "services": services},
    }


@router.get("/ready")
async def ready():
    db_ok = await health_check()
    if not db_ok:
        return {"success": False, "message": "Service not ready"}
    return {"success": True, "message": "Service is ready"}
