# NEO Labo V2 — Câblage

> Servo + Potentiomètre + MAX98357 + Détecteur son + Clavier 4×4

---

## Schéma de branchement

### Potentiomètre (3 broches)
```
Broche GAUCHE  → GND
Broche CENTRE  → GPIO 34  (signal analogique)
Broche DROITE  → 3.3V
```
> ⚠️ Utilise 3.3V, PAS 5V — l'ADC de l'ESP32 supporte max 3.3V

---

### Servo MG996R
```
Fil BRUN   (GND)    → GND
Fil ROUGE  (alim)   → alim externe 5V-6V  (ou VIN si juste 1 servo léger)
Fil ORANGE (signal) → GPIO 18
```

---

### MAX98357 (ampli I2S)
```
MAX98357  →  ESP32
VIN       →  5V (VIN du devkit)
GND       →  GND
BCLK      →  GPIO 26
LRC       →  GPIO 25
DIN       →  GPIO 22
SD        →  laisser non connecté (ou 3.3V pour activer en permanence)
```
> Le haut-parleur se branche sur les bornes "+" et "−" du MAX98357

---

### Détecteur de son (module 3 broches MH-M38)
```
VCC → 3.3V
GND → GND
OUT → GPIO 35   ← détection clap/son
```
> **OUT = LOW quand un son est détecté**, HIGH au repos.
>
> La sensibilité se règle avec le petit potentiomètre bleu sur le module.
> La LED "开关指示" (switch) s'allume quand un son est détecté.
> Tourne le potentiomètre jusqu'à ce qu'elle réagisse à tes claps.

**Si ça déclenche en permanence sans son :**
→ Tourne le potentiomètre dans le sens inverse (réduire la sensibilité)

**Si ça ne déclenche jamais :**
→ Tourne le potentiomètre pour augmenter la sensibilité, ou change dans le code :
```cpp
bool soundDetected = (digitalRead(PIN_DET_OUT) == LOW);
// → remplace LOW par HIGH
```

---

### Clavier 4×4
```
Clavier  →  GPIO ESP32
R1 (haut) →  13
R2        →  14
R3        →  16
R4 (bas)  →  17
C1 (gche) →  15
C2        →  12
C3        →   2
C4 (dte)  →   5
```

---

## Librairies Arduino nécessaires

| Librairie | Auteur |
|-----------|--------|
| `ESP32Servo` | Kevin Harrington |
| `Keypad` | Mark Stanley / Alexander Brevig |

L'I2S est intégré dans le core ESP32 — pas d'installation supplémentaire.

---

## Contrôles

| Touche | Action |
|--------|--------|
| `1`–`7` | Joue Do Ré Mi Fa Sol La Si |
| `8` | Mélodie : Frère Jacques |
| `9` | Alarme 3 bips montants |
| `0` | Silence (coupe le son) |
| `A` | Toggle balayage auto du servo |
| `B` | Servo → 0° |
| `C` | Servo → 90° |
| `D` | Servo → 180° |
| `*` | Toggle détection clap ON/OFF |
| `#` | Reset tout |

**Potentiomètre** = contrôle le servo en continu (désactivé si sweep ON)

**Clap** = le servo fait un sursaut + bip

---

## Dépannage

**Pas de son du speaker :**
→ Vérifie BCLK/LRC/DIN bien branchés
→ Vérifie que SD du MAX98357 n'est pas tiré vers GND
→ Dans Arduino IDE, sélectionne bien "ESP32 Dev Module" comme carte

**Potentiomètre fait trembler le servo :**
→ Normal, le code filtre les variations < 2° — si encore trop instable,
   augmente le seuil dans le code : `if (abs(angle - servoAngle) >= 5)`

**Détecteur son déclenche en permanence :**
→ Tourne le potentiomètre du module pour réduire la sensibilité
→ Ou change `LOW` en `HIGH` dans le code (ligne soundDetected)
