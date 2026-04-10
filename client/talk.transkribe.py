#!/usr/bin/env python3
"""Continuously record microphone audio in 10-second chunks and transcribe via HTTP."""

import argparse
import io
import json
import os
import queue
import re
import threading
import time
import wave
from dataclasses import dataclass
from typing import Optional, Union

import numpy as np
import requests
import sounddevice as sd

DEFAULT_URL = "http://localhost:54322/transcribe"
DEFAULT_TTS_URL = "http://localhost:54322/tts"
DEFAULT_ASK_URL = "http://localhost:54322/ask"
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1
DEFAULT_CHUNK_SECONDS = 10
DEFAULT_STEP_MS = 1000
DEFAULT_OVERLAP_SECONDS = 1.0
DEFAULT_OUTPUT_DIR = "recorded_chunks"

START_WORDS = ("start", "старт")
STOP_WORDS = ("end", "стоп", "кінець" )


@dataclass
class TranscriptionResult:
    chunk_index: int
    worker_id: int
    status_code: int
    elapsed_seconds: float
    payload: object | None
    raw_response_text: str
    transcript_text: str


class CaptureSessionState:
    """Track start/stop driven aggregation across transcribed chunks."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._capture_active = False
        self._captured_text_parts: list[str] = []
        self._finalized_text: Optional[str] = None

    @staticmethod
    def _contains_word(text: str, words: tuple[str, ...]) -> bool:
        if not text:
            return False
        lowered = text.lower()
        return any(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", lowered) for word in words)

    @staticmethod
    def _strip_words(text: str, words: tuple[str, ...]) -> str:
        if not text:
            return ""
        out = text
        for word in words:
            out = re.sub(rf"(?i)(?<!\w){re.escape(word)}(?!\w)", " ", out)
        return re.sub(r"\s+", " ", out).strip()

    def handle_transcript(self, transcript_text: str) -> tuple[bool, bool, str, Optional[str]]:
        """
        Update state using a transcribed text chunk.

        Returns: started_now, stopped_now, chunk_text_for_tts, finalized_text.
        """
        has_start = self._contains_word(transcript_text, START_WORDS)
        has_stop = self._contains_word(transcript_text, STOP_WORDS)
        cleaned_text = self._strip_words(self._strip_words(transcript_text, START_WORDS), STOP_WORDS)

        with self._lock:
            started_now = False
            stopped_now = False
            chunk_text_for_tts = ""
            finalized_text = None

            if has_start and not self._capture_active:
                self._capture_active = True
                self._captured_text_parts = []
                started_now = True

            if self._capture_active and cleaned_text:
                self._captured_text_parts.append(cleaned_text)
                chunk_text_for_tts = cleaned_text

            if has_stop and self._capture_active:
                finalized_text = " ".join(self._captured_text_parts).strip()
                self._finalized_text = finalized_text
                self._capture_active = False
                self._captured_text_parts = []
                stopped_now = True

        return started_now, stopped_now, chunk_text_for_tts, finalized_text

    def get_finalized_text(self) -> str:
        with self._lock:
            return (self._finalized_text or "").strip()


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


def resolve_tts_url(transcribe_url: str, tts_url: Optional[str]) -> str:
    """Use explicit --tts-url or derive it from --url by swapping /transcribe -> /tts."""
    if tts_url:
        return tts_url
    if transcribe_url.endswith("/transcribe"):
        return f"{transcribe_url[:-len('/transcribe')]}/tts"
    return DEFAULT_TTS_URL


def resolve_ask_url(transcribe_url: str, ask_url: Optional[str]) -> str:
    """Use explicit --ask-url or derive it from --url by swapping /transcribe -> /ask."""
    if ask_url:
        return ask_url
    if transcribe_url.endswith("/transcribe"):
        return f"{transcribe_url[:-len('/transcribe')]}/ask"
    return DEFAULT_ASK_URL


def resolve_ask_health_url(ask_url: str) -> str:
    """Derive readiness endpoint from ask endpoint URL."""
    normalized = ask_url.rstrip("/")
    if normalized.endswith("/ask"):
        return f"{normalized}/health"
    return f"{normalized}/ask/health"


def extract_transcript_text(payload: object | None, fallback_text: str) -> str:
    """Best-effort extraction of transcript text from API response payload."""
    if isinstance(payload, dict):
        message = payload.get("message")
        if isinstance(message, str):
            return message.strip()
        if isinstance(message, list):
            return " ".join(str(item) for item in message if item is not None).strip()
        if isinstance(message, dict):
            nested_text = message.get("text") or message.get("message")
            if isinstance(nested_text, str):
                return nested_text.strip()
        text_field = payload.get("text")
        if isinstance(text_field, str):
            return text_field.strip()
    elif isinstance(payload, str):
        return payload.strip()

    return (fallback_text or "").strip()


def request_gemini_answer(ask_url: str, question: str, timeout_seconds: int) -> Optional[str]:
    """Send a finalized question to /ask endpoint and return Gemini answer text."""
    try:
        response = requests.post(
            ask_url,
            json={"question": question},
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        print(f"[ask][error] request failed: {exc}")
        return None

    if response.status_code >= 400:
        body_preview = response.text.strip()[:200]
        print(f"[ask][error] status={response.status_code}, body={body_preview}")
        return None

    try:
        payload = response.json()
    except ValueError:
        print("[ask][error] invalid JSON response")
        return None

    answer = payload.get("answer")
    if isinstance(answer, str):
        return answer.strip()

    print("[ask][error] no 'answer' field in response")
    return None


def request_gemini_readiness(
    ask_health_url: str,
    timeout_seconds: int,
) -> tuple[Optional[bool], str, str]:
    """Query /ask/health and return (ready, detail, model)."""
    try:
        response = requests.get(ask_health_url, timeout=timeout_seconds)
    except requests.RequestException as exc:
        return None, f"health request failed: {exc}", "unknown"

    if response.status_code >= 400:
        body_preview = response.text.strip()[:200]
        return None, f"health status={response.status_code}, body={body_preview}", "unknown"

    try:
        payload = response.json()
    except ValueError:
        return None, "health response is not valid JSON", "unknown"

    ready = payload.get("ready")
    detail = payload.get("detail")
    model = payload.get("model")

    ready_value = ready if isinstance(ready, bool) else None
    detail_value = detail if isinstance(detail, str) else "No detail provided"
    model_value = model if isinstance(model, str) and model.strip() else "unknown"
    return ready_value, detail_value, model_value


def request_tts_wav_bytes(
    tts_url: str,
    text: str,
    timeout_seconds: int,
    voice: Optional[str],
    speed: Optional[int],
) -> Optional[bytes]:
    """Synthesize text to WAV bytes via /tts endpoint."""
    payload: dict[str, object] = {"text": text}
    if voice:
        payload["voice"] = voice
    if speed is not None:
        payload["speed"] = speed

    try:
        response = requests.post(tts_url, json=payload, timeout=timeout_seconds)
        if response.status_code >= 400:
            body_preview = response.text.strip()[:200]
            print(f"[tts][error] status={response.status_code}, body={body_preview}")
            return None
        return response.content
    except requests.RequestException as exc:
        print(f"[tts][error] request failed: {exc}")
        return None


def play_wav_bytes(wav_bytes: bytes) -> None:
    """Play WAV bytes through default output device."""
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()
            pcm = wav_file.readframes(frame_count)
    except wave.Error as exc:
        print(f"[tts][error] invalid WAV data: {exc}")
        return

    if sample_width != 2:
        print(f"[tts][warn] unsupported sample width: {sample_width * 8} bits")
        return

    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels)

    try:
        sd.play(audio, samplerate=sample_rate)
        sd.wait()
    except Exception as exc:
        print(f"[tts][error] playback failed: {exc}")


def handle_tts_and_playback(text: str, args: argparse.Namespace, tts_url: str, label: str) -> None:
    """Synthesize and play text if it is not empty."""
    cleaned = (text or "").strip()
    if not cleaned:
        return

    wav_bytes = request_tts_wav_bytes(
        tts_url=tts_url,
        text=cleaned,
        timeout_seconds=args.timeout,
        voice=args.tts_voice,
        speed=args.tts_speed,
    )
    if wav_bytes is None:
        return

    print(f"[tts] playing {label} ({len(cleaned)} chars)")
    play_wav_bytes(wav_bytes)


def transcribe_worker(
    worker_id: int,
    stop_event: threading.Event,
    transcribe_queue: "queue.Queue[tuple[int, np.ndarray]]",
    result_queue: "queue.Queue[TranscriptionResult]",
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
                result_queue.put(
                    TranscriptionResult(
                        chunk_index=chunk_index,
                        worker_id=worker_id,
                        status_code=0,
                        elapsed_seconds=0.0,
                        payload={"message": ""},
                        raw_response_text="",
                        transcript_text="",
                    )
                )
                continue

            wav_bytes = to_wav_bytes(audio, args.sample_rate, args.channels)
            if args.save:
                saved_path = save_chunk_wav(args.output_dir, chunk_index, wav_bytes)
                print(f"[chunk {chunk_index}] saved={saved_path}")

            started = time.time()
            response = send_for_transcription(args.url, wav_bytes, args.timeout)
            elapsed = time.time() - started
            payload = None
            raw_response_text = response.text
            try:
                payload = response.json()
            except ValueError:
                payload = None

            transcript_text = extract_transcript_text(payload, raw_response_text)
            result_queue.put(
                TranscriptionResult(
                    chunk_index=chunk_index,
                    worker_id=worker_id,
                    status_code=response.status_code,
                    elapsed_seconds=elapsed,
                    payload=payload,
                    raw_response_text=raw_response_text,
                    transcript_text=transcript_text,
                )
            )
        except requests.RequestException as exc:
            print(f"[error] worker={worker_id} request failed: {exc}")
            result_queue.put(
                TranscriptionResult(
                    chunk_index=chunk_index,
                    worker_id=worker_id,
                    status_code=-1,
                    elapsed_seconds=0.0,
                    payload=None,
                    raw_response_text=str(exc),
                    transcript_text="",
                )
            )
            time.sleep(0.2)
        except Exception as exc:
            print(f"[error] worker={worker_id} unexpected: {exc}")
            result_queue.put(
                TranscriptionResult(
                    chunk_index=chunk_index,
                    worker_id=worker_id,
                    status_code=-1,
                    elapsed_seconds=0.0,
                    payload=None,
                    raw_response_text=str(exc),
                    transcript_text="",
                )
            )
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
    parser.add_argument(
        "--tts-url",
        default=None,
        help="TTS endpoint URL (default: derived from --url)",
    )
    parser.add_argument(
        "--ask-url",
        default=None,
        help="Gemini ask endpoint URL (default: derived from --url)",
    )
    parser.add_argument(
        "--no-gemini",
        action="store_true",
        help="Skip /ask and speak finalized text directly",
    )
    parser.add_argument(
        "--tts-voice",
        default="uk",
        help="Voice passed to /tts endpoint",
    )
    parser.add_argument(
        "--tts-speed",
        type=int,
        default=170,
        help="Speech speed passed to /tts endpoint",
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
    if args.tts_speed <= 0:
        print("[error] --tts-speed must be > 0")
        return

    tts_url = resolve_tts_url(args.url, args.tts_url)
    ask_url = resolve_ask_url(args.url, args.ask_url)
    ask_health_url = resolve_ask_health_url(ask_url)

    if args.no_gemini:
        print("[ask][info] Gemini disabled by --no-gemini; skipping readiness check")
    else:
        ready, detail, model = request_gemini_readiness(
            ask_health_url=ask_health_url,
            timeout_seconds=args.timeout,
        )
        if ready is True:
            print(f"[ask][ready] Gemini configured. model={model}")
        elif ready is False:
            print(f"[ask][warn] Gemini is not ready: {detail}")
        else:
            print(f"[ask][warn] Could not verify Gemini readiness: {detail}")

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
        f"overlap~{overlap_seconds_effective:.3f}s, workers={args.workers}, "
        f"tts={tts_url}, ask={ask_url}, gemini={'off' if args.no_gemini else 'on'}"
    )
    print("[info] Session keywords: start/старт to begin, end/стоп to finalize")
    print("[info] Press Ctrl+C to stop.")

    audio_frame_queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=512)
    transcribe_queue: "queue.Queue[tuple[int, np.ndarray]]" = queue.Queue(maxsize=64)
    result_queue: "queue.Queue[TranscriptionResult]" = queue.Queue(maxsize=128)
    stop_event = threading.Event()
    pause_capture_event = threading.Event()
    session_state = CaptureSessionState()

    def audio_callback(indata, frames, time_info, status):
        del frames, time_info
        if pause_capture_event.is_set():
            return
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
            args=(worker_idx + 1, stop_event, transcribe_queue, result_queue, args),
            daemon=True,
        )
        t.start()
        workers.append(t)

    def result_processor() -> None:
        """Process worker outputs in chunk order for stable start/stop handling."""
        pending_results: dict[int, TranscriptionResult] = {}
        next_chunk = 1

        while not stop_event.is_set() or not result_queue.empty() or pending_results:
            try:
                result = result_queue.get(timeout=0.2)
                pending_results[result.chunk_index] = result
                result_queue.task_done()
            except queue.Empty:
                pass

            while next_chunk in pending_results:
                ordered_result = pending_results.pop(next_chunk)
                print(
                    f"\n[chunk {ordered_result.chunk_index}] worker={ordered_result.worker_id} "
                    f"status={ordered_result.status_code} ({ordered_result.elapsed_seconds:.2f}s)"
                )
                if ordered_result.payload is not None:
                    print(json.dumps(ordered_result.payload, indent=2, ensure_ascii=False))
                else:
                    print(ordered_result.raw_response_text)

                transcript_text = ordered_result.transcript_text
                started, stopped, _, finalized_text = session_state.handle_transcript(transcript_text)

                if started:
                    print("[session] Start keyword detected. Capturing transcript chunks.")

                if stopped:
                    print("[session] Stop keyword detected. Finalizing captured text.")
                    final_text = (finalized_text or "").strip()
                    print("\n[session] Aggregated text:")
                    print(final_text if final_text else "(empty)")
                    if final_text:
                        pause_capture_event.set()
                        # Drop buffered mic frames to avoid processing stale audio after playback.
                        while True:
                            try:
                                audio_frame_queue.get_nowait()
                            except queue.Empty:
                                break

                        spoken_text = final_text
                        if not args.no_gemini:
                            print("[ask] Sending finalized text to Gemini...")
                            answer = request_gemini_answer(
                                ask_url=ask_url,
                                question=final_text,
                                timeout_seconds=args.timeout,
                            )
                            if answer:
                                spoken_text = answer
                                print("[ask] Gemini answer received.")
                            else:
                                spoken_text = "Вибачте, зараз не вдалося отримати відповідь. Спробуйте ще раз, будь ласка."

                        handle_tts_and_playback(
                            text=spoken_text,
                            args=args,
                            tts_url=tts_url,
                            label="gemini answer" if not args.no_gemini else "final aggregated text",
                        )
                        pause_capture_event.clear()
                    print("[session] Listening continues. Say start/старт for a new session.")

                next_chunk += 1

    result_thread = threading.Thread(target=result_processor, daemon=True)
    result_thread.start()

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
                try:
                    frame = audio_frame_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

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
        result_thread.join(timeout=2.0)


if __name__ == "__main__":
    main()
