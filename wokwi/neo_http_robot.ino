/*
  NEO Robot - ESP32 HTTP Action Receiver
  --------------------------------------
  - Wi-Fi station with auto-reconnect
  - HTTP server endpoint: POST /action
  - JSON body: {"action":"turn_left|turn_right|nod|none"}
  - Servo control (G996R) with smooth motion

  Hardware (current target):
  - Servo signal: GPIO 18
  - Optional future audio output pins reserved (MAX98357A):
    BCLK=26, LRC=25, DIN=27
*/

#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>

// ----------------------- Wi-Fi config -----------------------
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// ----------------------- Servo config -----------------------
static constexpr int SERVO_PIN = 18;
static constexpr int ANGLE_CENTER = 90;
static constexpr int ANGLE_LEFT = 60;
static constexpr int ANGLE_RIGHT = 120;
static constexpr int STEP_DELAY_MS = 14;   // lower = faster motion
static constexpr int HOLD_DELAY_MS = 140;

Servo headServo;
int currentAngle = ANGLE_CENTER;

// ----------------------- HTTP server ------------------------
WebServer server(80);

// ------------------ Future audio placeholders ----------------
struct AudioConfig {
  int bclk = 26;
  int lrc = 25;
  int din = 27;
  bool enabled = false;
} audioConfig;

// ----------------------- Utilities --------------------------
void logLine(const String& line) {
  Serial.println("[NEO] " + line);
}

void ensureServoAttached() {
  if (!headServo.attached()) {
    headServo.setPeriodHertz(50);
    headServo.attach(SERVO_PIN, 500, 2400);
  }
}

void moveServoSmoothTo(int targetAngle, int stepDelay = STEP_DELAY_MS) {
  ensureServoAttached();

  targetAngle = constrain(targetAngle, 0, 180);
  int direction = (targetAngle >= currentAngle) ? 1 : -1;

  for (int angle = currentAngle; angle != targetAngle; angle += direction) {
    headServo.write(angle);
    delay(stepDelay);
  }

  headServo.write(targetAngle);
  currentAngle = targetAngle;
  delay(HOLD_DELAY_MS);
}

void actionTurnLeft() {
  logLine("Action turn_left");
  moveServoSmoothTo(ANGLE_LEFT);
}

void actionTurnRight() {
  logLine("Action turn_right");
  moveServoSmoothTo(ANGLE_RIGHT);
}

void actionNod() {
  logLine("Action nod");
  for (int i = 0; i < 2; i++) {
    moveServoSmoothTo(75, 10);
    moveServoSmoothTo(105, 10);
  }
  moveServoSmoothTo(ANGLE_CENTER, 10);
}

void actionNone() {
  logLine("Action none (no movement)");
}

bool runAction(const String& action) {
  if (action == "turn_left") {
    actionTurnLeft();
    return true;
  }
  if (action == "turn_right") {
    actionTurnRight();
    return true;
  }
  if (action == "nod") {
    actionNod();
    return true;
  }
  if (action == "none") {
    actionNone();
    return true;
  }
  return false;
}

// ----------------------- HTTP handlers ----------------------
void handleHealth() {
  DynamicJsonDocument doc(256);
  doc["ok"] = true;
  doc["ip"] = WiFi.localIP().toString();
  doc["rssi"] = WiFi.RSSI();
  doc["servo_angle"] = currentAngle;
  doc["audio_ready"] = audioConfig.enabled;

  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

void handleAction() {
  if (server.method() != HTTP_POST) {
    server.send(405, "application/json", "{\"error\":\"Method Not Allowed\"}");
    return;
  }

  DynamicJsonDocument doc(256);
  DeserializationError err = deserializeJson(doc, server.arg("plain"));
  if (err) {
    server.send(400, "application/json", "{\"error\":\"Invalid JSON\"}");
    return;
  }

  String action = String((const char*)doc["action"]);
  if (action.length() == 0) {
    server.send(400, "application/json", "{\"error\":\"Missing action\"}");
    return;
  }

  bool ok = runAction(action);
  if (!ok) {
    server.send(400, "application/json", "{\"error\":\"Unknown action\"}");
    return;
  }

  DynamicJsonDocument out(192);
  out["ok"] = true;
  out["action"] = action;
  out["servo_angle"] = currentAngle;

  String response;
  serializeJson(out, response);
  server.send(200, "application/json", response);
}

void handleNotFound() {
  server.send(404, "application/json", "{\"error\":\"Not Found\"}");
}

// -------------------- Connectivity helpers -------------------
void connectWifiBlocking() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(false);

  logLine("Connecting Wi-Fi...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  const unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print('.');
    if (millis() - start > 30000) {
      logLine("Wi-Fi timeout, retrying...");
      WiFi.disconnect();
      delay(300);
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    }
  }

  Serial.println();
  logLine("Wi-Fi connected. IP=" + WiFi.localIP().toString());
}

void ensureWifiConnected() {
  if (WiFi.status() == WL_CONNECTED) return;
  logLine("Wi-Fi lost, reconnecting...");
  connectWifiBlocking();
}

void setupHttpServer() {
  server.on("/health", HTTP_GET, handleHealth);
  server.on("/action", HTTP_POST, handleAction);
  server.onNotFound(handleNotFound);
  server.begin();
  logLine("HTTP server ready on port 80");
}

void setup() {
  Serial.begin(115200);
  delay(300);

  connectWifiBlocking();

  ensureServoAttached();
  moveServoSmoothTo(ANGLE_CENTER);

  setupHttpServer();
  logLine("Robot ready");
}

void loop() {
  ensureWifiConnected();
  server.handleClient();
  delay(2);
}
