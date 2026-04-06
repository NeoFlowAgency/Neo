import json
import logging
import os
import re
import socket
import threading
import time
import uuid
from pathlib import Path

import pyttsx3
import requests
from flask import Flask, jsonify, request, send_from_directory, url_for


# -------------------------- Configuration --------------------------
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma:4b")
ESP32_URL = os.environ.get("ESP32_URL", "http://192.168.1.50")
AUDIO_DIR = Path(os.environ.get("AUDIO_DIR", "audio_out"))
SERVER_HOST = os.environ.get("HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("PORT", "5000"))

ALLOWED_ACTIONS = {"turn_left", "turn_right", "nod", "none"}
SYSTEM_PROMPT = (
    "Tu es le cerveau d'un robot physique. "
    "Tu dois répondre UNIQUEMENT en JSON valide, sans texte avant/après. "
    "Format exact: {\"text\":\"...\",\"action\":\"turn_left|turn_right|nod|none\"}. "
    "Si aucune action physique n'est nécessaire, utilise action='none'. "
    "Le texte doit être naturel et court."
)

AUDIO_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("neo-local")

app = Flask(__name__)
_tts_lock = threading.Lock()


def get_local_ip() -> str:
    """Best-effort LAN IP discovery used for audio URL generation."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _extract_json_block(raw: str) -> dict:
    """Extract and parse JSON object from LLM output, with safe fallback."""
    cleaned = raw.strip()
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    raise ValueError("LLM output is not valid JSON")


def ask_ollama(prompt: str) -> dict:
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "prompt": f"{SYSTEM_PROMPT}\nUtilisateur: {prompt}",
        "options": {"temperature": 0.2},
    }

    logger.info("Calling Ollama model=%s", OLLAMA_MODEL)
    response = requests.post(OLLAMA_URL, json=payload, timeout=90)
    response.raise_for_status()
    data = response.json()
    raw_text = data.get("response", "").strip()

    logger.info("Raw LLM output: %s", raw_text[:200])
    parsed = _extract_json_block(raw_text)

    text = str(parsed.get("text", "")).strip()
    action = str(parsed.get("action", "none")).strip()

    if not text:
        text = "Je suis prêt, dis-moi quoi faire."
    if action not in ALLOWED_ACTIONS:
        logger.warning("Unsupported action '%s', forcing 'none'", action)
        action = "none"

    return {"text": text, "action": action}


def generate_wav(text: str, filename: str = "response.wav") -> Path:
    wav_path = AUDIO_DIR / filename
    with _tts_lock:
        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        engine.setProperty("volume", 1.0)
        engine.save_to_file(text, str(wav_path))
        engine.runAndWait()
        engine.stop()
    logger.info("WAV generated: %s", wav_path)
    return wav_path


def send_action_to_esp32(action: str) -> dict:
    url = f"{ESP32_URL.rstrip('/')}/action"
    payload = {"action": action}
    try:
        r = requests.post(url, json=payload, timeout=3)
        return {
            "ok": r.ok,
            "status_code": r.status_code,
            "response": r.text[:120],
        }
    except requests.RequestException as exc:
        logger.error("ESP32 call failed: %s", exc)
        return {"ok": False, "status_code": None, "error": str(exc)}


@app.after_request
def add_cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return resp


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "model": OLLAMA_MODEL, "esp32_url": ESP32_URL})


@app.route("/ask", methods=["POST", "OPTIONS"])
def ask_route():
    if request.method == "OPTIONS":
        return ("", 204)

    body = request.get_json(silent=True) or {}
    prompt = str(body.get("prompt", "")).strip()
    if not prompt:
        return jsonify({"error": "'prompt' est obligatoire"}), 400

    try:
        result = ask_ollama(prompt)
    except Exception as exc:
        logger.exception("Ollama failed")
        result = {
            "text": "Désolé, je n'ai pas pu générer une réponse correcte.",
            "action": "none",
            "error": str(exc),
        }

    # Keep a stable filename for simple clients, plus a unique backup for logs/debug.
    generate_wav(result["text"], "response.wav")
    unique_name = f"response_{int(time.time())}_{uuid.uuid4().hex[:6]}.wav"
    generate_wav(result["text"], unique_name)

    esp32_result = send_action_to_esp32(result["action"])
    logger.info("Action '%s' sent to ESP32: %s", result["action"], esp32_result)

    host_ip = get_local_ip()
    audio_url = f"http://{host_ip}:{SERVER_PORT}{url_for('serve_audio', filename='response.wav')}"
    return jsonify({
        "text": result["text"],
        "action": result["action"],
        "audio_url": audio_url,
        "esp32": esp32_result,
    })


@app.route("/audio/<path:filename>", methods=["GET"])
def serve_audio(filename: str):
    return send_from_directory(AUDIO_DIR, filename)


if __name__ == "__main__":
    logger.info("Starting local robot server on %s:%s", SERVER_HOST, SERVER_PORT)
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False)
