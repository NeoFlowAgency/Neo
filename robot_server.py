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

import espeakng_loader
import requests
import soundfile as sf
from flask import Flask, jsonify, request, send_from_directory, url_for
from kokoro_onnx import Kokoro
from kokoro_onnx.config import EspeakConfig


ROOT_DIR = Path(__file__).resolve().parent
AUDIO_DIR = Path(os.environ.get("AUDIO_DIR", ROOT_DIR / "audio_out"))
DATA_DIR = Path(os.environ.get("JARVIS_DATA_DIR", ROOT_DIR / "data"))
WEB_DIR = Path(os.environ.get("JARVIS_WEB_DIR", ROOT_DIR / "mobile_webapp"))
MODELS_DIR = Path(os.environ.get("JARVIS_MODELS_DIR", ROOT_DIR / "models"))
KOKORO_DIR = MODELS_DIR / "kokoro"
TMP_DIR = ROOT_DIR / "tmp"
CHAT_FILE = DATA_DIR / "chat_history.json"
LISTENER_STATE_FILE = DATA_DIR / "listener_state.json"

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL_LIGHT = os.environ.get("OLLAMA_MODEL_LIGHT", os.environ.get("OLLAMA_MODEL", "gemma4:e4b"))
OLLAMA_MODEL_HEAVY = os.environ.get("OLLAMA_MODEL_HEAVY", "qwen2.5:14b")
ESP32_URL = os.environ.get("ESP32_URL", "http://192.168.1.50")
SERVER_HOST = os.environ.get("HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("PORT", "5000"))
WHISPER_MODEL_NAME = os.environ.get("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "auto")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")

KOKORO_SPEED = float(os.environ.get("KOKORO_SPEED", "1.0"))
KOKORO_VOICE_EN = os.environ.get("KOKORO_VOICE_EN", "bf_emma")
KOKORO_VOICE_FR = os.environ.get("KOKORO_VOICE_FR", "bf_emma")
KOKORO_LANG_EN = os.environ.get("KOKORO_LANG_EN", "en-gb")
KOKORO_LANG_FR = os.environ.get("KOKORO_LANG_FR", "fr-fr")
KOKORO_MODEL_URL = os.environ.get(
    "KOKORO_MODEL_URL",
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
)
KOKORO_VOICES_URL = os.environ.get(
    "KOKORO_VOICES_URL",
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
)

ALLOWED_ACTIONS = {"turn_left", "turn_right", "nod", "center", "none"}
ALLOWED_FACES = {"neutral", "listening", "thinking", "speaking", "happy", "sleepy"}
ALLOWED_LANGUAGES = {"fr", "en"}
ALLOWED_LISTENING_MODES = {"wake", "continuous", "sleep"}

LIGHT_MODEL_HINTS = {
    "bonjour", "salut", "hello", "hi", "tourne", "droite", "gauche", "centre",
    "center", "heure", "date", "merci", "thanks", "thank", "time",
}
HEAVY_MODEL_HINTS = {
    "pourquoi", "comment", "explique", "analyse", "compare", "résume", "resume",
    "plan", "recherche", "cherche", "how", "why", "analyze", "compare", "explain",
    "summarize", "research",
}
ENGLISH_HINTS = {
    "hello", "hi", "please", "thanks", "thank", "what", "why", "how", "can", "could",
    "would", "english", "turn", "left", "right", "center", "time", "today",
}
FRENCH_HINTS = {
    "bonjour", "salut", "pourquoi", "comment", "peux", "heure", "francais", "français",
    "tourne", "droite", "gauche", "centre", "merci", "aujourd", "veux",
}
ACTIVATE_CONTINUOUS_PATTERNS = (
    r"\bactive (la )?(conversation|discussion|ecoute|écoute) continue\b",
    r"\bpasse en mode (conversation|discussion|ecoute|écoute) continue\b",
    r"\bactive (le )?mode (de )?(la )?(conversation|discussion|ecoute|écoute) continue\b",
)
DEACTIVATE_CONTINUOUS_PATTERNS = (
    r"\bd[ée]sactive (la )?(conversation|discussion|ecoute|écoute) continue\b",
    r"\bd[ée]sactive (le )?mode (de )?(la )?(conversation|discussion|ecoute|écoute) continue\b",
    r"\bstop (la )?(conversation|discussion|ecoute|écoute) continue\b",
    r"\bquitte le mode (conversation|discussion|ecoute|écoute) continue\b",
    r"\breviens? en mode (wake|veille|réveil)\b",
)
SLEEP_PATTERNS = (
    r"\b(mets?|met)\s*(toi|vous)?\s*en veille\b",
    r"\bgo to sleep\b",
    r"\bsleep mode\b",
    r"\bendors? toi\b",
)
WAKE_UP_PATTERNS = (
    r"\bwake up\b",
    r"\breveille toi\b",
    r"\breveille-toi\b",
    r"\bsors de veille\b",
)
LISTENER_ONLINE_TIMEOUT_SEC = 12

SYSTEM_PROMPT = (
    "You are Jarvis, the embodied assistant of a small desk robot. "
    "You are elegant, sharp, useful, and only occasionally lightly witty. "
    "Always reply in the same language as the user. "
    "Do not mix French and English in the same answer unless the user explicitly asks for it. "
    "Be genuinely helpful, perceptive, and faster than a generic assistant. "
    "Return ONLY valid JSON with this exact shape: "
    "{\"text\":\"...\",\"action\":\"turn_left|turn_right|nod|center|none\","
    "\"face\":\"neutral|listening|thinking|speaking|happy|sleepy\",\"language\":\"fr|en\"}. "
    "Use action only when a physical robot movement is explicitly useful. "
    "Keep simple requests fast and intelligent. "
    "For deeper requests, be more capable without becoming verbose."
)

AUDIO_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
KOKORO_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("jarvis-local")

app = Flask(__name__, static_folder=None)
LOCAL_SESSION = requests.Session()
LOCAL_SESSION.trust_env = False

_tts_lock = threading.Lock()
_kokoro_lock = threading.Lock()
_stt_lock = threading.Lock()
_kokoro_engine = None
_whisper_model = None


def read_json_file(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json_file(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def load_chat_history() -> list[dict]:
    data = read_json_file(CHAT_FILE, [])
    return data if isinstance(data, list) else []


def load_listener_state() -> dict:
    default_state = {
        "mode": "wake",
        "last_ping": None,
        "updated_at": int(time.time()),
        "source": "default",
    }
    data = read_json_file(LISTENER_STATE_FILE, default_state)
    if not isinstance(data, dict):
        return default_state
    merged = {**default_state, **data}
    if merged["mode"] not in ALLOWED_LISTENING_MODES:
        merged["mode"] = "wake"
    return merged


chat_history: deque[dict] = deque(load_chat_history(), maxlen=240)
listener_state = load_listener_state()
runtime_logs: deque[dict] = deque(maxlen=180)
runtime_state = {
    "last_transcript": "",
    "last_reply": "",
    "last_model": OLLAMA_MODEL_LIGHT,
    "last_action": "none",
    "last_face": "neutral",
    "last_language": "fr",
    "last_audio_url": None,
    "last_esp32_result": None,
    "last_error": None,
    "last_interaction_at": None,
    "assistant_speaking": False,
    "speech_until": None,
    "volume": 0.72,
    "head_angle": 90,
    "sleeping": False,
}


def save_chat_history() -> None:
    write_json_file(CHAT_FILE, list(chat_history))


def save_listener_state() -> None:
    write_json_file(LISTENER_STATE_FILE, listener_state)


def log_event(level: str, message: str, **extra) -> None:
    entry = {
        "time": time.strftime("%H:%M:%S"),
        "level": level,
        "message": message,
        **extra,
    }
    runtime_logs.append(entry)
    getattr(logger, level.lower(), logger.info)(message)


def shorten_error(message: str, limit: int = 220) -> str:
    return message if len(message) <= limit else message[: limit - 3] + "..."


def refresh_speaking_state() -> None:
    speech_until = runtime_state.get("speech_until")
    if speech_until and time.time() >= float(speech_until):
        runtime_state["assistant_speaking"] = False
        runtime_state["speech_until"] = None


def ensure_runtime_temp_env() -> None:
    os.environ["TEMP"] = str(TMP_DIR)
    os.environ["TMP"] = str(TMP_DIR)


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


def detect_language(text: str) -> str:
    lowered = re.findall(r"[a-zA-ZÀ-ÿ']+", text.lower())
    en_score = sum(token in ENGLISH_HINTS for token in lowered)
    fr_score = sum(token in FRENCH_HINTS for token in lowered)
    if re.search(r"\b(the|and|with|for|what|why|how)\b", text.lower()):
        en_score += 2
    if re.search(r"\b(le|la|les|des|est|que|quoi|pourquoi|comment)\b", text.lower()):
        fr_score += 2
    return "en" if en_score > fr_score else "fr"


def normalize_language_hint(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower()
    if lowered.startswith("fr"):
        return "fr"
    if lowered.startswith("en"):
        return "en"
    return None


def is_listener_online() -> bool:
    last_ping = listener_state.get("last_ping")
    return bool(last_ping and (time.time() - float(last_ping) < LISTENER_ONLINE_TIMEOUT_SEC))


def set_listening_mode(mode: str, source: str = "api") -> None:
    if mode not in ALLOWED_LISTENING_MODES:
        raise ValueError("invalid listening mode")
    listener_state["mode"] = mode
    listener_state["updated_at"] = int(time.time())
    listener_state["source"] = source
    save_listener_state()


def touch_listener(source: str = "jarvis_mode") -> None:
    listener_state["last_ping"] = time.time()
    listener_state["updated_at"] = int(time.time())
    listener_state["source"] = source
    save_listener_state()


def parse_mode_command(prompt: str, language: str) -> dict | None:
    lowered = prompt.lower()
    if any(re.search(pattern, lowered) for pattern in SLEEP_PATTERNS):
        set_listening_mode("sleep", source="voice")
        runtime_state["sleeping"] = True
        text = (
            "Going to sleep. Wake me when you need me."
            if language == "en"
            else "Je passe en veille. Reveille-moi quand tu as besoin de moi."
        )
        return {
            "text": text,
            "action": "center",
            "face": "sleepy",
            "language": language,
            "model": "control",
            "sleep_after": True,
            "wake_before": False,
        }
    if any(re.search(pattern, lowered) for pattern in WAKE_UP_PATTERNS):
        set_listening_mode("wake", source="voice")
        runtime_state["sleeping"] = False
        text = "I am awake." if language == "en" else "Je suis reveille."
        return {
            "text": text,
            "action": "center",
            "face": "happy",
            "language": language,
            "model": "control",
            "sleep_after": False,
            "wake_before": True,
        }
    if any(re.search(pattern, lowered) for pattern in ACTIVATE_CONTINUOUS_PATTERNS):
        set_listening_mode("continuous", source="voice")
        runtime_state["sleeping"] = False
        text = (
            "Continuous conversation is now active. Just keep talking."
            if language == "en"
            else "Le mode conversation continue est maintenant actif. Continue simplement à me parler."
        )
        return {
            "text": text,
            "action": "none",
            "face": "happy",
            "language": language,
            "model": "control",
            "sleep_after": False,
            "wake_before": True,
        }
    if any(re.search(pattern, lowered) for pattern in DEACTIVATE_CONTINUOUS_PATTERNS):
        set_listening_mode("wake", source="voice")
        runtime_state["sleeping"] = False
        text = (
            "Continuous conversation is now disabled. Say Jarvis when you want me again."
            if language == "en"
            else "Le mode conversation continue est désactivé. Dis Jarvis quand tu veux me réveiller."
        )
        return {
            "text": text,
            "action": "none",
            "face": "neutral",
            "language": language,
            "model": "control",
            "sleep_after": False,
            "wake_before": True,
        }
    return None


def choose_model(prompt: str) -> str:
    lowered = prompt.lower()
    words = prompt.split()
    hinted_heavy = any(token in lowered for token in HEAVY_MODEL_HINTS)
    hinted_light = any(token in lowered for token in LIGHT_MODEL_HINTS)
    if hinted_light and len(words) <= 18 and len(prompt) <= 160:
        return OLLAMA_MODEL_LIGHT
    if hinted_heavy and (len(words) > 10 or len(prompt) > 80):
        return OLLAMA_MODEL_HEAVY
    if len(words) <= 16 and len(prompt) <= 140:
        return OLLAMA_MODEL_LIGHT
    return OLLAMA_MODEL_HEAVY


def build_ollama_prompt(prompt: str, language: str) -> str:
    recent_turns = list(chat_history)[-10:]
    conversation = []
    for item in recent_turns:
        role = "User" if item.get("role") == "user" else "Jarvis"
        conversation.append(f"{role}: {item.get('text', '').strip()}")
    conversation.append(f"User: {prompt}")
    language_hint = "English" if language == "en" else "French"
    return f"{SYSTEM_PROMPT}\nReply language: {language_hint}.\n\n" + "\n".join(conversation)


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


def ask_ollama(prompt: str, preferred_language: str | None = None) -> dict:
    language = normalize_language_hint(preferred_language) or detect_language(prompt)
    model = choose_model(prompt)
    payload = {
        "model": model,
        "stream": False,
        "prompt": build_ollama_prompt(prompt, language),
        "options": {"temperature": 0.32},
    }

    runtime_state["last_model"] = model
    runtime_state["last_language"] = language
    log_event("INFO", f"Ollama request with model={model} language={language}")

    response = LOCAL_SESSION.post(OLLAMA_URL, json=payload, timeout=90)
    response.raise_for_status()
    raw_text = response.json().get("response", "").strip()
    parsed = extract_json_block(raw_text)

    text = str(parsed.get("text", "")).strip() or ("I am ready." if language == "en" else "Je suis prêt.")
    action = str(parsed.get("action", "none")).strip()
    face = str(parsed.get("face", "speaking")).strip()
    reply_language = normalize_language_hint(str(parsed.get("language", language)).strip()) or language

    if action not in ALLOWED_ACTIONS:
        action = "none"
    if face not in ALLOWED_FACES:
        face = "speaking"
    if detect_language(text) != reply_language and len(text.split()) <= 20:
        reply_language = language

    return {
        "text": text,
        "action": action,
        "face": face,
        "language": reply_language,
        "model": model,
    }


def fast_response(prompt: str, language: str) -> dict | None:
    lowered = prompt.lower()

    if any(token in lowered for token in ("salut", "bonjour", "hello", "hi", "ca va", "ça va", "comment vas-tu", "how are you")):
        text = (
            "I am doing great. I am ready to help."
            if language == "en"
            else "Je vais tres bien. Je suis pret a t'aider."
        )
        return {"text": text, "action": "none", "face": "happy", "language": language, "model": "fast"}

    if ("heure" in lowered) or ("what time" in lowered) or ("current time" in lowered):
        now_text = time.strftime("%H:%M")
        text = f"It is {now_text}." if language == "en" else f"Il est {now_text}."
        return {"text": text, "action": "none", "face": "neutral", "language": language, "model": "fast"}

    if ("date" in lowered) or ("what day" in lowered) or ("today's date" in lowered):
        today_text = time.strftime("%A %d %B %Y")
        text = f"Today is {today_text}." if language == "en" else f"Aujourd'hui, nous sommes le {today_text}."
        return {"text": text, "action": "none", "face": "neutral", "language": language, "model": "fast"}

    if any(token in lowered for token in ("tourne a droite", "tourne à droite", "turn right")):
        text = "Turning right." if language == "en" else "Je tourne à droite."
        return {"text": text, "action": "turn_right", "face": "listening", "language": language, "model": "fast"}

    if any(token in lowered for token in ("tourne a gauche", "tourne à gauche", "turn left")):
        text = "Turning left." if language == "en" else "Je tourne à gauche."
        return {"text": text, "action": "turn_left", "face": "listening", "language": language, "model": "fast"}

    if any(token in lowered for token in ("centre", "center", "look straight", "recentre")):
        text = "Centering." if language == "en" else "Je me recentre."
        return {"text": text, "action": "center", "face": "neutral", "language": language, "model": "fast"}

    return None


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with LOCAL_SESSION.get(url, stream=True, timeout=180) as response:
        response.raise_for_status()
        with destination.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 512):
                if chunk:
                    fh.write(chunk)


def ensure_kokoro_assets() -> tuple[Path, Path]:
    model_path = KOKORO_DIR / "kokoro-v1.0.onnx"
    voices_path = KOKORO_DIR / "voices-v1.0.bin"
    if not model_path.exists():
        log_event("INFO", "Downloading Kokoro model file")
        download_file(KOKORO_MODEL_URL, model_path)
    if not voices_path.exists():
        log_event("INFO", "Downloading Kokoro voice pack")
        download_file(KOKORO_VOICES_URL, voices_path)
    return model_path, voices_path


def get_kokoro_engine() -> Kokoro:
    global _kokoro_engine
    with _kokoro_lock:
        if _kokoro_engine is None:
            ensure_runtime_temp_env()
            model_path, voices_path = ensure_kokoro_assets()
            config = EspeakConfig(
                lib_path=espeakng_loader.get_library_path(),
                data_path=espeakng_loader.get_data_path(),
            )
            _kokoro_engine = Kokoro(str(model_path), str(voices_path), espeak_config=config)
            log_event("INFO", "Kokoro ready")
    return _kokoro_engine


def get_tts_profile(language: str) -> tuple[str, str]:
    if language == "en":
        return KOKORO_VOICE_EN, KOKORO_LANG_EN
    return KOKORO_VOICE_FR, KOKORO_LANG_FR


def generate_wav(text: str, filename: str, language: str) -> tuple[Path, float]:
    wav_path = AUDIO_DIR / filename
    voice, kokoro_lang = get_tts_profile(language)
    with _tts_lock:
        ensure_runtime_temp_env()
        kokoro = get_kokoro_engine()
        audio, sample_rate = kokoro.create(
            text,
            voice=voice,
            speed=KOKORO_SPEED,
            lang=kokoro_lang,
        )
    sf.write(str(wav_path), audio, sample_rate)
    duration_sec = float(len(audio) / sample_rate) if sample_rate else 0.0
    log_event("INFO", f"WAV generated: {wav_path.name} voice={voice} lang={kokoro_lang}")
    return wav_path, duration_sec


def send_esp32_json(endpoint: str, payload: dict | None = None, method: str = "POST", timeout: int = 8) -> dict:
    url = f"{ESP32_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    try:
        response = LOCAL_SESSION.get(url, timeout=timeout) if method == "GET" else LOCAL_SESSION.post(url, json=payload or {}, timeout=timeout)
        try:
            parsed = response.json() if "application/json" in response.headers.get("Content-Type", "") else response.text[:240]
        except ValueError:
            parsed = response.text[:240]
        return {"ok": response.ok, "status_code": response.status_code, "endpoint": endpoint, "data": parsed}
    except requests.RequestException as exc:
        return {"ok": False, "status_code": None, "endpoint": endpoint, "error": str(exc)}


def stop_robot_speaking() -> dict:
    result = send_esp32_json("stop", {"reason": "interrupt"}, timeout=3)
    runtime_state["assistant_speaking"] = False
    runtime_state["speech_until"] = None
    runtime_state["last_esp32_result"] = result
    return result


def set_robot_volume(volume: float) -> dict:
    clamped = max(0.0, min(1.2, float(volume)))
    result = send_esp32_json("volume", {"volume": clamped}, timeout=4)
    if result.get("ok"):
        runtime_state["volume"] = clamped
    return result


def send_robot_head_angle(angle: float | int) -> dict:
    clamped = max(0, min(180, int(round(float(angle)))))
    result = send_esp32_json("angle", {"angle": clamped}, timeout=5)
    if result.get("ok"):
        runtime_state["head_angle"] = clamped
    runtime_state["last_esp32_result"] = result
    return result


def set_robot_sleeping(sleeping: bool) -> dict:
    result = send_esp32_json("sleep", {"sleep": bool(sleeping)}, timeout=5)
    if result.get("ok"):
        runtime_state["sleeping"] = bool(sleeping)
    runtime_state["last_esp32_result"] = result
    return result


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

            log_event("INFO", f"Loading Whisper model={WHISPER_MODEL_NAME} device={WHISPER_DEVICE} compute={WHISPER_COMPUTE_TYPE}")
            _whisper_model = WhisperModel(WHISPER_MODEL_NAME, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE)
    return _whisper_model


def transcribe_audio_file(file_path: Path) -> tuple[str, str]:
    model = get_whisper_model()
    segments, info = model.transcribe(str(file_path), language=None)
    text = "".join(segment.text for segment in segments).strip()
    language = normalize_language_hint(getattr(info, "language", None)) or detect_language(text)
    return text, language


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


def ollama_health() -> dict:
    url = OLLAMA_URL[:-len("/api/generate")] + "/api/tags" if OLLAMA_URL.endswith("/api/generate") else OLLAMA_URL
    try:
        response = LOCAL_SESSION.get(url, timeout=3)
        return {"ok": response.ok, "status_code": response.status_code}
    except requests.RequestException as exc:
        return {"ok": False, "status_code": None, "error": str(exc)}


def esp32_health() -> dict:
    return send_esp32_json("health", method="GET", timeout=4)


def current_status() -> dict:
    refresh_speaking_state()
    return {
        "jarvis": {"ok": True, "host": SERVER_HOST, "port": SERVER_PORT, "local_ip": get_local_ip()},
        "ollama": ollama_health(),
        "esp32": esp32_health(),
        "listener": {
            "mode": listener_state["mode"],
            "online": is_listener_online(),
            "last_ping": listener_state.get("last_ping"),
            "source": listener_state.get("source"),
        },
        "state": runtime_state,
        "history_count": len(chat_history),
        "recent_logs": list(runtime_logs)[-24:],
        "models": {"light": OLLAMA_MODEL_LIGHT, "heavy": OLLAMA_MODEL_HEAVY},
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


@app.route("/api/listening-mode", methods=["GET", "POST", "OPTIONS"])
def api_listening_mode():
    if request.method == "OPTIONS":
        return ("", 204)
    if request.method == "GET":
        return jsonify({
            "ok": True,
            "mode": listener_state["mode"],
            "listener_online": is_listener_online(),
            "last_ping": listener_state.get("last_ping"),
        })

    body = parse_json_body()
    mode = str(body.get("mode", "")).strip()
    if mode not in ALLOWED_LISTENING_MODES:
        return jsonify({"error": "Mode d'écoute invalide"}), 400
    set_listening_mode(mode, source="dashboard")
    runtime_state["sleeping"] = mode == "sleep"
    if mode == "sleep":
        set_robot_sleeping(True)
    else:
        set_robot_sleeping(False)
    log_event("INFO", f"Listening mode changed to {mode}")
    return jsonify({"ok": True, "mode": mode, "listener_online": is_listener_online()})


@app.route("/api/listener/ping", methods=["POST", "OPTIONS"])
def api_listener_ping():
    if request.method == "OPTIONS":
        return ("", 204)
    body = parse_json_body()
    touch_listener(source=str(body.get("source", "jarvis_mode")))
    return jsonify({"ok": True, "mode": listener_state["mode"]})


@app.route("/api/action", methods=["POST", "OPTIONS"])
def api_action():
    if request.method == "OPTIONS":
        return ("", 204)

    body = parse_json_body()
    action = str(body.get("action", "")).strip()
    if action not in ALLOWED_ACTIONS:
        return jsonify({"error": "Action invalide"}), 400

    result = send_robot_action(action) if action != "none" else {"ok": True, "endpoint": "action", "data": {"action": "none"}}
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


@app.route("/api/stop-speaking", methods=["POST", "OPTIONS"])
def api_stop_speaking():
    if request.method == "OPTIONS":
        return ("", 204)
    result = stop_robot_speaking()
    log_event("INFO", "Speaking interrupted")
    return jsonify({"ok": True, "robot": result})


@app.route("/api/volume", methods=["POST", "OPTIONS"])
def api_volume():
    if request.method == "OPTIONS":
        return ("", 204)
    body = parse_json_body()
    try:
        volume = float(body.get("volume", runtime_state["volume"]))
    except (TypeError, ValueError):
        return jsonify({"error": "Volume invalide"}), 400
    result = set_robot_volume(volume)
    return jsonify({"ok": True, "volume": runtime_state["volume"], "robot": result})


@app.route("/api/head-angle", methods=["POST", "OPTIONS"])
def api_head_angle():
    if request.method == "OPTIONS":
        return ("", 204)
    body = parse_json_body()
    try:
        angle = float(body.get("angle", runtime_state["head_angle"]))
    except (TypeError, ValueError):
        return jsonify({"error": "Angle invalide"}), 400
    result = send_robot_head_angle(angle)
    return jsonify({"ok": True, "angle": runtime_state["head_angle"], "robot": result})


@app.route("/api/ask", methods=["POST", "OPTIONS"])
def api_ask():
    if request.method == "OPTIONS":
        return ("", 204)

    body = parse_json_body()
    prompt = str(body.get("prompt", "")).strip()
    if not prompt:
        return jsonify({"error": "'prompt' est obligatoire"}), 400

    requested_language = normalize_language_hint(str(body.get("language", "")).strip())
    input_language = requested_language or detect_language(prompt)
    runtime_state["last_transcript"] = prompt
    runtime_state["last_error"] = None
    runtime_state["last_interaction_at"] = int(time.time())
    runtime_state["last_language"] = input_language
    add_chat_entry("user", prompt, {"language": input_language})

    if runtime_state.get("assistant_speaking"):
        stop_robot_speaking()

    control_result = parse_mode_command(prompt, input_language)
    if control_result:
        result = control_result
    else:
        direct_result = fast_response(prompt, input_language)
        if direct_result:
            result = direct_result
        else:
            send_robot_face("thinking")
            try:
                result = ask_ollama(prompt, preferred_language=input_language)
            except Exception as exc:
                runtime_state["last_error"] = shorten_error(str(exc))
                log_event("ERROR", f"Ollama failed: {exc}")
                result = {
                    "text": "I could not process that properly." if input_language == "en" else "Je n'ai pas réussi à traiter ça correctement.",
                    "action": "none",
                    "face": "neutral",
                    "language": input_language,
                    "model": runtime_state["last_model"],
                }

    audio_url = None
    audio_duration_sec = None
    sleep_after = bool(result.get("sleep_after"))
    wake_before = bool(result.get("wake_before"))
    if wake_before:
        set_robot_sleeping(False)
    try:
        unique_name = f"response_{int(time.time())}_{uuid.uuid4().hex[:6]}.wav"
        _wav_path, audio_duration_sec = generate_wav(result["text"], unique_name, result["language"])
        audio_url = replace_host(url_for("serve_audio", filename=unique_name, _external=True), get_local_ip(), SERVER_PORT)
    except Exception as exc:
        runtime_state["last_error"] = shorten_error(str(exc))
        log_event("ERROR", f"TTS failed: {exc}")

    if audio_url:
        speak_payload = {
            "action": result["action"],
            "text": result["text"],
            "audio_url": audio_url,
            "face": result["face"],
            "sleep_after": sleep_after,
            "wake_before": wake_before,
        }
        esp32_result = send_esp32_json("speak", speak_payload, timeout=4)
        runtime_state["assistant_speaking"] = True
        runtime_state["speech_until"] = time.time() + float(audio_duration_sec or 0) + 0.6
    else:
        face_result = send_robot_face(result["face"])
        action_result = send_robot_action(result["action"])
        esp32_result = {"ok": True, "face": face_result, "action": action_result}
        runtime_state["assistant_speaking"] = False
        runtime_state["speech_until"] = None
        if sleep_after:
            set_robot_sleeping(True)

    runtime_state["last_reply"] = result["text"]
    runtime_state["last_action"] = result["action"]
    runtime_state["last_face"] = result["face"]
    runtime_state["last_language"] = result["language"]
    runtime_state["last_audio_url"] = audio_url
    runtime_state["sleeping"] = sleep_after or listener_state["mode"] == "sleep"
    runtime_state["last_esp32_result"] = esp32_result

    add_chat_entry(
        "assistant",
        result["text"],
        {
            "action": result["action"],
            "face": result["face"],
            "model": result["model"],
            "language": result["language"],
            "audio_url": audio_url,
            "duration_sec": audio_duration_sec,
        },
    )
    log_event("INFO", f"Jarvis reply sent with model={result['model']} action={result['action']} language={result['language']}")

    return jsonify(
        {
            "ok": True,
            "text": result["text"],
            "action": result["action"],
            "face": result["face"],
            "language": result["language"],
            "model": result["model"],
            "audio_url": audio_url,
            "speech_duration": audio_duration_sec,
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
        text, language = transcribe_audio_file(temp_path)
        runtime_state["last_transcript"] = text
        runtime_state["last_language"] = language if text else runtime_state["last_language"]
        log_event("INFO", f"Audio transcribed: {text[:80]}")
        return jsonify({"ok": True, "text": text, "language": language if text else "fr"})
    except Exception as exc:
        runtime_state["last_error"] = shorten_error(str(exc))
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
    ensure_runtime_temp_env()
    log_event("INFO", f"Starting Jarvis local server on {SERVER_HOST}:{SERVER_PORT}")
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False)
