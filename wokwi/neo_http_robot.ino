/*
  Jarvis Robot - ESP32 HTTP + Servo + OLED Eyes + Audio
  -----------------------------------------------------
  Endpoints:
  - GET  /health
  - POST /action  {"action":"turn_left|turn_right|nod|center|none"}
  - POST /face    {"face":"neutral|listening|thinking|speaking|happy|sleepy"}
  - POST /speak   {"action":"...","text":"...","audio_url":"http://PC_IP:5000/audio/file.wav","face":"speaking"}
*/

#include <WiFi.h>
#include <WebServer.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "driver/i2s.h"

const char* WIFI_SSID = "Freebox-C82B11";
const char* WIFI_PASSWORD = "FREEGRELIER44";

static constexpr int SERVO_PIN = 18;
static constexpr int ANGLE_CENTER = 90;
static constexpr int ANGLE_LEFT = 55;
static constexpr int ANGLE_RIGHT = 125;
static constexpr int STEP_DELAY_MS = 14;
static constexpr int HOLD_DELAY_MS = 140;

static constexpr int SCREEN_WIDTH = 128;
static constexpr int SCREEN_HEIGHT = 64;
static constexpr int OLED_RESET = -1;
static constexpr uint8_t OLED_ADDR = 0x3C;
static constexpr int OLED_SDA = 21;
static constexpr int OLED_SCL = 23;

static constexpr int I2S_BCLK = 26;
static constexpr int I2S_LRC = 25;
static constexpr int I2S_DIN = 27;
static constexpr int AUDIO_SAMPLE_RATE = 22050;

Servo headServo;
WebServer server(80);
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

int currentAngle = ANGLE_CENTER;
bool oledReady = false;
String currentFace = "neutral";
bool blinkClosed = false;
unsigned long nextBlinkAt = 0;
unsigned long blinkUntil = 0;
unsigned long lastFaceRedraw = 0;

void logLine(const String& line) {
  Serial.println("[JARVIS] " + line);
}

void scheduleBlink() {
  nextBlinkAt = millis() + random(3200, 6800);
}

void drawRoundedEye(int x, int y, int w, int h, bool filled, int radius = 6) {
  if (filled) {
    display.fillRoundRect(x, y, w, h, radius, SSD1306_WHITE);
  } else {
    display.drawRoundRect(x, y, w, h, radius, SSD1306_WHITE);
  }
}

void drawPupil(int x, int y, int size) {
  display.fillRoundRect(x, y, size, size, size / 2, SSD1306_BLACK);
}

void drawFace() {
  if (!oledReady) return;

  display.clearDisplay();

  if (blinkClosed) {
    display.drawLine(26, 28, 50, 28, SSD1306_WHITE);
    display.drawLine(78, 28, 102, 28, SSD1306_WHITE);
    display.display();
    return;
  }

  int eyeY = 18;
  int eyeW = 26;
  int eyeH = 28;
  int leftX = 20;
  int rightX = 82;

  if (currentFace == "sleepy") {
    display.drawLine(22, 30, 48, 28, SSD1306_WHITE);
    display.drawLine(80, 28, 106, 30, SSD1306_WHITE);
    display.drawLine(20, 32, 50, 32, SSD1306_WHITE);
    display.drawLine(78, 32, 108, 32, SSD1306_WHITE);
  } else if (currentFace == "happy") {
    display.drawRoundRect(leftX, eyeY + 4, eyeW, eyeH - 8, 8, SSD1306_WHITE);
    display.drawRoundRect(rightX, eyeY + 4, eyeW, eyeH - 8, 8, SSD1306_WHITE);
    drawPupil(leftX + 14, eyeY + 11, 7);
    drawPupil(rightX + 5, eyeY + 11, 7);
    display.drawLine(28, 52, 40, 56, SSD1306_WHITE);
    display.drawLine(40, 56, 50, 52, SSD1306_WHITE);
    display.drawLine(78, 52, 90, 56, SSD1306_WHITE);
    display.drawLine(90, 56, 100, 52, SSD1306_WHITE);
  } else {
    int pupilOffsetY = 9;
    int pupilOffsetXLeft = 8;
    int pupilOffsetXRight = 8;

    if (currentFace == "listening") {
      pupilOffsetXLeft = 10;
      pupilOffsetXRight = 6;
    } else if (currentFace == "thinking") {
      pupilOffsetXLeft = 6;
      pupilOffsetXRight = 10;
      display.fillCircle(62, 14, 2, SSD1306_WHITE);
      display.fillCircle(68, 10, 2, SSD1306_WHITE);
      display.fillCircle(74, 14, 2, SSD1306_WHITE);
    } else if (currentFace == "speaking") {
      eyeH = 24;
      eyeY = 20;
      pupilOffsetY = 7;
    }

    drawRoundedEye(leftX, eyeY, eyeW, eyeH, true);
    drawRoundedEye(rightX, eyeY, eyeW, eyeH, true);
    drawPupil(leftX + pupilOffsetXLeft, eyeY + pupilOffsetY, 8);
    drawPupil(rightX + pupilOffsetXRight, eyeY + pupilOffsetY, 8);

    if (currentFace == "speaking") {
      display.drawLine(53, 50, 75, 50, SSD1306_WHITE);
      display.drawLine(55, 53, 73, 53, SSD1306_WHITE);
    }
  }

  display.display();
}

void updateFaceAnimation() {
  unsigned long now = millis();

  if (!blinkClosed && now > nextBlinkAt) {
    blinkClosed = true;
    blinkUntil = now + 140;
    drawFace();
    return;
  }

  if (blinkClosed && now > blinkUntil) {
    blinkClosed = false;
    scheduleBlink();
    drawFace();
    return;
  }

  if (now - lastFaceRedraw > 1500) {
    lastFaceRedraw = now;
    drawFace();
  }
}

void setFace(const String& face) {
  currentFace = face;
  blinkClosed = false;
  lastFaceRedraw = millis();
  drawFace();
}

void setupOLED() {
  Wire.begin(OLED_SDA, OLED_SCL);
  oledReady = display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR);
  if (oledReady) {
    randomSeed(analogRead(0));
    scheduleBlink();
    setFace("neutral");
  } else {
    logLine("OLED not detected");
  }
}

void setupI2SOut() {
  i2s_config_t cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = AUDIO_SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 256,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0
  };

  i2s_pin_config_t pins = {
    .bck_io_num = I2S_BCLK,
    .ws_io_num = I2S_LRC,
    .data_out_num = I2S_DIN,
    .data_in_num = I2S_PIN_NO_CHANGE
  };

  i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pins);
  i2s_zero_dma_buffer(I2S_NUM_0);
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
  setFace("listening");
  moveServoSmoothTo(ANGLE_LEFT);
}

void actionTurnRight() {
  logLine("Action turn_right");
  setFace("listening");
  moveServoSmoothTo(ANGLE_RIGHT);
}

void actionCenter() {
  logLine("Action center");
  setFace("neutral");
  moveServoSmoothTo(ANGLE_CENTER);
}

void actionNod() {
  logLine("Action nod");
  setFace("happy");
  for (int i = 0; i < 2; i++) {
    moveServoSmoothTo(ANGLE_LEFT + 8, 10);
    moveServoSmoothTo(ANGLE_RIGHT - 8, 10);
  }
  moveServoSmoothTo(ANGLE_CENTER, 10);
}

void actionNone() {
  logLine("Action none");
  setFace("neutral");
}

bool runAction(const String& action) {
  if (action == "turn_left") { actionTurnLeft(); return true; }
  if (action == "turn_right") { actionTurnRight(); return true; }
  if (action == "center") { actionCenter(); return true; }
  if (action == "nod") { actionNod(); return true; }
  if (action == "none") { actionNone(); return true; }
  return false;
}

bool isKnownFace(const String& face) {
  return face == "neutral" || face == "listening" || face == "thinking" ||
         face == "speaking" || face == "happy" || face == "sleepy";
}

bool playWavFromUrl(const String& url) {
  if (url.length() == 0) return false;

  HTTPClient http;
  WiFiClient streamClient;
  http.begin(streamClient, url);
  int code = http.GET();
  if (code != HTTP_CODE_OK) {
    logLine("Audio HTTP error=" + String(code));
    http.end();
    return false;
  }

  WiFiClient* stream = http.getStreamPtr();
  const size_t WAV_HEADER = 44;
  uint8_t header[WAV_HEADER];
  int readHeader = stream->readBytes(header, WAV_HEADER);
  if (readHeader != (int)WAV_HEADER) {
    logLine("Incomplete WAV header");
    http.end();
    return false;
  }

  setFace("speaking");
  uint8_t buf[1024];
  size_t bw = 0;
  unsigned long lastRefresh = millis();

  while (http.connected()) {
    int available = stream->available();
    if (available <= 0) {
      delay(2);
      continue;
    }

    int toRead = min((int)sizeof(buf), available);
    int r = stream->readBytes(buf, toRead);
    if (r > 0) {
      i2s_write(I2S_NUM_0, buf, r, &bw, portMAX_DELAY);
    }

    if (millis() - lastRefresh > 180) {
      drawFace();
      lastRefresh = millis();
    }
  }

  i2s_zero_dma_buffer(I2S_NUM_0);
  http.end();
  setFace("neutral");
  return true;
}

void handleHealth() {
  DynamicJsonDocument doc(256);
  doc["ok"] = true;
  doc["ip"] = WiFi.localIP().toString();
  doc["rssi"] = WiFi.RSSI();
  doc["servo_angle"] = currentAngle;
  doc["audio_ready"] = true;
  doc["oled_ready"] = oledReady;
  doc["face"] = currentFace;

  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

void handleAction() {
  DynamicJsonDocument doc(256);
  auto err = deserializeJson(doc, server.arg("plain"));
  if (err) {
    server.send(400, "application/json", "{\"error\":\"Invalid JSON\"}");
    return;
  }

  String action = String((const char*)doc["action"]);
  if (!runAction(action)) {
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

void handleFace() {
  DynamicJsonDocument doc(256);
  auto err = deserializeJson(doc, server.arg("plain"));
  if (err) {
    server.send(400, "application/json", "{\"error\":\"Invalid JSON\"}");
    return;
  }

  String face = String((const char*)doc["face"]);
  if (!isKnownFace(face)) {
    server.send(400, "application/json", "{\"error\":\"Unknown face\"}");
    return;
  }

  setFace(face);

  DynamicJsonDocument out(160);
  out["ok"] = true;
  out["face"] = face;
  String response;
  serializeJson(out, response);
  server.send(200, "application/json", response);
}

void handleSpeak() {
  DynamicJsonDocument doc(768);
  auto err = deserializeJson(doc, server.arg("plain"));
  if (err) {
    server.send(400, "application/json", "{\"error\":\"Invalid JSON\"}");
    return;
  }

  String action = String((const char*)doc["action"]);
  String audioUrl = String((const char*)doc["audio_url"]);
  String face = String((const char*)doc["face"]);

  if (isKnownFace(face)) {
    setFace(face);
  } else {
    setFace("speaking");
  }

  bool actionOk = runAction(action.length() ? action : "none");
  bool audioOk = playWavFromUrl(audioUrl);

  DynamicJsonDocument out(256);
  out["ok"] = (actionOk || audioOk);
  out["action_ok"] = actionOk;
  out["audio_ok"] = audioOk;
  out["servo_angle"] = currentAngle;
  out["face"] = currentFace;

  String response;
  serializeJson(out, response);
  server.send(200, "application/json", response);
}

void connectWifiBlocking() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(false);

  logLine("Connecting Wi-Fi...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print('.');
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
  server.on("/face", HTTP_POST, handleFace);
  server.on("/speak", HTTP_POST, handleSpeak);
  server.onNotFound([]() {
    server.send(404, "application/json", "{\"error\":\"Not Found\"}");
  });
  server.begin();
  logLine("HTTP server ready on port 80");
}

void setup() {
  Serial.begin(115200);
  delay(250);

  setupOLED();
  setupI2SOut();
  connectWifiBlocking();

  ensureServoAttached();
  moveServoSmoothTo(ANGLE_CENTER);
  setFace("neutral");
  setupHttpServer();
  logLine("Robot ready");
}

void loop() {
  ensureWifiConnected();
  server.handleClient();
  updateFaceAnimation();
  delay(2);
}
