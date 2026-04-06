// ═══════════════════════════════════════════════════════════════════════════
//  Neo Robot V1 — Sketch de test Wokwi
//  Composants testés : Servos ×5, LCD I2C, Keypad 4×4, RTC DS1307,
//                      Buzzer, Switch, Potentiomètre
//  ⚠️  INMP441 + MAX98357 non simulables sur Wokwi → testés en vrai câblage
// ═══════════════════════════════════════════════════════════════════════════

#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Keypad.h>
#include <ESP32Servo.h>
#include <RTClib.h>

// ─── PINS (voir docs/neo-wiring-guide.md) ────────────────────────────────────
#define PIN_I2C_SDA   4
#define PIN_I2C_SCL   5

#define PIN_S1       18   // Torse (MG996R)
#define PIN_S2       19   // Cou yaw (MG996R)
#define PIN_S3       21   // Roll (MG996R)
#define PIN_S4       23   // Pitch (MG996R)
#define PIN_S5       27   // Bouche (SG90)

#define PIN_BUZZER   13
#define PIN_SWITCH   36   // INPUT-only, pullup externe 10kΩ
#define PIN_POT      39   // ADC INPUT

// ─── LCD ─────────────────────────────────────────────────────────────────────
LiquidCrystal_I2C lcd(0x27, 16, 2);

// ─── RTC ─────────────────────────────────────────────────────────────────────
RTC_DS1307 rtc;

// ─── Servos ──────────────────────────────────────────────────────────────────
Servo s1, s2, s3, s4, s5;

// ─── Keypad 4×4 ──────────────────────────────────────────────────────────────
const byte ROWS = 4, COLS = 4;
char keys[ROWS][COLS] = {
  { '1', '2', '3', 'A' },
  { '4', '5', '6', 'B' },
  { '7', '8', '9', 'C' },
  { '*', '0', '#', 'D' }
};
// Rows = INPUT (pullup externe sur GPIO 34/35, interne sur 16/17)
// Cols = OUTPUT
byte rowPins[ROWS] = { 16, 17, 34, 35 };
byte colPins[COLS] = { 33, 12,  2,  0 };
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

// ─── Utilitaires ─────────────────────────────────────────────────────────────
void beep(int freq, int duree = 150) {
  tone(PIN_BUZZER, freq, duree);
  delay(duree + 30);
}

void lcdMsg(const char* ligne0, const char* ligne1 = "") {
  lcd.clear();
  lcd.setCursor(0, 0); lcd.print(ligne0);
  lcd.setCursor(0, 1); lcd.print(ligne1);
}

void servosCentre() {
  s1.write(90); s2.write(90); s3.write(90);
  s4.write(90); s5.write(30);  // Bouche fermée à 30°
}

void animationDemarrage() {
  lcdMsg("  NEO V1 Boot   ", "Test servos...");
  // Balayage de tous les servos
  for (int pos = 0; pos <= 180; pos += 15) {
    s1.write(pos); s2.write(pos); s3.write(pos);
    s4.write(pos); s5.write(map(pos, 0, 180, 30, 90));
    delay(40);
  }
  for (int pos = 180; pos >= 0; pos -= 15) {
    s1.write(pos); s2.write(pos); s3.write(pos);
    s4.write(pos); s5.write(map(pos, 0, 180, 30, 90));
    delay(40);
  }
  servosCentre();
  // Mélodie de démarrage (do mi sol)
  beep(523, 100); beep(659, 100); beep(784, 200);
  lcdMsg("  NEO est pret! ", " Appuie Keypad  ");
}

void afficherEtat() {
  DateTime now = rtc.now();
  int potVal = analogRead(PIN_POT) / 16;  // 0–255
  bool swEtat = (digitalRead(PIN_SWITCH) == LOW);

  lcd.setCursor(0, 1);
  char buf[17];
  snprintf(buf, sizeof(buf), "%02d:%02d:%02d V:%3d %c",
           now.hour(), now.minute(), now.second(),
           potVal,
           swEtat ? 'S' : '-');
  lcd.print(buf);
}

// ─── Setup ───────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  Serial.println("NEO V1 — Demarrage");

  // Pins entrée
  pinMode(PIN_SWITCH, INPUT);  // Pullup EXTERNE 10kΩ — pas INPUT_PULLUP ici

  // GPIO 34/35 input-only : forcer INPUT (pas INPUT_PULLUP)
  // La bibliothèque Keypad tente INPUT_PULLUP, on corrige après son init
  pinMode(34, INPUT);
  pinMode(35, INPUT);

  // I2C sur GPIO 4 (SDA) et GPIO 5 (SCL)
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);

  // LCD
  lcd.init();
  lcd.backlight();
  lcdMsg("Initialisation..", "");

  // RTC
  if (!rtc.begin()) {
    lcdMsg("RTC INTROUVABLE!", "Check I2C 0x68  ");
    Serial.println("ERREUR : RTC non detecte sur I2C 0x68");
    while (true) { beep(300, 500); delay(1000); }
  }
  if (!rtc.isrunning()) {
    rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
    Serial.println("RTC regle sur heure de compilation");
  }

  // Servos
  s1.attach(PIN_S1); s2.attach(PIN_S2); s3.attach(PIN_S3);
  s4.attach(PIN_S4); s5.attach(PIN_S5);
  servosCentre();
  delay(300);

  // Animation de démarrage
  animationDemarrage();
}

// ─── Loop ────────────────────────────────────────────────────────────────────
void loop() {
  // ── Keypad ──────────────────────────────────────────────────────────────
  char touche = keypad.getKey();
  if (touche) {
    Serial.print("Touche : ");
    Serial.println(touche);
    beep(1200, 60);

    lcd.setCursor(0, 0);
    char msg[17];
    snprintf(msg, sizeof(msg), "Touche : [ %c ]   ", touche);
    lcd.print(msg);

    switch (touche) {
      // ── Mouvements tête ─────────────────────────────────────
      case '2': s4.write(60);  break;  // Pitch haut
      case '8': s4.write(120); break;  // Pitch bas
      case '4': s2.write(45);  break;  // Yaw gauche
      case '6': s2.write(135); break;  // Yaw droite
      case '5': servosCentre(); break; // Centre tout

      // ── Expressions bouche ──────────────────────────────────
      case '1': s5.write(30);  break;  // Bouche fermée
      case '3': s5.write(90);  break;  // Bouche ouverte max

      // ── Roll ────────────────────────────────────────────────
      case 'A': s3.write(45);  break;  // Roll gauche
      case 'B': s3.write(90);  break;  // Roll centre
      case 'C': s3.write(135); break;  // Roll droite

      // ── Test complet ────────────────────────────────────────
      case 'D': animationDemarrage(); break;

      // ── Torse ───────────────────────────────────────────────
      case '7': s1.write(45);  break;
      case '9': s1.write(135); break;

      // ── Sons ────────────────────────────────────────────────
      case '*': beep(440, 400); break;
      case '#': beep(2000,80); beep(2000,80); beep(2000,80); break;
      case '0': noTone(PIN_BUZZER); break;
    }
  }

  // ── Switch : contrôle Roll passif ───────────────────────────────────────
  static bool lastSwitch = false;
  bool swActif = (digitalRead(PIN_SWITCH) == LOW);
  if (swActif != lastSwitch) {
    lastSwitch = swActif;
    s3.write(swActif ? 45 : 90);  // Roll gauche si switch ON
    Serial.print("Switch : ");
    Serial.println(swActif ? "ON" : "OFF");
  }

  // ── Potentiomètre → angle torse ─────────────────────────────────────────
  int potBrut = analogRead(PIN_POT);                // 0–4095
  int angleTorse = map(potBrut, 0, 4095, 0, 180);
  s1.write(angleTorse);

  // ── Rafraîchissement heure toutes les secondes ──────────────────────────
  static unsigned long dernierUpdate = 0;
  if (millis() - dernierUpdate >= 1000) {
    dernierUpdate = millis();
    afficherEtat();
  }
}
