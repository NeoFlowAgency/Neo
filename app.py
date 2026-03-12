import json
import os
import threading
import time
import websocket
from collections import deque
from flask import Flask, render_template, send_from_directory, jsonify
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt

# ── Config (env vars or defaults) ────────────────────────────
MQTT_HOST    = os.environ.get("NEO_MQTT_HOST", "72.61.111.8")
MQTT_PORT    = int(os.environ.get("NEO_MQTT_PORT", "1883"))
OPENCLAW_WS  = os.environ.get("NEO_OPENCLAW_WS", "ws://72.61.111.8:18789")
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

# ── OpenClaw ──────────────────────────────────────────────────
_oc_ws   = None
_oc_lock = threading.Lock()
_oc_id   = 0

def openclaw_send(message):
    global _oc_ws, _oc_id, openclaw_ok
    with _oc_lock:
        try:
            if _oc_ws is None or not _oc_ws.connected:
                log("INFO", f"Connexion à OpenClaw ({OPENCLAW_WS})…")
                _oc_ws = websocket.create_connection(OPENCLAW_WS, timeout=15)
            _oc_id += 1
            req = {
                "method": "agent.send_message",
                "params": {"agentId": "main", "message": message},
                "id": _oc_id,
            }
            _oc_ws.send(json.dumps(req))
            raw  = _oc_ws.recv()
            data = json.loads(raw)
            openclaw_ok = True
            socketio.emit("conn_state", get_conn_state())
            output = data.get("result", {}).get("output", "")
            if not output:
                log("WARN", "OpenClaw a répondu avec un message vide")
                return "Neo n'a pas pu formuler de réponse."
            return output
        except Exception as e:
            openclaw_ok = False
            _oc_ws = None
            log("ERR", f"OpenClaw: {e}")
            socketio.emit("conn_state", get_conn_state())
            return None

# ── Helpers ───────────────────────────────────────────────────
def get_conn_state():
    esp32_alive = (time.time() - esp32_last_seen) < 30 if esp32_last_seen else False
    return {
        "mqtt":     mqtt_connected,
        "openclaw": openclaw_ok,
        "esp32":    esp32_alive,
    }

# ── Routes ────────────────────────────────────────────────────
@app.route("/")
def index():
    # Serve React build if available, otherwise fallback to templates
    try:
        return send_from_directory("static", "index.html")
    except Exception:
        return render_template("index.html")

@app.route("/api/status")
def api_status():
    return jsonify({
        **get_conn_state(),
        "servo": servo_state,
        "uptime": int(time.time()),
    })

# ── Socket events ─────────────────────────────────────────────
@socketio.on("connect")
def on_connect():
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
    emit("chat_thinking", {})

    def _ask():
        try:
            reply = openclaw_send(message)
            if reply is None:
                # Connection failed
                socketio.emit("chat_reply", {
                    "text": f"Je n'arrive pas à me connecter à OpenClaw ({OPENCLAW_WS}). "
                            f"Vérifie que le serveur est lancé et que le port est accessible."
                })
                return
            log("CHAT", f"Neo → {reply[:100]}")
            socketio.emit("chat_reply", {"text": reply})
            if reply and not reply.startswith("Erreur"):
                send_command("lcd", texte=f"Neo: {reply[:28]}")
                send_command("dire", texte=reply[:200])
        except Exception as e:
            log("ERR", f"Chat error: {e}")
            socketio.emit("chat_reply", {"text": f"Erreur interne: {e}"})

    threading.Thread(target=_ask, daemon=True).start()

@socketio.on("test_component")
def on_test(data):
    comp = data.get("component", "")
    result = {"component": comp, "ok": False, "msg": ""}

    if comp == "mqtt":
        result["ok"]  = mqtt_connected
        result["msg"] = f"Broker MQTT connecté ({MQTT_HOST})" if mqtt_connected else f"MQTT non connecté à {MQTT_HOST}:{MQTT_PORT}"

    elif comp == "openclaw":
        def _ping():
            try:
                r = openclaw_send("Réponds juste: PONG")
                if r is None:
                    socketio.emit("test_result", {"component": "openclaw", "ok": False,
                                                  "msg": f"Impossible de se connecter à {OPENCLAW_WS}"})
                else:
                    socketio.emit("test_result", {"component": "openclaw", "ok": True,
                                                  "msg": f"Réponse: {r[:80]}"})
            except Exception as e:
                socketio.emit("test_result", {"component": "openclaw", "ok": False,
                                              "msg": f"Erreur: {e}"})
        threading.Thread(target=_ping, daemon=True).start()
        return

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
            oc_reply = openclaw_send("PONG test")
            if oc_reply is None:
                errors.append("OpenClaw inaccessible")
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
    log("INFO", f"MQTT → {MQTT_HOST}:{MQTT_PORT} | OpenClaw → {OPENCLAW_WS}")
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
