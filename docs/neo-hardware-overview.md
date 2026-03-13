# Neo — Vue d'ensemble Hardware

## 1. Architecture générale

```
┌─────────────────────────────────────────────────────┐
│                    VPS (Cloud)                       │
│   Flask + SocketIO ←→ OpenClaw AI                   │
└────────────────────┬────────────────────────────────┘
                     │ WiFi / MQTT
┌────────────────────▼────────────────────────────────┐
│                  ESP32 (cerveau)                     │
│  I2S Mic  │  I2S Amp  │  Servos  │  LCD  │  Keypad  │
└─────┬─────┴─────┬─────┴────┬─────┴───┬───┴────┬─────┘
      │           │          │         │        │
  INMP441    MAX98357    4×MG996R   LCD 16x2  Keypad
  (micro)    (ampli)    + 1×SG90   + RTC DS  4×4
                           │
                        Alimentation
                      5V / 5A externe
```

## 2. Mécanique & Mouvements (V1)

```
         ┌──────────────────────┐
         │   TÊTE (creux)       │  ← tous les composants légers ici
         │   LCD, ESP32, mic... │
         └──────────┬───────────┘
                    │ câbles internes
         ┌──────────▼───────────┐
         │   COU                │  ← Servo 3 : inclinaison gauche/droite
         │   Servo 4 : haut/bas │     (pan)
         └──────────┬───────────┘
                    │
         ┌──────────▼───────────┐
         │   TORSE              │  ← Servo 2 : rotation cou (yaw)
         └──────────┬───────────┘
                    │
         ┌──────────▼───────────┐
         │   BASE               │  ← Servo 1 : rotation torse (base)
         │   Alimentation       │
         │   Switch, Potentio   │
         └──────────────────────┘
```

| Servo | Emplacement | Mouvement | Modèle | Plage |
|-------|-------------|-----------|--------|-------|
| S1    | Base        | Rotation torse (yaw) | MG996R | 30°–150° |
| S2    | Torse       | Rotation cou (yaw) | MG996R | 40°–140° |
| S3    | Cou         | Inclinaison tête gauche/droite (roll) | MG996R | 50°–130° |
| S4    | Cou         | Inclinaison tête haut/bas (pitch) | MG996R | 50°–130° |
| S5    | Tête        | Bouche (open/close) | SG90 | 0°–45° |

## 3. Plan GPIO ESP32

> L'ESP32 dispose de ~30 GPIO utilisables. Voici l'attribution complète.

| GPIO | Label DevKit | Fonction | Composant | Notes |
|------|-------------|----------|-----------|-------|
| 0  | D0  | Keypad Col 4 | Keypad 4×4 | Strapping pin — OK après boot |
| 2  | D2  | Keypad Col 3 | Keypad 4×4 | Strapping pin — OK après boot |
| 4  | D4  | I2C SDA | LCD 16x2 + RTC | Bus I2C partagé |
| 5  | D5  | I2C SCL | LCD 16x2 + RTC | Bus I2C partagé |
| 12 | D12 | Keypad Col 2 | Keypad 4×4 | Strapping pin — OK après boot |
| 13 | D13 | Buzzer | KSG3603 | Via résistance 100Ω |
| 14 | D14 | I2S SCK (mic) | INMP441 | Horloge micro |
| 15 | D15 | I2S WS (mic) | INMP441 | Word Select micro |
| 16 | RX2 | Keypad Row 1 | Keypad 4×4 | INPUT_PULLUP interne |
| 17 | TX2 | Keypad Row 2 | Keypad 4×4 | INPUT_PULLUP interne |
| 18 | D18 | Servo S1 — Torse | MG996R | PWM |
| 19 | D19 | Servo S2 — Cou | MG996R | PWM |
| 21 | D21 | Servo S3 — Roll | MG996R | PWM |
| 22 | D22 | I2S DIN (ampli) | MAX98357 | Data audio |
| 23 | D23 | Servo S4 — Pitch | MG996R | PWM |
| 25 | D25 | I2S LRC (ampli) | MAX98357 | Word Select ampli |
| 26 | D26 | I2S BCLK (ampli) | MAX98357 | Bit Clock ampli |
| 27 | D27 | Servo S5 — Bouche | SG90 | PWM |
| 32 | D32 | I2S SD (mic) | INMP441 | Données micro (INPUT) |
| 33 | D33 | Keypad Col 1 | Keypad 4×4 | OUTPUT |
| 34 | D34 | Keypad Row 3 | Keypad 4×4 | INPUT seul — 10kΩ pullup externe |
| 35 | D35 | Keypad Row 4 | Keypad 4×4 | INPUT seul — 10kΩ pullup externe |
| 36 | VP  | Switch | Interrupteur | INPUT seul — 10kΩ pullup externe |
| 39 | VN  | Potentiomètre | Volume/réglage | ADC INPUT |

> **Note LCD :** Le LCD 16x2 doit avoir un module I2C (PCF8574) soudé derrière. À commander si absent (~1€). Adresse par défaut : `0x27`.

> **Note RTC :** Partage le même bus I2C que le LCD (même SDA/SCL, GPIO 4/5). Adresse `0x68`, aucun conflit.

> **Note GPIO input-only :** GPIO 34, 35, 36 sont entrées uniquement et n'ont PAS de pull-up interne. Ajouter des résistances 10kΩ externes entre ces pins et 3.3V (voir guide de câblage).

## 4. Alimentation — POINT CRITIQUE ⚠️

### Problème : le LiPo 1S 300mAh est insuffisant

| Composant | Tension | Courant typique | Courant max (stall) |
|-----------|---------|-----------------|---------------------|
| MG996R ×4 | 5V–6V | 4 × 500mA = 2A | 4 × 2.5A = **10A** |
| SG90 ×1 | 5V | 100mA | 600mA |
| ESP32 | 3.3V (via régulateur 5V) | 240mA | 500mA |
| LCD + RTC | 5V | 50mA | — |
| Micro + Ampli | 3.3V | 50mA | — |
| **TOTAL estimé** | | **~2.5A** repos | **>10A** bloqué |

La LiPo 1S 3.7V 300mAh = **300mAh à 3.7V** → inutilisable pour les servos.

### Solution recommandée pour V1 (filaire — sur secteur)

```
Prise secteur
     │
[Alimentation 5V / 5A]  ← Commander : ~10€ (type "5V 5A DC adapter")
     │
     ├── [Rail 5V servo]  → S1, S2, S3, S4 (MG996R) + S5 (SG90)
     │        │
     │    [Condensateur 1000µF 10V]  ← absorbe les pics de courant
     │
     └── [Régulateur 3.3V ou pin VIN ESP32]  → ESP32, LCD, RTC, Mic, Ampli
```

> L'ESP32 accepte 5V sur sa pin VIN (il a un régulateur 3.3V interne).
> **Ne jamais alimenter les servos depuis les pins 3.3V ou 5V de l'ESP32** — il ne peut fournir que ~40mA par pin.

### Usage du LiPo 1S 300mAh

Garde-le pour un usage futur (alimentation de secours d'un Arduino Nano, ou capteur BLE autonome).

### Usage des MB102 Power Modules

Les modules MB102 (3.3V/5V depuis jack barrel ou USB) sont utiles pour :
- Alimenter les breadboards de prototypage
- Alimenter séparément les modules capteurs lors des tests

## 5. Composants V1 — tableau de décision

| Composant | V1 | Raison |
|-----------|-----|--------|
| ESP32 Type-C | ✅ | Cerveau principal |
| 4× MG996R | ✅ | Mouvements torse/cou/tête |
| 1× SG90 | ✅ | Bouche (optionnel) |
| INMP441 | ✅ | Micro I2S — entrée voix |
| MAX98357 | ✅ | Ampli I2S — sortie voix |
| LCD 16x2 | ✅ | Affichage état/texte |
| MH RTC | ✅ | Heure locale même sans WiFi |
| Buzzer KSG3603 | ✅ | Feedback sonore simple |
| Keypad 4×4 | ✅ | Contrôle manuel |
| Switch | ✅ | Marche/Arrêt ou mode |
| Potentiomètre | ✅ | Volume ou réglage vitesse |
| KY-037 sound sensor | 🔶 V2 | Détection son/voix (INMP441 suffit en V1) |
| SN74HC595 | 🔶 V2 | Utile si besoin >30 LEDs |
| Arduino Nano ×3 | 🔶 V2/V3 | Co-processeurs si ESP32 saturé |
| LiPo 1S 300mAh | ❌ V1 | Trop petite, garde pour autre projet |
| TT motors + roues | 🔶 V2 | Déplacement — pas prévu en V1 |
| Capteur eau | ❌ | Pas pertinent pour Neo |
| Capteur humidité | 🔶 | Capteur ambiance (optionnel) |

## 6. À commander pour compléter V1

| Composant | Pourquoi | Coût estimé |
|-----------|----------|-------------|
| **Alimentation 5V / 5A** (jack DC ou USB-C PD) | Indispensable pour les servos | ~8–12€ |
| **Haut-parleur 3W 4Ω ou 8Ω** (petit, ~40mm) | Nécessaire pour le MAX98357 | ~3–5€ |
| **Module I2C pour LCD 16x2** (PCF8574) | Libère 4 GPIO, câblage simple | ~2€ |
| **Condensateur 1000µF 10V** | Stabilise le rail servo | ~1€ |

## 7. Roadmap versions

### V1 — Buste expressif (objectif actuel)
- [x] Backend VPS (Flask + MQTT + OpenClaw)
- [x] Interface web de contrôle
- [ ] Firmware ESP32 (MQTT, servos, LCD, micro, ampli)
- [ ] Schéma électronique complet
- [ ] Structure 3D de base (torse + cou + tête)
- [ ] Câblage final

### V2 — Mobilité
- [ ] Base roulante (TT motors + roues)
- [ ] Détection obstacle
- [ ] Navigation simple

### V3 — Expressions faciales
- [ ] Micro servos pour yeux/sourcils
- [ ] Impression 3D tête expressive (Bambu Lab A1)
- [ ] Lèvres animées (SG90 amélioré)
