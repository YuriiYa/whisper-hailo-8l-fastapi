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

    @staticmethod
    def _resolve_engine_kind(engine_binary: str) -> str:
        normalized = (engine_binary or "").strip().lower()
        base_name = os.path.basename(normalized)

        if base_name in {"espeak", "espeak-ng"}:
            return "espeak"
        if base_name in {"piper", "piper-tts"}:
            return "piper"

        if "espeak" in base_name:
            return "espeak"
        if "piper" in base_name:
            return "piper"

        raise RuntimeError(
            f"Unsupported TTS engine '{engine_binary}'. Use 'espeak-ng' or 'piper'."
        )

    def _build_espeak_command(self, output_path: str, text: str, voice: str, speed: int) -> list[str]:
        return [
            self.engine_binary,
            "-v",
            voice,
            "-s",
            str(speed),
            "-w",
            output_path,
            text,
        ]

    @staticmethod
    def _build_piper_length_scale(speed: int) -> str:
        # Piper controls speaking rate through length_scale (lower is faster).
        normalized_speed = max(speed, 1)
        length_scale = 170.0 / float(normalized_speed)
        length_scale = max(0.5, min(2.0, length_scale))
        return f"{length_scale:.3f}"

    @staticmethod
    def _looks_like_model_path(value: str) -> bool:
        return value.endswith(".onnx") or "/" in value or "\\" in value

    def _resolve_model_path(self, model_path: str) -> str:
        if os.path.isabs(model_path):
            return model_path

        # Try common runtime roots: current dir, app root, and repository root.
        app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        repo_root = os.path.abspath(os.path.join(app_root, ".."))
        candidates = [
            model_path,
            os.path.join(os.getcwd(), model_path),
            os.path.join(app_root, model_path),
            os.path.join(repo_root, model_path),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate

        return model_path

    def _resolve_piper_voice(self, selected_voice: str) -> str:
        selected_voice = (selected_voice or "").strip()
        default_voice = (self.default_voice or "").strip()

        # Preserve backward compatibility with payloads like {"voice":"uk"}.
        if (
            selected_voice
            and not self._looks_like_model_path(selected_voice)
            and len(selected_voice) <= 5
            and self._looks_like_model_path(default_voice)
        ):
            return self._resolve_model_path(default_voice)

        if self._looks_like_model_path(selected_voice):
            return self._resolve_model_path(selected_voice)

        return selected_voice

    def _build_piper_command(self, output_path: str, voice: str, speed: int) -> list[str]:
        piper_binary = "piper" if self.engine_binary.strip().lower() == "piper-tts" else self.engine_binary
        return [
            piper_binary,
            "--model",
            voice,
            "--output_file",
            output_path,
            "--length_scale",
            self._build_piper_length_scale(speed),
        ]

    def synthesize(self, text: str, voice: str | None = None, speed: int | None = None) -> bytes:
        if not text or not text.strip():
            raise RuntimeError("Text cannot be empty.")

        selected_voice = voice or self.default_voice
        selected_speed = speed if speed is not None else self.default_speed
        engine_kind = self._resolve_engine_kind(self.engine_binary)

        if engine_kind == "piper" and not selected_voice:
            raise RuntimeError(
                "Piper requires a voice model path. Set TTS_DEFAULT_VOICE to a .onnx model path or pass voice in the request."
            )
        if engine_kind == "piper":
            selected_voice = self._resolve_piper_voice(selected_voice)

        with NamedTemporaryFile(delete=False, suffix=".wav") as tmp_out:
            output_path = tmp_out.name

        try:
            if engine_kind == "espeak":
                cmd = self._build_espeak_command(
                    output_path=output_path,
                    text=text,
                    voice=selected_voice,
                    speed=selected_speed,
                )
                subprocess.run(cmd, check=True, capture_output=True, text=True)
            else:
                cmd = self._build_piper_command(
                    output_path=output_path,
                    voice=selected_voice,
                    speed=selected_speed,
                )
                subprocess.run(
                    cmd,
                    input=text,
                    check=True,
                    capture_output=True,
                    text=True,
                )

            with open(output_path, "rb") as wav_file:
                return wav_file.read()
        except FileNotFoundError as exc:
            if engine_kind == "piper":
                raise RuntimeError(
                    "TTS engine 'piper' is not installed. Install it with `pip install piper-tts`."
                ) from exc
            raise RuntimeError(
                f"TTS engine '{self.engine_binary}' is not installed. Install espeak-ng on the host."
            ) from exc
        except subprocess.CalledProcessError as exc:
            error_text = (exc.stderr or "").strip() or (exc.stdout or "").strip() or "Unknown TTS engine error."
            raise RuntimeError(f"TTS synthesis failed: {error_text}") from exc
        finally:
            if os.path.exists(output_path):
                os.remove(output_path)
