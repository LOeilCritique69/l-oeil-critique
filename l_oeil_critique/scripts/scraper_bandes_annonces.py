#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script d’automatisation pour récupérer les bandes-annonces depuis CineHorizons et TMDb,
les fusionner dans un bloc HTML standardisé, puis pousser automatiquement sur GitHub.

Auteur : Yanis (L’Œil Critique)
Version : 2.0 — Optimisée pour stabilité, performance et maintenance.
"""

import os
import re
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError

# ------------------------------
# CONFIGURATION GLOBALE
# ------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
LOG_FILE = SCRIPT_DIR / "bande_annonces_log.json"
OUTPUT_FILE = ROOT_DIR / "bande_annonces_blocs.html"

LIST_CINE_URL = "https://www.cinehorizons.net/bandes-annonces-prochains-films"
TMDB_API_KEY = "2cf75db44f938aeaf1e7d873a38fdcaa"
TMDB_UPCOMING_URL = "https://api.themoviedb.org/3/movie/upcoming"

MAX_BANDES_CINE = 3
MAX_BANDES_TMDB = 3
MAX_SYNOPSIS_LEN = 500

# ------------------------------
# LOGGING
# ------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ------------------------------
# OUTILS GÉNÉRIQUES
# ------------------------------
def clean_text(text: str) -> str:
    """Nettoie et normalise un texte."""
    return ' '.join(text.strip().split())

def summarize_synopsis(synopsis: str) -> str:
    """Raccourcit le synopsis s’il dépasse la limite."""
    return synopsis if len(synopsis) <= MAX_SYNOPSIS_LEN else synopsis[:MAX_SYNOPSIS_LEN].rstrip() + "..."

def load_log() -> List[str]:
    """Charge la liste des identifiants déjà ajoutés."""
    if LOG_FILE.exists():
        try:
            with LOG_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning("⚠️ Fichier log corrompu, réinitialisation.")
            return []
    return []

def save_log(log: List[str]) -> None:
    """Sauvegarde la liste mise à jour des identifiants."""
    with LOG_FILE.open("w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

# ------------------------------
# SCRAPER CINEHORIZONS
# ------------------------------
def scrape_cinehorizons(log: List[str]) -> Tuple[List[str], List[str]]:
    """Scrape CineHorizons pour obtenir les nouvelles bandes-annonces."""
    articles, ids = [], []
    date_ajout = datetime.now().strftime("%d %B %Y")

    logger.info("🎬 [CineHorizons] Démarrage du scraping...")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(LIST_CINE_URL, timeout=15000)
            page.wait_for_selector(".view-content .views-row", timeout=10000)

            soup = BeautifulSoup(page.content(), "html.parser")
            blocs = soup.select(".view-content .views-row")[:MAX_BANDES_CINE]

            for bloc in blocs:
                link = bloc.select_one('h3[itemprop="name"] a[href]')
                if not link:
                    continue

                titre = clean_text(link.text)
                detail_url = urljoin(LIST_CINE_URL, link["href"])
                identifiant = f"cinehorizons::{titre}::{detail_url}"

                if identifiant in log:
                    continue

                try:
                    page.goto(detail_url, timeout=10000)
                    page.wait_for_selector(".block-synopsis", timeout=8000)
                except TimeoutError:
                    logger.warning(f"⏱ Timeout pour {titre}")
                    continue

                detail = BeautifulSoup(page.content(), "html.parser")
                date_sortie = clean_text(detail.select_one(".movie-release span").text) if detail.select_one(".movie-release span") else "Date inconnue"
                syn_tag = detail.select_one(".block-synopsis .field-item.even p")
                synopsis = summarize_synopsis(clean_text(syn_tag.text)) if syn_tag else "Pas de synopsis"

                iframe = detail.select_one(".ba .player iframe")
                iframe_html = f'<iframe width="560" height="315" src="{iframe["src"] if iframe else ""}" frameborder="0" allowfullscreen></iframe>' if iframe else "<!-- Pas d'iframe -->"

                article_html = f"""
                <article class="card-bande">
                    <span class="badge-nouveau">NOUVEAU</span>
                    <h2>{titre}</h2>
                    <p class="date-sortie">Sortie prévue : {date_sortie}</p>
                    <p class="ajout-site">Ajouté le : {date_ajout}</p>
                    <p class="synopsis">{synopsis}</p>
                    <div class="video-responsive">{iframe_html}</div>
                </article>
                """.strip()

                articles.append(article_html)
                ids.append(identifiant)

            browser.close()

    except Exception as e:
        logger.error(f"❌ Erreur CineHorizons : {e}")

    logger.info(f"✅ [CineHorizons] {len(articles)} nouvelles bandes-annonces trouvées.")
    return articles, ids

# ------------------------------
# SCRAPER TMDB
# ------------------------------
def scrape_tmdb(log: List[str]) -> Tuple[List[str], List[str]]:
    """Scrape TMDb pour les prochains films avec trailers."""
    logger.info("🎞 [TMDb] Démarrage du scraping...")
    articles, ids = [], []
    date_ajout = datetime.now().strftime("%d %B %Y")

    try:
        session = requests.Session()
        r = session.get(TMDB_UPCOMING_URL, params={"api_key": TMDB_API_KEY, "language": "fr-FR", "region": "FR"})
        r.raise_for_status()
        movies = r.json().get("results", [])[:MAX_BANDES_TMDB]
    except Exception as e:
        logger.error(f"❌ Erreur requête TMDb : {e}")
        return articles, ids

    for movie in movies:
        titre = movie.get("title", "Titre inconnu")
        date_sortie = movie.get("release_date", "Date inconnue")
        try:
            date_sortie = datetime.strptime(date_sortie, "%Y-%m-%d").strftime("%d %B %Y")
        except Exception:
            pass

        movie_id = movie.get("id")
        if not movie_id:
            continue

        rv = session.get(f"https://api.themoviedb.org/3/movie/{movie_id}/videos",
                         params={"api_key": TMDB_API_KEY, "language": "fr-FR"})
        videos = rv.json().get("results", [])
        trailer = next((v for v in videos if v.get("type") == "Trailer" and v.get("site") == "YouTube"), None)

        if not trailer:
            continue

        video_id = trailer.get("key")
        identifiant = f"tmdb::{titre}::{video_id}"
        if identifiant in log:
            continue

        iframe_html = f'<iframe width="560" height="315" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>'
        synopsis = summarize_synopsis(movie.get("overview", "Pas de synopsis"))

        article_html = f"""
        <article class="card-bande">
            <span class="badge-nouveau">NOUVEAU</span>
            <h2>{titre}</h2>
            <p class="date-sortie">Sortie prévue : {date_sortie}</p>
            <p class="ajout-site">Ajouté le : {date_ajout}</p>
            <p class="synopsis">{synopsis}</p>
            <div class="video-responsive">{iframe_html}</div>
        </article>
        """.strip()

        articles.append(article_html)
        ids.append(identifiant)

    logger.info(f"✅ [TMDb] {len(articles)} nouvelles bandes-annonces ajoutées.")
    return articles, ids

# ------------------------------
# PUSH GITHUB
# ------------------------------
def push_to_github() -> None:
    """Pousse automatiquement les mises à jour sur le dépôt GitHub."""
    try:
        repo_root = SCRIPT_DIR.parent.parent
        os.chdir(repo_root)

        subprocess.run(["git", "config", "user.name", "LOeilCritique69"], check=True)
        subprocess.run(["git", "config", "user.email", "yanisfoa69@gmail.com"], check=True)
        subprocess.run(["git", "add", "."], check=True)

        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if status.stdout.strip():
            subprocess.run(["git", "commit", "-m", "MAJ automatique des bandes-annonces"], check=True)
            subprocess.run(["git", "push", "-f", "origin", "main"], check=True)
            logger.info("✅ Push GitHub réussi.")
        else:
            logger.info("ℹ️ Aucun changement détecté, push annulé.")
    except Exception as e:
        logger.error(f"❌ Erreur GitHub : {e}")

# ------------------------------
# MAIN
# ------------------------------
def main():
    logger.info("🚀 Lancement du script de mise à jour des bandes-annonces...")
    log = load_log()

    cine_articles, cine_ids = scrape_cinehorizons(log)
    tmdb_articles, tmdb_ids = scrape_tmdb(log)

    nouveaux_articles = cine_articles + tmdb_articles
    nouveaux_ids = cine_ids + tmdb_ids

    if not nouveaux_articles:
        logger.info("Aucune nouvelle bande-annonce détectée.")
        return

    ancien_contenu = OUTPUT_FILE.read_text(encoding="utf-8") if OUTPUT_FILE.exists() else ""
    anciens_articles = re.findall(r'(<article class="card-bande"[^>]*>.*?</article>)', ancien_contenu, flags=re.DOTALL)

    all_articles = nouveaux_articles + anciens_articles

    OUTPUT_FILE.write_text("\n\n".join(all_articles), encoding="utf-8")
    save_log(log + nouveaux_ids)

    logger.info(f"✅ {len(nouveaux_articles)} nouvelles bandes-annonces ajoutées.")
    push_to_github()

if __name__ == "__main__":
    main()
