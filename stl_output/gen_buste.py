"""
Pièce 2 — BUSTE (section trapézoïdale 120→80 mm, profondeur 75 mm, hauteur 130 mm)
"""
import cadquery as cq

H = 130
T = 3.0

# Corps trapézoïdal : on loft bas (120×75) → haut (80×60)
pts_bas = [(-60, -37.5), (60, -37.5), (60, 37.5), (-60, 37.5)]
pts_haut = [(-40, -30), (40, -30), (40, 30), (-40, 30)]

profile_bas  = cq.Workplane("XY").polyline(pts_bas).close()
profile_haut = cq.Workplane("XY").workplane(offset=H).polyline(pts_haut).close()

buste = cq.Workplane("XY").add(profile_bas).workplane(offset=H).add(profile_haut)
buste = cq.Workplane("XY").shell  # reset

# Loft manuel via deux sketches
bas  = cq.Workplane("XY").polyline(pts_bas + [pts_bas[0]]).close()
haut = cq.Workplane("XY").workplane(offset=H).polyline(pts_haut + [pts_haut[0]]).close()

buste = (
    cq.Workplane("XY")
    .polyline([(-60,-37.5),(60,-37.5),(60,37.5),(-60,37.5),(-60,-37.5)])
    .close()
    .workplane(offset=H)
    .polyline([(-40,-30),(40,-30),(40,30),(-40,30),(-40,-30)])
    .close()
    .loft()
)

# Évider (shell négatif T=3)
buste = buste.shell(-T)

# ── Bas — plateau horn S1 : Ø58 mm, épaisseur 5 mm ─────────────────────
horn_bas = (
    cq.Workplane("XY")
    .circle(29).extrude(5)
)
# 4 × vis M3 sur Ø42 mm
for angle in [0, 90, 180, 270]:
    import math
    x = 21 * math.cos(math.radians(angle))
    y = 21 * math.sin(math.radians(angle))
    horn_bas = horn_bas.faces(">Z").workplane().center(x, y).circle(1.6).cutThruAll()
# trou central Ø6.5
horn_bas = horn_bas.faces(">Z").workplane().circle(3.25).cutThruAll()

buste = buste.union(horn_bas)

# ── Haut — logement servo S2 (à plat, axe vers le haut), centré ─────────
buste = (
    buste.faces(">Z")
    .workplane()
    .center(0, 0)
    .rect(44, 22)
    .cutBlind(-25)
)
for dx, dy in [(-24.5,-5),(24.5,-5),(-24.5,5),(24.5,5)]:
    buste = (
        buste.faces(">Z").workplane()
        .center(dx, dy).circle(1.6).cutThruAll()
    )
buste = buste.faces(">Z").workplane().circle(4).cutThruAll()

# ── Gouttière câbles centrale Ø12 mm sur toute la hauteur ───────────────
buste = (
    buste.faces(">Z").workplane()
    .center(0, 20).circle(6).cutThruAll()
)

cq.exporters.export(buste, "/home/user/Neo/stl_output/neo_buste.stl")
print("✅ neo_buste.stl généré")
