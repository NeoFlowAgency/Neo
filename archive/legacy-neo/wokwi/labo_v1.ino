/*
  ╔══════════════════════════════════════════════════════════════╗
  ║  NEO — LABO V1 : Clavier + Servo + LEDs + LCD               ║
  ║  Projet d'apprentissage — pas de WiFi / MQTT / I2S           ║
  ╠══════════════════════════════════════════════════════════════╣
  ║  CÂBLAGE :                                                   ║
  ║  Servo signal → GPIO 18                                      ║
  ║  LCD SDA → GPIO 21 | SCL → GPIO 22 | Addr 0x27              ║
  ║  Keypad lignes → 13, 14, 16, 17                              ║
  ║  Keypad colonnes → 15, 12,  2,  5                            ║
  ║  LED rouge → GPIO 26  (+ résistance 220Ω → GND)             ║
  ║  LED verte → GPIO 27  (+ résistance 220Ω → GND)             ║
  ║  LED bleue → GPIO 32  (+ résistance 220Ω → GND)             ║
  ╠══════════════════════════════════════════════════════════════╣
  ║  CLAVIER :                                                   ║
  ║   1 2 3 A    →  1-9 : angles servo (0° à 180°)              ║
  ║   4 5 6 B    →  A/B/C : toggle LED rouge/verte/bleue         ║
  ║   7 8 9 C    →  D : toggle TOUTES les LEDs                   ║
  ║   * 0 # D    →  0 : servo centre 90°                        ║
  ║                  # : reset tout                              ║
  ║                  * : affiche menu sur LCD                    ║
  ╚══════════════════════════════════════════════════════════════╝
*/

#include <ESP32Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Keypad.h>

// ── PINS ─────────────────────────────────────────────────────────────────────
#define PIN_SERVO  18
#define PIN_LED_R  26
#define PIN_LED_G  27
#define PIN_LED_B  32

// ── LCD ───────────────────────────────────────────────────────────────────────
LiquidCrystal_I2C lcd(0x27, 16, 2);

// ── SERVO ─────────────────────────────────────────────────────────────────────
Servo servo;
int servoAngle = 90;  // position initiale : centre

// ── CLAVIER 4×4 ──────────────────────────────────────────────────────────────
const byte KP_ROWS = 4;
const byte KP_COLS = 4;

char keys[KP_ROWS][KP_COLS] = {
  {'1','2','3','A'},
  {'4','5','6','B'},
  {'7','8','9','C'},
  {'*','0','#','D'}
};
byte rowPins[KP_ROWS] = {13, 14, 16, 17};
byte colPins[KP_COLS] = {15, 12,  2,  5};

Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, KP_ROWS, KP_COLS);

// ── ÉTAT LEDs ─────────────────────────────────────────────────────────────────
bool ledR = false;
bool ledG = false;
bool ledB = false;

// ── Angles servo associés aux touches 1-9 ────────────────────────────────────
//  1→0°  2→22°  3→45°
//  4→67° 5→90°  6→112°
//  7→135° 8→157° 9→180°
const int angles[10] = {90, 0, 22, 45, 67, 90, 112, 135, 157, 180};
//                       0   1   2   3   4   5    6    7    8    9

// ── FONCTIONS ─────────────────────────────────────────────────────────────────

void applyLeds() {
  digitalWrite(PIN_LED_R, ledR ? HIGH : LOW);
  digitalWrite(PIN_LED_G, ledG ? HIGH : LOW);
  digitalWrite(PIN_LED_B, ledB ? HIGH : LOW);
}

void moveServo(int angle) {
  servoAngle = constrain(angle, 0, 180);
  servo.write(servoAngle);
}

void updateLCD() {
  // Ligne 1 : angle servo
  lcd.setCursor(0, 0);
  lcd.print("Servo: ");
  lcd.print(servoAngle);
  lcd.print((char)223);   // symbole degré °
  lcd.print("   ");       // efface les anciens caractères

  // Ligne 2 : état LEDs
  lcd.setCursor(0, 1);
  lcd.print("R:");
  lcd.print(ledR ? "ON " : "OFF");
  lcd.print(" G:");
  lcd.print(ledG ? "ON " : "OFF");
  // Bleu n'a pas la place, on abrège
  lcd.print(ledB ? " B" : "  ");
}

void showMenu() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("1-9:servo A:R");
  lcd.setCursor(0, 1);
  lcd.print("0:centre B:G C:B");
  delay(2500);
  lcd.clear();
  updateLCD();
}

void resetAll() {
  ledR = false; ledG = false; ledB = false;
  applyLeds();
  moveServo(90);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("  == RESET ==   ");
  lcd.setCursor(0, 1);
  lcd.print("  Servo: 90     ");
  delay(1000);
  lcd.clear();
  updateLCD();
}

// ── SETUP ─────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);

  // LEDs
  pinMode(PIN_LED_R, OUTPUT);
  pinMode(PIN_LED_G, OUTPUT);
  pinMode(PIN_LED_B, OUTPUT);
  applyLeds();

  // Servo
  servo.attach(PIN_SERVO, 500, 2400);
  servo.write(servoAngle);

  // LCD
  Wire.begin(21, 22);
  lcd.init();
  lcd.backlight();

  // Écran de démarrage
  lcd.setCursor(0, 0);
  lcd.print("  NEO  LABO  V1 ");
  lcd.setCursor(0, 1);
  lcd.print(" Pret! Appuie * ");
  delay(2000);
  lcd.clear();

  updateLCD();
  Serial.println("=== NEO LABO V1 démarré ===");
}

// ── LOOP ──────────────────────────────────────────────────────────────────────
void loop() {
  char key = keypad.getKey();
  if (!key) return;

  Serial.print("Touche: ");
  Serial.println(key);

  // Touches 1-9 : angles servo
  if (key >= '1' && key <= '9') {
    int idx = key - '0';
    moveServo(angles[idx]);
    Serial.print("Servo → ");
    Serial.print(servoAngle);
    Serial.println("°");
  }
  // Touche 0 : servo centre
  else if (key == '0') {
    moveServo(90);
    Serial.println("Servo → 90° (centre)");
  }
  // Touche A : toggle LED rouge
  else if (key == 'A') {
    ledR = !ledR;
    applyLeds();
    Serial.print("LED Rouge: ");
    Serial.println(ledR ? "ON" : "OFF");
  }
  // Touche B : toggle LED verte
  else if (key == 'B') {
    ledG = !ledG;
    applyLeds();
    Serial.print("LED Verte: ");
    Serial.println(ledG ? "ON" : "OFF");
  }
  // Touche C : toggle LED bleue
  else if (key == 'C') {
    ledB = !ledB;
    applyLeds();
    Serial.print("LED Bleue: ");
    Serial.println(ledB ? "ON" : "OFF");
  }
  // Touche D : toggle TOUTES les LEDs
  else if (key == 'D') {
    bool allOn = ledR && ledG && ledB;
    ledR = ledG = ledB = !allOn;
    applyLeds();
    Serial.println(ledR ? "Toutes LEDs: ON" : "Toutes LEDs: OFF");
  }
  // Touche * : affiche le menu
  else if (key == '*') {
    showMenu();
    return;
  }
  // Touche # : reset tout
  else if (key == '#') {
    resetAll();
    return;
  }

  updateLCD();
}
