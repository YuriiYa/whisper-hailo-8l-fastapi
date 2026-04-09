import os
import subprocess
from tempfile import NamedTemporaryFile


class TTSService:
    def __init__(
        self,
        engine_binary: str = "espeak-ng",
        default_voice: str = "uk",
        default_speed: int = 170,
    ):
        self.engine_binary = engine_binary
        self.default_voice = default_voice
        self.default_speed = default_speed

    def synthesize(self, text: str, voice: str | None = None, speed: int | None = None) -> bytes:
        if not text or not text.strip():
            raise RuntimeError("Text cannot be empty.")

        selected_voice = voice or self.default_voice
        selected_speed = speed if speed is not None else self.default_speed

        with NamedTemporaryFile(delete=False, suffix=".wav") as tmp_out:
            output_path = tmp_out.name

        cmd = [
            self.engine_binary,
            "-v",
            selected_voice,
            "-s",
            str(selected_speed),
            "-w",
            output_path,
            text,
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            with open(output_path, "rb") as wav_file:
                return wav_file.read()
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"TTS engine '{self.engine_binary}' is not installed. Install espeak-ng on the host."
            ) from exc
        except subprocess.CalledProcessError as exc:
            error_text = (exc.stderr or "").strip() or "Unknown TTS engine error."
            raise RuntimeError(f"TTS synthesis failed: {error_text}") from exc
        finally:
            if os.path.exists(output_path):
                os.remove(output_path)
