# Neo — Guide de câblage complet

> **Référence principale.** Ce document décrit la connexion exacte de chaque
> composant à l'ESP32. Le fichier Wokwi (`docs/wokwi/diagram.json`) est
> basé sur ce tableau.

---

## Plan GPIO ESP32 (FINAL)

> L'ESP32 DevKit V1 a 20 GPIO réguliers + 4 entrées uniquement (34/35/36/39).
> Le plan ci-dessous utilise les 24 GPIO disponibles sans conflit.

| GPIO | Label DevKit | Fonction | Composant | Direction | Notes |
|------|-------------|----------|-----------|-----------|-------|
| 0    | D0  | Keypad Col 4 | Keypad 4×4 | OUTPUT | Strapping pin — OK après boot |
| 2    | D2  | Keypad Col 3 | Keypad 4×4 | OUTPUT | Strapping pin — OK après boot |
| 4    | D4  | I2C SDA | LCD 16×2 + RTC | I/O | Bus I2C partagé |
| 5    | D5  | I2C SCL | LCD 16×2 + RTC | OUTPUT | Bus I2C partagé |
| 12   | D12 | Keypad Col 2 | Keypad 4×4 | OUTPUT | Strapping pin — OK après boot |
| 13   | D13 | Buzzer | KSG3603 | OUTPUT | Via résistance 100Ω |
| 14   | D14 | I2S SCK (mic) | INMP441 | OUTPUT | Horloge I2S micro |
| 15   | D15 | I2S WS (mic) | INMP441 | OUTPUT | Word Select I2S micro |
| 16   | RX2 | Keypad Row 1 | Keypad 4×4 | INPUT_PULLUP | |
| 17   | TX2 | Keypad Row 2 | Keypad 4×4 | INPUT_PULLUP | |
| 18   | D18 | Servo S1 — Torse | MG996R n°1 | PWM | Rotation base |
| 19   | D19 | Servo S2 — Cou | MG996R n°2 | PWM | Rotation gauche/droite |
| 21   | D21 | Servo S3 — Roll | MG996R n°3 | PWM | Inclinaison latérale |
| 22   | D22 | I2S DIN (ampli) | MAX98357 | OUTPUT | Data audio |
| 23   | D23 | Servo S4 — Pitch | MG996R n°4 | PWM | Inclinaison haut/bas |
| 25   | D25 | I2S LRC (ampli) | MAX98357 | OUTPUT | Word Select ampli |
| 26   | D26 | I2S BCLK (ampli) | MAX98357 | OUTPUT | Bit clock ampli |
| 27   | D27 | Servo S5 — Bouche | SG90 | PWM | Expression bouche |
| 32   | D32 | I2S SD (mic) | INMP441 | INPUT | Données micro entrant |
| 33   | D33 | Keypad Col 1 | Keypad 4×4 | OUTPUT | |
| 34   | D34 | Keypad Row 3 | Keypad 4×4 | INPUT seul | ⚠ Ajouter 10kΩ pullup → 3.3V |
| 35   | D35 | Keypad Row 4 | Keypad 4×4 | INPUT seul | ⚠ Ajouter 10kΩ pullup → 3.3V |
| 36   | VN  | Switch (interrupteur) | Switch | INPUT seul | ⚠ Ajouter 10kΩ pullup → 3.3V |
| 39   | VP  | Potentiomètre | Potentiomètre | ADC INPUT | Entrée analogique |

---

## Câblage par composant

### 1. Servos MG996R (×4) + SG90 (×1)

> ⚠️ **IMPORTANT** : Ne jamais alimenter les servos depuis les pins 3.3V ou
> 5V de l'ESP32. Utiliser une alimentation externe **5V / 5A minimum**.

Chaque servo a 3 fils :
- **Marron** (ou noir) → GND commun (ESP32 + alim. externe)
- **Rouge** → 5V externe (⚠ pas l'ESP32)
- **Orange** (ou jaune/blanc) → Signal PWM ESP32

| Servo | Fil signal → GPIO | Fil rouge → | Fil marron → |
|-------|-------------------|-------------|--------------|
| S1 — Torse (MG996R) | GPIO 18 | 5V externe | GND commun |
| S2 — Cou yaw (MG996R) | GPIO 19 | 5V externe | GND commun |
| S3 — Roll (MG996R) | GPIO 21 | 5V externe | GND commun |
| S4 — Pitch (MG996R) | GPIO 23 | 5V externe | GND commun |
| S5 — Bouche (SG90) | GPIO 27 | 5V externe | GND commun |

**Schéma alimentation servos :**
```
[Alim. 5V/5A] ──┬── [+5V Rail] ──┬── Servo S1 rouge
                │                 ├── Servo S2 rouge
                │                 ├── Servo S3 rouge
                │                 ├── Servo S4 rouge
                │                 └── Servo S5 rouge
                │
                └── [GND Rail] ───┬── Servo S1-S5 marron
                                  ├── GND ESP32
                                  └── GND toutes cartes

Ajouter un condensateur 1000µF 10V entre +5V Rail et GND Rail
(absorbe les pics de courant au démarrage des servos)
```

---

### 2. INMP441 — Microphone I2S

| Pin INMP441 | Connexion | Note |
|-------------|-----------|------|
| VDD | 3.3V ESP32 | |
| GND | GND | |
| SD  | GPIO 32 | Données audio (sortie micro) |
| WS  | GPIO 15 | Word Select |
| SCK | GPIO 14 | Horloge série |
| L/R | GND | Micro gauche (mettre à GND) |

---

### 3. MAX98357 — Amplificateur I2S + Haut-parleur

| Pin MAX98357 | Connexion | Note |
|-------------|-----------|------|
| VIN | 5V externe | Peut aussi prendre 3.3V (moins fort) |
| GND | GND | |
| LRC | GPIO 25 | Word Select |
| BCLK | GPIO 26 | Bit Clock |
| DIN | GPIO 22 | Données audio |
| GAIN | Laisser libre | Gain par défaut 9dB (ou GND=6dB, 3.3V=12dB) |
| SD  | Laisser libre | Pas en mode shutdown |
| **+** (sortie) | Haut-parleur + | Câble vers HP 3W 4Ω ou 8Ω |
| **-** (sortie) | Haut-parleur - | |

---

### 4. LCD 16×2 avec module I2C (PCF8574)

> Le LCD doit avoir un module I2C PCF8574 soudé derrière. Adresse par
> défaut : `0x27` (ou `0x3F` selon le module).

| Pin module I2C | Connexion |
|----------------|-----------|
| VCC | 5V externe ou 3.3V |
| GND | GND |
| SDA | GPIO 4 |
| SCL | GPIO 5 |

Vérifier l'adresse I2C avec un scanner I2C sur l'ESP32 si l'écran ne s'allume pas.

---

### 5. RTC — Module MH (DS1307 ou DS3231)

> Partage le même bus I2C que le LCD. Adresse : `0x68`.

| Pin RTC | Connexion |
|---------|-----------|
| VCC | 3.3V ou 5V |
| GND | GND |
| SDA | GPIO 4 (même fil que LCD SDA) |
| SCL | GPIO 5 (même fil que LCD SCL) |

---

### 6. Keypad 4×4 Matrix

> Brancher les **colonnes en OUTPUT** (ESP32 pilote) et les **rangées en INPUT_PULLUP**.
> Pour les GPIO 34 et 35 (input-only) : ajouter une résistance **10kΩ entre la pin et 3.3V** (pullup externe).

```
Keypad :    C1    C2    C3    C4
             │     │     │     │
            D33   D12   D2    D0   ← GPIO ESP32 (OUTPUT)

            R1    R2    R3    R4
             │     │     │     │
           RX2   TX2   D34   D35  ← GPIO ESP32 (INPUT)
                        │     │
                      10kΩ   10kΩ  ← vers 3.3V (pullup externe)
```

| Pin Keypad | GPIO | Direction | Pullup |
|------------|------|-----------|--------|
| R1 (Row 1) | GPIO 16 (RX2) | INPUT_PULLUP | Interne |
| R2 (Row 2) | GPIO 17 (TX2) | INPUT_PULLUP | Interne |
| R3 (Row 3) | GPIO 34 | INPUT | **Externe 10kΩ → 3.3V** |
| R4 (Row 4) | GPIO 35 | INPUT | **Externe 10kΩ → 3.3V** |
| C1 (Col 1) | GPIO 33 | OUTPUT | — |
| C2 (Col 2) | GPIO 12 | OUTPUT | — |
| C3 (Col 3) | GPIO 2  | OUTPUT | — |
| C4 (Col 4) | GPIO 0  | OUTPUT | — |

---

### 7. Buzzer KSG3603

| Connexion | Détail |
|-----------|--------|
| Pin + (signal) | GPIO 13 → résistance 100Ω → pin + buzzer |
| Pin - (GND) | GND |

---

### 8. Interrupteur (Switch)

| Connexion | Détail |
|-----------|--------|
| Pin 1 | GPIO 36 (VN) |
| Pin 2 | GND |
| Pullup | **Externe 10kΩ entre GPIO 36 et 3.3V** |

Quand l'interrupteur est ouvert → GPIO 36 lit HIGH (3.3V via pullup)
Quand l'interrupteur est fermé → GPIO 36 lit LOW (connecté à GND)

---

### 9. Potentiomètre

| Pin Potentiomètre | Connexion |
|-------------------|-----------|
| Gauche (VCC) | 3.3V |
| Droite (GND) | GND |
| Centre (signal) | GPIO 39 (VP) |

Valeur recommandée : 10kΩ

---

## Résumé alimentation

| Source | Tension | Alimente |
|--------|---------|----------|
| Alim. externe 5V/5A | 5V | Tous les servos + rail 5V |
| Rail 5V → ESP32 VIN | 5V → 3.3V interne | ESP32, LCD, RTC, buzzer |
| 3.3V ESP32 | 3.3V | INMP441, pullups keypad/switch |
| 5V externe | 5V | MAX98357 VIN, LCD VCC optionnel |

---

## Résistances nécessaires

| Résistance | Quantité | Usage |
|------------|----------|-------|
| 10kΩ | 3 | Pullup GPIO 34, 35 (keypad) + GPIO 36 (switch) |
| 100Ω | 1 | Buzzer série |
| Condensateur 1000µF 10V | 1 | Découplage rail servo 5V |
