import json
import threading
import time
import websocket
from collections import deque
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt

# ── Config ─────────────────────────────────────────────────────
MQTT_HOST    = "72.61.111.8"
MQTT_PORT    = 1883
OPENCLAW_WS  = "ws://127.0.0.1:18789"
TOPIC_CMD    = "neo/commandes"
TOPIC_STATUS = "neo/status"

app = Flask(__name__)
app.config["SECRET_KEY"] = "neo-secret"
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
    socketio.emit("log_entry", entry)
    print(f"[{level}] {msg}")

# ── MQTT ──────────────────────────────────────────────────────
mqtt_client = mqtt.Client()

def on_mqtt_connect(client, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        client.subscribe(TOPIC_STATUS)
        log("OK", "MQTT connecté au broker")
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
    payload = {"action": action, **kwargs}
    mqtt_client.publish(TOPIC_CMD, json.dumps(payload))
    log("CMD", f"→ {action} {kwargs if kwargs else ''}")

# ── OpenClaw ──────────────────────────────────────────────────
_oc_ws   = None
_oc_lock = threading.Lock()
_oc_id   = 0

def openclaw_send(message):
    global _oc_ws, _oc_id, openclaw_ok
    with _oc_lock:
        try:
            if _oc_ws is None or not _oc_ws.connected:
                _oc_ws = websocket.create_connection(OPENCLAW_WS, timeout=10)
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
            return data.get("result", {}).get("output", "")
        except Exception as e:
            openclaw_ok = False
            _oc_ws = None
            log("ERR", f"OpenClaw: {e}")
            socketio.emit("conn_state", get_conn_state())
            return f"Erreur connexion OpenClaw: {e}"

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
    # Update local servo state for directional commands
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
        reply = openclaw_send(message)
        log("CHAT", f"Neo → {reply[:100]}")
        socketio.emit("chat_reply", {"text": reply})
        if reply:
            send_command("lcd", texte=f"Neo: {reply[:28]}")
            send_command("dire", texte=reply[:200])

    threading.Thread(target=_ask, daemon=True).start()

@socketio.on("test_component")
def on_test(data):
    comp = data.get("component", "")
    result = {"component": comp, "ok": False, "msg": ""}

    if comp == "mqtt":
        result["ok"]  = mqtt_connected
        result["msg"] = "Broker MQTT joignable" if mqtt_connected else "MQTT non connecté"

    elif comp == "openclaw":
        def _ping():
            r = openclaw_send("Réponds juste: PONG")
            ok = bool(r and len(r) < 200)
            socketio.emit("test_result", {"component": "openclaw", "ok": ok,
                                          "msg": f"Réponse: {r[:60]}" if ok else "Pas de réponse"})
        threading.Thread(target=_ping, daemon=True).start()
        return

    elif comp == "lcd":
        send_command("lcd", texte="TEST LCD OK     ")
        result["ok"]  = mqtt_connected
        result["msg"] = "Pattern envoyé au LCD"

    elif comp == "buzzer":
        send_command("buzzer_test")
        result["ok"]  = mqtt_connected
        result["msg"] = "Signal envoyé au buzzer"

    elif comp == "servo_pan":
        send_command("servo_direct", pan=60,  tilt=servo_state["tilt"])
        time.sleep(0.6)
        send_command("servo_direct", pan=120, tilt=servo_state["tilt"])
        time.sleep(0.6)
        send_command("servo_direct", pan=90,  tilt=servo_state["tilt"])
        servo_state["pan"] = 90
        result["ok"]  = True
        result["msg"] = "Sweep Pan gauche→droite→centre"

    elif comp == "servo_tilt":
        send_command("servo_direct", pan=servo_state["pan"], tilt=60)
        time.sleep(0.6)
        send_command("servo_direct", pan=servo_state["pan"], tilt=120)
        time.sleep(0.6)
        send_command("servo_direct", pan=servo_state["pan"], tilt=90)
        servo_state["tilt"] = 90
        result["ok"]  = True
        result["msg"] = "Sweep Tilt haut→bas→centre"

    elif comp == "full":
        def _full():
            steps = [
                ("lcd",  {"texte": "TEST COMPLET..."}),
                ("tete_gauche", {}), ("tete_droite", {}),
                ("tete_haut",   {}), ("tete_bas",    {}),
                ("tete_centre", {}),
                ("lcd",  {"texte": "TEST OK!        "}),
            ]
            for action, kwargs in steps:
                send_command(action, **kwargs)
                time.sleep(0.5)
            socketio.emit("test_result", {"component": "full", "ok": True,
                                          "msg": "Test complet terminé avec succès"})
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
    log("INFO", "Neo Control Center démarré sur http://0.0.0.0:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)
