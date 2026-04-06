/*
  NEO Robot - ESP32 HTTP Action + Audio + OLED
  ---------------------------------------------
  Endpoints:
  - GET  /health
  - POST /action  {"action":"turn_left|turn_right|nod|none"}
  - POST /speak   {"action":"...","text":"...","audio_url":"http://PC_IP:5000/audio/file.wav"}

  Hardware:
  - Servo G996R: GPIO18
  - OLED SSD1306 I2C: SDA=21 SCL=23 addr=0x3C
  - MAX98357A I2S: BCLK=26, LRC=25, DIN=27
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

// ----------------------- Wi-Fi config -----------------------
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// ----------------------- Servo config -----------------------
static constexpr int SERVO_PIN = 18;
static constexpr int ANGLE_CENTER = 90;
static constexpr int ANGLE_LEFT = 60;
static constexpr int ANGLE_RIGHT = 120;
static constexpr int STEP_DELAY_MS = 14;
static constexpr int HOLD_DELAY_MS = 140;

Servo headServo;
int currentAngle = ANGLE_CENTER;

// ----------------------- OLED config ------------------------
static constexpr int SCREEN_WIDTH = 128;
static constexpr int SCREEN_HEIGHT = 64;
static constexpr int OLED_RESET = -1;
static constexpr uint8_t OLED_ADDR = 0x3C;
static constexpr int OLED_SDA = 21;
static constexpr int OLED_SCL = 23;
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
bool oledReady = false;

// ----------------------- I2S audio out ----------------------
static constexpr int I2S_BCLK = 26;
static constexpr int I2S_LRC = 25;
static constexpr int I2S_DIN = 27;
static constexpr int AUDIO_SAMPLE_RATE = 22050;

// ----------------------- HTTP server ------------------------
WebServer server(80);

void logLine(const String& line) {
  Serial.println("[NEO] " + line);
}

void oledShow(const String& l1, const String& l2 = "", const String& l3 = "") {
  if (!oledReady) return;
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println(l1);
  if (l2.length()) display.println(l2);
  if (l3.length()) display.println(l3);
  display.display();
}

void setupOLED() {
  Wire.begin(OLED_SDA, OLED_SCL);
  oledReady = display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR);
  if (oledReady) {
    oledShow("NEO", "Boot...");
  } else {
    logLine("OLED non detecte");
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
  oledShow("Action", "turn_left");
  moveServoSmoothTo(ANGLE_LEFT);
}

void actionTurnRight() {
  logLine("Action turn_right");
  oledShow("Action", "turn_right");
  moveServoSmoothTo(ANGLE_RIGHT);
}

void actionNod() {
  logLine("Action nod");
  oledShow("Action", "nod");
  for (int i = 0; i < 2; i++) {
    moveServoSmoothTo(75, 10);
    moveServoSmoothTo(105, 10);
  }
  moveServoSmoothTo(ANGLE_CENTER, 10);
}

void actionNone() {
  logLine("Action none");
  oledShow("Action", "none");
}

bool runAction(const String& action) {
  if (action == "turn_left") { actionTurnLeft(); return true; }
  if (action == "turn_right") { actionTurnRight(); return true; }
  if (action == "nod") { actionNod(); return true; }
  if (action == "none") { actionNone(); return true; }
  return false;
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
    logLine("WAV header incomplet");
    http.end();
    return false;
  }

  oledShow("Lecture audio...", "depuis PC");
  uint8_t buf[1024];
  size_t bw = 0;

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
  }

  i2s_zero_dma_buffer(I2S_NUM_0);
  http.end();
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

void handleSpeak() {
  DynamicJsonDocument doc(768);
  auto err = deserializeJson(doc, server.arg("plain"));
  if (err) {
    server.send(400, "application/json", "{\"error\":\"Invalid JSON\"}");
    return;
  }

  String action = String((const char*)doc["action"]);
  String text = String((const char*)doc["text"]);
  String audioUrl = String((const char*)doc["audio_url"]);

  if (text.length()) {
    oledShow("Neo:", text.substring(0, 20), text.substring(20, 40));
  }

  bool actionOk = runAction(action.length() ? action : "none");
  bool audioOk = playWavFromUrl(audioUrl);

  DynamicJsonDocument out(256);
  out["ok"] = (actionOk || audioOk);
  out["action_ok"] = actionOk;
  out["audio_ok"] = audioOk;
  out["servo_angle"] = currentAngle;

  String response;
  serializeJson(out, response);
  server.send(200, "application/json", response);
}

void connectWifiBlocking() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(false);

  logLine("Connecting Wi-Fi...");
  oledShow("Connexion Wi-Fi...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print('.');
  }
  Serial.println();

  logLine("Wi-Fi connected. IP=" + WiFi.localIP().toString());
  oledShow("Wi-Fi OK", WiFi.localIP().toString());
}

void ensureWifiConnected() {
  if (WiFi.status() == WL_CONNECTED) return;
  logLine("Wi-Fi lost, reconnecting...");
  connectWifiBlocking();
}

void setupHttpServer() {
  server.on("/health", HTTP_GET, handleHealth);
  server.on("/action", HTTP_POST, handleAction);
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

  setupHttpServer();
  oledShow("NEO ready", "HTTP + Audio + OLED");
  logLine("Robot ready");
}

void loop() {
  ensureWifiConnected();
  server.handleClient();
  delay(2);
}
