"""
Pièce 4 — SUPPORT TÊTE
Corps central 90×90×50 mm + bras droit (S4) + bras gauche (palier)
Largeur totale avec bras : 160 mm
"""
import cadquery as cq
import math

# ── Corps central ────────────────────────────────────────────────────────
corps = cq.Workplane("XY").box(90, 90, 50, centered=(True, True, False))

# Évider le centre (allège + passage câbles)
corps = corps.cut(
    cq.Workplane("XY").workplane(offset=3)
    .box(84, 84, 44, centered=(True, True, False))
)

# ── Bras droit (+X) — logement S4 (44×22×45 mm) ─────────────────────────
bras_d = (
    cq.Workplane("XY")
    .center(90/2 + 35/2, 0)
    .box(35, 30, 45, centered=(True, True, False))
)
corps = corps.union(bras_d)

# Cavité S4 dans le bras droit (ouverture vers l'intérieur, -X)
cavity_s4 = (
    cq.Workplane("XY")
    .center(90/2 + 35/2, 0)
    .workplane(offset=0)
    .box(44, 22, 45, centered=(True, True, False))
)
corps = corps.cut(cavity_s4)

# 4 × trous M3 fixation S4 (faces +Y/-Y du bras droit)
for dy_side in [15, -15]:
    for dz in [5, 40]:
        hole = (
            cq.Workplane("XZ")
            .workplane(offset=dy_side)
            .center(90/2 + 35/2, dz)
            .circle(1.6).extrude(10)
        )
        corps = corps.cut(hole)

# ── Bras gauche (-X) — palier libre axe M4 ─────────────────────────────
bras_g = (
    cq.Workplane("XY")
    .center(-90/2 - 35/2, 0)
    .box(35, 30, 45, centered=(True, True, False))
)
corps = corps.union(bras_g)

# Trou traversant Ø4.3 mm (axe M4 palier), horizontal sur Y
palier_hole = (
    cq.Workplane("XZ")
    .workplane(offset=15)
    .center(-90/2 - 35/2, 22)   # à mi-hauteur du bras
    .circle(2.15).extrude(30)
)
corps = corps.cut(palier_hole)

# ── Bas — plateau horn S3 : Ø58 mm, épaisseur 5 mm ──────────────────────
horn = cq.Workplane("XY").circle(29).extrude(5)
for angle in [0, 90, 180, 270]:
    x = 21 * math.cos(math.radians(angle))
    y = 21 * math.sin(math.radians(angle))
    horn = horn.cut(cq.Workplane("XY").center(x, y).circle(1.6).extrude(5))
horn = horn.cut(cq.Workplane("XY").circle(3.25).extrude(5))
corps = corps.union(horn)

# ── Rainure câble S4 vers centre (8×6 mm) ───────────────────────────────
rainure = (
    cq.Workplane("XY")
    .workplane(offset=20)
    .center(90/2 - 5, 0)
    .box(50, 6, 8, centered=(True, True, False))
)
corps = corps.cut(rainure)

cq.exporters.export(corps, "/home/user/Neo/stl_output/neo_support_tete.stl")
print("✅ neo_support_tete.stl généré")
