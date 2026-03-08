#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import List
from urllib.parse import urljoin
from contextlib import contextmanager

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ------------------------------
# CONFIGURATION "GRAND RATTRAPAGE"
# ------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

LOG_FILE = SCRIPT_DIR / "bande_annonces_log.json"
OUTPUT_FILE = ROOT_DIR / "bande_annonces_blocs.html"

LIST_CINE_URL = "https://www.cinehorizons.net/bandes-annonces-prochains-films"
TMDB_API_KEY = "2cf75db44f938aeaf1e7d873a38fdcaa"
TMDB_UPCOMING_URL = "https://api.themoviedb.org/3/movie/upcoming"

# Paramètres augmentés pour le rattrapage
MAX_PAGES_CINE = 10      # Scraper les 10 premières pages de CineHorizons
MAX_PAGES_TMDB = 10      # Scraper les 10 premières pages de l'API TMDb
MAX_CARDS_FILE = 500     # Garder jusqu'à 500 bandes-annonces dans le HTML
MAX_SYNOPSIS_LEN = 500

PAGE_TIMEOUT = 20000

# ------------------------------
# LOGGING
# ------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(SCRIPT_DIR / "scraper_rattrapage.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# ------------------------------
# OUTILS
# ------------------------------

def load_log() -> List[str]:
    if not LOG_FILE.exists(): return []
    try:
        with LOG_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def save_incremental(new_article_html, new_id):
    """Sauvegarde immédiatement un article pour éviter les pertes sur crash."""
    # 1. Mise à jour du LOG
    log = load_log()
    if new_id not in log:
        log.append(new_id)
        with LOG_FILE.open("w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
    
    # 2. Mise à jour du HTML
    content = OUTPUT_FILE.read_text(encoding="utf-8") if OUTPUT_FILE.exists() else ""
    articles = re.findall(r'(<article class="card-bande"[^>]*>.*?</article>)', content, flags=re.DOTALL)
    
    # On ajoute le nouveau au début
    articles.insert(0, new_article_html)
    # On limite la taille du fichier
    articles = articles[:MAX_CARDS_FILE]
    
    OUTPUT_FILE.write_text("\n\n".join(articles), encoding="utf-8")

def clean_text(text: str) -> str:
    return ' '.join(text.strip().split()) if text else ""

def summarize_synopsis(synopsis: str) -> str:
    synopsis = clean_text(synopsis)
    if len(synopsis) <= MAX_SYNOPSIS_LEN: return synopsis
    return synopsis[:MAX_SYNOPSIS_LEN].rsplit(' ', 1)[0] + "..."

def format_date(date_str: str) -> str:
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        mois = ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"]
        return f"{date_obj.day} {mois[date_obj.month - 1]} {date_obj.year}"
    except: return date_str

def generate_article_html(titre, date_sortie, synopsis, iframe_html, is_nouveau=True):
    date_ajout = datetime.now().strftime("%d %B %Y")
    badge = '<span class="badge-nouveau">NOUVEAU</span>' if is_nouveau else ''
    return f"""
<article class="card-bande">
{badge}
<h2>{titre}</h2>
<p class="date-sortie">Sortie prévue : {date_sortie}</p>
<p class="ajout-site">Ajouté le : {date_ajout}</p>
<p class="synopsis">{synopsis}</p>
<div class="video-responsive">{iframe_html}</div>
</article>
""".strip()

# ------------------------------
# SCRAPERS
# ------------------------------

def scrape_cinehorizons():
    logger.info("Départ Grand Scraping CineHorizons...")
    log = load_log()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        for p_idx in range(MAX_PAGES_CINE):
            url = LIST_CINE_URL if p_idx == 0 else f"{LIST_CINE_URL}?page={p_idx}"
            logger.info(f"Traitement page {p_idx} : {url}")
            
            try:
                page.goto(url, timeout=PAGE_TIMEOUT)
                soup = BeautifulSoup(page.content(), "html.parser")
                blocs = soup.select(".view-content .views-row")
                
                for bloc in blocs:
                    link = bloc.select_one('h3[itemprop="name"] a[href]')
                    if not link: continue
                    
                    titre = clean_text(link.text)
                    detail_url = urljoin(LIST_CINE_URL, link["href"])
                    identifiant = f"cinehorizons::{titre}::{detail_url}"
                    
                    if identifiant in log: continue

                    # Extraction détails
                    page.goto(detail_url, timeout=PAGE_TIMEOUT)
                    detail_soup = BeautifulSoup(page.content(), "html.parser")
                    
                    date_elem = detail_soup.select_one(".movie-release span")
                    date_sortie = clean_text(date_elem.text) if date_elem else "Inconnue"
                    syn_tag = detail_soup.select_one(".block-synopsis .field-item.even p")
                    synopsis = summarize_synopsis(syn_tag.text) if syn_tag else "Pas de synopsis"
                    iframe = detail_soup.select_one(".ba .player iframe")
                    
                    if iframe and iframe.get("src"):
                        iframe_html = f'<iframe src="{iframe["src"]}" frameborder="0" allowfullscreen></iframe>'
                        html = generate_article_html(titre, date_sortie, synopsis, iframe_html)
                        save_incremental(html, identifiant)
                        logger.info(f"Sauvegardé (Cine) : {titre}")
                        time.sleep(1) # Petit délai pour la stabilité
            except Exception as e:
                logger.error(f"Erreur sur page {p_idx}: {e}")
                continue
        browser.close()

def scrape_tmdb():
    logger.info("Départ Grand Scraping TMDb...")
    log = load_log()
    
    with requests.Session() as s:
        for p_idx in range(1, MAX_PAGES_TMDB + 1):
            logger.info(f"Traitement TMDb page {p_idx}")
            try:
                r = s.get(TMDB_UPCOMING_URL, params={"api_key": TMDB_API_KEY, "language":"fr-FR", "region":"FR", "page": p_idx})
                movies = r.json().get("results", [])
                
                for movie in movies:
                    titre = movie.get("title")
                    movie_id = movie.get("id")
                    
                    # Vérif vidéo
                    rv = s.get(f"https://api.themoviedb.org/3/movie/{movie_id}/videos", params={"api_key": TMDB_API_KEY, "language":"fr-FR"})
                    videos = rv.json().get("results", [])
                    trailer = next((v for v in videos if v.get("type")=="Trailer" and v.get("site")=="YouTube"), None)
                    
                    if not trailer: continue
                    
                    identifiant = f"tmdb::{titre}::{trailer['key']}"
                    if identifiant in log: continue
                    
                    iframe_html = f'<iframe src="https://www.youtube.com/embed/{trailer["key"]}" frameborder="0" allowfullscreen></iframe>'
                    html = generate_article_html(titre, format_date(movie.get("release_date")), summarize_synopsis(movie.get("overview", "")), iframe_html)
                    
                    save_incremental(html, identifiant)
                    logger.info(f"Sauvegardé (TMDb) : {titre}")
            except Exception as e:
                logger.error(f"Erreur TMDb page {p_idx}: {e}")
                continue

# ------------------------------
# GITHUB (Un seul push à la fin)
# ------------------------------

def push_to_github():
    try:
        repo_root = SCRIPT_DIR.parent.parent
        os.chdir(repo_root)
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "Rattrapage annuel : Scraping massif réussi"], check=True)
        subprocess.run(["git", "push", "-f", "origin", "main"], check=True)
        logger.info("Toutes les données sont sur GitHub.")
    except Exception as e:
        logger.error(f"Erreur push final: {e}")

# ------------------------------
# LANCEUR
# ------------------------------

if __name__ == "__main__":
    try:
        scrape_cinehorizons()
        scrape_tmdb()
        push_to_github()
        logger.info("==== Rattrapage terminé avec succès ====")
    except Exception as e:
        logger.critical(f"Crash script: {e}")