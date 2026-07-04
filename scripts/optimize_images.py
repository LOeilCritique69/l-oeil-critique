#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Optimise les images du site en les convertissant vers WebP et en mettant à jour les références HTML/JSON."""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageOps

REPO_ROOT = Path(__file__).resolve().parents[2]
IMAGE_DIR = REPO_ROOT / "l_oeil_critique" / "assets" / "img"
MAX_FILE_SIZE = 300 * 1024
MAX_WIDTH = 1600
QUALITY = 80
TARGET_EXTENSIONS = {".jpg", ".jpeg", ".png"}
TEXT_FILE_EXTENSIONS = {".html", ".json"}


def iter_image_files() -> List[Path]:
    return [
        path
        for path in IMAGE_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in TARGET_EXTENSIONS
    ]


def should_process(path: Path) -> bool:
    return path.stat().st_size > MAX_FILE_SIZE


def build_reference_variants(path: Path) -> List[str]:
    relative_path = path.relative_to(REPO_ROOT).as_posix()
    relative_no_prefix = relative_path.replace("", "", 1)
    variants = {
        relative_path,
        "/" + relative_path,
        relative_no_prefix,
        "/" + relative_no_prefix,
        path.name,
    }
    return [item for item in variants if item]


def update_references_in_text(text: str, original_path: Path, webp_path: Path) -> str:
    old_variants = build_reference_variants(original_path)
    new_variants = build_reference_variants(webp_path)
    updated_text = text
    for old_variant, new_variant in zip(old_variants, new_variants):
        if old_variant and new_variant:
            updated_text = updated_text.replace(old_variant, new_variant)

    # Fallback pour les références du nom de fichier seul (ex. foo.jpg -> foo.webp)
    old_name = original_path.name
    new_name = webp_path.name
    if old_name != new_name:
        updated_text = updated_text.replace(old_name, new_name)
    return updated_text


def has_existing_webp_references(path: Path) -> bool:
    webp_name = path.with_suffix(".webp").name
    for file_path in REPO_ROOT.rglob("*"):
        if not file_path.is_file() or file_path.suffix.lower() not in TEXT_FILE_EXTENSIONS:
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            continue
        if webp_name in content:
            return True
    return False


def optimize_image(path: Path) -> Tuple[Path | None, int, int, bool]:
    before_bytes = path.stat().st_size
    output_path = path.with_suffix(".webp")

    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode in {"RGBA", "LA", "P"}:
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")

        if img.width > MAX_WIDTH:
            new_width = MAX_WIDTH
            new_height = max(1, int(img.height * (MAX_WIDTH / img.width)))
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        img.save(output_path, format="WEBP", quality=QUALITY, optimize=True)

    after_bytes = output_path.stat().st_size
    keep_original = not has_existing_webp_references(path)
    if not keep_original:
        path.unlink(missing_ok=True)
    return output_path if output_path.exists() else None, before_bytes, after_bytes, keep_original


def update_text_references(original_path: Path, webp_path: Path) -> None:
    for file_path in REPO_ROOT.rglob("*"):
        if not file_path.is_file() or file_path.suffix.lower() not in TEXT_FILE_EXTENSIONS:
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            continue

        if original_path.name not in content and original_path.relative_to(REPO_ROOT).as_posix() not in content:
            continue

        new_content = update_references_in_text(content, original_path, webp_path)
        if new_content != content:
            file_path.write_text(new_content, encoding="utf-8")


def main() -> None:
    image_files = sorted(iter_image_files())
    processed = []
    total_before = 0
    total_after = 0

    for path in image_files:
        if not should_process(path):
            continue

        output_path, before_bytes, after_bytes, keep_original = optimize_image(path)
        if output_path is None:
            continue

        update_text_references(path, output_path)
        processed.append((path, before_bytes, after_bytes, keep_original))
        total_before += before_bytes
        total_after += after_bytes

    if processed:
        gain_pct = round(((total_before - total_after) / total_before) * 100, 2) if total_before else 0.0
        print(f"✅ Optimisation terminée : {len(processed)} fichiers traités")
        print(f"   Poids avant : {total_before / (1024 * 1024):.2f} Mo")
        print(f"   Poids après : {total_after / (1024 * 1024):.2f} Mo")
        print(f"   Gain : {gain_pct}%")
    else:
        print("✅ Aucun fichier à optimiser.")


if __name__ == "__main__":
    main()
