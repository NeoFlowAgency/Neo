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
WHISPER_MODEL_NAME = os.environ.get("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "auto")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")

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
_stt_lock = threading.Lock()
_whisper_model = None


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


def send_esp32_payload(endpoint: str, payload: dict, timeout: int = 6) -> dict:
    url = f"{ESP32_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        return {
            "ok": r.ok,
            "status_code": r.status_code,
            "response": r.text[:120],
            "endpoint": endpoint,
        }
    except requests.RequestException as exc:
        logger.error("ESP32 call failed: %s", exc)
        return {"ok": False, "status_code": None, "error": str(exc), "endpoint": endpoint}


def get_whisper_model():
    global _whisper_model
    with _stt_lock:
        if _whisper_model is None:
            try:
                from faster_whisper import WhisperModel  # lazy import (optional dependency at runtime)
            except Exception as exc:
                raise RuntimeError(
                    "faster-whisper indisponible sur ce système (import bloqué). "
                    "Désactive STT fallback web ou ajuste la politique de sécurité Windows."
                ) from exc
            logger.info(
                "Loading faster-whisper model=%s device=%s compute_type=%s",
                WHISPER_MODEL_NAME,
                WHISPER_DEVICE,
                WHISPER_COMPUTE_TYPE,
            )
            _whisper_model = WhisperModel(
                WHISPER_MODEL_NAME,
                device=WHISPER_DEVICE,
                compute_type=WHISPER_COMPUTE_TYPE,
            )
    return _whisper_model


def transcribe_audio_file(file_path: Path) -> str:
    model = get_whisper_model()
    segments, _info = model.transcribe(str(file_path), language="fr")
    text = "".join(segment.text for segment in segments).strip()
    return text


def parse_json_body() -> dict:
    """
    Parse JSON body robustly, including Windows PowerShell UTF-16 payloads.
    """
    parsed = request.get_json(silent=True)
    if isinstance(parsed, dict):
        return parsed

    raw = request.get_data(cache=False) or b""
    if not raw:
        return {}

    # Try common encodings in order.
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            decoded = raw.decode(encoding)
            obj = json.loads(decoded)
            if isinstance(obj, dict):
                return obj
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue

    return {}


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

    body = parse_json_body()
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

    # Keep compatibility file + unique file (prevents browser caching stale audio).
    generate_wav(result["text"], "response.wav")
    unique_name = f"response_{int(time.time())}_{uuid.uuid4().hex[:6]}.wav"
    generate_wav(result["text"], unique_name)

    host_ip = get_local_ip()
    audio_url = f"http://{host_ip}:{SERVER_PORT}{url_for('serve_audio', filename=unique_name)}"

    # Try full speak endpoint first (action + wav playback on robot speaker).
    speak_payload = {
        "action": result["action"],
        "text": result["text"],
        "audio_url": audio_url,
    }
    esp32_result = send_esp32_payload("speak", speak_payload, timeout=12)
    if not esp32_result.get("ok"):
        # Fallback for older firmware that only supports /action.
        esp32_result = send_esp32_payload("action", {"action": result["action"]}, timeout=4)

    logger.info("Action '%s' sent to ESP32: %s", result["action"], esp32_result)
    return jsonify({
        "text": result["text"],
        "action": result["action"],
        "audio_url": audio_url,
        "esp32": esp32_result,
    })


@app.route("/transcribe", methods=["POST", "OPTIONS"])
def transcribe_route():
    if request.method == "OPTIONS":
        return ("", 204)

    if "audio" not in request.files:
        return jsonify({"error": "Fichier audio manquant (champ 'audio')."}), 400

    audio_file = request.files["audio"]
    if not audio_file.filename:
        return jsonify({"error": "Nom de fichier audio invalide."}), 400

    suffix = Path(audio_file.filename).suffix.lower() or ".webm"
    temp_name = f"stt_{int(time.time())}_{uuid.uuid4().hex[:8]}{suffix}"
    temp_path = AUDIO_DIR / temp_name

    try:
        audio_file.save(temp_path)
        text = transcribe_audio_file(temp_path)
        return jsonify({"text": text})
    except Exception as exc:
        logger.exception("STT transcription failed")
        return jsonify({"error": f"Transcription échouée: {exc}"}), 500
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass


@app.route("/audio/<path:filename>", methods=["GET"])
def serve_audio(filename: str):
    return send_from_directory(AUDIO_DIR, filename)


if __name__ == "__main__":
    logger.info("Starting local robot server on %s:%s", SERVER_HOST, SERVER_PORT)
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False)
