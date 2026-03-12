import json
import threading
import time
import websocket
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt

# ── Configuration ──────────────────────────────────────────────
MQTT_HOST = "72.61.111.8"
MQTT_PORT = 1883
OPENCLAW_WS = "ws://127.0.0.1:18789"

TOPIC_CMD = "neo/commandes"
TOPIC_STATUS = "neo/status"

app = Flask(__name__)
app.config["SECRET_KEY"] = "neo-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# ── MQTT ────────────────────────────────────────────────────────
mqtt_client = mqtt.Client()
mqtt_connected = False


def on_mqtt_connect(client, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        client.subscribe(TOPIC_STATUS)
        print("[MQTT] Connecté au broker")
    else:
        print(f"[MQTT] Échec connexion, code {rc}")


def on_mqtt_disconnect(client, userdata, rc):
    global mqtt_connected
    mqtt_connected = False
    print("[MQTT] Déconnecté")


def on_mqtt_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)
        socketio.emit("neo_status", data)
    except Exception as e:
        print(f"[MQTT] Erreur message: {e}")


def mqtt_connect_loop():
    global mqtt_connected
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_disconnect = on_mqtt_disconnect
    mqtt_client.on_message = on_mqtt_message
    while True:
        try:
            mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            mqtt_client.loop_forever()
        except Exception as e:
            print(f"[MQTT] Erreur: {e} — reconnexion dans 5s")
            mqtt_connected = False
            time.sleep(5)


def send_command(action: str, **kwargs):
    payload = {"action": action, **kwargs}
    mqtt_client.publish(TOPIC_CMD, json.dumps(payload))


# ── OpenClaw WebSocket ──────────────────────────────────────────
openclaw_ws: websocket.WebSocket | None = None
openclaw_lock = threading.Lock()
_req_id = 0


def _next_id():
    global _req_id
    _req_id += 1
    return _req_id


def openclaw_send(message: str) -> str:
    global openclaw_ws
    with openclaw_lock:
        try:
            if openclaw_ws is None or not openclaw_ws.connected:
                openclaw_ws = websocket.create_connection(OPENCLAW_WS, timeout=10)
            req = {
                "method": "agent.send_message",
                "params": {"agentId": "main", "message": message},
                "id": _next_id(),
            }
            openclaw_ws.send(json.dumps(req))
            raw = openclaw_ws.recv()
            data = json.loads(raw)
            return data.get("result", {}).get("output", "")
        except Exception as e:
            print(f"[OpenClaw] Erreur: {e}")
            openclaw_ws = None
            return f"Erreur de connexion à Neo: {e}"


# ── Flask routes ────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


# ── Socket.IO events ────────────────────────────────────────────
@socketio.on("connect")
def on_connect():
    emit("mqtt_state", {"connected": mqtt_connected})


@socketio.on("command")
def on_command(data):
    action = data.get("action")
    if not action:
        return
    extra = {k: v for k, v in data.items() if k != "action"}
    send_command(action, **extra)


@socketio.on("chat")
def on_chat(data):
    message = data.get("message", "").strip()
    if not message:
        return
    emit("chat_thinking", {})

    def _ask():
        reply = openclaw_send(message)
        socketio.emit("chat_reply", {"text": reply})
        # Make Neo say the reply out loud
        if reply:
            send_command("dire", texte=reply[:200])

    threading.Thread(target=_ask, daemon=True).start()


@socketio.on("get_status")
def on_get_status():
    emit("mqtt_state", {"connected": mqtt_connected})


# ── Main ────────────────────────────────────────────────────────
if __name__ == "__main__":
    mqtt_thread = threading.Thread(target=mqtt_connect_loop, daemon=True)
    mqtt_thread.start()
    print("Neo Control Center démarré sur http://0.0.0.0:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)
