import logging
import os
import asyncio
from typing import Any
from fastapi import FastAPI
from infrastructure.config.utils_config import hef_utils, args_utils

# whisper_hailo = None
# encoder_path = hef_utils.get_encoder_hef_path(variant)
# decoder_path = hef_utils.get_decoder_hef_path(variant)

# print(f"encoder_path: {encoder_path}")
# print(f"decoder_path: {decoder_path}")
system_logger = logging.getLogger(__file__)
# whisper_hailo: HailoWhisperPipeline | None = None
# whisper_hailo = HailoWhisperPipeline(
#     encoder_model_path=encoder_path,
#     decoder_model_path=decoder_path,
#     variant='tiny',
#     multi_process_service=False)

hailo_model = ""
whisper_variant = "base"
encoder_path = ""
decoder_path = ""
multi_process_service = False
whisper_hailo_instance: Any = None
whisper_hailo_lock = asyncio.Lock()


def _get_whisper_variant_from_env() -> str:
    variant = (os.getenv("WHISPER_VARIANT") or "base").strip().lower()
    supported_variants = {"tiny", "base"}
    if variant not in supported_variants:
        system_logger.warning(
            "Invalid WHISPER_VARIANT='%s'. Falling back to 'base'. Supported variants: tiny/base",
            variant,
        )
        return "base"
    return variant


def _get_multi_process_service_from_env() -> bool:
    raw = (os.getenv("WHISPER_MULTI_PROCESS_SERVICE") or "FALSE").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def config(app: FastAPI, _model: str = "hailo8l") -> None:
    system_logger.info(f"Configuring pipeline with model: {_model}")
    global hailo_model, whisper_hailo_instance
    hailo_model = _model

    if whisper_hailo_instance is not None:
        whisper_hailo_instance.stop()
        whisper_hailo_instance = None

    if _model.upper() == "VOSK":
        from application.pipelines.vosk_pipeline import VoskPipeline
        vosk_model_path = (os.getenv("VOSK_MODEL_PATH") or "vosk-model").strip()
        system_logger.info("Configuring VOSK pipeline with model path: %s", vosk_model_path)
        whisper_hailo_instance = VoskPipeline(model_path=vosk_model_path)
        system_logger.info("VOSK pipeline configured successfully")
        return

    from application.pipelines.hailo_whisper_pipeline import HailoWhisperPipeline

    global whisper_variant
    whisper_variant = _get_whisper_variant_from_env()
    system_logger.info("Configuring Whisper variant: %s", whisper_variant)

    global encoder_path
    encoder_path = hef_utils.get_encoder_hef_path(_model, whisper_variant)

    global decoder_path
    decoder_path = hef_utils.get_decoder_hef_path(_model, whisper_variant)

    global multi_process_service
    multi_process_service = _get_multi_process_service_from_env()
    system_logger.info("Configuring multi_process_service: %s", multi_process_service)

    whisper_hailo_instance = HailoWhisperPipeline(
        encoder_model_path=encoder_path,
        decoder_model_path=decoder_path,
        variant=whisper_variant,
        multi_process_service=multi_process_service,
    )
    system_logger.info("Configuring Whisper Hailo was successful")


def whisper_hailo_stop():
    global whisper_hailo_instance
    if whisper_hailo_instance is not None:
        whisper_hailo_instance.stop()
        whisper_hailo_instance = None


def get_whisper_hailo_lock() -> asyncio.Lock:
    return whisper_hailo_lock

def get_whisper_hailo() -> Any:
    return whisper_hailo_instance