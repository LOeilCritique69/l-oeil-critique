#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script d'automatisation pour récupérer les bandes-annonces depuis CineHorizons et TMDb,
les fusionner dans un bloc HTML standardisé, puis pousser automatiquement sur GitHub.
Logs détaillés ajoutés pour suivi complet.
"""

import os
import re
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List
from urllib.parse import urljoin
from contextlib import contextmanager

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

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
MAX_CARDS_FILE = 40

REQUEST_TIMEOUT = 10
PAGE_TIMEOUT = 15000

# ------------------------------
# LOGGING
# ------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(SCRIPT_DIR / "scraper.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# ------------------------------
# OUTILS GÉNÉRIQUES
# ------------------------------

def clean_text(text: str) -> str:
    logger.debug("Nettoyage du texte...")
    if not text:
        return ""
    return ' '.join(text.strip().split())

def summarize_synopsis(synopsis: str, max_len: int = MAX_SYNOPSIS_LEN) -> str:
    logger.debug("Résumé du synopsis...")
    synopsis = clean_text(synopsis)
    if len(synopsis) <= max_len:
        return synopsis
    return synopsis[:max_len].rsplit(' ', 1)[0] + "..."

def load_log() -> List[str]:
    logger.info(f"Chargement du log depuis {LOG_FILE}")
    if not LOG_FILE.exists():
        logger.info("Log inexistant, création d'une nouvelle liste")
        return []
    try:
        with LOG_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            logger.info(f"{len(data)} identifiants chargés depuis le log")
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"Erreur lecture log : {e}")
        return []

def save_log(log: List[str]):
    logger.info(f"Sauvegarde du log avec {len(log)} identifiants")
    with LOG_FILE.open("w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def format_date(date_str: str, input_format: str = "%Y-%m-%d") -> str:
    try:
        date_obj = datetime.strptime(date_str, input_format)
        mois_fr = [
            "janvier","février","mars","avril","mai","juin",
            "juillet","août","septembre","octobre","novembre","décembre"
        ]
        return f"{date_obj.day} {mois_fr[date_obj.month - 1]} {date_obj.year}"
    except:
        logger.warning(f"Impossible de formater la date: {date_str}")
        return date_str

@contextmanager
def get_requests_session():
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    try:
        yield session
    finally:
        session.close()
        logger.debug("Session requests fermée")

# ------------------------------
# GÉNÉRATION HTML
# ------------------------------

def generate_article_html(titre, date_sortie, synopsis, iframe_html, date_ajout=None, is_nouveau=False):
    if date_ajout is None:
        date_ajout = datetime.now().strftime("%d %B %Y")
    badge = '<span class="badge-nouveau">NOUVEAU</span>' if is_nouveau else ''
    logger.debug(f"Génération HTML pour {titre}, badge={is_nouveau}")
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
# SCRAPER CINEHORIZONS
# ------------------------------

def extract_cinehorizons_detail(page, detail_url, titre):
    logger.info(f"Extraction détails CineHorizons pour {titre}")
    try:
        page.goto(detail_url, timeout=PAGE_TIMEOUT)
        page.wait_for_selector(".block-synopsis", timeout=8000)
    except Exception as e:
        logger.warning(f"Erreur chargement page {titre}: {e}")
        return None

    detail = BeautifulSoup(page.content(), "html.parser")
    date_elem = detail.select_one(".movie-release span")
    date_sortie = clean_text(date_elem.text) if date_elem else "Date inconnue"
    syn_tag = detail.select_one(".block-synopsis .field-item.even p")
    synopsis = summarize_synopsis(syn_tag.text) if syn_tag else "Pas de synopsis"
    iframe = detail.select_one(".ba .player iframe")
    iframe_html = f'<iframe width="560" height="315" src="{iframe["src"]}" frameborder="0" allowfullscreen></iframe>' if iframe and iframe.get("src") else ""
    return {"date_sortie": date_sortie, "synopsis": synopsis, "iframe_html": iframe_html}

def scrape_cinehorizons(log):
    logger.info("Démarrage scraping CineHorizons...")
    articles, ids = [], []
    date_ajout = datetime.now().strftime("%d %B %Y")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(LIST_CINE_URL)
        logger.info(f"Page CineHorizons chargée: {LIST_CINE_URL}")
        soup = BeautifulSoup(page.content(), "html.parser")
        blocs = soup.select(".view-content .views-row")[:MAX_BANDES_CINE]
        logger.info(f"{len(blocs)} blocs détectés (limite {MAX_BANDES_CINE})")

        for bloc in blocs:
            link = bloc.select_one('h3[itemprop="name"] a[href]')
            if not link: 
                logger.debug("Bloc sans lien trouvé, ignoré")
                continue
            titre = clean_text(link.text)
            detail_url = urljoin(LIST_CINE_URL, link["href"])
            identifiant = f"cinehorizons::{titre}::{detail_url}"
            if identifiant in log:
                logger.debug(f"{titre} déjà présent dans le log, ignoré")
                continue
            details = extract_cinehorizons_detail(page, detail_url, titre)
            if not details:
                logger.debug(f"Détails non récupérés pour {titre}, ignoré")
                continue
            article_html = generate_article_html(titre, details["date_sortie"], details["synopsis"], details["iframe_html"], date_ajout, True)
            articles.append(article_html)
            ids.append(identifiant)
            logger.info(f"Article ajouté CineHorizons: {titre}")
        browser.close()
        logger.info("Scraping CineHorizons terminé")
    return articles, ids

# ------------------------------
# SCRAPER TMDB
# ------------------------------

def fetch_tmdb_trailer(session, movie_id):
    logger.debug(f"Récupération trailer TMDb film ID={movie_id}")
    try:
        r = session.get(f"https://api.themoviedb.org/3/movie/{movie_id}/videos", params={"api_key": TMDB_API_KEY,"language":"fr-FR"})
        videos = r.json().get("results", [])
        trailer = next((v for v in videos if v.get("type")=="Trailer" and v.get("site")=="YouTube"), None)
        return trailer.get("key") if trailer else None
    except Exception as e:
        logger.warning(f"Erreur récupération trailer TMDb: {e}")
        return None

def scrape_tmdb(log):
    logger.info("Démarrage scraping TMDb...")
    articles, ids = [], []
    date_ajout = datetime.now().strftime("%d %B %Y")
    with get_requests_session() as session:
        r = session.get(TMDB_UPCOMING_URL, params={"api_key": TMDB_API_KEY, "language":"fr-FR","region":"FR"})
        movies = r.json().get("results", [])
        logger.info(f"{len(movies)} films récupérés depuis TMDb")
        for movie in movies[:MAX_BANDES_TMDB*2]:
            if len(articles)>=MAX_BANDES_TMDB: break
            titre = movie.get("title")
            movie_id = movie.get("id")
            video_id = fetch_tmdb_trailer(session, movie_id)
            if not video_id:
                logger.debug(f"{titre} sans trailer, ignoré")
                continue
            identifiant = f"tmdb::{titre}::{video_id}"
            if identifiant in log:
                logger.debug(f"{titre} déjà dans le log, ignoré")
                continue
            iframe_html = f'<iframe width="560" height="315" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>'
            synopsis = summarize_synopsis(movie.get("overview",""))
            article_html = generate_article_html(titre, format_date(movie.get("release_date")), synopsis, iframe_html, date_ajout, True)
            articles.append(article_html)
            ids.append(identifiant)
            logger.info(f"Article ajouté TMDb: {titre}")
    logger.info("Scraping TMDb terminé")
    return articles, ids

# ------------------------------
# HTML UTILS
# ------------------------------

def remove_badge_from_article(article_html):
    logger.debug("Suppression badge NOUVEAU si présent")
    return re.sub(r'\s*<span class="badge-nouveau">NOUVEAU</span>\s*', '\n', article_html)

def extract_articles_from_html(html_content):
    articles = re.findall(r'(<article class="card-bande"[^>]*>.*?</article>)', html_content, flags=re.DOTALL)
    logger.debug(f"{len(articles)} articles extraits du HTML")
    return articles

# ------------------------------
# GITHUB
# ------------------------------

def push_to_github():
    logger.info("Poussée automatique FORCÉE vers GitHub...")
    try:
        repo_root = SCRIPT_DIR.parent.parent
        os.chdir(repo_root)
        
        # Prépare les fichiers
        subprocess.run(["git", "add", "."], check=True)
        
        # Commit (on ignore l'erreur si rien n'a changé avec un try/except local ou en vérifiant le status)
        try:
            subprocess.run(["git", "commit", "-m", "MAJ automatique bandes annonces"], check=True)
        except subprocess.CalledProcessError:
            logger.info("Rien à commiter, le répertoire est propre.")
            return True

        # LE PUSH FORCÉ : On ajoute "-f"
        subprocess.run(["git", "push", "-f", "origin", "main"], check=True)
        
        logger.info("Push GitHub FORCE réussi")
        return True
    except Exception as e:
        logger.error(f"Erreur push GitHub: {e}")
        return False

# ------------------------------
# MAIN
# ------------------------------

def main():
    logger.info("==== Début du script bandes-annonces ====")
    log = load_log()
    cine_articles, cine_ids = scrape_cinehorizons(log)
    tmdb_articles, tmdb_ids = scrape_tmdb(log)

    nouveaux_articles = cine_articles + tmdb_articles
    nouveaux_ids = cine_ids + tmdb_ids
    logger.info(f"{len(nouveaux_articles)} nouveaux articles détectés")

    if not nouveaux_articles:
        logger.info("Aucun nouvel article à ajouter")
        return

    ancien_contenu = OUTPUT_FILE.read_text(encoding="utf-8") if OUTPUT_FILE.exists() else ""
    anciens_articles = extract_articles_from_html(ancien_contenu)
    anciens_articles = [remove_badge_from_article(a) for a in anciens_articles]

    all_articles = nouveaux_articles + anciens_articles
    articles_finaux = []

    for i, article in enumerate(all_articles):
        if i>=6: 
            article = remove_badge_from_article(article)
        articles_finaux.append(article)

    articles_finaux = articles_finaux[:MAX_CARDS_FILE]
    OUTPUT_FILE.write_text("\n\n".join(articles_finaux), encoding="utf-8")
    logger.info(f"{len(articles_finaux)} articles sauvegardés dans {OUTPUT_FILE}")

    save_log(log + nouveaux_ids)
    push_to_github()
    logger.info("==== Fin du script bandes-annonces ====")

if __name__=="__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("Interruption utilisateur")
    except Exception as e:
        logger.critical(f"Erreur critique: {e}", exc_info=True)
        exit(1)