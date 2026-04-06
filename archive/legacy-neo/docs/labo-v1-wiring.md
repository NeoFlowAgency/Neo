# NEO Labo V1 — Guide de câblage rapide

> Projet d'apprentissage : Servo + LEDs + LCD + Clavier 4×4 sur ESP32

---

## Composants nécessaires

- 1× ESP32 DevKit-C
- 1× Servo MG996R (ou SG90 pour commencer)
- 1× LCD 16×2 avec module I2C (adresse 0x27 par défaut)
- 1× Clavier matriciel 4×4
- 3× LEDs (rouge, verte, bleue)
- 3× Résistances 220Ω (une par LED)
- Fils dupont, breadboard

---

## Schéma de branchement

### Servo MG996R (ou SG90)
```
Servo fil BRUN  (GND)    → GND de l'ESP32
Servo fil ROUGE (5V/6V)  → VIN de l'ESP32 (ou alim externe 6V)
Servo fil ORANGE (signal) → GPIO 18
```
> ⚠️ Pour un seul servo en test, le VIN du devkit (5V USB) suffit.
> Pour plusieurs servos lourds, utilise une alim externe.

### LCD 16×2 I2C
```
LCD VCC → 3.3V ou 5V ESP32
LCD GND → GND
LCD SDA → GPIO 21
LCD SCL → GPIO 22
```
> Si l'écran n'affiche rien, tourne le petit potentiomètre bleu
> derrière le module I2C pour ajuster le contraste.

### LEDs
```
LED ROUGE  : anode → GPIO 26 → résistance 220Ω → GND
LED VERTE  : anode → GPIO 27 → résistance 220Ω → GND
LED BLEUE  : anode → GPIO 32 → résistance 220Ω → GND
```
> Sens LED : patte longue = anode (+), patte courte = cathode (−)

### Clavier 4×4
```
 ┌─────────────────────────────────────┐
 │  Clavier  │  Broche  │  GPIO ESP32  │
 ├───────────┼──────────┼──────────────┤
 │  Ligne 1  │   R1     │   GPIO 13    │
 │  Ligne 2  │   R2     │   GPIO 14    │
 │  Ligne 3  │   R3     │   GPIO 16    │
 │  Ligne 4  │   R4     │   GPIO 17    │
 │  Col 1    │   C1     │   GPIO 15    │
 │  Col 2    │   C2     │   GPIO 12    │
 │  Col 3    │   C3     │   GPIO  2    │
 │  Col 4    │   C4     │   GPIO  5    │
 └─────────────────────────────────────┘
```

---

## Librairies Arduino à installer

Dans Arduino IDE → Gestionnaire de bibliothèques :

| Librairie | Auteur |
|-----------|--------|
| `ESP32Servo` | Kevin Harrington |
| `LiquidCrystal I2C` | Frank de Brabander |
| `Keypad` | Mark Stanley / Alexander Brevig |

---

## Contrôles (rappel)

| Touche | Action |
|--------|--------|
| `1` | Servo → 0° |
| `2` | Servo → 22° |
| `3` | Servo → 45° |
| `4` | Servo → 67° |
| `5` | Servo → 90° (centre) |
| `6` | Servo → 112° |
| `7` | Servo → 135° |
| `8` | Servo → 157° |
| `9` | Servo → 180° |
| `0` | Servo → 90° (centre rapide) |
| `A` | Toggle LED ROUGE |
| `B` | Toggle LED VERTE |
| `C` | Toggle LED BLEUE |
| `D` | Toggle TOUTES les LEDs |
| `*` | Affiche le menu sur LCD |
| `#` | Reset tout (servo 90°, LEDs OFF) |

---

## Problèmes fréquents

**LCD blanc/rien affiché :**
→ Tourne le potentiomètre bleu au dos du module I2C
→ Vérifie l'adresse I2C avec un sketch de scan (chercher "I2C scanner Arduino")

**Servo qui tremble :**
→ Alimente-le en externe (ne pas tirer 5V du port USB de l'ESP32 pour les gros servos)
→ Mets une capa 100µF en parallèle sur l'alim du servo

**Clavier ne répond pas :**
→ Vérifie l'ordre des fils (compte depuis le pin 1 marqué sur le connecteur)
→ Certains claviers ont R1-R4 à gauche, d'autres à droite — inverse les lignes/colonnes si besoin
