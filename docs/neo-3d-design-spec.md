# Neo — Spécification 3D (V2)

> Guide de modélisation pour Fusion 360 — imprimante Bambu Lab A1
> Tête Ultron scalée à **250mm de hauteur**

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

## Vue d'ensemble — Hauteurs de la chaîne cinématique

```
┌──────────────────────────────────────────────────────┐
│  TÊTE ULTRON           250 mm  ←── tête scalée       │
│  CAGE INTERNE TÊTE      ~50 mm (structure interne)   │
│  SUPPORT TÊTE           50 mm  (S3 + bras S4/palier) │
│  COU                    80 mm  (creux, passage câble) │
│  BUSTE                 130 mm  (torse Ultron stylisé) │
│  BASE                  100 mm  (électronique)         │
├──────────────────────────────────────────────────────┤
│  HAUTEUR TOTALE        ~610 mm                        │
│  (sans compter les pieds de l'antenne/décoration)     │
└──────────────────────────────────────────────────────┘
```

---

## Contraintes Bambu Lab A1 (volume 256×256×256 mm)

| Pièce | Dims max estimées | Imprimable d'un coup ? |
|-------|-------------------|------------------------|
| Tête Ultron | ~180×200×250 mm | ✅ Oui |
| Base | 200×160×100 mm | ✅ Oui |
| Buste | 120×90×130 mm | ✅ Oui |
| Cou | Ø65×80 mm | ✅ Oui |
| Support tête | 160×90×50 mm | ✅ Oui |
| Cage interne | ~170×190×50 mm | ✅ Oui |

> ⚠️ Si la tête Ultron dépasse 256mm en largeur ou profondeur après scaling,
> elle devra être coupée en 2 moitiés (gauche/droite) et collée à la résine.

---

## Passage de câbles — Principe général

```
Base → Buste : gouttière centrale Ø12 mm (4× câbles servo + alim)
Buste → Cou  : gouttière centrale Ø12 mm
Cou → Support: gouttière centrale Ø10 mm
Support → Cage: 2× trous Ø6 mm sur les bras latéraux
```

Câbles concernés par pièce :
- **Base** : ESP32 USB (charge/prog), câble alim 5V/6V servos, câble écran LCD, câble clavier
- **Buste** : câble S1 (sort par bas) + câbles S2/S3/S4 (transit vers haut)
- **Cou** : câbles S3 + S4 en transit
- **Support** : câble S4 local

---

## PIÈCE 1 — BASE

**Fonction :** Boîtier principal — contient toute l'électronique — porte le Servo S1 (rotation torse)

**Dimensions extérieures :**
```
Longueur : 200 mm
Largeur  : 160 mm
Hauteur  : 100 mm
Épaisseur parois : 3 mm (PETG) ou 2.5 mm (PLA+)
```

**Façade AVANT (interface utilisateur) :**
```
Écran LCD 16×2 I2C :
  Fenêtre découpe : 74 mm × 25 mm
  Position : centré horizontalement, à 12 mm du bord supérieur

Clavier matriciel 4×4 :
  Fenêtre découpe : 72 mm × 72 mm
  Position : centré horizontalement, à 10 mm du bord inférieur
  (espace entre LCD et clavier : ~25 mm pour câblage)
```

**Façade LATÉRALE gauche :**
```
Interrupteur marche/arrêt (bouton poussoir ou toggle) : trou Ø7 mm
Potentiomètre volume/réglage : trou Ø7 mm
Passage USB-C ESP32 (charge/programmation) : découpe 10×5 mm
```

**Façade LATÉRALE droite :**
```
Passage câbles servos (gaine spirale) : passage Ø12 mm avec guide
```

**Dessus de la BASE :**
```
Logement servo S1 (MG996R À PLAT, axe vers le haut) :
  Cavité : 44 mm × 22 mm × 25 mm
  4 × trous M3, entraxe 49 mm × 10 mm
  Axe centré en largeur, décalé de 25 mm vers l'arrière
  Ouverture Ø8 mm pour l'axe S1 (vers le haut)

Passage câbles (côté arrière du servo) : gouttière 12×8 mm
```

**Intérieur BASE :**
```
ESP32 DevKit-C (55×28 mm) :
  4 × plots M2.5 hauteur 5 mm, en bas à gauche de la base
  Accès USB-C vers le trou latéral

Porte-batterie / régulateur 6V :
  Zone réservée 80×40 mm côté arrière droit

Gouttières câbles : 2 × gouttières latérales 10 mm de large
```

**Matériau :** PETG
**Infill :** 25%, gyroïde
**Couleur suggérée :** Gris foncé ou noir

---

## PIÈCE 2 — BUSTE

**Fonction :** Torse de Neo — tourne avec S1 — porte S2 (rotation cou)

**Dimensions :**
```
Largeur bas  : 120 mm (s'emboîte sur la base)
Largeur haut : 80 mm
Profondeur   : 75 mm
Hauteur      : 130 mm
Épaisseur paroi : 3 mm
```

**Bas du buste — adaptateur horn S1 :**
```
Plateau circulaire Ø58 mm, épaisseur 5 mm
  4 × trous M3 sur cercle Ø42 mm (vis horn standard)
  Trou central Ø6.5 mm (passage axe)
  Ce plateau descend DANS la base (jeu vertical +0.3 mm → rotation libre)
```

**Haut du buste — logement S2 :**
```
S2 monté À PLAT (axe vers le haut)
Cavité : 44 mm × 22 mm × 25 mm
4 × trous M3, entraxe 49 mm × 10 mm
Axe centré en largeur et profondeur
Ouverture Ø8 mm vers le haut
```

**Passage câbles :**
```
Gouttière centrale verticale Ø12 mm (câbles S2/S3/S4 en transit)
```

**Forme esthétique :**
```
Section trapézoïdale (plus large en bas)
Chanfreins 5 mm sur les arêtes verticales
Style "torse Ultron" (légers creux sur les flancs, optionnel)
```

**Matériau :** PETG
**Infill :** 30%, gyroïde

---

## PIÈCE 3 — COU

**Fonction :** Relie buste et support tête — tourne avec S2 — porte S3 (inclinaison)

**Dimensions :**
```
Diamètre extérieur : 65 mm
Diamètre intérieur : 59 mm (paroi 3 mm)
Hauteur : 80 mm
```

**Bas du cou — adaptateur horn S2 :**
```
Identique aux autres : plateau Ø58 mm, vis horn sur Ø42 mm
Jeu +0.3 mm par rapport au logement dans le buste
```

**Haut du cou — logement S3 :**
```
S3 monté HORIZONTALEMENT (axe perpendiculaire à l'axe de rotation du cou)
Cavité ouverte latéralement : 44 mm × 22 mm × 45 mm
4 × trous M3, entraxe 49 mm × 10 mm
L'axe de S3 pointe vers la gauche ou la droite (inclinaison tête)
```

**Passage câbles :**
```
Canal central Ø12 mm sur toute la hauteur (câbles S3 + S4)
```

**Matériau :** PETG
**Infill :** 35%, gyroïde (pièce sous contrainte mécanique)

---

## PIÈCE 4 — SUPPORT TÊTE

**Fonction :** Plateau en croix — reçoit horn S3 — porte S4 (inclinaison haut/bas) + palier opposé

```
⚠️ Architecture servos :
  S3 (dans le cou) : rotation GAUCHE/DROITE de la tête
  S4 (dans ce support) : inclinaison HAUT/BAS de la tête
  Côté opposé à S4 : palier libre (axe M4 + rondelles téflon)
```

**Dimensions :**
```
Corps central     : 90 mm × 90 mm × 50 mm
Bras droit (S4)   : 35 mm long × 30 mm large × 45 mm haut
Bras gauche (palier) : 35 mm long × 30 mm large × 45 mm haut
Largeur totale avec bras : 160 mm
```

> 160 mm < largeur tête (~180 mm) → ✅ La tête peut s'emboîter sans interférence

**Bas du support — horn S3 :**
```
Plateau Ø58 mm, 4 × vis M3 sur Ø42 mm
```

**Bras droit — logement S4 :**
```
S4 monté VERTICALEMENT dans le bras droit
Cavité : 44 mm × 22 mm × 45 mm
Axe de S4 pointe vers l'INTÉRIEUR (vers l'axe de la tête)
4 × trous M3, entraxe 49 mm × 10 mm
```

**Bras gauche — palier libre :**
```
Trou traversant Ø4.3 mm (vis M4 × 40 mm comme axe)
2 × rondelles téflon comme palier (épaisseur 1 mm chacune)
Écrou borgne M4 côté extérieur
```

**Passage câbles :**
```
Rainure 8×6 mm de S4 vers le centre (câble servo S4)
```

**Matériau :** PETG haute densité
**Infill :** 40%, gyroïde (pièce critique — supporte le poids de la tête)

---

## PIÈCE 5 — CAGE INTERNE TÊTE

**Fonction :** Armature rigide à l'intérieur de la tête Ultron — connecte S4 et le palier à la coque

**⚠️ Cette pièce se modélise APRÈS avoir importé la tête scalée dans Fusion 360.**
Les dimensions ci-dessous sont estimatives — à confirmer après mesure dans Fusion.

**Estimation basée sur tête Ultron 250mm de haut :**
```
Anneau supérieur (s'insère dans le crâne) :
  Diamètre extérieur : ~170 mm (à mesurer dans Fusion)
  Épaisseur anneau   : 4 mm
  Hauteur anneau     : 15 mm
  → Se fixe par collage epoxy ou 3 clips imprimés

2 bras latéraux (descendent de l'anneau vers S4 et le palier) :
  Longueur bras       : ~80 mm
  Section bras        : 20 mm × 10 mm (rectangle plein)
  Espacement bras     : 160 mm (doit correspondre à l'entraxe du SUPPORT TÊTE)

Extrémité bras droit — adaptateur horn S4 :
  Plateau Ø58 mm, 4 × M3 sur Ø42 mm, trou central Ø6.5 mm

Extrémité bras gauche — palier :
  Trou Ø4.3 mm (axe M4 libre)
```

**Passage câbles internes :**
```
2 × passages Ø6 mm sur les bras (câbles éventuels dans la tête)
```

**Étapes dans Fusion 360 :**
```
1. Importer la tête Ultron scalée (STL → Corps maillage)
2. Outils → Inspecter → Mesurer → diamètre intérieur crâne
3. Mesurer hauteur intérieure disponible
4. Modéliser la cage en SOLIDE (pas maillage) sur ces mesures
5. Vérifier le jeu de rotation (la cage tourne avec la tête)
```

**Matériau :** PETG
**Infill :** 40%

---

## Tolérances d'impression (Bambu Lab A1)

| Type d'ajustement | Jeu recommandé |
|-------------------|----------------|
| Pièces emboîtées glissantes | +0.3 mm sur le diamètre |
| Trous de vis M3 | Ø3.2 mm |
| Trous de vis M4 | Ø4.2 mm |
| Horn servo (plateau Ø58) | Ø58.3 mm en creux |
| Axe palier libre M4 | Ø4.3 mm |
| Passage câbles (gaine Ø10) | Ø10.5 mm |

---

## Ordre d'assemblage mécanique

```
1.  Visser S1 dans la BASE (cavité dessus)
2.  Faire passer tous les câbles S2/S3/S4 dans la gouttière BASE
3.  Monter le BUSTE sur le horn de S1
4.  Visser S2 dans le BUSTE (haut)
5.  Faire passer les câbles S3/S4 dans le COU
6.  Monter le COU sur le horn de S2
7.  Visser S3 dans le COU (horizontal)
8.  Faire passer le câble S4 dans le SUPPORT
9.  Monter le SUPPORT TÊTE sur le horn de S3
10. Visser S4 dans le bras droit du SUPPORT
11. Insérer l'axe palier M4 + rondelles dans le bras gauche
12. Coller/clipser la CAGE INTERNE dans la tête Ultron
13. Connecter cage → horn S4 (droite) + axe palier (gauche)
14. ✅ Tester les rotations à la main avant de brancher les servos
```

---

## Checklist avant modélisation Fusion 360

- [ ] Lancer `scale_ultron_head.py` sur ton PC Windows
- [ ] Noter la largeur (X) et profondeur (Y) de la tête après scaling
- [ ] Importer le STL tête scalée dans Fusion 360
- [ ] Mesurer le diamètre intérieur du crâne (outil Inspecter → Mesurer)
- [ ] Mesurer la hauteur intérieure disponible
- [ ] Reporter ces 2 mesures dans la section PIÈCE 5 ci-dessus
- [ ] Hauteur totale robot souhaitée : __ mm (optionnel, pour ajuster le COU)
- [ ] Longueur câbles servos disponibles : __ mm (impacte gouttières)

---

## Résumé des matériaux et quantités

| Pièce | Matériau | Infill | Couleur |
|-------|----------|--------|---------|
| BASE | PETG | 25% gyroïde | Noir/gris |
| BUSTE | PETG | 30% gyroïde | Argent (Ultron) |
| COU | PETG | 35% gyroïde | Argent |
| SUPPORT TÊTE | PETG | 40% gyroïde | Noir (caché) |
| CAGE INTERNE | PETG | 40% gyroïde | Noir (caché) |
| TÊTE ULTRON | PLA+ | 20% gyroïde | Argent / Or |
