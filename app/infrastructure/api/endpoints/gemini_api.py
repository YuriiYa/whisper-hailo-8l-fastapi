import asyncio
import logging

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from application.services.gemini_service import GeminiService
from infrastructure.config.services_config import get_gemini_service

router = APIRouter()
system_logger = logging.getLogger(__name__)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)


class AskResponse(BaseModel):
    answer: str


class GeminiReadinessResponse(BaseModel):
    ready: bool
    model: str
    detail: str


def config(app: FastAPI):
    app.include_router(router)


@router.get("/ask/health", response_model=GeminiReadinessResponse)
async def gemini_readiness(
    gemini_service: GeminiService = Depends(get_gemini_service),
):
    is_ready = bool(gemini_service.api_key)
    detail = "Gemini is configured" if is_ready else "GEMINI_API_KEY is not configured"
    return GeminiReadinessResponse(
        ready=is_ready,
        model=gemini_service.model,
        detail=detail,
    )


@router.post("/ask", response_model=AskResponse)
async def ask_gemini(
    payload: AskRequest,
    gemini_service: GeminiService = Depends(get_gemini_service),
):
    try:
        answer = await asyncio.to_thread(gemini_service.ask, payload.question)
        return AskResponse(answer=answer)
    except RuntimeError as e:
        system_logger.error("Error during Gemini request: %s", e)
        raise HTTPException(status_code=503, detail=str(e)) from e
