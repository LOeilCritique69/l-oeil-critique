#!/usr/bin/env python3
"""
Corrige les fichiers HTML de L'Œil Critique contenant des <iframe> de bandes-annonces.

Deux corrections :
1. Nettoie les URLs YouTube doublement encodées (?width%3D...%26amp%3B...)
   -> les remplace par une URL propre https://www.youtube.com/embed/{ID}
2. Repère tous les <iframe src="https://player.allocine.fr/XXXXXXXX.html">
   et les liste séparément, car ces embeds ne peuvent pas être "réparés"
   automatiquement (ce sont des tokens Allociné, pas des vidéos YouTube).

Usage :
    python3 fix_bandes_annonces.py mon_fichier.html
Produit :
    mon_fichier.fixed.html   -> fichier corrigé
    allocine_a_remplacer.csv -> liste des titres/liens Allociné à traiter à la main
"""

import re
import sys
import csv
from pathlib import Path

YT_ID_RE = re.compile(
    r'src=["\'](?:https?:)?//(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{6,})[^"\']*["\']'
)
ALLOCINE_RE = re.compile(
    r'<h2>(.*?)</h2>.*?src=["\'](https?://player\.allocine\.fr/[0-9]+\.html)["\']',
    re.DOTALL
)

def clean_youtube_embeds(html: str) -> str:
    def repl(match):
        video_id = match.group(1)
        return f'src="https://www.youtube.com/embed/{video_id}"'
    return YT_ID_RE.sub(repl, html)

def extract_allocine_links(html: str):
    return [(title.strip(), link) for title, link in ALLOCINE_RE.findall(html)]

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 fix_bandes_annonces.py mon_fichier.html")
        sys.exit(1)

    src_path = Path(sys.argv[1])
    html = src_path.read_text(encoding="utf-8")

    fixed_html = clean_youtube_embeds(html)
    out_path = src_path.with_suffix(".fixed.html")
    out_path.write_text(fixed_html, encoding="utf-8")

    allocine_links = extract_allocine_links(html)
    csv_path = src_path.parent / "allocine_a_remplacer.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["titre", "lien_allocine_casse"])
        writer.writerows(allocine_links)

    n_yt_fixed = len(YT_ID_RE.findall(html))
    print(f"✅ {n_yt_fixed} embeds YouTube nettoyés -> {out_path}")
    print(f"⚠️  {len(allocine_links)} embeds Allociné repérés (non réparables auto) -> {csv_path}")

if __name__ == "__main__":
    main()