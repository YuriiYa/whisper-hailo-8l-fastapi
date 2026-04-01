import logging
import os
from fastapi import FastAPI
from application.pipelines.hailo_whisper_pipeline import HailoWhisperPipeline
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


def config(app: FastAPI, _model: str = "hailo8l") -> None:
    system_logger.info(f"Configuring Whisper Hailo with model: {_model}")
    global hailo_model
    hailo_model = _model

    global whisper_variant
    whisper_variant = _get_whisper_variant_from_env()
    system_logger.info("Configuring Whisper variant: %s", whisper_variant)

    global encoder_path
    encoder_path = hef_utils.get_encoder_hef_path(_model, whisper_variant)

    global decoder_path
    decoder_path = hef_utils.get_decoder_hef_path(_model, whisper_variant)


    # encoder_path = hef_utils.get_encoder_hef_path(model)
    # decoder_path = hef_utils.get_decoder_hef_path(model)

    # app.state.whisper_hailo = HailoWhisperPipeline(
    #     encoder_model_path=encoder_path,
    #     decoder_model_path=decoder_path,
    #     variant='tiny',
    #     multi_process_service=False)
    system_logger.info(f"Configuring Whisper Hailo was successful")


def whisper_hailo_stop():
    whisper_hailo.stop()

def get_whisper_hailo() -> HailoWhisperPipeline:
    whisper_hailo = HailoWhisperPipeline(
        encoder_model_path=encoder_path,
        decoder_model_path=decoder_path,
        variant=whisper_variant,
        multi_process_service=False)

    return whisper_hailo