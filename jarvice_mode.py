#!/usr/bin/env python3
"""
Jarvis listener (local PC)
- Always-on microphone
- Wake words: Jarvis, OK Jarvis, Neo
- Continuous conversation mode synced with the backend
- Sends transcribed requests to the Flask backend
"""

from __future__ import annotations

import os
import queue
import re
import sys
import time
from dataclasses import dataclass

import numpy as np
import requests
import sounddevice as sd
from faster_whisper import WhisperModel


@dataclass
class Config:
    sample_rate: int = int(os.environ.get("JARVICE_SAMPLE_RATE", "16000"))
    wake_chunk_sec: float = float(os.environ.get("JARVICE_WAKE_CHUNK_SEC", "1.8"))
    command_max_sec: float = float(os.environ.get("JARVICE_COMMAND_MAX_SEC", "10.0"))
    silence_rms_threshold: float = float(os.environ.get("JARVICE_SILENCE_RMS", "170"))
    silence_timeout_sec: float = float(os.environ.get("JARVICE_SILENCE_TIMEOUT", "1.0"))
    backend_url: str = os.environ.get("JARVICE_BACKEND", "http://127.0.0.1:5000")
    wake_model: str = os.environ.get("JARVICE_WAKE_MODEL", "tiny")
    command_model: str = os.environ.get("JARVICE_COMMAND_MODEL", "small")
    ping_interval_sec: float = float(os.environ.get("JARVICE_PING_INTERVAL", "4.0"))
    poll_mode_interval_sec: float = float(os.environ.get("JARVICE_POLL_MODE_INTERVAL", "2.0"))
    wake_timeout_after_word_sec: float = float(os.environ.get("JARVICE_WAKE_TIMEOUT_AFTER_WORD", "5.0"))


WAKE_PATTERNS = [
    r"\bok\s+jarvis\b",
    r"\bok\s+jarvice\b",
    r"\bjarvis\b",
    r"\bjarvice\b",
    r"\bneo\b",
]


def rms_int16(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))


def transcribe_int16_pcm(model: WhisperModel, pcm: np.ndarray) -> str:
    if pcm.size == 0:
        return ""

    float_audio = pcm.astype(np.float32) / 32768.0
    segments, _ = model.transcribe(
        float_audio,
        language=None,
        vad_filter=True,
        beam_size=1,
        condition_on_previous_text=False,
    )
    return " ".join(segment.text.strip() for segment in segments if segment.text).strip()


def has_wake_word(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in WAKE_PATTERNS)


def strip_wake_words(text: str) -> str:
    cleaned = text.lower()
    for pattern in WAKE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.!?;:")
    return cleaned.strip()


def ask_backend(prompt: str, backend_url: str) -> dict:
    response = requests.post(
        f"{backend_url.rstrip('/')}/api/ask",
        json={"prompt": prompt},
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


def handle_prompt(prompt: str, cfg: Config) -> None:
    cleaned = prompt.strip()
    if not cleaned:
        return
    print(f"[ToBrain] {cleaned}")
    try:
        data = ask_backend(cleaned, cfg.backend_url)
        print(f"[Jarvis] {data.get('text', '')}")
        print(f"[Meta] model={data.get('model', '-')} action={data.get('action', 'none')} lang={data.get('language', '-')}")
    except Exception as exc:
        print(f"[Jarvis] Backend error: {exc}")


def main() -> int:
    cfg = Config()
    print(f"[JarvisListener] Backend: {cfg.backend_url}")
    print(f"[JarvisListener] Whisper wake={cfg.wake_model}, command={cfg.command_model}")
    print("[JarvisListener] Loading Whisper models...")

    wake_model = WhisperModel(cfg.wake_model, device="cpu", compute_type="int8")
    command_model = WhisperModel(cfg.command_model, device="cpu", compute_type="int8")

    q: queue.Queue[np.ndarray] = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(f"[Audio] {status}")
        q.put(indata[:, 0].copy())

    wake_samples_target = int(cfg.sample_rate * cfg.wake_chunk_sec)
    wake_buffer = np.empty((0,), dtype=np.int16)
    current_mode = fetch_mode(cfg.backend_url)
    last_ping_at = 0.0
    last_poll_at = 0.0

    print(f"[JarvisListener] Ready. Mode={current_mode}. Wake word: Jarvis / OK Jarvis / Neo")

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
                    print(f"[JarvisListener] Mode switched to: {current_mode}")
                last_poll_at = now

            frame = q.get()

            if current_mode == "continuous":
                if rms_int16(frame) <= cfg.silence_rms_threshold:
                    continue
                phrase_pcm = capture_until_silence(q, cfg, include_first=[frame])
                prompt = transcribe_int16_pcm(command_model, phrase_pcm)
                if prompt:
                    print(f"[Continuous] {prompt}")
                    handle_prompt(prompt, cfg)
                continue

            wake_buffer = np.concatenate([wake_buffer, frame])
            if wake_buffer.size < wake_samples_target:
                continue

            wake_chunk = wake_buffer[:wake_samples_target]
            wake_buffer = wake_buffer[wake_samples_target:]
            wake_text = transcribe_int16_pcm(wake_model, wake_chunk)
            if not wake_text or not has_wake_word(wake_text):
                continue

            print(f"[Wake] {wake_text}")
            inline_prompt = strip_wake_words(wake_text)
            if inline_prompt:
                handle_prompt(inline_prompt, cfg)
                continue

            print("[JarvisListener] Wake word detected. Listening...")
            phrase_pcm = wait_for_phrase_start(q, cfg)
            prompt = transcribe_int16_pcm(command_model, phrase_pcm)

            if not prompt:
                print("[JarvisListener] Empty command, returning to wake mode.")
                continue

            handle_prompt(prompt, cfg)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[JarvisListener] Stopped.")
        sys.exit(0)
