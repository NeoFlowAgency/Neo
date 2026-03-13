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

| GPIO | Fonction | Composant | Protocole |
|------|----------|-----------|-----------|
| 25   | I2S WS (LRC) | MAX98357 ampli | I2S |
| 26   | I2S BCLK | MAX98357 ampli | I2S |
| 22   | I2S DOUT | MAX98357 ampli | I2S |
| 32   | I2S WS | INMP441 micro | I2S |
| 33   | I2S SCK | INMP441 micro | I2S |
| 34   | I2S SD (data in) | INMP441 micro | I2S (entrée) |
| 18   | Servo S1 (torse) | MG996R | PWM |
| 19   | Servo S2 (cou yaw) | MG996R | PWM |
| 21   | Servo S3 (tête roll) | MG996R | PWM |
| 23   | Servo S4 (tête pitch) | MG996R | PWM |
| 27   | Servo S5 (bouche) | SG90 | PWM |
| 4    | I2C SDA | LCD 16x2 + RTC | I2C |
| 5    | I2C SCL | LCD 16x2 + RTC | I2C |
| 13   | Keypad Row 1 | Keypad 4×4 | Digital |
| 14   | Keypad Row 2 | Keypad 4×4 | Digital |
| 15   | Keypad Row 3 | Keypad 4×4 | Digital |
| 16   | Keypad Row 4 | Keypad 4×4 | Digital |
| 17   | Keypad Col 1 | Keypad 4×4 | Digital |
| 12   | Keypad Col 2 | Keypad 4×4 | Digital |
| 35   | Keypad Col 3 | Keypad 4×4 | Digital |
| 36   | Keypad Col 4 | Keypad 4×4 | Digital |
| 2    | Buzzer | KSG3603 | Digital/PWM |
| 0    | Switch | Interrupteur | Digital (INPUT_PULLUP) |
| 39   | Potentiomètre | Volume/réglage | Analogique (ADC) |
| 1    | UART TX | Debug/Serial | UART |
| 3    | UART RX | Debug/Serial | UART |

> **Note LCD :** Le LCD 16x2 doit utiliser un module I2C (PCF8574) pour éviter d'utiliser 6 GPIO. Si ton LCD n'a pas encore de module I2C, il faut en commander un (~1€).

> **Note RTC :** Le module MH RTC (DS1307 ou DS3231) se met sur le même bus I2C (même SDA/SCL). Adresse I2C différente, aucun conflit.

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
