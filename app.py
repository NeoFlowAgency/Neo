import json
import os
import threading
import time
import requests
import eventlet
from collections import deque
from flask import Flask, render_template, send_from_directory, jsonify, request, session
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt

# ── Config ────────────────────────────────────────────────────
MQTT_HOST      = os.environ.get("NEO_MQTT_HOST", "72.61.111.8")
MQTT_PORT      = int(os.environ.get("NEO_MQTT_PORT", "1883"))
APP_PASSWORD   = os.environ.get("APP_PASSWORD", "neo")
OPENCLAW_URL   = os.environ.get("OPENCLAW_URL", "http://127.0.0.1:18789")
OPENCLAW_TOKEN = os.environ.get("OPENCLAW_TOKEN", "48456fb15f32065747b6d2c540179d1dac3c67773521c6d3ebbe70268d63e8fa")
OPENCLAW_AGENT = os.environ.get("OPENCLAW_AGENT", "main")

TOPIC_CMD    = "neo/commandes"
TOPIC_STATUS = "neo/status"

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "neo-secret-change-me-in-prod")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# ── State ──────────────────────────────────────────────────────
mqtt_connected  = False
esp32_last_seen = 0
servo_state     = {"pan": 90, "tilt": 90}
logs            = deque(maxlen=400)
chat_history    = deque(maxlen=20)

# ── OpenClaw status cache ──────────────────────────────────────
_openclaw_alive      = False
_openclaw_last_check = 0
_openclaw_check_lock = threading.Lock()

def _refresh_openclaw_status():
    global _openclaw_alive, _openclaw_last_check
    try:
        r = requests.get(
            f"{OPENCLAW_URL}/v1/models",
            headers={"Authorization": f"Bearer {OPENCLAW_TOKEN}"},
            timeout=2,
        )
        _openclaw_alive = (r.status_code == 200)
    except Exception:
        _openclaw_alive = False
    _openclaw_last_check = time.time()

def openclaw_alive() -> bool:
    with _openclaw_check_lock:
        if time.time() - _openclaw_last_check > 10:
            threading.Thread(target=_refresh_openclaw_status, daemon=True).start()
    return _openclaw_alive

# ── Logging ───────────────────────────────────────────────────
def log(level, msg):
    entry = {"t": time.strftime("%H:%M:%S"), "l": level, "m": msg}
    logs.append(entry)
    try:
        socketio.emit("log_entry", entry)
    except Exception:
        pass
    print(f"[{level}] {msg}")

# ── MQTT ──────────────────────────────────────────────────────
mqtt_client = mqtt.Client()

def on_mqtt_connect(client, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        client.subscribe(TOPIC_STATUS)
        log("OK", f"MQTT connecté au broker ({MQTT_HOST})")
        socketio.emit("conn_state", get_conn_state())
    else:
        log("ERR", f"MQTT échec connexion code={rc}")

def on_mqtt_disconnect(client, userdata, rc):
    global mqtt_connected
    mqtt_connected = False
    log("WARN", "MQTT déconnecté")
    socketio.emit("conn_state", get_conn_state())

def on_mqtt_message(client, userdata, msg):
    global esp32_last_seen
    try:
        payload = msg.payload.decode("utf-8")
        data    = json.loads(payload)
        esp32_last_seen = time.time()
        socketio.emit("neo_status", data)
        log("INFO", f"ESP32 → {payload[:80]}")
    except Exception as e:
        log("ERR", f"MQTT message parse: {e}")

def mqtt_loop():
    mqtt_client.on_connect    = on_mqtt_connect
    mqtt_client.on_disconnect = on_mqtt_disconnect
    mqtt_client.on_message    = on_mqtt_message
    while True:
        try:
            mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            mqtt_client.loop_forever()
        except Exception as e:
            log("ERR", f"MQTT: {e} — retry in 5s")
            time.sleep(5)

def send_command(action, **kwargs):
    if not mqtt_connected:
        log("WARN", f"MQTT non connecté — commande {action} ignorée")
        return False
    payload = {"action": action, **kwargs}
    mqtt_client.publish(TOPIC_CMD, json.dumps(payload))
    log("CMD", f"→ {action} {kwargs if kwargs else ''}")
    return True

# ── OpenClaw — appel HTTP streaming ───────────────────────────
def _openclaw_stream_tokens(messages, user_id="neo_user"):
    """Générateur : yield les tokens depuis l'API OpenClaw (OpenAI-compatible)."""
    headers = {
        "Authorization":      f"Bearer {OPENCLAW_TOKEN}",
        "Content-Type":       "application/json",
        "x-openclaw-agent-id": OPENCLAW_AGENT,
    }
    payload = {
        "model":    "openclaw",
        "stream":   True,
        "user":     user_id,
        "messages": messages,
    }
    with requests.post(
        f"{OPENCLAW_URL}/v1/chat/completions",
        headers=headers,
        json=payload,
        stream=True,
        timeout=60,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith(b"data: "):
                chunk_str = line[6:].decode("utf-8")
                if chunk_str.strip() == "[DONE]":
                    return
                try:
                    chunk = json.loads(chunk_str)
                    token = chunk["choices"][0]["delta"].get("content", "")
                    if token:
                        yield token
                except (json.JSONDecodeError, KeyError, IndexError):
                    pass

# ── Helpers ───────────────────────────────────────────────────
def get_conn_state():
    esp32_alive = (time.time() - esp32_last_seen) < 30 if esp32_last_seen else False
    return {
        "mqtt":     mqtt_connected,
        "openclaw": openclaw_alive(),
        "esp32":    esp32_alive,
    }

# ── Routes ────────────────────────────────────────────────────
@app.route("/")
def index():
    try:
        return send_from_directory("static", "index.html")
    except Exception:
        return render_template("index.html")

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    if data.get("password") == APP_PASSWORD:
        session["auth"] = True
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Mot de passe incorrect"}), 401

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.pop("auth", None)
    return jsonify({"ok": True})

@app.route("/api/me")
def api_me():
    return jsonify({"authenticated": bool(session.get("auth"))})

@app.route("/api/status")
def api_status():
    return jsonify({
        **get_conn_state(),
        "servo":  servo_state,
        "uptime": int(time.time()),
    })

# ── Socket events ─────────────────────────────────────────────
@socketio.on("connect")
def on_connect():
    if not session.get("auth"):
        return False
    emit("conn_state",   get_conn_state())
    emit("servo_state",  servo_state)
    emit("logs_history", list(logs)[-60:])

@socketio.on("command")
def on_command(data):
    action = data.get("action")
    if not action:
        return
    step = 15
    if action == "tete_gauche":
        servo_state["pan"] = max(30,  servo_state["pan"] - step)
    elif action == "tete_droite":
        servo_state["pan"] = min(150, servo_state["pan"] + step)
    elif action == "tete_haut":
        servo_state["tilt"] = max(50,  servo_state["tilt"] - step)
    elif action == "tete_bas":
        servo_state["tilt"] = min(130, servo_state["tilt"] + step)
    elif action in ("tete_centre", "repos"):
        servo_state["pan"]  = 90
        servo_state["tilt"] = 90
    extra = {k: v for k, v in data.items() if k != "action"}
    send_command(action, **extra)
    socketio.emit("servo_state", servo_state)

@socketio.on("servo_angle")
def on_servo_angle(data):
    pan  = int(data.get("pan",  servo_state["pan"]))
    tilt = int(data.get("tilt", servo_state["tilt"]))
    pan  = max(30, min(150, pan))
    tilt = max(50, min(130, tilt))
    servo_state["pan"]  = pan
    servo_state["tilt"] = tilt
    send_command("servo_direct", pan=pan, tilt=tilt)
    socketio.emit("servo_state", servo_state)

@socketio.on("chat")
def on_chat(data):
    message = data.get("message", "").strip()
    if not message:
        return

    log("CHAT", f"Tu → {message}")
    chat_history.append({"role": "user", "text": message, "t": time.time()})

    # Construire le contexte pour OpenClaw (10 derniers tours)
    messages = []
    for h in list(chat_history)[-10:]:
        role = "assistant" if h["role"] == "neo" else "user"
        messages.append({"role": role, "content": h["text"]})

    emit("chat_thinking", {})

    def _stream():
        full = ""
        try:
            for token in _openclaw_stream_tokens(messages):
                full += token
                socketio.emit("chat_token", {"token": token})
        except Exception as e:
            log("ERR", f"OpenClaw: {e}")
            socketio.emit("chat_reply", {
                "text":  "Désolé, je ne peux pas me connecter à mon cerveau.",
                "error": True,
            })
            return

        if full:
            chat_history.append({"role": "neo", "text": full, "t": time.time()})
            socketio.emit("chat_reply", {"text": full})
            send_command("lcd",  texte=f"Neo: {full[:28]}")
            send_command("dire", texte=full[:200])
            log("CHAT", f"Neo → {full[:100]}")

    threading.Thread(target=_stream, daemon=True).start()

@socketio.on("test_component")
def on_test(data):
    comp   = data.get("component", "")
    result = {"component": comp, "ok": False, "msg": ""}

    if comp == "mqtt":
        result["ok"]  = mqtt_connected
        result["msg"] = (f"Broker MQTT connecté ({MQTT_HOST})" if mqtt_connected
                         else f"MQTT non connecté à {MQTT_HOST}:{MQTT_PORT}")

    elif comp == "openclaw":
        _refresh_openclaw_status()
        result["ok"]  = _openclaw_alive
        result["msg"] = (f"OpenClaw actif sur {OPENCLAW_URL}" if _openclaw_alive
                         else f"OpenClaw injoignable sur {OPENCLAW_URL} — vérifie que chatCompletions est activé")

    elif comp == "lcd":
        ok = send_command("lcd", texte="TEST LCD OK     ")
        result["ok"]  = ok
        result["msg"] = "Commande envoyée au LCD" if ok else "MQTT non connecté"

    elif comp == "buzzer":
        ok = send_command("buzzer_test")
        result["ok"]  = ok
        result["msg"] = "Signal envoyé au buzzer" if ok else "MQTT non connecté"

    elif comp == "servo_pan":
        if not mqtt_connected:
            result = {"component": comp, "ok": False, "msg": "MQTT non connecté"}
        else:
            def _sweep():
                send_command("servo_direct", pan=60,  tilt=servo_state["tilt"])
                time.sleep(0.6)
                send_command("servo_direct", pan=120, tilt=servo_state["tilt"])
                time.sleep(0.6)
                send_command("servo_direct", pan=90,  tilt=servo_state["tilt"])
                servo_state["pan"] = 90
                socketio.emit("servo_state", servo_state)
                socketio.emit("test_result", {"component": "servo_pan", "ok": True,
                                              "msg": "Sweep Pan 60°→120°→90° (vérifie visuellement)"})
            threading.Thread(target=_sweep, daemon=True).start()
            return

    elif comp == "servo_tilt":
        if not mqtt_connected:
            result = {"component": comp, "ok": False, "msg": "MQTT non connecté"}
        else:
            def _sweep():
                send_command("servo_direct", pan=servo_state["pan"], tilt=60)
                time.sleep(0.6)
                send_command("servo_direct", pan=servo_state["pan"], tilt=120)
                time.sleep(0.6)
                send_command("servo_direct", pan=servo_state["pan"], tilt=90)
                servo_state["tilt"] = 90
                socketio.emit("servo_state", servo_state)
                socketio.emit("test_result", {"component": "servo_tilt", "ok": True,
                                              "msg": "Sweep Tilt 60°→120°→90° (vérifie visuellement)"})
            threading.Thread(target=_sweep, daemon=True).start()
            return

    elif comp == "full":
        if not mqtt_connected:
            emit("test_result", {"component": "full", "ok": False, "msg": "MQTT non connecté"})
            return

        def _full():
            errors = []
            _refresh_openclaw_status()
            if not _openclaw_alive:
                errors.append("OpenClaw injoignable")
            send_command("tete_gauche"); time.sleep(0.4)
            send_command("tete_droite"); time.sleep(0.4)
            send_command("tete_haut");   time.sleep(0.4)
            send_command("tete_bas");    time.sleep(0.4)
            send_command("tete_centre"); time.sleep(0.3)
            send_command("lcd", texte="TEST COMPLET OK!")
            msg = f"Partiel — erreurs: {', '.join(errors)}" if errors else "Tous les composants OK"
            socketio.emit("test_result", {"component": "full", "ok": not errors, "msg": msg})

        threading.Thread(target=_full, daemon=True).start()
        return

    log("TEST", f"{comp} → {'OK' if result['ok'] else 'FAIL'} {result['msg']}")
    emit("test_result", result)

@socketio.on("get_logs")
def on_get_logs():
    emit("logs_history", list(logs))

@socketio.on("clear_logs")
def on_clear_logs():
    logs.clear()
    emit("logs_history", [])

# ── Main ──────────────────────────────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=mqtt_loop, daemon=True).start()
    threading.Thread(target=_refresh_openclaw_status, daemon=True).start()
    port = int(os.environ.get("PORT", 8000))
    log("INFO", f"Neo Control Center démarré sur http://0.0.0.0:{port}")
    log("INFO", f"OpenClaw → {OPENCLAW_URL} (agent: {OPENCLAW_AGENT})")
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
