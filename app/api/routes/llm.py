"""LLM provider management endpoints — switch providers at runtime."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.llm_service import llm_service

router = APIRouter(prefix="/llm", tags=["llm"])


# ── Schemas ──────────────────────────────────────────────────────────

class SwitchProviderRequest(BaseModel):
    provider: str  # "ollama" or "gemini"


class ProviderInfo(BaseModel):
    active_provider: str
    provider_display: str
    supported_providers: list[str]


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/provider", response_model=ProviderInfo)
async def get_current_provider():
    """Return which LLM provider is currently active."""
    return llm_service.info()


@router.post("/provider/switch")
async def switch_provider(body: SwitchProviderRequest):
    """
    Hot-swap the LLM provider at runtime (no restart needed).

    Example body: { "provider": "gemini" }
    """
    try:
        result = llm_service.switch_provider(body.provider)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/provider/health")
async def provider_health():
    """Check if the current LLM provider is reachable."""
    available = llm_service.check_availability()
    return {
        "success": available,
        "provider": llm_service.active_provider_key,
        "status": "healthy" if available else "unhealthy",
    }
