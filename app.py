import json
import os
import threading
import time
from collections import deque
from flask import Flask, render_template, send_from_directory, jsonify, request, session
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt

# ── Config (env vars or defaults) ────────────────────────────
MQTT_HOST        = os.environ.get("NEO_MQTT_HOST", "72.61.111.8")
MQTT_PORT        = int(os.environ.get("NEO_MQTT_PORT", "1883"))
APP_PASSWORD     = os.environ.get("APP_PASSWORD", "neo")
OPENCLAW_API_KEY = os.environ.get("OPENCLAW_API_KEY", "")
TOPIC_CMD    = "neo/commandes"
TOPIC_STATUS = "neo/status"

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "neo-secret-change-me-in-prod")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# ── State ──────────────────────────────────────────────────────
mqtt_connected   = False
openclaw_ok      = False
esp32_last_seen  = 0
servo_state      = {"pan": 90, "tilt": 90}
logs             = deque(maxlen=400)

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

# ── OpenClaw — file d'attente (OpenClaw polls /api/neo/pending) ──
_pending      = deque(maxlen=50)   # messages user → OpenClaw en attente
_pending_lock = threading.Lock()
_openclaw_last_poll = 0            # timestamp du dernier poll OpenClaw

def _check_openclaw_api_key():
    """Vérifie la clé API si elle est configurée. Retourne True si OK."""
    if not OPENCLAW_API_KEY:
        return True  # pas de clé configurée = accès libre
    return request.headers.get("X-Api-Key") == OPENCLAW_API_KEY

# ── Helpers ───────────────────────────────────────────────────
def get_conn_state():
    esp32_alive     = (time.time() - esp32_last_seen)     < 30 if esp32_last_seen     else False
    openclaw_alive  = (time.time() - _openclaw_last_poll) < 60 if _openclaw_last_poll else False
    return {
        "mqtt":     mqtt_connected,
        "openclaw": openclaw_alive,
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
        "servo": servo_state,
        "uptime": int(time.time()),
    })

# ── OpenClaw REST API ──────────────────────────────────────────

@app.route("/api/neo/pending", methods=["GET"])
def api_neo_pending():
    """OpenClaw polls cet endpoint pour récupérer les messages utilisateur."""
    global openclaw_ok, _openclaw_last_poll
    if not _check_openclaw_api_key():
        return jsonify({"error": "Unauthorized"}), 401
    with _pending_lock:
        messages = list(_pending)
        _pending.clear()
    openclaw_ok = True
    _openclaw_last_poll = time.time()
    socketio.emit("conn_state", get_conn_state())
    return jsonify({"messages": messages})

@app.route("/api/neo/message", methods=["POST"])
def api_neo_message():
    """OpenClaw envoie une réponse à afficher dans le chat."""
    global openclaw_ok, _openclaw_last_poll
    if not _check_openclaw_api_key():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Champ 'text' manquant"}), 400
    log("CHAT", f"OpenClaw → {text[:100]}")
    socketio.emit("chat_reply", {"text": text})
    # Affichage sur LCD + synthèse vocale
    send_command("lcd",  texte=f"Neo: {text[:28]}")
    send_command("dire", texte=text[:200])
    openclaw_ok = True
    _openclaw_last_poll = time.time()
    socketio.emit("conn_state", get_conn_state())
    return jsonify({"ok": True})

# ── Socket events ─────────────────────────────────────────────
@socketio.on("connect")
def on_connect():
    if not session.get("auth"):
        return False  # reject unauthenticated connections
    emit("conn_state",  get_conn_state())
    emit("servo_state", servo_state)
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
    # Mettre le message en file d'attente pour OpenClaw
    with _pending_lock:
        _pending.append({"text": message, "timestamp": time.time()})
    emit("chat_thinking", {})

@socketio.on("test_component")
def on_test(data):
    comp = data.get("component", "")
    result = {"component": comp, "ok": False, "msg": ""}

    if comp == "mqtt":
        result["ok"]  = mqtt_connected
        result["msg"] = f"Broker MQTT connecté ({MQTT_HOST})" if mqtt_connected else f"MQTT non connecté à {MQTT_HOST}:{MQTT_PORT}"

    elif comp == "openclaw":
        alive = (time.time() - _openclaw_last_poll) < 60 if _openclaw_last_poll else False
        result["ok"]  = alive
        result["msg"] = (
            f"OpenClaw actif (dernier poll il y a {int(time.time()-_openclaw_last_poll)}s)"
            if alive else
            "OpenClaw n'a pas encore pollé /api/neo/pending. "
            "Configure OpenClaw pour appeler GET http://72.61.111.8:8080/api/neo/pending"
        )

    elif comp == "lcd":
        ok = send_command("lcd", texte="TEST LCD OK     ")
        result["ok"]  = ok
        result["msg"] = "Commande envoyée au LCD" if ok else "MQTT non connecté — commande non envoyée"

    elif comp == "buzzer":
        ok = send_command("buzzer_test")
        result["ok"]  = ok
        result["msg"] = "Signal envoyé au buzzer" if ok else "MQTT non connecté — commande non envoyée"

    elif comp == "servo_pan":
        if not mqtt_connected:
            result["ok"]  = False
            result["msg"] = "MQTT non connecté — impossible de tester les servos"
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
                                              "msg": "Sweep Pan: 60° → 120° → 90° (vérifie visuellement)"})
            threading.Thread(target=_sweep, daemon=True).start()
            return

    elif comp == "servo_tilt":
        if not mqtt_connected:
            result["ok"]  = False
            result["msg"] = "MQTT non connecté — impossible de tester les servos"
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
                                              "msg": "Sweep Tilt: 60° → 120° → 90° (vérifie visuellement)"})
            threading.Thread(target=_sweep, daemon=True).start()
            return

    elif comp == "full":
        if not mqtt_connected:
            result = {"component": "full", "ok": False, "msg": "MQTT non connecté — test complet impossible"}
            emit("test_result", result)
            return

        def _full():
            errors = []
            # Test MQTT
            if not mqtt_connected:
                errors.append("MQTT déconnecté")
            # Test OpenClaw
            oc_alive = (time.time() - _openclaw_last_poll) < 60 if _openclaw_last_poll else False
            if not oc_alive:
                errors.append("OpenClaw n'a pas encore pollé")
            # Test servos
            send_command("tete_gauche")
            time.sleep(0.4)
            send_command("tete_droite")
            time.sleep(0.4)
            send_command("tete_haut")
            time.sleep(0.4)
            send_command("tete_bas")
            time.sleep(0.4)
            send_command("tete_centre")
            time.sleep(0.3)
            # Test LCD
            send_command("lcd", texte="TEST COMPLET OK!")
            time.sleep(0.3)

            if errors:
                socketio.emit("test_result", {"component": "full", "ok": False,
                                              "msg": f"Partiel — erreurs: {', '.join(errors)}"})
            else:
                socketio.emit("test_result", {"component": "full", "ok": True,
                                              "msg": "Tous les composants OK"})

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
    port = int(os.environ.get("PORT", 8000))
    log("INFO", f"Neo Control Center démarré sur http://0.0.0.0:{port}")
    log("INFO", f"MQTT → {MQTT_HOST}:{MQTT_PORT} | OpenClaw → polling sur /api/neo/pending")
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
