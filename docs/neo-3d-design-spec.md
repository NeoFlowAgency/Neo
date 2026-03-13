# Neo — Spécification 3D (V1)

> Guide de modélisation pour Fusion 360 — imprimante Bambu Lab A1

---

## Dimensions de référence : Servo MG996R

```
Longueur : 40.7 mm
Largeur  : 19.7 mm
Hauteur  : 42.9 mm (corps) + ~15 mm axe
Trous de fixation : 49 mm entre-axes (axe long) × 10 mm (axe court)
Diamètre vis fixation : M3
Diamètre axe (horn) : ~6 mm cannelé, 25 dents
Vis de fixation horn : M3 × 8 mm
```

---

## Pièces à modéliser — dans l'ordre

```
PIÈCE 1 : BASE
PIÈCE 2 : BUSTE (monté sur S1 dans la base)
PIÈCE 3 : COU  (monté sur S2 dans le buste)
PIÈCE 4 : SUPPORT TÊTE (monté sur S3 dans le cou)
PIÈCE 5 : CAGE INTERNE TÊTE (adaptateur → tête Ultron)
```

---

## PIÈCE 1 — BASE

**Fonction :** Boîtier principal qui contient l'électronique + porte le Servo S1 (rotation torse)

**Dimensions extérieures recommandées :**
```
Longueur : 180 mm
Largeur  : 130 mm
Hauteur  : 90 mm
Épaisseur parois : 3 mm (PETG) ou 2.5 mm (PLA+)
```

**Découpes façade avant (face avec LCD et clavier) :**
```
LCD 16×2 (I2C) :
  Fenêtre : 74 mm × 25 mm
  Position : centré en haut, à 10 mm du bord supérieur

Clavier 4×4 :
  Fenêtre : 72 mm × 72 mm
  Position : centré en bas, à 8 mm du bord inférieur

Entrée câbles (côté) : passage Ø8 mm
Interrupteur marche/arrêt (côté) : trou Ø7 mm
Potentiomètre (côté) : trou Ø7 mm
```

**Dessus de la base :**
```
Centre dessus : logement servo S1 (MG996R à PLAT)
  Cavité : 44 mm × 22 mm × 23 mm (corps servo)
  Trous de vis : 4 × M3, selon entraxe 49 mm × 10 mm
  L'axe servo pointe VERS LE HAUT
  Axe centré sur la largeur, décalé vers l'arrière de 20 mm
```

**Intérieur :**
```
Plots de montage ESP32 : 4 × plots M2.5, hauteur 5 mm
  (Dimensions carte ESP32 DevKit-C : 55 mm × 28 mm)
Passage câbles : gouttières 8 mm de large sur les côtés
```

**Matériau recommandé :** PETG ou PLA+ (résistance à la chaleur de l'ESP32)
**Infill :** 25–30%, gyroïde

---

## PIÈCE 2 — BUSTE

**Fonction :** Torse de Neo — tourne gauche/droite avec S1 (base) — porte S2 (rotation cou)

**⚠️ Contrainte mécanique :** Le buste doit avoir en bas un adaptateur vissé sur le horn de S1, et en haut un logement pour S2.

**Dimensions :**
```
Largeur bas   : 100 mm
Largeur haut  : 70 mm
Profondeur    : 60 mm
Hauteur       : 110 mm
Épaisseur paroi : 3 mm
```

**Bas du buste — adaptateur horn S1 :**
```
Plateau circulaire Ø55 mm, épaisseur 5 mm
  Trous de vis horn standard : 4 × M3 sur Ø42 mm
  Trou central : Ø6.5 mm (passage axe servo)
Ce plateau s'emboîte DANS la base (5 mm de jeu vertical → rotation libre)
```

**Haut du buste — logement S2 :**
```
S2 monté À PLAT (axe pointant vers le haut)
Cavité : 44 mm × 22 mm × 23 mm
Trous de vis : 4 × M3, entraxe 49 mm × 10 mm
Axe centré sur la largeur et la profondeur
```

**Forme :**
```
Section trapézoïdale (plus large en bas)
Léger creux esthétique sur les côtés (optionnel)
Trous Ø8 mm pour passage câbles internes
```

**Matériau :** PETG
**Infill :** 30%, gyroïde

---

## PIÈCE 3 — COU

**Fonction :** Relie buste et support tête — tourne gauche/droite avec S2 — porte S3

**Dimensions :**
```
Diamètre ext : 55 mm
Hauteur      : 70 mm
Épaisseur paroi : 3 mm (cylindre creux)
```

**Bas du cou — adaptateur horn S2 :**
```
Identique au bas du buste (plateau Ø55 mm, vis horn sur Ø42 mm)
```

**Haut du cou — logement S3 :**
```
S3 monté HORIZONTALEMENT (axe pointant vers la droite ou la gauche)
Cavité ouverte sur le côté : 44 mm × 22 mm × 43 mm
Trous de vis : 4 × M3, entraxe 49 mm × 10 mm
L'axe de S3 pointe perpendiculairement à l'axe de rotation du cou
```

**Passage câbles :** gouttière centrale Ø10 mm sur toute la hauteur

**Matériau :** PETG
**Infill :** 35% (pièce de liaison sous stress)

---

## PIÈCE 4 — SUPPORT TÊTE

**Fonction :** Plateau en croix — reçoit le horn de S3 — porte 2× servos (S4 + symétrique) pour incliner la tête haut/bas

```
⚠️ NOTE : En V1 avec 4× MG996R, le support utilise :
  - S3 : reçoit la rotation gauche/droite du cou (axe entrant par le bas)
  - S4 : monté latéralement, son horn se connecte à la cage tête (inclinaison)
  - Côté opposé à S4 : palier de support (pas de servo, juste un axe libre)
```

**Dimensions :**
```
Corps central : 80 mm × 80 mm × 50 mm
Bras latéraux (pour S4 + palier) : 2 × (30 mm de long × 25 mm de large × 40 mm de haut)
Largeur totale avec bras : 140 mm
```

**Bas du support — connecteur horn S3 :**
```
Identique aux autres (plateau Ø55 mm vissé sur horn)
```

**Côté droit — logement S4 :**
```
S4 monté VERTICALEMENT dans le bras droit
Cavité : 44 mm × 22 mm × 43 mm
Axe de S4 pointe vers l'intérieur (vers la tête)
Trous vis : 4 × M3, entraxe 49 mm × 10 mm
```

**Côté gauche — palier libre :**
```
Trou traversant Ø8 mm (axe de rotation libre)
+ vis M4 × 30 mm comme axe + rondelles téflon comme palier
```

**Matériau :** PETG haute densité
**Infill :** 40%, gyroïde (pièce critique — supporte le poids de la tête)

---

## PIÈCE 5 — CAGE INTERNE TÊTE

**Fonction :** Structure rigide à l'intérieur de la tête Ultron — relie S4 et le palier à la tête

**Design :**
```
Anneau supérieur : Ø[à mesurer sur la tête Ultron] mm
  → Colle ou clips dans la partie intérieure du crâne

2 bras latéraux (gauche + droit) descendant vers :
  - Droit : adaptateur horn S4 (Ø55 mm, vis sur Ø42 mm)
  - Gauche : trou Ø8 mm (palier sur le bras gauche du support)
```

**⚠️ Avant de modéliser cette pièce :**
1. Dans Fusion 360, mesurer le diamètre intérieur de la tête Ultron
2. Mesurer la hauteur disponible à l'intérieur
3. Reporter ces mesures ici

**Matériau :** PETG
**Infill :** 40%

---

## Tolérances d'impression (Bambu Lab A1)

| Type d'ajustement | Jeu recommandé |
|-------------------|----------------|
| Pièces emboîtées (glissantes) | +0.3 mm sur le diamètre |
| Trous de vis M3 | Ø3.2 mm |
| Trous de vis M4 | Ø4.2 mm |
| Horn servo (plateau Ø55) | Ø55.5 mm en creux |
| Axe palier libre M4 | Ø4.3 mm |

---

## Ordre d'assemblage mécanique

```
1. Visser S1 dans la BASE (cavité dessus)
2. Monter le BUSTE sur le horn de S1
3. Visser S2 dans le BUSTE (cavité haut)
4. Monter le COU sur le horn de S2
5. Visser S3 dans le COU (horizontal, haut)
6. Monter le SUPPORT TÊTE sur le horn de S3
7. Visser S4 dans le bras droit du SUPPORT
8. Insérer l'axe palier M4 dans le bras gauche
9. Clipser/coller la CAGE dans la tête Ultron
10. Connecter la cage → horn S4 (côté droit) + axe palier (côté gauche)
```

---

## Par où commencer dans Fusion 360

### Étape 1 — MESURE LA TÊTE ULTRON
Dans Fusion 360 (onglet MAILLAGE) :
1. Outils → **Inspecter** → **Mesurer**
2. Mesure le diamètre intérieur du crâne
3. Note la hauteur intérieure disponible

### Étape 2 — MODÉLISE LA BASE
1. Onglet **SOLIDE** (pas Maillage)
2. Nouveau composant → "Base_Neo"
3. Crée une boîte 180×130×90 mm (outil **Boîte**)
4. Soustrait les cavités (LCD, clavier, servo S1) avec **Extrusion coupe**
5. Ajoute les trous de vis M3

### Étape 3 — BUSTE, puis COU, puis SUPPORT
Chaque pièce = un nouveau composant dans le même fichier Fusion
→ Tu pourras vérifier l'assemblage en temps réel

---

## Questions/mesures encore manquantes

- [ ] Diamètre intérieur tête Ultron (à mesurer dans Fusion)
- [ ] Hauteur intérieure tête Ultron (à mesurer dans Fusion)
- [ ] Hauteur totale souhaitée du robot (base à tête) : __ mm
- [ ] Câbles des servos : longueur disponible ? (impacte les gouttières)
