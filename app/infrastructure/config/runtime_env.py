import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeEnvConfig:
    is_hailo_on_device: bool
    hailo_version: str

    @property
    def is_vosk_mode(self) -> bool:
        return self.hailo_version == "VOSK"

    @property
    def can_transcribe(self) -> bool:
        return self.is_hailo_on_device or self.is_vosk_mode

    @classmethod
    def from_env(cls) -> "RuntimeEnvConfig":
        is_hailo_on_device = (os.getenv("IS_HAILO_ON_DEVICE") or "").strip().upper() == "TRUE"
        hailo_version = (os.getenv("HAILO_VERSION") or "").strip().upper()
        return cls(
            is_hailo_on_device=is_hailo_on_device,
            hailo_version=hailo_version,
        )