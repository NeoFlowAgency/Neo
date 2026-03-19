/*
  ╔══════════════════════════════════════════════════════════════╗
  ║  NEO — LABO V2                                               ║
  ║  Potentiomètre → Servo   |   Clavier → actions              ║
  ║  MAX98357 I2S → sons     |   Détecteur son → réaction       ║
  ╠══════════════════════════════════════════════════════════════╣
  ║  CÂBLAGE :                                                   ║
  ║  Potentiomètre  → GPIO 34  (broche centrale, 3.3V / GND)    ║
  ║  Servo signal   → GPIO 18                                    ║
  ║  MAX98357 BCLK  → GPIO 26                                    ║
  ║  MAX98357 LRC   → GPIO 25                                    ║
  ║  MAX98357 DIN   → GPIO 22                                    ║
  ║  Détecteur DO   → GPIO 35  (sortie digitale du module)      ║
  ║  Détecteur AO   → GPIO 36  (sortie analogique — optionnel)  ║
  ║  Clavier lignes → GPIO 13, 14, 16, 17                       ║
  ║  Clavier cols   → GPIO 15, 12, 2, 5                         ║
  ╠══════════════════════════════════════════════════════════════╣
  ║  CLAVIER :                                                   ║
  ║   1→Do  2→Ré  3→Mi    A→Sweep servo ON/OFF                  ║
  ║   4→Fa  5→Sol 6→La    B→Servo 0°                            ║
  ║   7→Si  8→Mélodie 9→Alarme  C→Servo 90°                    ║
  ║   *→toggle clap  0→Silence  #→Reset   D→Servo 180°          ║
  ╚══════════════════════════════════════════════════════════════╝
*/

#include <ESP32Servo.h>
#include <Keypad.h>
#include <driver/i2s.h>
#include <math.h>

// ── PINS ─────────────────────────────────────────────────────────────────────
#define PIN_POT      34   // Potentiomètre (ADC1 — fonctionne sans WiFi)
#define PIN_SERVO    18
#define PIN_DET_DO   35   // Détecteur son — sortie digitale (input only)
#define PIN_DET_AO   36   // Détecteur son — sortie analogique (input only)

// ── I2S / MAX98357 ────────────────────────────────────────────────────────────
#define I2S_BCLK     26
#define I2S_LRC      25
#define I2S_DIN      22
#define SAMPLE_RATE  16000
#define AMPLITUDE    8000   // volume (max 32767 — baisse si trop fort)

// ── CLAVIER 4×4 ──────────────────────────────────────────────────────────────
const byte KP_ROWS = 4, KP_COLS = 4;
char keys[KP_ROWS][KP_COLS] = {
  {'1','2','3','A'},
  {'4','5','6','B'},
  {'7','8','9','C'},
  {'*','0','#','D'}
};
byte rowPins[KP_ROWS] = {13, 14, 16, 17};
byte colPins[KP_COLS] = {15, 12,  2,  5};
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, KP_ROWS, KP_COLS);

// ── SERVO ─────────────────────────────────────────────────────────────────────
Servo servo;
int  servoAngle  = 90;
bool sweepMode   = false;   // balayage automatique
int  sweepAngle  = 0;
int  sweepDir    = 1;       // +1 ou -1
unsigned long lastSweep = 0;

// ── DÉTECTION SON ─────────────────────────────────────────────────────────────
bool clapEnabled = true;
unsigned long lastClap = 0;
#define CLAP_DEBOUNCE_MS 800  // évite les déclenchements multiples

// ── NOTES (fréquences en Hz) ──────────────────────────────────────────────────
#define DO   262
#define RE   294
#define MI   330
#define FA   349
#define SOL  392
#define LA   440
#define SI   494
#define DO5  523

// Mélodie : Frère Jacques (premières mesures)
const int MELODY[]   = {DO,RE,MI,DO, DO,RE,MI,DO, MI,FA,SOL, MI,FA,SOL};
const int DURATIONS[] = {350,350,350,350, 350,350,350,350, 350,350,700, 350,350,700};
const int MELODY_LEN  = 14;

// ── FONCTIONS AUDIO ───────────────────────────────────────────────────────────

void i2sInit() {
  i2s_config_t cfg = {
    .mode                 = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate          = SAMPLE_RATE,
    .bits_per_sample      = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format       = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags     = 0,
    .dma_buf_count        = 8,
    .dma_buf_len          = 64,
    .use_apll             = false,
    .tx_desc_auto_clear   = true,
  };
  i2s_pin_config_t pins = {
    .bck_io_num   = I2S_BCLK,
    .ws_io_num    = I2S_LRC,
    .data_out_num = I2S_DIN,
    .data_in_num  = I2S_PIN_NO_CHANGE,
  };
  i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pins);
}

// Joue une note (bloquant pendant duration_ms)
void playTone(int freq, int duration_ms) {
  const int BUF_SIZE = 256;
  int16_t buf[BUF_SIZE];
  int totalSamples = (long)SAMPLE_RATE * duration_ms / 1000;
  int played = 0;

  while (played < totalSamples) {
    int chunk = min(BUF_SIZE, totalSamples - played);
    for (int i = 0; i < chunk; i++) {
      // Enveloppe légère pour éviter les clics (5ms fade in/out)
      float env = 1.0f;
      int fadeLen = SAMPLE_RATE * 5 / 1000;
      if (played + i < fadeLen)
        env = (float)(played + i) / fadeLen;
      else if (played + i > totalSamples - fadeLen)
        env = (float)(totalSamples - played - i) / fadeLen;

      buf[i] = (int16_t)(AMPLITUDE * env * sinf(2.0f * PI * freq * (played + i) / SAMPLE_RATE));
    }
    size_t bw;
    i2s_write(I2S_NUM_0, buf, chunk * sizeof(int16_t), &bw, portMAX_DELAY);
    played += chunk;
  }
}

// Silence (vide le buffer DMA)
void silence() {
  int16_t buf[256] = {};
  size_t bw;
  for (int i = 0; i < 4; i++)
    i2s_write(I2S_NUM_0, buf, sizeof(buf), &bw, 100);
}

// Mélodie Frère Jacques
void playMelody() {
  Serial.println("♪ Frère Jacques...");
  for (int i = 0; i < MELODY_LEN; i++) {
    playTone(MELODY[i], DURATIONS[i]);
    delay(40);  // petit silence entre les notes
  }
  silence();
}

// Alarme (3 bips montants)
void playAlarm() {
  Serial.println("⚠ Alarme!");
  for (int i = 0; i < 3; i++) {
    playTone(800 + i * 300, 200);
    delay(80);
  }
  silence();
}

// Son de clap détecté (petite fanfare)
void playBip() {
  playTone(DO5, 100);
  silence();
}

// ── SERVO ─────────────────────────────────────────────────────────────────────

void setServo(int angle) {
  servoAngle = constrain(angle, 0, 180);
  servo.write(servoAngle);
  Serial.print("Servo → "); Serial.print(servoAngle); Serial.println("°");
}

// ── SETUP ─────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);

  // Servo
  servo.attach(PIN_SERVO, 500, 2400);
  servo.write(90);

  // I2S
  i2sInit();

  // Pins détecteur (input only — pas de pullup interne possible sur 35/36)
  pinMode(PIN_DET_DO, INPUT);

  // Démarrage
  Serial.println("=== NEO LABO V2 ===");
  Serial.println("Pot → Servo | Clavier → sons & servo | Détecteur → réaction");
  Serial.println("Clavier: 1-7=notes 8=mélodie 9=alarme 0=silence");
  Serial.println("         A=sweep B=0° C=90° D=180° *=clap #=reset");

  playTone(DO, 150); delay(50);
  playTone(MI, 150); delay(50);
  playTone(SOL, 250);
  silence();
  Serial.println("Prêt !");
}

// ── LOOP ──────────────────────────────────────────────────────────────────────
void loop() {

  // ── 1. POTENTIOMÈTRE → servo (sauf si sweep actif) ──────────────────────
  if (!sweepMode) {
    int raw = analogRead(PIN_POT);              // 0-4095 (12 bits)
    int angle = map(raw, 0, 4095, 0, 180);
    if (abs(angle - servoAngle) >= 2) {         // seuil anti-tremblement
      servoAngle = angle;
      servo.write(servoAngle);
    }
  }

  // ── 2. SWEEP AUTOMATIQUE ─────────────────────────────────────────────────
  if (sweepMode && millis() - lastSweep > 20) {
    sweepAngle += sweepDir * 2;
    if (sweepAngle >= 180) { sweepAngle = 180; sweepDir = -1; }
    if (sweepAngle <= 0)   { sweepAngle = 0;   sweepDir =  1; }
    servo.write(sweepAngle);
    lastSweep = millis();
  }

  // ── 3. DÉTECTION SON ────────────────────────────────────────────────────
  if (clapEnabled) {
    // DO = LOW quand son détecté sur la plupart des modules KY-038
    // Si ça ne marche pas, essaie d'inverser : (digitalRead == HIGH)
    bool soundDetected = (digitalRead(PIN_DET_DO) == LOW);

    if (soundDetected && millis() - lastClap > CLAP_DEBOUNCE_MS) {
      lastClap = millis();
      Serial.println(">> Son détecté ! <<");

      // Action : servo fait un petit sursaut
      int oldAngle = sweepMode ? sweepAngle : servoAngle;
      servo.write(constrain(oldAngle + 30, 0, 180));
      delay(200);
      servo.write(oldAngle);
      playBip();
    }
  }

  // ── 4. CLAVIER ───────────────────────────────────────────────────────────
  char key = keypad.getKey();
  if (!key) return;

  Serial.print("Touche: "); Serial.println(key);

  switch (key) {
    // Notes
    case '1': playTone(DO,  400); silence(); break;
    case '2': playTone(RE,  400); silence(); break;
    case '3': playTone(MI,  400); silence(); break;
    case '4': playTone(FA,  400); silence(); break;
    case '5': playTone(SOL, 400); silence(); break;
    case '6': playTone(LA,  400); silence(); break;
    case '7': playTone(SI,  400); silence(); break;
    case '8': playMelody(); break;
    case '9': playAlarm();  break;
    case '0': silence(); Serial.println("Silence"); break;

    // Servo positions fixes
    case 'B': sweepMode = false; setServo(0);   break;
    case 'C': sweepMode = false; setServo(90);  break;
    case 'D': sweepMode = false; setServo(180); break;

    // Sweep toggle
    case 'A':
      sweepMode = !sweepMode;
      sweepAngle = servoAngle;
      Serial.println(sweepMode ? "Sweep: ON" : "Sweep: OFF");
      break;

    // Toggle détection clap
    case '*':
      clapEnabled = !clapEnabled;
      Serial.println(clapEnabled ? "Détection son: ON" : "Détection son: OFF");
      break;

    // Reset
    case '#':
      sweepMode   = false;
      clapEnabled = true;
      setServo(90);
      silence();
      Serial.println("== RESET ==");
      break;
  }
}
