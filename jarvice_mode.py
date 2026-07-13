#!/usr/bin/env python3
"""
Jarvis listener (local PC)
- Always-on microphone
- Wake words: Jarvis, OK Jarvis
- Continuous conversation mode synced with the backend
- Sends transcribed requests to the Flask backend
"""

from __future__ import annotations

import difflib
import io
import os
import queue
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from threading import Thread

import numpy as np
import requests
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel


@dataclass
class Config:
    sample_rate: int = int(os.environ.get("JARVICE_SAMPLE_RATE", "16000"))
    wake_chunk_sec: float = float(os.environ.get("JARVICE_WAKE_CHUNK_SEC", "2.6"))
    wake_overlap_sec: float = float(os.environ.get("JARVICE_WAKE_OVERLAP_SEC", "1.6"))
    command_max_sec: float = float(os.environ.get("JARVICE_COMMAND_MAX_SEC", "10.0"))
    silence_rms_threshold: float = float(os.environ.get("JARVICE_SILENCE_RMS", "170"))
    interrupt_rms_threshold: float = float(os.environ.get("JARVICE_INTERRUPT_RMS", "420"))
    silence_timeout_sec: float = float(os.environ.get("JARVICE_SILENCE_TIMEOUT", "1.0"))
    backend_url: str = os.environ.get("JARVICE_BACKEND", "http://127.0.0.1:5000")
    wake_model: str = os.environ.get("JARVICE_WAKE_MODEL", "medium")
    command_model: str = os.environ.get("JARVICE_COMMAND_MODEL", "small")
    stt_language: str = os.environ.get("JARVICE_STT_LANGUAGE", "fr")
    ping_interval_sec: float = float(os.environ.get("JARVICE_PING_INTERVAL", "4.0"))
    poll_mode_interval_sec: float = float(os.environ.get("JARVICE_POLL_MODE_INTERVAL", "2.0"))
    wake_timeout_after_word_sec: float = float(os.environ.get("JARVICE_WAKE_TIMEOUT_AFTER_WORD", "5.0"))
    interrupt_cooldown_sec: float = float(os.environ.get("JARVICE_INTERRUPT_COOLDOWN", "1.2"))


WAKE_PATTERNS = [
    r"\bok\s+jarvis\b",
    r"\bok\s+jarvice\b",
    r"\bok\s+jarvise\b",
    r"\bok\s+javis\b",
    r"\bok\s+charvis\b",
    r"\bhey\s+jarvis\b",
    r"\bjarvis\b",
    r"\bjarvice\b",
    r"\bjarvise\b",
    r"\bjavis\b",
    r"\bcharvis\b",
    r"\bchavis\b",
    r"\bdjarvis\b",
]

WAKE_UP_PATTERNS = [
    r"\bwake up\b",
    r"\breveille toi\b",
    r"\breveille-toi\b",
    r"\bsors de veille\b",
]

STOP_ONLY_PATTERNS = [
    r"^\s*stop\s*$",
    r"^\s*tais toi\s*$",
    r"^\s*ta gueule\s*$",
    r"^\s*silence\s*$",
    r"^\s*shut up\s*$",
]

WAKE_ALIASES = [
    "jarvis",
    "jarvice",
    "jarvise",
    "javis",
    "charvis",
    "chavis",
    "jervis",
]


def rms_int16(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))


def log(message: str) -> None:
    print(message, flush=True)


def normalize_language(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower()
    if lowered.startswith("fr"):
        return "fr"
    if lowered.startswith("en"):
        return "en"
    return None


def transcribe_int16_pcm(model: WhisperModel, pcm: np.ndarray, forced_language: str | None = None) -> tuple[str, str | None]:
    if pcm.size == 0:
        return "", None

    float_audio = pcm.astype(np.float32) / 32768.0
    segments, info = model.transcribe(
        float_audio,
        language=forced_language or None,
        vad_filter=True,
        beam_size=1,
        condition_on_previous_text=False,
    )
    text = " ".join(segment.text.strip() for segment in segments if segment.text).strip()
    return text, normalize_language(getattr(info, "language", None))


def has_wake_word(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in WAKE_PATTERNS)


def normalize_text(text: str) -> str:
    lowered = unicodedata.normalize("NFKD", text.lower())
    lowered = "".join(ch for ch in lowered if not unicodedata.combining(ch))
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def has_fuzzy_wake_word(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    if has_wake_word(normalized):
        return True
    tokens = normalized.split()
    if len(tokens) > 6:
        return False
    chunks = tokens + [" ".join(tokens[i : i + 2]) for i in range(max(0, len(tokens) - 1))]
    for chunk in chunks:
        # Keep fuzzy wake strict to avoid accidental triggers (ex: "j'arrive", "je revisse")
        if not (
            chunk.startswith("jar")
            or chunk.startswith("jav")
            or chunk.startswith("char")
            or chunk.startswith("chav")
        ):
            continue
        for alias in WAKE_ALIASES:
            if difflib.SequenceMatcher(None, chunk, alias).ratio() >= 0.87:
                return True
    return False


def strip_wake_words(text: str) -> str:
    cleaned = text
    for pattern in WAKE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.!?;:")
    return cleaned.strip()


def is_wake_up_intent(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in WAKE_UP_PATTERNS)


def strip_wake_prefix(text: str) -> str:
    cleaned = strip_wake_words(text)
    if cleaned != text.strip():
        return cleaned
    normalized_tokens = normalize_text(text).split()
    original_tokens = text.strip().split()
    if not normalized_tokens or not original_tokens:
        return ""
    first = normalized_tokens[0]
    for alias in WAKE_ALIASES:
        if (
            first.startswith("jar")
            or first.startswith("jav")
            or first.startswith("char")
            or first.startswith("chav")
        ) and difflib.SequenceMatcher(None, first, alias).ratio() >= 0.87:
            return " ".join(original_tokens[1:]).strip(" ,.!?;:")
    return text.strip()


def ask_backend(prompt: str, backend_url: str, language: str | None = None) -> dict:
    response = requests.post(
        f"{backend_url.rstrip('/')}/api/ask",
        json={"prompt": prompt, "language": language},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def fetch_mode(backend_url: str) -> str:
    try:
        response = requests.get(f"{backend_url.rstrip('/')}/api/listening-mode", timeout=5)
        response.raise_for_status()
        return response.json().get("mode", "wake")
    except requests.RequestException:
        return "wake"


def push_ping(backend_url: str, mode: str) -> None:
    try:
        requests.post(
            f"{backend_url.rstrip('/')}/api/listener/ping",
            json={"mode": mode, "source": "jarvice_mode"},
            timeout=5,
        )
    except requests.RequestException:
        pass


def stop_backend_speaking(backend_url: str) -> None:
    try:
        requests.post(f"{backend_url.rstrip('/')}/api/stop-speaking", json={}, timeout=5)
    except requests.RequestException:
        pass


def set_backend_mode(backend_url: str, mode: str) -> None:
    try:
        requests.post(f"{backend_url.rstrip('/')}/api/listening-mode", json={"mode": mode}, timeout=5)
    except requests.RequestException:
        pass


def play_audio_url_async(audio_url: str) -> None:
    def worker() -> None:
        try:
            response = requests.get(audio_url, timeout=30)
            response.raise_for_status()
            data, sample_rate = sf.read(io.BytesIO(response.content), dtype="float32")
            if isinstance(data, np.ndarray) and data.ndim > 1:
                data = np.mean(data, axis=1)
            sd.play(data, sample_rate)
            sd.wait()
        except Exception as exc:
            log(f"[AudioPlayback] Failed: {exc}")

    Thread(target=worker, daemon=True).start()


def is_stop_only(text: str) -> bool:
    lowered = text.strip().lower()
    return any(re.search(pattern, lowered) for pattern in STOP_ONLY_PATTERNS)


def drain_queue(q: "queue.Queue[np.ndarray]", max_items: int = 24) -> None:
    drained = 0
    while drained < max_items:
        try:
            q.get_nowait()
            drained += 1
        except queue.Empty:
            break


def capture_until_silence(q: "queue.Queue[np.ndarray]", cfg: Config, include_first: list[np.ndarray] | None = None) -> np.ndarray:
    frames = list(include_first or [])
    started_at = time.time()
    last_voice = time.time()

    while time.time() - started_at < cfg.command_max_sec:
        frame = q.get()
        frames.append(frame)
        if rms_int16(frame) > cfg.silence_rms_threshold:
            last_voice = time.time()
        if time.time() - last_voice > cfg.silence_timeout_sec and len(frames) > 6:
            break

    return np.concatenate(frames) if frames else np.empty((0,), dtype=np.int16)


def wait_for_phrase_start(q: "queue.Queue[np.ndarray]", cfg: Config) -> np.ndarray:
    deadline = time.time() + cfg.wake_timeout_after_word_sec
    buffered: list[np.ndarray] = []

    while time.time() < deadline:
        frame = q.get()
        buffered.append(frame)
        if rms_int16(frame) > cfg.silence_rms_threshold:
            return capture_until_silence(q, cfg, include_first=buffered)
    return np.empty((0,), dtype=np.int16)


def handle_prompt(prompt: str, cfg: Config, language: str | None = None) -> float:
    cleaned = prompt.strip()
    if not cleaned:
        return 0.0
    log(f"[ToBrain] {cleaned}")
    try:
        data = ask_backend(cleaned, cfg.backend_url, language=language)
        log(f"[Jarvis] {data.get('text', '')}")
        log(f"[Meta] model={data.get('model', '-')} action={data.get('action', 'none')} lang={data.get('language', '-')}")
        audio_url = data.get("audio_url")
        if isinstance(audio_url, str) and audio_url.strip():
            play_audio_url_async(audio_url.strip())
        return float(data.get("speech_duration") or 0.0)
    except Exception as exc:
        log(f"[Jarvis] Backend error: {exc}")
        return 0.0


def handle_prompt_and_sync_mode(prompt: str, cfg: Config, language: str | None, current_mode: str) -> tuple[float, str]:
    duration = handle_prompt(prompt, cfg, language)
    synced_mode = fetch_mode(cfg.backend_url)
    if synced_mode != current_mode:
        log(f"[JarvisListener] Mode switched to: {synced_mode}")
    return duration, synced_mode


def main() -> int:
    cfg = Config()
    log(f"[JarvisListener] Backend: {cfg.backend_url}")
    log(f"[JarvisListener] Whisper wake={cfg.wake_model}, command={cfg.command_model}")
    log("[JarvisListener] Loading Whisper models...")
    wake_model = WhisperModel(cfg.wake_model, device="cpu", compute_type="int8")
    command_model = WhisperModel(cfg.command_model, device="cpu", compute_type="int8")

    q: queue.Queue[np.ndarray] = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            log(f"[Audio] {status}")
        q.put(indata[:, 0].copy())

    set_backend_mode(cfg.backend_url, "wake")
    current_mode = "wake"
    last_ping_at = 0.0
    last_poll_at = 0.0
    speaking_until = 0.0
    last_interrupt_at = 0.0

    log(f"[JarvisListener] Ready. Mode={current_mode}. Wake word: Jarvis / OK Jarvis")

    with sd.InputStream(
        samplerate=cfg.sample_rate,
        channels=1,
        dtype="int16",
        blocksize=1024,
        callback=callback,
    ):
        while True:
            now = time.time()
            if now - last_ping_at >= cfg.ping_interval_sec:
                push_ping(cfg.backend_url, current_mode)
                last_ping_at = now

            if now - last_poll_at >= cfg.poll_mode_interval_sec:
                polled_mode = fetch_mode(cfg.backend_url)
                if polled_mode != current_mode:
                    current_mode = polled_mode
                    log(f"[JarvisListener] Mode switched to: {current_mode}")
                last_poll_at = now

            frame = q.get()
            frame_rms = rms_int16(frame)

            if time.time() < speaking_until and frame_rms >= cfg.interrupt_rms_threshold:
                if now - last_interrupt_at < cfg.interrupt_cooldown_sec:
                    continue
                last_interrupt_at = now
                log("[Interrupt] User voice detected, stopping Jarvis.")
                stop_backend_speaking(cfg.backend_url)
                speaking_until = 0.0
                drain_queue(q)
                phrase_pcm = capture_until_silence(q, cfg, include_first=[frame])
                prompt, prompt_language = transcribe_int16_pcm(wake_model, phrase_pcm, forced_language=cfg.stt_language)
                if prompt:
                    log(f"[InterruptPrompt] {prompt}")
                    if not is_stop_only(prompt):
                        duration, current_mode = handle_prompt_and_sync_mode(prompt, cfg, prompt_language or cfg.stt_language, current_mode)
                        speaking_until = time.time() + duration + 0.2
                drain_queue(q)
                continue

            if current_mode == "sleep":
                if frame_rms <= cfg.silence_rms_threshold:
                    continue
                phrase_pcm = capture_until_silence(q, cfg, include_first=[frame])
                prompt, prompt_language = transcribe_int16_pcm(command_model, phrase_pcm, forced_language=cfg.stt_language)
                if not prompt:
                    continue
                log(f"[SleepHeard] {prompt}")
                if has_fuzzy_wake_word(prompt) or is_wake_up_intent(prompt):
                    set_backend_mode(cfg.backend_url, "wake")
                    current_mode = "wake"
                    duration, current_mode = handle_prompt_and_sync_mode("wake up", cfg, prompt_language or cfg.stt_language, current_mode)
                    speaking_until = time.time() + duration + 0.2
                    drain_queue(q)
                continue

            if current_mode == "continuous":
                if frame_rms <= cfg.silence_rms_threshold:
                    continue
                phrase_pcm = capture_until_silence(q, cfg, include_first=[frame])
                prompt, prompt_language = transcribe_int16_pcm(command_model, phrase_pcm, forced_language=cfg.stt_language)
                if prompt:
                    log(f"[Continuous] {prompt}")
                    duration, current_mode = handle_prompt_and_sync_mode(prompt, cfg, prompt_language or cfg.stt_language, current_mode)
                    speaking_until = time.time() + duration + 0.2
                    drain_queue(q)
                continue

            if frame_rms <= cfg.silence_rms_threshold:
                continue
            phrase_pcm = capture_until_silence(q, cfg, include_first=[frame])
            wake_text, wake_language = transcribe_int16_pcm(wake_model, phrase_pcm, forced_language=cfg.stt_language)
            if not wake_text:
                continue
            log(f"[WakeCandidate] {wake_text}")
            if not has_fuzzy_wake_word(wake_text):
                continue

            inline_prompt = strip_wake_prefix(wake_text)
            if inline_prompt:
                duration, current_mode = handle_prompt_and_sync_mode(inline_prompt, cfg, wake_language or cfg.stt_language, current_mode)
                speaking_until = time.time() + duration + 0.2
                drain_queue(q)
                continue

            log("[JarvisListener] Wake word detected. Listening...")
            phrase_pcm = wait_for_phrase_start(q, cfg)
            prompt, prompt_language = transcribe_int16_pcm(command_model, phrase_pcm, forced_language=cfg.stt_language)

            if not prompt:
                log("[JarvisListener] Empty command, returning to wake mode.")
                continue

            duration, current_mode = handle_prompt_and_sync_mode(prompt, cfg, prompt_language or cfg.stt_language, current_mode)
            speaking_until = time.time() + duration + 0.2
            drain_queue(q)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("\n[JarvisListener] Stopped.")
        sys.exit(0)
