/*  ╔══════════════════════════════════════════════════════════╗
    ║  NEO V1  —  ESP32 firmware                               ║
    ║  Contrôle : 4x MG996R (Pan+Tilt), LCD I2C, Clavier 4x4  ║
    ║  Audio    : INMP441 (mic I2S) + MAX98357 (speaker I2S)   ║
    ║  Comm     : WiFi + MQTT                                   ║
    ╚══════════════════════════════════════════════════════════╝

    Wokwi simulation : définir #define WOKWI_SIM pour désactiver I2S
    Hardware réel    : commenter le define ci-dessous
*/

// #define WOKWI_SIM   // ← décommenter pour simuler dans Wokwi

// ── Includes ──────────────────────────────────────────────────────────────────
#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ESP32Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Keypad.h>
#include <ArduinoJson.h>

#ifndef WOKWI_SIM
  #include <driver/i2s.h>
#endif

// ── WiFi & MQTT ───────────────────────────────────────────────────────────────
const char* WIFI_SSID     = "TON_SSID";
const char* WIFI_PASSWORD = "TON_MOT_DE_PASSE";
const char* MQTT_SERVER   = "72.61.111.8";
const int   MQTT_PORT     = 1883;
const char* MQTT_CLIENT   = "neo-esp32";

const char* TOPIC_CMD    = "neo/commandes";
const char* TOPIC_STATUS = "neo/status";
const char* TOPIC_AUDIO  = "neo/audio/data";
const char* TOPIC_MIC    = "neo/audio/mic";

// ── GPIO Pinout ───────────────────────────────────────────────────────────────
// Servos
#define PIN_PAN_A   18
#define PIN_PAN_B   19
#define PIN_TILT_A  23
#define PIN_TILT_B   4

// LCD I2C
#define LCD_SDA 21
#define LCD_SCL 22
#define LCD_ADDR 0x27

// Clavier 4×4
#define KP_ROWS 4
#define KP_COLS 4
byte kpRowPins[KP_ROWS] = {13, 14, 16, 17};
byte kpColPins[KP_COLS] = {15, 12,  2,  5};

// Buzzer (Wokwi) / Speaker (GPIO 25 partagé)
#define PIN_BUZZER 25

#ifndef WOKWI_SIM
  // I2S Microphone INMP441
  #define I2S_MIC_SCK  32
  #define I2S_MIC_WS   33
  #define I2S_MIC_SD   34

  // I2S Speaker MAX98357
  #define I2S_SPK_BCLK 25
  #define I2S_SPK_LRC  26
  #define I2S_SPK_DIN  27
#endif

// ── Servo limits ──────────────────────────────────────────────────────────────
#define SERVO_MIN  500   // µs
#define SERVO_MAX  2500  // µs
#define PAN_MIN    30
#define PAN_MAX    150
#define PAN_CENTER 90
#define TILT_MIN   50
#define TILT_MAX   130
#define TILT_CENTER 90
#define STEP        15   // degrés par commande

// ── Objects ───────────────────────────────────────────────────────────────────
Servo servoPanA, servoPanB, servoTiltA, servoTiltB;
LiquidCrystal_I2C lcd(LCD_ADDR, 16, 2);

const char keys[KP_ROWS][KP_COLS] = {
  {'1','2','3','A'},
  {'4','5','6','B'},
  {'7','8','9','C'},
  {'*','0','#','D'}
};
Keypad keypad = Keypad(makeKeymap(keys), kpRowPins, kpColPins, KP_ROWS, KP_COLS);

WiFiClient   wifiClient;
PubSubClient mqttClient(wifiClient);

// ── State ─────────────────────────────────────────────────────────────────────
int currentPan  = PAN_CENTER;
int currentTilt = TILT_CENTER;

// ── Helpers ───────────────────────────────────────────────────────────────────
void setHead(int pan, int tilt) {
  pan  = constrain(pan,  PAN_MIN,  PAN_MAX);
  tilt = constrain(tilt, TILT_MIN, TILT_MAX);
  currentPan  = pan;
  currentTilt = tilt;
  servoPanA.write(pan);
  servoPanB.write(180 - pan);   // miroir
  servoTiltA.write(tilt);
  servoTiltB.write(180 - tilt); // miroir
}

void lcdPrint(const char* line1, const char* line2 = "") {
  lcd.clear();
  lcd.setCursor(0, 0); lcd.print(line1);
  lcd.setCursor(0, 1); lcd.print(line2);
}

void publishStatus(const char* state) {
  StaticJsonDocument<128> doc;
  doc["state"] = state;
  doc["pan"]   = currentPan;
  doc["tilt"]  = currentTilt;
  char buf[128];
  serializeJson(doc, buf);
  mqttClient.publish(TOPIC_STATUS, buf);
}

// ── Buzzer beep (Wokwi) ───────────────────────────────────────────────────────
#ifdef WOKWI_SIM
void beep(int freq, int ms) {
  tone(PIN_BUZZER, freq, ms);
  delay(ms + 10);
}
#endif

// ── MQTT callback ─────────────────────────────────────────────────────────────
void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  // Audio data → play raw PCM
  if (strcmp(topic, TOPIC_AUDIO) == 0) {
#ifndef WOKWI_SIM
    size_t written = 0;
    i2s_write(I2S_NUM_0, payload, length, &written, portMAX_DELAY);
#endif
    return;
  }

  // Commands JSON
  StaticJsonDocument<256> doc;
  if (deserializeJson(doc, payload, length) != DeserializationError::Ok) return;

  const char* action = doc["action"] | "";

  if      (strcmp(action, "tete_gauche")  == 0) setHead(currentPan - STEP, currentTilt);
  else if (strcmp(action, "tete_droite")  == 0) setHead(currentPan + STEP, currentTilt);
  else if (strcmp(action, "tete_haut")    == 0) setHead(currentPan, currentTilt - STEP);
  else if (strcmp(action, "tete_bas")     == 0) setHead(currentPan, currentTilt + STEP);
  else if (strcmp(action, "tete_centre")  == 0) setHead(PAN_CENTER, TILT_CENTER);
  else if (strcmp(action, "repos")        == 0) {
    setHead(PAN_CENTER, TILT_CENTER);
    lcdPrint("NEO READY", "");
  }
  else if (strcmp(action, "servo_direct") == 0) {
    int pan  = doc["pan"]  | currentPan;
    int tilt = doc["tilt"] | currentTilt;
    setHead(pan, tilt);
  }
  else if (strcmp(action, "buzzer_test")  == 0) {
#ifdef WOKWI_SIM
    beep(523, 120); beep(659, 120); beep(784, 200);
#endif
    lcdPrint("BUZZER TEST", "");
  }
  else if (strcmp(action, "lcd") == 0) {
    const char* texte = doc["texte"] | "";
    char l1[17], l2[17];
    strncpy(l1, texte,      16); l1[16] = '\0';
    strncpy(l2, texte + 16, 16); l2[16] = '\0';
    lcdPrint(l1, l2);
  }
  else if (strcmp(action, "dire") == 0) {
    // Audio TTS arrivera via TOPIC_AUDIO
    // Affiche le texte sur le LCD en attendant
    const char* texte = doc["texte"] | "";
    char l1[17];
    strncpy(l1, texte, 16); l1[16] = '\0';
    lcdPrint("Neo:", l1);
#ifdef WOKWI_SIM
    beep(880, 200);
#endif
  }

  publishStatus("ok");
}

// ── WiFi ──────────────────────────────────────────────────────────────────────
void connectWifi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  lcdPrint("WiFi...", "");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
  lcdPrint("WiFi OK", WiFi.localIP().toString().c_str());
  delay(1000);
}

// ── MQTT reconnect ────────────────────────────────────────────────────────────
void reconnectMqtt() {
  while (!mqttClient.connected()) {
    lcdPrint("MQTT...", "");
    if (mqttClient.connect(MQTT_CLIENT)) {
      mqttClient.subscribe(TOPIC_CMD);
      mqttClient.subscribe(TOPIC_AUDIO);
      lcdPrint("Neo pret!", "");
      publishStatus("ready");
    } else {
      delay(3000);
    }
  }
}

// ── I2S setup ─────────────────────────────────────────────────────────────────
#ifndef WOKWI_SIM
void setupI2S() {
  // Speaker (I2S_NUM_0)
  i2s_config_t spkCfg = {
    .mode                 = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate          = 22050,
    .bits_per_sample      = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format       = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags     = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count        = 8,
    .dma_buf_len          = 1024,
    .use_apll             = false,
    .tx_desc_auto_clear   = true,
  };
  i2s_pin_config_t spkPins = {
    .bck_io_num   = I2S_SPK_BCLK,
    .ws_io_num    = I2S_SPK_LRC,
    .data_out_num = I2S_SPK_DIN,
    .data_in_num  = I2S_PIN_NO_CHANGE,
  };
  i2s_driver_install(I2S_NUM_0, &spkCfg, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &spkPins);

  // Microphone (I2S_NUM_1)
  i2s_config_t micCfg = {
    .mode                 = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate          = 16000,
    .bits_per_sample      = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format       = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags     = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count        = 4,
    .dma_buf_len          = 1024,
    .use_apll             = false,
    .tx_desc_auto_clear   = false,
  };
  i2s_pin_config_t micPins = {
    .bck_io_num   = I2S_MIC_SCK,
    .ws_io_num    = I2S_MIC_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num  = I2S_MIC_SD,
  };
  i2s_driver_install(I2S_NUM_1, &micCfg, 0, NULL);
  i2s_set_pin(I2S_NUM_1, &micPins);
}

// Mic task — lit le micro et publie en MQTT
void micTask(void* param) {
  static int32_t buf[512];
  static int16_t pcm[512];
  size_t bytesRead = 0;
  for (;;) {
    i2s_read(I2S_NUM_1, buf, sizeof(buf), &bytesRead, portMAX_DELAY);
    int samples = bytesRead / 4;
    for (int i = 0; i < samples; i++) {
      pcm[i] = (int16_t)(buf[i] >> 14); // 32-bit → 16-bit
    }
    mqttClient.publish(TOPIC_MIC, (uint8_t*)pcm, samples * 2, false);
  }
}
#endif

// ── Keypad actions ────────────────────────────────────────────────────────────
void handleKey(char key) {
  switch (key) {
    case '2': setHead(currentPan, currentTilt - STEP); break; // haut
    case '8': setHead(currentPan, currentTilt + STEP); break; // bas
    case '4': setHead(currentPan - STEP, currentTilt); break; // gauche
    case '6': setHead(currentPan + STEP, currentTilt); break; // droite
    case '5': setHead(PAN_CENTER, TILT_CENTER);         break; // centre
    case '0': setHead(PAN_CENTER, TILT_CENTER); lcdPrint("NEO READY", ""); break;
    case 'A': lcdPrint("Pan:", String(currentPan).c_str());   break;
    case 'B': lcdPrint("Tilt:", String(currentTilt).c_str()); break;
    case '*': publishStatus("ping"); break;
    default: break;
  }
}

// ── setup ─────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);

  // Servos
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  ESP32PWM::allocateTimer(2);
  ESP32PWM::allocateTimer(3);
  servoPanA.setPeriodHertz(50);   servoPanA.attach(PIN_PAN_A,   SERVO_MIN, SERVO_MAX);
  servoPanB.setPeriodHertz(50);   servoPanB.attach(PIN_PAN_B,   SERVO_MIN, SERVO_MAX);
  servoTiltA.setPeriodHertz(50);  servoTiltA.attach(PIN_TILT_A, SERVO_MIN, SERVO_MAX);
  servoTiltB.setPeriodHertz(50);  servoTiltB.attach(PIN_TILT_B, SERVO_MIN, SERVO_MAX);
  setHead(PAN_CENTER, TILT_CENTER);

  // LCD
  Wire.begin(LCD_SDA, LCD_SCL);
  lcd.init();
  lcd.backlight();
  lcdPrint("NEO BOOT...", "");

#ifdef WOKWI_SIM
  pinMode(PIN_BUZZER, OUTPUT);
  beep(440, 150);
  beep(660, 150);
  beep(880, 200);
#else
  setupI2S();
  xTaskCreate(micTask, "micTask", 4096, NULL, 1, NULL);
#endif

  connectWifi();

  mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
  mqttClient.setCallback(onMqttMessage);
  mqttClient.setBufferSize(8192); // audio chunks
  reconnectMqtt();
}

// ── loop ──────────────────────────────────────────────────────────────────────
void loop() {
  if (!mqttClient.connected()) reconnectMqtt();
  mqttClient.loop();

  char key = keypad.getKey();
  if (key) handleKey(key);
}
