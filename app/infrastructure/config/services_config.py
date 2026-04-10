import os

from application.services.gemini_service import GeminiService
from application.services.tts_service import TTSService
from application.services.whisper_service import WhisperService
from infrastructure.config.utils_config import audio_utils
# from infrastructure.config.whisper_hailo import whisper_hailo


def get_whisper_service() -> WhisperService:
    return WhisperService(
        audio_utils=audio_utils,
        # whisper_hailo=whisper_hailo,
    )


def get_tts_service() -> TTSService:
    default_speed = int(os.getenv("TTS_DEFAULT_SPEED", "170"))
    return TTSService(
        engine_binary=os.getenv("TTS_ENGINE_BINARY", "espeak-ng"),
        default_voice=os.getenv("TTS_DEFAULT_VOICE", "uk"),
        default_speed=default_speed,
    )


def get_gemini_service() -> GeminiService:
    timeout_seconds = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))
    return GeminiService(
        api_key=os.getenv("GEMINI_API_KEY", ""),
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite"),
        timeout_seconds=timeout_seconds,
    )
