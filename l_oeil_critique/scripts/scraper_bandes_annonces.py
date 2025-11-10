#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script d'automatisation pour récupérer les bandes-annonces depuis CineHorizons et TMDb,
les fusionner dans un bloc HTML standardisé, puis pousser automatiquement sur GitHub.

Auteur : Yanis (L'Œil Critique)
Version : 2.1 — Optimisée pour stabilité, performance et maintenance.
"""

import os
import re
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from urllib.parse import urljoin
from contextlib import contextmanager

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

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
    """Nettoie et normalise un texte."""
    if not text:
        return ""
    return ' '.join(text.strip().split())

def summarize_synopsis(synopsis: str, max_len: int = MAX_SYNOPSIS_LEN) -> str:
    """Raccourcit le synopsis s'il dépasse la limite."""
    synopsis = clean_text(synopsis)
    if len(synopsis) <= max_len:
        return synopsis
    return synopsis[:max_len].rsplit(' ', 1)[0] + "..."

def load_log() -> List[str]:
    """Charge la liste des identifiants déjà ajoutés."""
    if not LOG_FILE.exists():
        return []
    
    try:
        with LOG_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"⚠️ Erreur lecture log : {e}. Réinitialisation.")
        return []

def save_log(log: List[str]) -> None:
    """Sauvegarde la liste mise à jour des identifiants."""
    try:
        with LOG_FILE.open("w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"❌ Impossible de sauvegarder le log : {e}")

def format_date(date_str: str, input_format: str = "%Y-%m-%d") -> str:
    """Formate une date au format français."""
    try:
        date_obj = datetime.strptime(date_str, input_format)
        # Traduction manuelle des mois en français
        mois_fr = [
            "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre"
        ]
        return f"{date_obj.day} {mois_fr[date_obj.month - 1]} {date_obj.year}"
    except (ValueError, IndexError):
        return date_str

@contextmanager
def get_requests_session():
    """Context manager pour gérer les sessions requests."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    try:
        yield session
    finally:
        session.close()

# ------------------------------
# GÉNÉRATION HTML
# ------------------------------
def generate_article_html(
    titre: str,
    date_sortie: str,
    synopsis: str,
    iframe_html: str,
    date_ajout: Optional[str] = None,
    is_nouveau: bool = False
) -> str:
    """Génère le HTML d'un article de bande-annonce."""
    if date_ajout is None:
        date_ajout = datetime.now().strftime("%d %B %Y")
    
    # Échappement HTML basique
    titre = titre.replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    synopsis = synopsis.replace('<', '&lt;').replace('>', '&gt;')
    
    # Badge NOUVEAU uniquement si is_nouveau est True
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
# SCRAPER CINEHORIZONS
# ------------------------------
def extract_cinehorizons_detail(page, detail_url: str, titre: str) -> Optional[Dict[str, str]]:
    """Extrait les détails d'une page CineHorizons."""
    try:
        page.goto(detail_url, timeout=PAGE_TIMEOUT)
        page.wait_for_selector(".block-synopsis", timeout=8000)
    except PlaywrightTimeout:
        logger.warning(f"⏱ Timeout pour {titre}")
        return None
    except Exception as e:
        logger.error(f"❌ Erreur chargement page {titre}: {e}")
        return None

    detail = BeautifulSoup(page.content(), "html.parser")
    
    # Extraction date de sortie
    date_elem = detail.select_one(".movie-release span")
    date_sortie = clean_text(date_elem.text) if date_elem else "Date inconnue"
    
    # Extraction synopsis
    syn_tag = detail.select_one(".block-synopsis .field-item.even p")
    synopsis = summarize_synopsis(syn_tag.text) if syn_tag else "Pas de synopsis"
    
    # Extraction iframe
    iframe = detail.select_one(".ba .player iframe")
    if iframe and iframe.get("src"):
        iframe_html = f'<iframe width="560" height="315" src="{iframe["src"]}" frameborder="0" allowfullscreen></iframe>'
    else:
        iframe_html = "<!-- Pas d'iframe -->"
        logger.warning(f"⚠️ Pas d'iframe trouvée pour {titre}")
    
    return {
        "date_sortie": date_sortie,
        "synopsis": synopsis,
        "iframe_html": iframe_html
    }

def scrape_cinehorizons(log: List[str]) -> Tuple[List[str], List[str]]:
    """Scrape CineHorizons pour obtenir les nouvelles bandes-annonces."""
    articles, ids = [], []
    date_ajout = datetime.now().strftime("%d %B %Y")

    logger.info("🎬 [CineHorizons] Démarrage du scraping...")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            
            page.goto(LIST_CINE_URL, timeout=PAGE_TIMEOUT)
            page.wait_for_selector(".view-content .views-row", timeout=10000)

            soup = BeautifulSoup(page.content(), "html.parser")
            blocs = soup.select(".view-content .views-row")[:MAX_BANDES_CINE]

            for i, bloc in enumerate(blocs, 1):
                link = bloc.select_one('h3[itemprop="name"] a[href]')
                if not link:
                    logger.warning(f"⚠️ Bloc {i} sans lien, ignoré")
                    continue

                titre = clean_text(link.text)
                detail_url = urljoin(LIST_CINE_URL, link["href"])
                identifiant = f"cinehorizons::{titre}::{detail_url}"

                if identifiant in log:
                    logger.debug(f"ℹ️ {titre} déjà présent, ignoré")
                    continue

                details = extract_cinehorizons_detail(page, detail_url, titre)
                if not details:
                    continue

                article_html = generate_article_html(
                    titre=titre,
                    date_sortie=details["date_sortie"],
                    synopsis=details["synopsis"],
                    iframe_html=details["iframe_html"],
                    date_ajout=date_ajout,
                    is_nouveau=True  # Les nouveaux articles obtiennent le badge
                )

                articles.append(article_html)
                ids.append(identifiant)
                logger.info(f"✅ Ajouté : {titre}")

            browser.close()

    except Exception as e:
        logger.error(f"❌ Erreur CineHorizons : {e}", exc_info=True)

    logger.info(f"✅ [CineHorizons] {len(articles)} nouvelles bandes-annonces trouvées.")
    return articles, ids

# ------------------------------
# SCRAPER TMDB
# ------------------------------
def fetch_tmdb_trailer(session: requests.Session, movie_id: int) -> Optional[str]:
    """Récupère l'ID de la bande-annonce YouTube pour un film TMDb."""
    try:
        r = session.get(
            f"https://api.themoviedb.org/3/movie/{movie_id}/videos",
            params={"api_key": TMDB_API_KEY, "language": "fr-FR"},
            timeout=REQUEST_TIMEOUT
        )
        r.raise_for_status()
        videos = r.json().get("results", [])
        
        # Prioriser les trailers officiels
        trailer = next(
            (v for v in videos if v.get("type") == "Trailer" and v.get("site") == "YouTube"),
            None
        )
        return trailer.get("key") if trailer else None
    except Exception as e:
        logger.warning(f"⚠️ Erreur récupération trailer pour film {movie_id}: {e}")
        return None

def scrape_tmdb(log: List[str]) -> Tuple[List[str], List[str]]:
    """Scrape TMDb pour les prochains films avec trailers."""
    logger.info("🎞 [TMDb] Démarrage du scraping...")
    articles, ids = [], []
    date_ajout = datetime.now().strftime("%d %B %Y")

    try:
        with get_requests_session() as session:
            r = session.get(
                TMDB_UPCOMING_URL,
                params={"api_key": TMDB_API_KEY, "language": "fr-FR", "region": "FR"},
                timeout=REQUEST_TIMEOUT
            )
            r.raise_for_status()
            movies = r.json().get("results", [])
    except Exception as e:
        logger.error(f"❌ Erreur requête TMDb : {e}")
        return articles, ids

    with get_requests_session() as session:
        for movie in movies[:MAX_BANDES_TMDB * 2]:  # Récupérer plus pour compenser ceux sans trailer
            if len(articles) >= MAX_BANDES_TMDB:
                break
            
            titre = movie.get("title", "Titre inconnu")
            date_sortie = format_date(movie.get("release_date", "Date inconnue"))
            movie_id = movie.get("id")
            
            if not movie_id:
                continue

            video_id = fetch_tmdb_trailer(session, movie_id)
            if not video_id:
                logger.debug(f"ℹ️ Pas de trailer pour {titre}")
                continue

            identifiant = f"tmdb::{titre}::{video_id}"
            if identifiant in log:
                logger.debug(f"ℹ️ {titre} déjà présent, ignoré")
                continue

            iframe_html = f'<iframe width="560" height="315" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>'
            synopsis = summarize_synopsis(movie.get("overview", "Pas de synopsis"))

            article_html = generate_article_html(
                titre=titre,
                date_sortie=date_sortie,
                synopsis=synopsis,
                iframe_html=iframe_html,
                date_ajout=date_ajout,
                is_nouveau=True  # Les nouveaux articles obtiennent le badge
            )

            articles.append(article_html)
            ids.append(identifiant)
            logger.info(f"✅ Ajouté : {titre}")

    logger.info(f"✅ [TMDb] {len(articles)} nouvelles bandes-annonces ajoutées.")
    return articles, ids

# ------------------------------
# UTILITAIRES HTML
# ------------------------------
def remove_badge_from_article(article_html: str) -> str:
    """Retire le badge NOUVEAU d'un article HTML."""
    # Retire la ligne complète contenant le badge
    return re.sub(r'\s*<span class="badge-nouveau">NOUVEAU</span>\s*', '\n    ', article_html)

def extract_articles_from_html(html_content: str) -> List[str]:
    """Extrait tous les articles d'un contenu HTML."""
    articles = re.findall(
        r'(<article class="card-bande"[^>]*>.*?</article>)',
        html_content,
        flags=re.DOTALL
    )
    return articles

# ------------------------------
# PUSH GITHUB
# ------------------------------
def push_to_github() -> bool:
    """Pousse automatiquement les mises à jour sur le dépôt GitHub."""
    try:
        repo_root = SCRIPT_DIR.parent.parent
        os.chdir(repo_root)

        # Configuration Git
        subprocess.run(["git", "config", "user.name", "LOeilCritique69"], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "yanisfoa69@gmail.com"], check=True, capture_output=True)
        
        # Ajout des fichiers
        subprocess.run(["git", "add", "."], check=True, capture_output=True)

        # Vérification des changements
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
        
        if not status.stdout.strip():
            logger.info("ℹ️ Aucun changement détecté, push annulé.")
            return False

        # Commit et push
        commit_msg = f"MAJ automatique des bandes-annonces - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True, capture_output=True)
        subprocess.run(["git", "push", "origin", "main"], check=True, capture_output=True)
        
        logger.info("✅ Push GitHub réussi.")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Erreur Git : {e.stderr.decode() if e.stderr else str(e)}")
        return False
    except Exception as e:
        logger.error(f"❌ Erreur GitHub : {e}", exc_info=True)
        return False

# ------------------------------
# MAIN
# ------------------------------
def main():
    """Point d'entrée principal du script."""
    logger.info("=" * 60)
    logger.info("🚀 Lancement du script de mise à jour des bandes-annonces")
    logger.info("=" * 60)
    
    # Chargement du log
    log = load_log()
    logger.info(f"📋 {len(log)} bandes-annonces déjà en base")

    # Scraping
    cine_articles, cine_ids = scrape_cinehorizons(log)
    tmdb_articles, tmdb_ids = scrape_tmdb(log)

    nouveaux_articles = cine_articles + tmdb_articles
    nouveaux_ids = cine_ids + tmdb_ids

    if not nouveaux_articles:
        logger.info("ℹ️ Aucune nouvelle bande-annonce détectée.")
        return

    # Fusion avec l'ancien contenu
    ancien_contenu = OUTPUT_FILE.read_text(encoding="utf-8") if OUTPUT_FILE.exists() else ""
    anciens_articles = extract_articles_from_html(ancien_contenu)
    
    # Retirer le badge NOUVEAU des anciens articles
    anciens_articles_sans_badge = [remove_badge_from_article(article) for article in anciens_articles]

    # Les nouveaux articles en premier (avec badge)
    all_articles = nouveaux_articles + anciens_articles_sans_badge
    
    # Limiter le badge NOUVEAU aux 6 premiers articles seulement
    articles_finaux = []
    for i, article in enumerate(all_articles):
        if i >= 6:
            # Retirer le badge si présent pour les articles au-delà du 6ème
            article = remove_badge_from_article(article)
        articles_finaux.append(article)

    # Sauvegarde
    try:
        OUTPUT_FILE.write_text("\n\n".join(articles_finaux), encoding="utf-8")
        logger.info(f"💾 Fichier HTML mis à jour : {OUTPUT_FILE}")
        logger.info(f"🏷️  Badge NOUVEAU appliqué aux 6 premiers articles")
    except IOError as e:
        logger.error(f"❌ Impossible d'écrire le fichier HTML : {e}")
        return

    # Mise à jour du log
    save_log(log + nouveaux_ids)

    # Push GitHub
    logger.info(f"✅ {len(nouveaux_articles)} nouvelles bandes-annonces ajoutées.")
    push_to_github()
    
    logger.info("=" * 60)
    logger.info("✅ Script terminé avec succès")
    logger.info("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n⚠️ Script interrompu par l'utilisateur")
    except Exception as e:
        logger.critical(f"💥 Erreur critique : {e}", exc_info=True)
        exit(1)