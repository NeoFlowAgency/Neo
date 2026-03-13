"""
Pièce 3 — COU (cylindre creux Ø65/Ø59, hauteur 80 mm)
"""
import cadquery as cq
import math

H = 80
R_EXT = 32.5
R_INT = 29.5  # paroi 3 mm

# Corps cylindrique creux
cou = (
    cq.Workplane("XY")
    .circle(R_EXT).extrude(H)
)
# Alésage central
alésage = cq.Workplane("XY").circle(R_INT).extrude(H)
cou = cou.cut(alésage)

# ── Bas — plateau horn S2 : Ø58 mm, épaisseur 5 mm ─────────────────────
horn = cq.Workplane("XY").circle(29).extrude(5)
# 4 × vis M3 sur Ø42 mm
for angle in [0, 90, 180, 270]:
    x = 21 * math.cos(math.radians(angle))
    y = 21 * math.sin(math.radians(angle))
    pillar = cq.Workplane("XY").center(x, y).circle(1.6).extrude(5)
    horn = horn.cut(pillar)
# trou central Ø6.5
center_hole = cq.Workplane("XY").circle(3.25).extrude(5)
horn = horn.cut(center_hole)

cou = cou.union(horn)

# ── Haut — cavité servo S3 (44×22×45 mm) ouverte côté +X ───────────────
# La cavité est un box décalé vers +X depuis le centre, dans la partie haute
cavity_s3 = (
    cq.Workplane("XY")
    .workplane(offset=H - 45)
    .center(R_EXT, 0)               # décalé vers +X (ouvert sur le côté)
    .box(45, 22, 45, centered=(True, True, False))
)
cou = cou.cut(cavity_s3)

# 4 × trous M3 sur la face +X (fixation S3)
for dz in [H - 45 + 5, H - 45 + 40]:
    for dy in [-4.9, 4.9]:
        hole = (
            cq.Workplane("YZ")
            .workplane(offset=R_EXT + 5)
            .center(dy, dz)
            .circle(1.6).extrude(20)
        )
        cou = cou.cut(hole)

# ── Canal câbles central Ø12 mm ─────────────────────────────────────────
cable_canal = cq.Workplane("XY").circle(6).extrude(H)
cou = cou.cut(cable_canal)

cq.exporters.export(cou, "/home/user/Neo/stl_output/neo_cou.stl")
print("✅ neo_cou.stl généré")
