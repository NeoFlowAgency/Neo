"""
scale_ultron_head.py — Neo Robot Project
=========================================
Ce script :
  1. Extrait le zip des pièces Ultron
  2. Analyse toutes les pièces STL
  3. Scale la tête à 250mm de hauteur
  4. Sauvegarde les versions scalées dans un dossier /scaled/

Prérequis (installe une seule fois) :
    pip install numpy-stl

Usage :
    python scale_ultron_head.py
    → Réponds aux questions dans le terminal

Auteur : Claude / Neo Project
"""

import os
import sys
import zipfile
import shutil
from pathlib import Path

try:
    import numpy as np
    from stl import mesh
except ImportError:
    print("❌ Bibliothèque manquante. Installe-la avec :")
    print("   pip install numpy-stl")
    sys.exit(1)


# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

# Chemin du fichier zip Ultron (modifie si besoin)
ZIP_PATH = r"C:\Users\Noakim Grelier\Desktop\PROJETS\Neo in my home\Avengers Ulton Mask Perfectly done - 1973193.zip"

# Dossier de sortie (sera créé à côté du zip)
OUTPUT_DIR = r"C:\Users\Noakim Grelier\Desktop\PROJETS\Neo in my home\Neo_STL_Scaled"

# Hauteur cible de la tête en mm
TARGET_HEAD_HEIGHT_MM = 250.0

# Fichier STL de la tête COMPLÈTE (pour calculer le scale factor)
# Le script cherchera automatiquement un fichier contenant "full", "complet", "head" ou "mask" dans le nom
# Tu peux aussi spécifier manuellement ci-dessous (laisser None pour auto-détection)
FULL_HEAD_STL = None  # Exemple: "Ultron_Head_Full.stl"


# ─────────────────────────────────────────────
# FONCTIONS
# ─────────────────────────────────────────────

def get_stl_bounds(stl_path: str):
    """Retourne (min_xyz, max_xyz, size_xyz) en mm d'un fichier STL."""
    m = mesh.Mesh.from_file(stl_path)
    all_verts = m.vectors.reshape(-1, 3)
    mins = all_verts.min(axis=0)
    maxs = all_verts.max(axis=0)
    size = maxs - mins
    return mins, maxs, size


def scale_stl(input_path: str, output_path: str, scale_factor: float):
    """Scale un STL par un facteur uniforme et le sauvegarde."""
    m = mesh.Mesh.from_file(input_path)
    m.vectors *= scale_factor
    m.save(output_path)


def find_full_head_stl(stl_files: list[str]) -> str | None:
    """Cherche automatiquement le STL de la tête complète dans la liste."""
    keywords = ["full", "complet", "complete", "head", "mask", "tete", "crâne", "crane", "assembly", "assembled"]
    for f in stl_files:
        name_lower = Path(f).stem.lower()
        if any(kw in name_lower for kw in keywords):
            return f
    return None


def format_mm(value: float) -> str:
    return f"{value:.1f} mm"


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print()
    print("═" * 60)
    print("  NEO ROBOT — Scale Tête Ultron")
    print("═" * 60)
    print()

    # 1. Vérifier que le zip existe
    if not os.path.exists(ZIP_PATH):
        print(f"❌ Zip introuvable : {ZIP_PATH}")
        alt = input("   Entre le chemin complet du zip : ").strip().strip('"')
        if not os.path.exists(alt):
            print("❌ Fichier toujours introuvable. Abandon.")
            sys.exit(1)
        zip_path = alt
    else:
        zip_path = ZIP_PATH

    # 2. Extraire le zip dans un dossier temporaire
    tmp_dir = Path(zip_path).parent / "_neo_tmp_extract"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir()

    print(f"📦 Extraction de : {Path(zip_path).name}")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(tmp_dir)

    # 3. Trouver tous les STL (récursif)
    stl_files = sorted([str(p) for p in tmp_dir.rglob("*.stl")] +
                       [str(p) for p in tmp_dir.rglob("*.STL")])

    if not stl_files:
        print("❌ Aucun fichier STL trouvé dans le zip.")
        sys.exit(1)

    print(f"\n✅ {len(stl_files)} fichier(s) STL trouvé(s) :\n")
    for i, f in enumerate(stl_files):
        _, _, size = get_stl_bounds(f)
        print(f"  [{i+1:2d}] {Path(f).name}")
        print(f"       Dimensions actuelles : {format_mm(size[0])} × {format_mm(size[1])} × {format_mm(size[2])}")
    print()

    # 4. Identifier le STL tête complète
    if FULL_HEAD_STL:
        full_head = next((f for f in stl_files if Path(f).name == FULL_HEAD_STL), None)
    else:
        full_head = find_full_head_stl(stl_files)

    if full_head:
        print(f"🎯 Tête complète détectée automatiquement : {Path(full_head).name}")
    else:
        print("⚠️  Impossible de détecter automatiquement la tête complète.")
        print("   Parmi les fichiers ci-dessus, quel numéro est la tête complète ?")
        idx = int(input("   Numéro : ").strip()) - 1
        full_head = stl_files[idx]

    # 5. Calculer le scale factor
    _, _, head_size = get_stl_bounds(full_head)
    current_height = head_size[2]  # axe Z = hauteur
    scale_factor = TARGET_HEAD_HEIGHT_MM / current_height

    print()
    print(f"📐 Tête actuelle hauteur (Z) : {format_mm(current_height)}")
    print(f"📐 Tête cible              : {format_mm(TARGET_HEAD_HEIGHT_MM)}")
    print(f"📐 Facteur de scale        : {scale_factor:.4f}×")
    print()
    print(f"   ➜ Largeur scalée (X) : {format_mm(head_size[0] * scale_factor)}")
    print(f"   ➜ Profondeur scalée (Y) : {format_mm(head_size[1] * scale_factor)}")
    print(f"   ➜ Hauteur scalée (Z) : {format_mm(head_size[2] * scale_factor)}")
    print()

    # Vérification Bambu Lab A1 (volume max 256×256×256 mm)
    max_dim = max(head_size * scale_factor)
    if max_dim > 256:
        print(f"⚠️  ATTENTION : dimension max {format_mm(max_dim)} > 256mm (limite Bambu Lab A1)")
        print("   → Il faudra couper la pièce en 2 et la coller")
    else:
        print("✅ Toutes dimensions < 256mm — compatible Bambu Lab A1")

    print()
    confirm = input("Confirmes-tu le scale factor et le dossier de sortie ? (o/n) : ").strip().lower()
    if confirm != 'o':
        new_target = input(f"Nouvelle hauteur cible en mm [{TARGET_HEAD_HEIGHT_MM}] : ").strip()
        if new_target:
            scale_factor = float(new_target) / current_height
            print(f"Nouveau scale factor : {scale_factor:.4f}×")

    # 6. Créer le dossier de sortie
    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 7. Scaler et sauvegarder tous les STL
    print(f"\n⚙️  Scaling de {len(stl_files)} pièce(s) → {out_dir}\n")
    results = []

    for stl_path in stl_files:
        name = Path(stl_path).name
        out_path = out_dir / name
        scale_stl(stl_path, str(out_path), scale_factor)
        _, _, size_after = get_stl_bounds(str(out_path))
        results.append((name, size_after))
        print(f"  ✅ {name}")
        print(f"     → {format_mm(size_after[0])} × {format_mm(size_after[1])} × {format_mm(size_after[2])}")

    # 8. Rapport final
    print()
    print("═" * 60)
    print("  RAPPORT FINAL — Dimensions après scaling")
    print("═" * 60)
    print()
    print(f"{'Fichier':<40} {'Larg(X)':>10} {'Prof(Y)':>10} {'Haut(Z)':>10}")
    print("-" * 70)
    for name, size in results:
        print(f"{name:<40} {format_mm(size[0]):>10} {format_mm(size[1]):>10} {format_mm(size[2]):>10}")

    print()
    print(f"📁 Fichiers scalés dans : {out_dir}")
    print()

    # 9. Dimensions clés pour la cage interne (PIÈCE 5)
    head_name = Path(full_head).name
    head_result = next((r for r in results if r[0] == head_name), None)
    if head_result:
        _, hs = head_result
        print("═" * 60)
        print("  DONNÉES POUR CAGE INTERNE (PIÈCE 5) — Copie dans Fusion 360")
        print("═" * 60)
        print()
        print(f"  Largeur intérieure crâne (X) ≈ {format_mm(hs[0] - 6)}")
        print(f"  Profondeur intérieure (Y)    ≈ {format_mm(hs[1] - 6)}")
        print(f"  Hauteur intérieure (Z)       ≈ {format_mm(hs[2] * 0.7)}")
        print()
        print("  (Ces valeurs sont des estimations : -3mm par côté pour l'épaisseur de coque)")
        print("  → À affiner après mesure dans Fusion 360")
        print()

    # Nettoyage dossier temporaire
    shutil.rmtree(tmp_dir)

    print("✅ Terminé ! Lance Fusion 360 et importe les fichiers du dossier :")
    print(f"   {out_dir}")
    print()
    input("Appuie sur Entrée pour fermer...")


if __name__ == "__main__":
    main()
