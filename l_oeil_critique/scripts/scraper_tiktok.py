#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Scrape les 2 dernières vidéos TikTok d'un compte
et récupère le code <blockquote> d'intégration complet
(pas juste le lien).
"""

import os
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# --- CONFIG ---
TIKTOK_URL = "https://www.tiktok.com/@user9861171480021"
OUTPUT_FILE = "l_oeil_critique/tiktok.html"
NB_VIDEOS = 2


def get_latest_videos(page):
    """Récupère les liens des dernières vidéos depuis la page profil."""
    page.goto(TIKTOK_URL, timeout=60000)
    page.wait_for_timeout(7000)
    soup = BeautifulSoup(page.content(), "html.parser")

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/video/" in href and href.startswith("https://www.tiktok.com/"):
            if href not in links:
                links.append(href)
    return links[:NB_VIDEOS]


def get_embed_block(page, video_url):
    """Ouvre une vidéo TikTok et extrait le code <blockquote> complet."""
    page.goto(video_url, timeout=60000)
    page.wait_for_timeout(7000)
    html = page.content()

    # On cherche le bloc JSON contenant les infos vidéo
    soup = BeautifulSoup(html, "html.parser")
    description = soup.find("meta", {"name": "description"})
    desc = description["content"] if description else "Vidéo TikTok"

    # Recréation du code TikTok officiel
    video_id = video_url.split("/video/")[-1].split("?")[0]
    username = TIKTOK_URL.split("@")[-1]
    embed_code = f'''
<blockquote class="tiktok-embed" cite="{video_url}" data-video-id="{video_id}" style="max-width: 605px;min-width: 325px;">
    <section>
        <a target="_blank" title="@{username}" href="{TIKTOK_URL}?refer=embed">@{username}</a>
        {desc}
        <a target="_blank" href="{video_url}">#TikTok</a>
    </section>
</blockquote>
    '''
    return embed_code


def main():
    print("[INFO] Démarrage du scraping TikTok (version embed complet)...")
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        page = browser.new_page()

        # Étape 1 : Récupération des 2 dernières vidéos
        videos = get_latest_videos(page)
        if not videos:
            print("⚠️ Aucune vidéo trouvée, vérifie ton profil TikTok.")
            browser.close()
            return

        # Étape 2 : Génération du fichier HTML
        html = """<!-- SECTION AUTO-GÉNÉRÉE TIKTOK -->
<section class="tiktok-section">
    <h2 class="section-title">🎥 Derniers TikToks</h2>
    <div class="tiktok-container">
"""

        for v in videos:
            print(f"[INFO] Intégration de {v}")
            html += get_embed_block(page, v)

        html += """
    </div>
    <script async src="https://www.tiktok.com/embed.js"></script>
</section>
"""

        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(html)

        browser.close()
        print(f"[✅] Fichier généré avec succès : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
