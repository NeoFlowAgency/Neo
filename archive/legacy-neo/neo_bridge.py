#!/usr/bin/env python3
"""
neo_bridge.py — Pont audio Neo
  Micro ESP32 (MQTT neo/audio/mic)
    → STT (faster-whisper)
    → OpenClaw (HTTP /v1/chat/completions)
    → TTS (edge-tts)
    → Speaker ESP32 (MQTT neo/audio/data)
"""

import asyncio
import io
import json
import threading
import time
import wave

import paho.mqtt.client as mqtt
import requests
import edge_tts
from faster_whisper import WhisperModel

# ── Config ─────────────────────────────────────────────────────
MQTT_HOST      = "localhost"
MQTT_PORT      = 1883
TOPIC_MIC      = "neo/audio/mic"
TOPIC_AUDIO    = "neo/audio/data"
TOPIC_CMD      = "neo/commandes"

OPENCLAW_URL   = "http://127.0.0.1:18789"
OPENCLAW_TOKEN = "48456fb15f32065747b6d2c540179d1dac3c67773521c6d3ebbe70268d63e8fa"
OPENCLAW_AGENT = "main"
TTS_VOICE      = "fr-FR-DeniseNeural"
SAMPLE_RATE  = 16000
CHUNK_SIZE   = 1024            # bytes per MQTT publish
SILENCE_SEC  = 1.5             # silence before processing utterance
VAD_THRESH   = 500             # RMS threshold for voice activity

# ── Whisper model (tiny = rapide, small = meilleur) ─────────────
print("[Bridge] Chargement Whisper…")
whisper = WhisperModel("small", device="cpu", compute_type="int8")
print("[Bridge] Whisper prêt")

# ── Audio buffer ───────────────────────────────────────────────
audio_buf: list[bytes] = []
last_voice_time = time.time()
processing = False


def rms(data: bytes) -> float:
    import struct, math
    samples = struct.unpack(f"{len(data)//2}h", data)
    if not samples:
        return 0.0
    return math.sqrt(sum(s * s for s in samples) / len(samples))


# ── OpenClaw ───────────────────────────────────────────────────
def openclaw_ask(text: str) -> str:
    """Envoie un message à OpenClaw via l'API HTTP (OpenAI-compatible) et retourne la réponse."""
    try:
        headers = {
            "Authorization":       f"Bearer {OPENCLAW_TOKEN}",
            "Content-Type":        "application/json",
            "x-openclaw-agent-id": OPENCLAW_AGENT,
        }
        payload = {
            "model":    "openclaw",
            "user":     "neo_bridge",
            "messages": [{"role": "user", "content": text}],
        }
        r = requests.post(
            f"{OPENCLAW_URL}/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[OpenClaw] Erreur: {e}")
        return "Désolé, je n'ai pas pu me connecter à mon cerveau."


# ── TTS → MQTT ─────────────────────────────────────────────────
def speak(text: str, client: mqtt.Client):
    async def _tts():
        tts = edge_tts.Communicate(text, TTS_VOICE)
        buf = io.BytesIO()
        async for chunk in tts.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        buf.seek(0)
        raw = buf.read()
        # Publish in chunks
        for i in range(0, len(raw), CHUNK_SIZE):
            client.publish(TOPIC_AUDIO, raw[i:i + CHUNK_SIZE])
            time.sleep(0.01)

    asyncio.run(_tts())


# ── Process utterance ──────────────────────────────────────────
def process_utterance(pcm_data: bytes, client: mqtt.Client):
    global processing
    processing = True
    try:
        # Build WAV in memory
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm_data)
        buf.seek(0)

        # STT
        segments, _ = whisper.transcribe(buf, language="fr")
        text = " ".join(s.text for s in segments).strip()
        if not text:
            return
        print(f"[STT] {text!r}")

        # Show on LCD
        client.publish(TOPIC_CMD, json.dumps({"action": "lcd", "texte": text[:32]}))

        # Ask Neo
        reply = openclaw_ask(text)
        print(f"[Neo] {reply!r}")

        # TTS
        if reply:
            client.publish(TOPIC_CMD, json.dumps({"action": "lcd", "texte": f"Neo: {reply[:28]}"}))
            speak(reply, client)
    except Exception as e:
        print(f"[Bridge] Erreur traitement: {e}")
    finally:
        processing = False


# ── MQTT callbacks ─────────────────────────────────────────────
def on_message(client, userdata, msg):
    global audio_buf, last_voice_time, processing

    if msg.topic != TOPIC_MIC or processing:
        return

    data = msg.payload
    level = rms(data)

    if level > VAD_THRESH:
        last_voice_time = time.time()
        audio_buf.append(data)
    elif audio_buf:
        # Still accumulate a bit after silence starts
        audio_buf.append(data)
        if time.time() - last_voice_time > SILENCE_SEC:
            pcm = b"".join(audio_buf)
            audio_buf.clear()
            threading.Thread(target=process_utterance, args=(pcm, client), daemon=True).start()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe(TOPIC_MIC)
        print("[Bridge] MQTT connecté, écoute sur neo/audio/mic")
    else:
        print(f"[Bridge] MQTT erreur {rc}")


# ── Main ───────────────────────────────────────────────────────
def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    print(f"[Bridge] Connexion à {MQTT_HOST}:{MQTT_PORT}…")
    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            client.loop_forever()
        except Exception as e:
            print(f"[Bridge] Erreur: {e} — reconnexion dans 5s")
            time.sleep(5)


if __name__ == "__main__":
    main()
