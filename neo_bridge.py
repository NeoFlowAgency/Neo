#!/usr/bin/env python3
"""
neo_bridge.py — Pont audio Neo
  Micro ESP32 (MQTT neo/audio/mic)
    → STT (faster-whisper)
    → OpenClaw (WebSocket Gateway)
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
import websocket
import edge_tts
from faster_whisper import WhisperModel

# ── Config ─────────────────────────────────────────────────────
MQTT_HOST    = "localhost"
MQTT_PORT    = 1883
TOPIC_MIC    = "neo/audio/mic"
TOPIC_AUDIO  = "neo/audio/data"
TOPIC_CMD    = "neo/commandes"

OPENCLAW_WS  = "ws://127.0.0.1:18789"
TTS_VOICE    = "fr-FR-DeniseNeural"
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
_oc_ws: websocket.WebSocket | None = None
_oc_id = 0


def openclaw_ask(text: str) -> str:
    global _oc_ws, _oc_id
    try:
        if _oc_ws is None or not _oc_ws.connected:
            _oc_ws = websocket.create_connection(OPENCLAW_WS, timeout=15)
        _oc_id += 1
        req = {
            "method": "agent.send_message",
            "params": {"agentId": "main", "message": text},
            "id": _oc_id,
        }
        _oc_ws.send(json.dumps(req))
        raw = _oc_ws.recv()
        data = json.loads(raw)
        return data.get("result", {}).get("output", "")
    except Exception as e:
        print(f"[OpenClaw] Erreur: {e}")
        _oc_ws = None
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
