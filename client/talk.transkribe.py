#!/usr/bin/env python3
"""Continuously record microphone audio in 10-second chunks and transcribe via HTTP."""

import argparse
import io
import json
import os
import time
import wave
from typing import Optional, Union

import numpy as np
import requests
import sounddevice as sd

DEFAULT_URL = "http://localhost:54322/transcribe"
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1
DEFAULT_CHUNK_SECONDS = 10
DEFAULT_OUTPUT_DIR = "recorded_chunks"


def list_input_devices() -> None:
    """Print available audio input devices."""
    devices = sd.query_devices()
    print("[audio] available input devices:")
    for idx, dev in enumerate(devices):
        max_in = int(dev.get("max_input_channels", 0))
        if max_in > 0:
            print(f"  - index={idx}, name={dev['name']}, max_input_channels={max_in}")


def compute_levels(audio: np.ndarray) -> tuple[float, float]:
    """Return RMS and peak levels for the chunk."""
    samples = np.asarray(audio, dtype=np.float32).reshape(-1)
    if samples.size == 0:
        return 0.0, 0.0
    rms = float(np.sqrt(np.mean(np.square(samples))))
    peak = float(np.max(np.abs(samples)))
    return rms, peak


def record_chunk(
    sample_rate: int,
    channels: int,
    chunk_seconds: int,
    input_device: Optional[Union[int, str]],
) -> np.ndarray:
    """Record a chunk of audio from microphone and return float32 array."""
    frames = int(sample_rate * chunk_seconds)
    print(
        f"[recording] {chunk_seconds}s chunk (device={input_device if input_device is not None else 'default'})..."
    )
    audio = sd.rec(
        frames,
        samplerate=sample_rate,
        channels=channels,
        dtype="float32",
        device=input_device,
    )
    sd.wait()
    return audio


def to_wav_bytes(audio: np.ndarray, sample_rate: int, channels: int) -> bytes:
    """Convert float32 audio in range [-1, 1] into 16-bit PCM WAV bytes."""
    clipped = np.clip(audio, -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype(np.int16)

    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16.tobytes())

    return wav_buffer.getvalue()


def save_chunk_wav(output_dir: str, chunk_index: int, wav_bytes: bytes) -> str:
    """Save WAV bytes to disk and return the saved file path."""
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, f"chunk_{chunk_index:06d}.wav")
    with open(file_path, "wb") as wav_file:
        wav_file.write(wav_bytes)
    return file_path


def send_for_transcription(url: str, wav_bytes: bytes, timeout: int) -> requests.Response:
    """Send WAV bytes to transcribe endpoint as multipart form-data."""
    files = {"file": ("chunk.wav", wav_bytes, "audio/wav")}
    return requests.post(url, files=files, timeout=timeout)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Listen to mic and send 10-second WAV chunks to transcribe endpoint"
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Transcribe endpoint URL")
    parser.add_argument(
        "--chunk-seconds",
        type=int,
        default=DEFAULT_CHUNK_SECONDS,
        help="Seconds per recorded chunk",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=DEFAULT_SAMPLE_RATE,
        help="Recording sample rate (Hz)",
    )
    parser.add_argument(
        "--channels",
        type=int,
        default=DEFAULT_CHANNELS,
        help="Number of audio channels",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="HTTP timeout in seconds",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where recorded WAV chunks will be saved",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save each recorded chunk to WAV before sending",
    )
    parser.add_argument(
        "--input-device",
        default=None,
        help="Input device index or name (use --list-devices to discover)",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available input devices and exit",
    )
    args = parser.parse_args()

    list_input_devices()

    if args.list_devices:
        return

    input_device: Optional[Union[int, str]] = None
    if args.input_device is not None:
        input_device = int(args.input_device) if args.input_device.isdigit() else args.input_device
    else:
        while True:
            selected = input("[audio] Select input device index or name: ").strip()
            if not selected:
                print("[audio] Please provide a device index or name.")
                continue
            input_device = int(selected) if selected.isdigit() else selected
            break

    try:
        sd.check_input_settings(
            device=input_device,
            channels=args.channels,
            samplerate=args.sample_rate,
            dtype="float32",
        )
    except Exception as exc:
        print(f"[error] invalid input settings: {exc}")
        print("[hint] Run with --list-devices and choose a device using --input-device")
        return

    print(f"[start] endpoint={args.url}")
    print(
        f"[start] audio={args.sample_rate}Hz, channels={args.channels}, "
        f"chunk={args.chunk_seconds}s"
    )
    print("[info] Press Ctrl+C to stop.")

    chunk_index = 1
    while True:
        try:
            audio = record_chunk(
                args.sample_rate,
                args.channels,
                args.chunk_seconds,
                input_device=input_device,
            )
            rms, peak = compute_levels(audio)
            print(f"[chunk {chunk_index}] level: rms={rms:.6f}, peak={peak:.6f}")
            if peak < 0.005:
                print("[warn] very low input level detected; check mic device/gain/mute")
            wav_bytes = to_wav_bytes(audio, args.sample_rate, args.channels)
            if args.save:
                saved_path = save_chunk_wav(args.output_dir, chunk_index, wav_bytes)
                print(f"[chunk {chunk_index}] saved={saved_path}")

            started = time.time()
            response = send_for_transcription(args.url, wav_bytes, args.timeout)
            elapsed = time.time() - started

            print(f"\n[chunk {chunk_index}] status={response.status_code} ({elapsed:.2f}s)")
            try:
                payload = response.json()
                print(json.dumps(payload, indent=2, ensure_ascii=True))
            except ValueError:
                print(response.text)

            chunk_index += 1
        except KeyboardInterrupt:
            print("\n[stop] Exiting...")
            break
        except requests.RequestException as exc:
            print(f"[error] request failed: {exc}")
            time.sleep(1)
        except Exception as exc:  # Keep listening even if one chunk fails
            print(f"[error] unexpected: {exc}")
            time.sleep(1)


if __name__ == "__main__":
    main()
