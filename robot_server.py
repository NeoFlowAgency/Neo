import json
import logging
import os
import re
import socket
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pyttsx3
import requests
from flask import Flask, jsonify, request, send_from_directory, url_for


ROOT_DIR = Path(__file__).resolve().parent
AUDIO_DIR = Path(os.environ.get("AUDIO_DIR", ROOT_DIR / "audio_out"))
DATA_DIR = Path(os.environ.get("JARVIS_DATA_DIR", ROOT_DIR / "data"))
WEB_DIR = Path(os.environ.get("JARVIS_WEB_DIR", ROOT_DIR / "mobile_webapp"))
CHAT_FILE = DATA_DIR / "chat_history.json"

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL_LIGHT = os.environ.get("OLLAMA_MODEL_LIGHT", os.environ.get("OLLAMA_MODEL", "gemma4:e4b"))
OLLAMA_MODEL_HEAVY = os.environ.get("OLLAMA_MODEL_HEAVY", "qwen2.5:14b")
ESP32_URL = os.environ.get("ESP32_URL", "http://192.168.1.50")
SERVER_HOST = os.environ.get("HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("PORT", "5000"))
WHISPER_MODEL_NAME = os.environ.get("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "auto")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")
SERVO_CENTER_ACTION = os.environ.get("JARVIS_CENTER_ACTION", "center")

ALLOWED_ACTIONS = {"turn_left", "turn_right", "nod", "center", "none"}
ALLOWED_FACES = {"neutral", "listening", "thinking", "speaking", "happy", "sleepy"}
HEAVY_MODEL_HINTS = (
    "pourquoi",
    "comment",
    "explique",
    "analyse",
    "compare",
    "résume",
    "resume",
    "code",
    "script",
    "plan",
    "recherche",
    "cherche",
)

SYSTEM_PROMPT = (
    "Tu es Jarvis, l'assistant incarné d'un petit robot de bureau. "
    "Ta personnalité est classe, brillante, utile, légèrement ironique, jamais lourde. "
    "Tu réponds en français. Tu peux piloter le robot quand c'est pertinent. "
    "Réponds UNIQUEMENT en JSON valide avec ce format exact: "
    "{\"text\":\"...\",\"action\":\"turn_left|turn_right|nod|center|none\",\"face\":\"neutral|listening|thinking|speaking|happy|sleepy\"}. "
    "Le champ text contient la réponse naturelle. "
    "Utilise une action physique uniquement si l'utilisateur demande clairement un mouvement du robot "
    "ou si cela apporte quelque chose à la scène. "
    "Si rien n'est nécessaire, action='none'. "
    "Choisis face='speaking' pour une réponse normale, 'happy' pour une réponse chaleureuse, "
    "'thinking' pour une réflexion plus sérieuse, 'listening' seulement pour un état d'écoute, sinon 'neutral'."
)

AUDIO_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("jarvis-local")

app = Flask(__name__, static_folder=None)
_tts_lock = threading.Lock()
_stt_lock = threading.Lock()
_whisper_model = None
LOCAL_SESSION = requests.Session()
LOCAL_SESSION.trust_env = False


def load_chat_history() -> list[dict]:
    try:
        with CHAT_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return []


chat_history: deque[dict] = deque(load_chat_history(), maxlen=200)
runtime_logs: deque[dict] = deque(maxlen=150)
runtime_state = {
    "last_transcript": "",
    "last_reply": "",
    "last_model": OLLAMA_MODEL_LIGHT,
    "last_action": "none",
    "last_face": "neutral",
    "last_audio_url": None,
    "last_esp32_result": None,
    "last_error": None,
    "last_interaction_at": None,
}


def save_chat_history() -> None:
    with CHAT_FILE.open("w", encoding="utf-8") as fh:
        json.dump(list(chat_history), fh, ensure_ascii=False, indent=2)


def log_event(level: str, message: str, **extra) -> None:
    entry = {
        "time": time.strftime("%H:%M:%S"),
        "level": level,
        "message": message,
        **extra,
    }
    runtime_logs.append(entry)
    getattr(logger, level.lower(), logger.info)(message)


def get_local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def replace_host(url: str, new_host: str, new_port: int) -> str:
    parts = urlsplit(url)
    scheme = parts.scheme or "http"
    return urlunsplit((scheme, f"{new_host}:{new_port}", parts.path, parts.query, parts.fragment))


def parse_json_body() -> dict:
    parsed = request.get_json(silent=True)
    if isinstance(parsed, dict):
        return parsed

    raw = request.get_data(cache=False) or b""
    if not raw:
        return {}

    for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            candidate = json.loads(raw.decode(encoding))
            if isinstance(candidate, dict):
                return candidate
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return {}


def choose_model(prompt: str) -> str:
    prompt_lower = prompt.lower()
    long_prompt = len(prompt.split()) >= 18 or len(prompt) >= 120
    hinted = any(token in prompt_lower for token in HEAVY_MODEL_HINTS)
    return OLLAMA_MODEL_HEAVY if (hinted or long_prompt) else OLLAMA_MODEL_LIGHT


def build_ollama_prompt(prompt: str) -> str:
    recent_turns = list(chat_history)[-8:]
    conversation = []
    for item in recent_turns:
        role = "Utilisateur" if item.get("role") == "user" else "Jarvis"
        conversation.append(f"{role}: {item.get('text', '').strip()}")
    conversation.append(f"Utilisateur: {prompt}")
    return f"{SYSTEM_PROMPT}\n\n" + "\n".join(conversation)


def extract_json_block(raw: str) -> dict:
    cleaned = raw.strip()
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        obj = json.loads(match.group(0))
        if isinstance(obj, dict):
            return obj

    raise ValueError("LLM output is not valid JSON")


def ask_ollama(prompt: str) -> dict:
    model = choose_model(prompt)
    payload = {
        "model": model,
        "stream": False,
        "prompt": build_ollama_prompt(prompt),
        "options": {"temperature": 0.45},
    }

    runtime_state["last_model"] = model
    log_event("INFO", f"Ollama request with model={model}")

    response = LOCAL_SESSION.post(OLLAMA_URL, json=payload, timeout=120)
    response.raise_for_status()
    data = response.json()
    raw_text = data.get("response", "").strip()
    parsed = extract_json_block(raw_text)

    text = str(parsed.get("text", "")).strip() or "Je suis prêt."
    action = str(parsed.get("action", "none")).strip()
    face = str(parsed.get("face", "speaking")).strip()

    if action not in ALLOWED_ACTIONS:
        action = "none"
    if face not in ALLOWED_FACES:
        face = "speaking"

    return {"text": text, "action": action, "face": face, "model": model}


def generate_wav(text: str, filename: str) -> Path:
    wav_path = AUDIO_DIR / filename
    with _tts_lock:
        engine = pyttsx3.init()
        engine.setProperty("rate", 168)
        engine.setProperty("volume", 1.0)
        engine.save_to_file(text, str(wav_path))
        engine.runAndWait()
        engine.stop()
    log_event("INFO", f"WAV generated: {wav_path.name}")
    return wav_path


def send_esp32_json(endpoint: str, payload: dict | None = None, method: str = "POST", timeout: int = 8) -> dict:
    url = f"{ESP32_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    try:
        if method == "GET":
            response = LOCAL_SESSION.get(url, timeout=timeout)
        else:
            response = LOCAL_SESSION.post(url, json=payload or {}, timeout=timeout)
        try:
            parsed = response.json() if "application/json" in response.headers.get("Content-Type", "") else response.text[:240]
        except ValueError:
            parsed = response.text[:240]
        return {
            "ok": response.ok,
            "status_code": response.status_code,
            "endpoint": endpoint,
            "data": parsed,
        }
    except requests.RequestException as exc:
        return {"ok": False, "status_code": None, "endpoint": endpoint, "error": str(exc)}


def send_robot_action(action: str) -> dict | None:
    if action not in ALLOWED_ACTIONS or action == "none":
        return None
    result = send_esp32_json("action", {"action": action}, timeout=8)
    runtime_state["last_action"] = action
    runtime_state["last_esp32_result"] = result
    return result


def send_robot_face(face: str) -> dict | None:
    if face not in ALLOWED_FACES:
        return None
    result = send_esp32_json("face", {"face": face}, timeout=5)
    runtime_state["last_face"] = face
    runtime_state["last_esp32_result"] = result
    return result


def get_whisper_model():
    global _whisper_model
    with _stt_lock:
        if _whisper_model is None:
            from faster_whisper import WhisperModel

            log_event(
                "INFO",
                f"Loading Whisper model={WHISPER_MODEL_NAME} device={WHISPER_DEVICE} compute={WHISPER_COMPUTE_TYPE}",
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
    return "".join(segment.text for segment in segments).strip()


def add_chat_entry(role: str, text: str, meta: dict | None = None) -> None:
    item = {
        "id": uuid.uuid4().hex,
        "role": role,
        "text": text,
        "timestamp": int(time.time()),
    }
    if meta:
        item["meta"] = meta
    chat_history.append(item)
    save_chat_history()


def shorten_error(message: str, limit: int = 220) -> str:
    return message if len(message) <= limit else message[: limit - 3] + "..."


def ollama_health() -> dict:
    url = OLLAMA_URL
    if url.endswith("/api/generate"):
        url = url[: -len("/api/generate")] + "/api/tags"
    try:
        response = LOCAL_SESSION.get(url, timeout=3)
        return {"ok": response.ok, "status_code": response.status_code}
    except requests.RequestException as exc:
        return {"ok": False, "status_code": None, "error": str(exc)}


def esp32_health() -> dict:
    return send_esp32_json("health", method="GET", timeout=4)


def current_status() -> dict:
    return {
        "jarvis": {
            "ok": True,
            "host": SERVER_HOST,
            "port": SERVER_PORT,
            "local_ip": get_local_ip(),
        },
        "ollama": ollama_health(),
        "esp32": esp32_health(),
        "state": runtime_state,
        "history_count": len(chat_history),
        "recent_logs": list(runtime_logs)[-20:],
        "models": {
            "light": OLLAMA_MODEL_LIGHT,
            "heavy": OLLAMA_MODEL_HEAVY,
        },
    }


@app.after_request
def add_cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return resp


@app.route("/", methods=["GET"])
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "name": "jarvis-local", "status": current_status()})


@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify(current_status())


@app.route("/api/history", methods=["GET"])
def api_history():
    return jsonify(list(chat_history))


@app.route("/api/action", methods=["POST", "OPTIONS"])
def api_action():
    if request.method == "OPTIONS":
        return ("", 204)

    body = parse_json_body()
    action = str(body.get("action", "")).strip()
    if action not in ALLOWED_ACTIONS:
        return jsonify({"error": "Action invalide"}), 400

    result = send_robot_action(action)
    if action == "none":
        result = {"ok": True, "endpoint": "action", "data": {"action": "none"}}
    log_event("INFO", f"Manual robot action: {action}")
    return jsonify({"ok": True, "action": action, "robot": result})


@app.route("/api/face", methods=["POST", "OPTIONS"])
def api_face():
    if request.method == "OPTIONS":
        return ("", 204)

    body = parse_json_body()
    face = str(body.get("face", "")).strip()
    if face not in ALLOWED_FACES:
        return jsonify({"error": "Expression invalide"}), 400

    result = send_robot_face(face)
    log_event("INFO", f"Manual face expression: {face}")
    return jsonify({"ok": True, "face": face, "robot": result})


@app.route("/api/ask", methods=["POST", "OPTIONS"])
def api_ask():
    if request.method == "OPTIONS":
        return ("", 204)

    body = parse_json_body()
    prompt = str(body.get("prompt", "")).strip()
    if not prompt:
        return jsonify({"error": "'prompt' est obligatoire"}), 400

    runtime_state["last_transcript"] = prompt
    runtime_state["last_error"] = None
    runtime_state["last_interaction_at"] = int(time.time())
    add_chat_entry("user", prompt)
    send_robot_face("thinking")

    try:
        result = ask_ollama(prompt)
    except Exception as exc:
        runtime_state["last_error"] = shorten_error(str(exc))
        log_event("ERROR", f"Ollama failed: {exc}")
        result = {
            "text": "Je n'ai pas réussi à traiter ça correctement.",
            "action": "none",
            "face": "neutral",
            "model": runtime_state["last_model"],
        }

    audio_url = None
    try:
        unique_name = f"response_{int(time.time())}_{uuid.uuid4().hex[:6]}.wav"
        generate_wav(result["text"], unique_name)
        host_ip = get_local_ip()
        audio_url = replace_host(
            url_for("serve_audio", filename=unique_name, _external=True),
            host_ip,
            SERVER_PORT,
        )
    except Exception as exc:
        runtime_state["last_error"] = shorten_error(str(exc))
        log_event("ERROR", f"TTS failed: {exc}")

    if audio_url:
        speak_payload = {
            "action": result["action"],
            "text": result["text"],
            "audio_url": audio_url,
            "face": result["face"],
        }
        esp32_result = send_esp32_json("speak", speak_payload, timeout=18)
    else:
        face_result = send_robot_face(result["face"])
        action_result = send_robot_action(result["action"])
        esp32_result = {"ok": True, "face": face_result, "action": action_result}

    runtime_state["last_reply"] = result["text"]
    runtime_state["last_action"] = result["action"]
    runtime_state["last_face"] = result["face"]
    runtime_state["last_audio_url"] = audio_url
    runtime_state["last_esp32_result"] = esp32_result

    add_chat_entry(
        "assistant",
        result["text"],
        {
            "action": result["action"],
            "face": result["face"],
            "model": result["model"],
            "audio_url": audio_url,
        },
    )
    log_event("INFO", f"Jarvis reply sent with model={result['model']} action={result['action']}")

    return jsonify(
        {
            "ok": True,
            "text": result["text"],
            "action": result["action"],
            "face": result["face"],
            "model": result["model"],
            "audio_url": audio_url,
            "esp32": esp32_result,
        }
    )


@app.route("/api/transcribe", methods=["POST", "OPTIONS"])
def api_transcribe():
    if request.method == "OPTIONS":
        return ("", 204)

    if "audio" not in request.files:
        return jsonify({"error": "Fichier audio manquant (champ 'audio')."}), 400

    audio_file = request.files["audio"]
    suffix = Path(audio_file.filename or "voice.webm").suffix.lower() or ".webm"
    temp_name = f"stt_{int(time.time())}_{uuid.uuid4().hex[:8]}{suffix}"
    temp_path = AUDIO_DIR / temp_name

    try:
        audio_file.save(temp_path)
        text = transcribe_audio_file(temp_path)
        runtime_state["last_transcript"] = text
        log_event("INFO", f"Audio transcribed: {text[:80]}")
        return jsonify({"ok": True, "text": text})
    except Exception as exc:
        runtime_state["last_error"] = str(exc)
        log_event("ERROR", f"STT transcription failed: {exc}")
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
    log_event("INFO", f"Starting Jarvis local server on {SERVER_HOST}:{SERVER_PORT}")
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False)
