import os
import logging
from fastapi import APIRouter, Response, FastAPI, UploadFile, File, Depends
from pydantic import BaseModel, Field
from tempfile import NamedTemporaryFile
from infrastructure.config.whisper_hailo import get_whisper_hailo, get_whisper_hailo_lock
from infrastructure.config.runtime_env import RuntimeEnvConfig

from application.services.tts_service import TTSService
from application.services.whisper_service import WhisperService
from infrastructure.config.services_config import get_whisper_service, get_tts_service

router = APIRouter()

system_logger = logging.getLogger(__name__)


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice: str | None = None
    speed: int | None = Field(default=None, ge=80, le=450)


def config(app: FastAPI):
    app.include_router(router)


@router.post("/transcribe")
async def transcribe_audio(
    response: Response,
    file: UploadFile = File(...),
    whisper_service: WhisperService = Depends(get_whisper_service),
):

    runtime_env = RuntimeEnvConfig.from_env()

    if runtime_env.can_transcribe:
        suffix = os.path.splitext(file.filename)[1]
        with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        whisper_hailo = get_whisper_hailo()
        try:
            async with get_whisper_hailo_lock():
                result = await whisper_service.transcribe_audio(whisper_hailo, audio_file_path=tmp_path)
        except Exception as e:
            system_logger.error(f"Error during transcription: {e}")
            response.status_code = 500
            return {"error": "An error occurred during transcription."}
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        return {"message": result}
    else:
        return {"message": "Server in debug mode"}


@router.post("/tts")
async def text_to_speech(
    payload: TTSRequest,
    tts_service: TTSService = Depends(get_tts_service),
):
    try:
        wav_bytes = tts_service.synthesize(
            text=payload.text,
            voice=payload.voice,
            speed=payload.speed,
        )
    except RuntimeError as e:
        system_logger.error("Error during TTS synthesis: %s", e)
        return Response(
            content=str(e),
            status_code=503,
            media_type="text/plain",
        )

    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={"Content-Disposition": "inline; filename=tts.wav"},
    )


