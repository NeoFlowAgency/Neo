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
#include <math.h>

const char* WIFI_SSID = "Freebox-C82B11";
const char* WIFI_PASSWORD = "FREEGRELIER44";

static constexpr int SERVO_PIN = 18;
static constexpr int ANGLE_CENTER = 90;
static constexpr int ANGLE_LEFT = 55;
static constexpr int ANGLE_RIGHT = 125;
static constexpr int STEP_DELAY_MS = 6;
static constexpr int HOLD_DELAY_MS = 55;

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
bool robotSleeping = false;
bool blinkClosed = false;
unsigned long nextBlinkAt = 0;
unsigned long blinkUntil = 0;
unsigned long lastFaceRedraw = 0;
volatile bool audioPlaying = false;
volatile bool stopAudioRequested = false;
TaskHandle_t audioTaskHandle = nullptr;
float currentVolume = 0.72f;
unsigned long lastThinkingChimeAt = 0;

struct SpeakJob {
  String action;
  String face;
  String audioUrl;
  bool sleepAfter;
};

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

  if (robotSleeping) {
    display.clearDisplay();
    display.display();
    return;
  }

  display.clearDisplay();

  if (blinkClosed) {
    display.drawLine(26, 28, 50, 28, SSD1306_WHITE);
    display.drawLine(78, 28, 102, 28, SSD1306_WHITE);
    display.display();
    return;
  }

  int leftX = 19;
  int rightX = 83;
  int neutralY = 18;
  int neutralW = 26;
  int neutralH = 28;

  if (currentFace == "sleepy") {
    display.drawLine(22, 29, 49, 30, SSD1306_WHITE);
    display.drawLine(22, 31, 49, 32, SSD1306_WHITE);
    display.drawLine(80, 30, 107, 29, SSD1306_WHITE);
    display.drawLine(80, 32, 107, 31, SSD1306_WHITE);
  } else if (currentFace == "happy") {
    display.drawLine(22, 34, 30, 26, SSD1306_WHITE);
    display.drawLine(30, 26, 40, 24, SSD1306_WHITE);
    display.drawLine(40, 24, 50, 28, SSD1306_WHITE);
    display.drawLine(80, 28, 90, 24, SSD1306_WHITE);
    display.drawLine(90, 24, 100, 26, SSD1306_WHITE);
    display.drawLine(100, 26, 108, 34, SSD1306_WHITE);
  } else {
    int eyeY = neutralY;
    int eyeW = neutralW;
    int eyeH = neutralH;
    int pupilOffsetY = 9;
    int pupilOffsetXLeft = 9;
    int pupilOffsetXRight = 9;

    if (currentFace == "listening") {
      eyeY = 16;
      eyeH = 30;
      pupilOffsetXLeft = 12;
      pupilOffsetXRight = 5;
      display.drawLine(21, 14, 46, 11, SSD1306_WHITE);
      display.drawLine(81, 11, 106, 14, SSD1306_WHITE);
    } else if (currentFace == "thinking") {
      eyeY = 20;
      eyeH = 22;
      pupilOffsetY = 8;
      pupilOffsetXLeft = 7;
      pupilOffsetXRight = 11;
      display.drawLine(22, 16, 46, 17, SSD1306_WHITE);
      display.drawLine(82, 17, 106, 16, SSD1306_WHITE);
    } else if (currentFace == "speaking") {
      eyeY = 19;
      eyeH = 25;
      pupilOffsetY = 10;
      display.drawLine(22, 15, 46, 13, SSD1306_WHITE);
      display.drawLine(82, 13, 106, 15, SSD1306_WHITE);
    }

    drawRoundedEye(leftX, eyeY, eyeW, eyeH, true);
    drawRoundedEye(rightX, eyeY, eyeW, eyeH, true);
    drawPupil(leftX + pupilOffsetXLeft, eyeY + pupilOffsetY, 7);
    drawPupil(rightX + pupilOffsetXRight, eyeY + pupilOffsetY, 7);
  }

  display.display();
}

void updateFaceAnimation() {
  unsigned long now = millis();

  if (robotSleeping) {
    return;
  }

  if (currentFace == "thinking" && !audioPlaying) {
    playThinkingChime();
  }

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

void playThinkingChime() {
  if (millis() - lastThinkingChimeAt < 520) return;
  lastThinkingChimeAt = millis();

  const int sampleCount = 2400;
  int16_t buffer[sampleCount];
  for (int i = 0; i < sampleCount; i++) {
    float t = (float)i / AUDIO_SAMPLE_RATE;
    bool pulse = (i < 520) || (i > 820 && i < 1340) || (i > 1640 && i < 2140);
    float freq = (i < sampleCount / 2) ? 740.0f : 920.0f;
    float env = pulse ? 0.8f : 0.0f;
    float sample = sinf(2.0f * PI * freq * t) * env * currentVolume * 1400.0f;
    buffer[i] = (int16_t)sample;
  }
  size_t bw = 0;
  i2s_write(I2S_NUM_0, buffer, sizeof(buffer), &bw, portMAX_DELAY);
  i2s_zero_dma_buffer(I2S_NUM_0);
}

void setupOLED() {
  Wire.begin(OLED_SDA, OLED_SCL);
  oledReady = display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR);
  if (oledReady) {
    randomSeed((uint32_t)esp_random());
    scheduleBlink();
    setFace("neutral");
  } else {
    logLine("OLED not detected");
  }
}

void wakeRobot() {
  robotSleeping = false;
  if (oledReady) {
    display.ssd1306_command(SSD1306_DISPLAYON);
  }
  setFace("neutral");
}

void sleepRobot() {
  setFace("sleepy");
  delay(180);
  blinkClosed = true;
  drawFace();
  delay(160);
  robotSleeping = true;
  if (oledReady) {
    display.clearDisplay();
    display.display();
    display.ssd1306_command(SSD1306_DISPLAYOFF);
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
  if (robotSleeping) {
    wakeRobot();
  }
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
    if (stopAudioRequested) {
      logLine("Audio interrupted");
      break;
    }

    int available = stream->available();
    if (available <= 0) {
      delay(2);
      continue;
    }

    int toRead = min((int)sizeof(buf), available);
    int r = stream->readBytes(buf, toRead);
    if (r > 0) {
      int16_t* samples = reinterpret_cast<int16_t*>(buf);
      int sampleCount = r / 2;
      for (int i = 0; i < sampleCount; i++) {
        float scaled = samples[i] * currentVolume;
        if (scaled > 32767.0f) scaled = 32767.0f;
        if (scaled < -32768.0f) scaled = -32768.0f;
        samples[i] = (int16_t)scaled;
      }
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

void stopAudioPlayback() {
  stopAudioRequested = true;
  i2s_zero_dma_buffer(I2S_NUM_0);
}

void speakTask(void* parameter) {
  SpeakJob* job = static_cast<SpeakJob*>(parameter);
  audioPlaying = true;
  stopAudioRequested = false;

  if (isKnownFace(job->face)) {
    setFace(job->face);
  } else {
    setFace("speaking");
  }

  bool actionOk = runAction(job->action.length() ? job->action : "none");
  bool audioOk = playWavFromUrl(job->audioUrl);
  logLine("Speak finished actionOk=" + String(actionOk ? "true" : "false") + " audioOk=" + String(audioOk ? "true" : "false"));

  stopAudioRequested = false;
  audioPlaying = false;
  if (job->sleepAfter) {
    sleepRobot();
  } else {
    setFace("neutral");
  }
  delete job;
  audioTaskHandle = nullptr;
  vTaskDelete(NULL);
}

bool queueSpeak(const String& action, const String& face, const String& audioUrl, bool sleepAfter) {
  if (audioTaskHandle != nullptr) {
    stopAudioPlayback();
    unsigned long deadline = millis() + 1200;
    while (audioPlaying && millis() < deadline) {
      delay(10);
    }
  }

  SpeakJob* job = new SpeakJob{action, face, audioUrl, sleepAfter};
  BaseType_t result = xTaskCreatePinnedToCore(
    speakTask,
    "speakTask",
    8192,
    job,
    1,
    &audioTaskHandle,
    1
  );

  if (result != pdPASS) {
    delete job;
    audioTaskHandle = nullptr;
    audioPlaying = false;
    stopAudioRequested = false;
    return false;
  }
  return true;
}

void handleHealth() {
  DynamicJsonDocument doc(256);
  doc["ok"] = true;
  doc["ip"] = WiFi.localIP().toString();
  doc["rssi"] = WiFi.RSSI();
  doc["servo_angle"] = currentAngle;
  doc["audio_ready"] = true;
  doc["audio_playing"] = audioPlaying;
  doc["oled_ready"] = oledReady;
  doc["face"] = currentFace;
  doc["sleeping"] = robotSleeping;

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

void handleAngle() {
  DynamicJsonDocument doc(256);
  auto err = deserializeJson(doc, server.arg("plain"));
  if (err) {
    server.send(400, "application/json", "{\"error\":\"Invalid JSON\"}");
    return;
  }

  int requested = doc["angle"] | currentAngle;
  requested = constrain(requested, 0, 180);
  moveServoSmoothTo(requested);

  DynamicJsonDocument out(192);
  out["ok"] = true;
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
  if (face == "thinking") {
    playThinkingChime();
  }

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
  bool sleepAfter = doc["sleep_after"] | false;
  bool wakeBefore = doc["wake_before"] | false;

  if (wakeBefore) {
    wakeRobot();
  }

  DynamicJsonDocument out(256);
  bool queued = queueSpeak(action, face, audioUrl, sleepAfter);
  out["ok"] = queued;
  out["queued"] = queued;
  out["audio_playing"] = audioPlaying;
  out["servo_angle"] = currentAngle;
  out["face"] = currentFace;

  String response;
  serializeJson(out, response);
  server.send(200, "application/json", response);
}

void handleSleep() {
  DynamicJsonDocument doc(256);
  auto err = deserializeJson(doc, server.arg("plain"));
  if (err) {
    server.send(400, "application/json", "{\"error\":\"Invalid JSON\"}");
    return;
  }

  bool sleepRequested = doc["sleep"] | false;
  if (sleepRequested) {
    stopAudioPlayback();
    sleepRobot();
  } else {
    wakeRobot();
  }

  DynamicJsonDocument out(160);
  out["ok"] = true;
  out["sleeping"] = robotSleeping;
  String response;
  serializeJson(out, response);
  server.send(200, "application/json", response);
}

void handleStop() {
  stopAudioPlayback();
  DynamicJsonDocument out(160);
  out["ok"] = true;
  out["audio_playing"] = audioPlaying;
  String response;
  serializeJson(out, response);
  server.send(200, "application/json", response);
}

void handleVolume() {
  DynamicJsonDocument doc(256);
  auto err = deserializeJson(doc, server.arg("plain"));
  if (err) {
    server.send(400, "application/json", "{\"error\":\"Invalid JSON\"}");
    return;
  }

  float requested = doc["volume"] | currentVolume;
  currentVolume = constrain(requested, 0.0f, 1.2f);

  DynamicJsonDocument out(160);
  out["ok"] = true;
  out["volume"] = currentVolume;
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
  server.on("/angle", HTTP_POST, handleAngle);
  server.on("/face", HTTP_POST, handleFace);
  server.on("/speak", HTTP_POST, handleSpeak);
  server.on("/sleep", HTTP_POST, handleSleep);
  server.on("/stop", HTTP_POST, handleStop);
  server.on("/volume", HTTP_POST, handleVolume);
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
