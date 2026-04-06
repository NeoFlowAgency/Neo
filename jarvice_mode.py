#!/usr/bin/env python3
"""
Jarvice Phase 1 (local PC)
- Always-on mic listening
- Wake words: neo, aria, jarvis/jarvice, ok jarvis/jarvice
- After wake word: captures voice command and sends to Flask /ask
- Backend handles LLM+TTS+ESP32 action/audio
"""

from __future__ import annotations

import os
import queue
import re
import sys
import time
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import requests
import sounddevice as sd
from faster_whisper import WhisperModel


@dataclass
class Config:
    sample_rate: int = int(os.environ.get("JARVICE_SAMPLE_RATE", "16000"))
    wake_chunk_sec: float = float(os.environ.get("JARVICE_WAKE_CHUNK_SEC", "2.0"))
    command_max_sec: float = float(os.environ.get("JARVICE_COMMAND_MAX_SEC", "8.0"))
    silence_rms_threshold: float = float(os.environ.get("JARVICE_SILENCE_RMS", "220"))
    silence_timeout_sec: float = float(os.environ.get("JARVICE_SILENCE_TIMEOUT", "1.2"))
    backend_url: str = os.environ.get("JARVICE_BACKEND", "http://127.0.0.1:5000")
    wake_model: str = os.environ.get("JARVICE_WAKE_MODEL", "tiny")
    command_model: str = os.environ.get("JARVICE_COMMAND_MODEL", "small")


WAKE_PATTERNS = [
    r"\bneo\b",
    r"\baria\b",
    r"\bjarvis\b",
    r"\bjarvice\b",
    r"\bok\s+jarvis\b",
    r"\bok\s+jarvice\b",
]


def rms_int16(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))


def transcribe_int16_pcm(model: WhisperModel, pcm: np.ndarray, sample_rate: int) -> str:
    if pcm.size == 0:
        return ""

    float_audio = pcm.astype(np.float32) / 32768.0
    segments, _ = model.transcribe(float_audio, language="fr")
    text = " ".join(s.text.strip() for s in segments if s.text).strip()
    return text


def has_wake_word(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in WAKE_PATTERNS)


def ask_backend(prompt: str, backend_url: str) -> dict:
    r = requests.post(f"{backend_url.rstrip('/')}/ask", json={"prompt": prompt}, timeout=90)
    r.raise_for_status()
    return r.json()


def main() -> int:
    cfg = Config()

    print(f"[Jarvice] Backend: {cfg.backend_url}")
    print(f"[Jarvice] Wake model={cfg.wake_model}, Command model={cfg.command_model}")
    print("[Jarvice] Chargement modèles Whisper...")

    wake_model = WhisperModel(cfg.wake_model, device="cpu", compute_type="int8")
    command_model = WhisperModel(cfg.command_model, device="cpu", compute_type="int8")

    print("[Jarvice] Prêt. Dis: 'Neo' / 'Aria' / 'Jarvice' ...")

    q: queue.Queue[np.ndarray] = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(f"[Audio] {status}")
        q.put(indata[:, 0].copy())  # mono int16

    wake_samples_target = int(cfg.sample_rate * cfg.wake_chunk_sec)

    with sd.InputStream(
        samplerate=cfg.sample_rate,
        channels=1,
        dtype="int16",
        blocksize=1024,
        callback=callback,
    ):
        wake_buffer = np.empty((0,), dtype=np.int16)

        while True:
            chunk = q.get()
            wake_buffer = np.concatenate([wake_buffer, chunk])

            if wake_buffer.size < wake_samples_target:
                continue

            chunk_to_check = wake_buffer[:wake_samples_target]
            wake_buffer = wake_buffer[wake_samples_target:]

            wake_text = transcribe_int16_pcm(wake_model, chunk_to_check, cfg.sample_rate)
            if not wake_text:
                continue

            print(f"[WakeChunk] {wake_text}")
            if not has_wake_word(wake_text):
                continue

            print("[Jarvice] Wake word détecté. J'écoute ta commande...")

            cmd_frames: list[np.ndarray] = []
            start = time.time()
            last_voice = time.time()

            while time.time() - start < cfg.command_max_sec:
                frame = q.get()
                cmd_frames.append(frame)
                level = rms_int16(frame)
                if level > cfg.silence_rms_threshold:
                    last_voice = time.time()

                if time.time() - last_voice > cfg.silence_timeout_sec and len(cmd_frames) > 4:
                    break

            pcm = np.concatenate(cmd_frames) if cmd_frames else np.empty((0,), dtype=np.int16)
            command = transcribe_int16_pcm(command_model, pcm, cfg.sample_rate)

            if not command:
                print("[Jarvice] Commande vide, reprise écoute wake word.")
                continue

            print(f"[ToBrain] {command}")
            try:
                data = ask_backend(command, cfg.backend_url)
                print(f"[Neo] {data.get('text', '')}")
                print(f"[Action] {data.get('action', 'none')}")
            except Exception as exc:
                print(f"[Jarvice] Erreur backend: {exc}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[Jarvice] Arrêt manuel.")
        sys.exit(0)
