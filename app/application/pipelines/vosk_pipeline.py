import json
import logging
import os
import subprocess

from vosk import Model, KaldiRecognizer

system_logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK_SIZE = 4000  # samples per ffmpeg read

# Project root is 3 levels up from this file (app/application/pipelines/)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir))


class VoskPipeline:
    """CPU-based speech recognition pipeline using the VOSK library.

    Requires a pre-downloaded VOSK model directory specified via the
    VOSK_MODEL_PATH environment variable (defaults to
    ``requirements_files/vosk-model-uk-v3-lgraph``).

    See https://alphacephei.com/vosk/models for available models.
    """

    def __init__(self, model_path: str):
        # If the path is relative, resolve it from the project root
        if not os.path.isabs(model_path):
            model_path = os.path.join(_PROJECT_ROOT, model_path)
        system_logger.info("Loading VOSK model from: %s", model_path)
        self.model = Model(model_path)
        system_logger.info("VOSK model loaded successfully")

    def transcribe_file(self, audio_path: str) -> str:
        """Transcribe an audio file and return the recognised text.

        Uses ffmpeg to decode the audio to raw 16-bit mono PCM at 16 kHz
        and feeds it to KaldiRecognizer in chunks.
        """
        rec = KaldiRecognizer(self.model, SAMPLE_RATE)

        cmd = [
            "ffmpeg", "-nostdin", "-threads", "0",
            "-i", audio_path,
            "-f", "s16le", "-ac", "1", "-acodec", "pcm_s16le",
            "-ar", str(SAMPLE_RATE), "-",
        ]

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        results = []
        try:
            while True:
                data = process.stdout.read(CHUNK_SIZE * 2)  # 2 bytes per int16 sample
                if not data:
                    break
                if rec.AcceptWaveform(data):
                    part = json.loads(rec.Result())
                    if part.get("text"):
                        results.append(part["text"])
        finally:
            process.stdout.close()
            process.wait()

        final = json.loads(rec.FinalResult())
        if final.get("text"):
            results.append(final["text"])

        return " ".join(results)

    def stop(self):
        """No-op – provided so VoskPipeline matches the HailoWhisperPipeline interface."""
        pass
