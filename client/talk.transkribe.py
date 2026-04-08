#!/usr/bin/env python3
"""Continuously record microphone audio in 10-second chunks and transcribe via HTTP."""

import argparse
import io
import json
import os
import queue
import threading
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
DEFAULT_STEP_MS = 1000
DEFAULT_OVERLAP_SECONDS = 1.0
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


def transcribe_worker(
    worker_id: int,
    stop_event: threading.Event,
    transcribe_queue: "queue.Queue[tuple[int, np.ndarray]]",
    args: argparse.Namespace,
) -> None:
    """Consume queued chunks and send them for transcription."""
    while not stop_event.is_set() or not transcribe_queue.empty():
        try:
            chunk_index, audio = transcribe_queue.get(timeout=0.2)
        except queue.Empty:
            continue

        try:
            rms, peak =  compute_levels(audio)
            print(f"[chunk {chunk_index}] level: rms={rms:.6f}, peak={peak:.6f}")
            if peak < 0.005:
                print("[warn] very low input level detected; check mic device/gain/mute")
                continue

            wav_bytes = to_wav_bytes(audio, args.sample_rate, args.channels)
            if args.save:
                saved_path = save_chunk_wav(args.output_dir, chunk_index, wav_bytes)
                print(f"[chunk {chunk_index}] saved={saved_path}")

            started = time.time()
            response = send_for_transcription(args.url, wav_bytes, args.timeout)
            elapsed = time.time() - started

            print(
                f"\n[chunk {chunk_index}] worker={worker_id} "
                f"status={response.status_code} ({elapsed:.2f}s)"
            )
            try:
                payload = response.json()
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            except ValueError:
                print(response.text)
        except requests.RequestException as exc:
            print(f"[error] worker={worker_id} request failed: {exc}")
            time.sleep(0.2)
        except Exception as exc:
            print(f"[error] worker={worker_id} unexpected: {exc}")
            time.sleep(0.2)
        finally:
            transcribe_queue.task_done()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Listen to mic and send n-second WAV chunks to transcribe endpoint"
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Transcribe endpoint URL")
    parser.add_argument(
        "--chunk-seconds",
        type=float,
        default=DEFAULT_CHUNK_SECONDS,
        help="Seconds per transcription window",
    )
    parser.add_argument(
        "--step-ms",
        type=int,
        default=DEFAULT_STEP_MS,
        help="Milliseconds between emitted transcriptions (e.g. 10, 100, 1000)",
    )
    parser.add_argument(
        "--overlap-seconds",
        type=float,
        default=DEFAULT_OVERLAP_SECONDS,
        help="Minimum overlap between windows in seconds",
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
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel transcription workers",
    )
    args = parser.parse_args()

    if args.chunk_seconds <= 0:
        print("[error] --chunk-seconds must be > 0")
        return
    if args.step_ms <= 0:
        print("[error] --step-ms must be > 0")
        return
    if args.overlap_seconds < 0:
        print("[error] --overlap-seconds must be >= 0")
        return
    if args.workers <= 0:
        print("[error] --workers must be > 0")
        return

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
    chunk_samples = int(args.sample_rate * args.chunk_seconds)
    overlap_samples = int(args.sample_rate * args.overlap_seconds)
    max_step_samples = chunk_samples - overlap_samples
    if max_step_samples <= 0:
        print("[error] overlap must be smaller than chunk length")
        return

    requested_step_samples = int(args.sample_rate * (args.step_ms / 1000.0))
    step_samples = max(1, min(requested_step_samples, max_step_samples))
    if step_samples != requested_step_samples:
        adjusted_ms = int((step_samples * 1000) / args.sample_rate)
        print(
            "[warn] requested --step-ms reduced to preserve overlap. "
            f"effective_step_ms={adjusted_ms}"
        )

    overlap_seconds_effective = (chunk_samples - step_samples) / args.sample_rate
    print(
        f"[start] audio={args.sample_rate}Hz, channels={args.channels}, "
        f"chunk={args.chunk_seconds:.3f}s, step_ms={args.step_ms}, "
        f"overlap~{overlap_seconds_effective:.3f}s, workers={args.workers}"
    )
    print("[info] Press Ctrl+C to stop.")

    audio_frame_queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=512)
    transcribe_queue: "queue.Queue[tuple[int, np.ndarray]]" = queue.Queue(maxsize=64)
    stop_event = threading.Event()

    def audio_callback(indata, frames, time_info, status):
        del frames, time_info
        if status:
            print(f"[audio][warn] {status}")
        try:
            audio_frame_queue.put_nowait(indata.copy())
        except queue.Full:
            try:
                audio_frame_queue.get_nowait()
                audio_frame_queue.put_nowait(indata.copy())
            except queue.Empty:
                pass

    workers: list[threading.Thread] = []
    for worker_idx in range(args.workers):
        t = threading.Thread(
            target=transcribe_worker,
            args=(worker_idx + 1, stop_event, transcribe_queue, args),
            daemon=True,
        )
        t.start()
        workers.append(t)

    rolling = np.empty((0, args.channels), dtype=np.float32)
    samples_since_emit = 0
    chunk_index = 1
    keep_samples = chunk_samples + (step_samples * 4)

    try:
        with sd.InputStream(
            samplerate=args.sample_rate,
            channels=args.channels,
            dtype="float32",
            device=input_device,
            callback=audio_callback,
        ):
            print("[recording] streaming microphone input...")
            while True:
                frame = audio_frame_queue.get(timeout=0.5)
                if frame.ndim == 1:
                    frame = frame.reshape(-1, 1)

                rolling = np.concatenate((rolling, frame), axis=0)
                if rolling.shape[0] > keep_samples:
                    rolling = rolling[-keep_samples:]

                samples_since_emit += frame.shape[0]

                while rolling.shape[0] >= chunk_samples and samples_since_emit >= step_samples:
                    chunk_audio = np.array(rolling[-chunk_samples:], copy=True)
                    try:
                        transcribe_queue.put_nowait((chunk_index, chunk_audio))
                    except queue.Full:
                        try:
                            transcribe_queue.get_nowait()
                            transcribe_queue.task_done()
                        except queue.Empty:
                            pass
                        transcribe_queue.put_nowait((chunk_index, chunk_audio))
                        print("[warn] transcription queue was full; dropped oldest pending chunk")

                    chunk_index += 1
                    samples_since_emit -= step_samples
    except KeyboardInterrupt:
        print("\n[stop] Exiting...")
    except Exception as exc:
        print(f"[error] capture loop failed: {exc}")
    finally:
        stop_event.set()
        for t in workers:
            t.join(timeout=1.5)


if __name__ == "__main__":
    main()
