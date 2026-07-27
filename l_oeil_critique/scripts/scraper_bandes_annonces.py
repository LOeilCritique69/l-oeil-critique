#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script d'automatisation pour récupérer les bandes-annonces depuis CineHorizons, TMDb et Allociné,
les fusionner dans un bloc HTML standardisé, puis pousser automatiquement sur GitHub.

v3 : ajout d'un mode --backfill qui reconstruit ENTIÈREMENT bande_annonces_blocs.html
à partir de toutes les sources (au lieu d'ajouter seulement les nouveautés au log).
Utile quand une grosse partie des anciens embeds est cassée : plutôt que corriger
fichier existant, on regénère tout avec des liens frais, filtré par date de sortie,
et mélangé par source pour mettre en avant les dernières bandes-annonces de chacune.

Usage quotidien (comportement inchangé par rapport à la v2) :
    python3 scrape_bandes_annonces_v3.py

Reconstruction complète depuis début 2025 (à lancer une fois pour "repartir propre") :
    python3 scrape_bandes_annonces_v3.py --backfill --since 2025-01-01 --max-pages 40

Options utiles du mode backfill :
    --since YYYY-MM-DD       ne garder que les sorties à partir de cette date (def: 2025-01-01)
    --max-pages N            nombre de pages à parcourir par source (def: 40, plus haut = plus long)
    --keep-unknown-dates     garder aussi les entrées dont la date n'a pas pu être lue
                              (ex: "Date inconnue"), à la fin du fichier

⚠️ Le mode --backfill fait BEAUCOUP de requêtes (jusqu'à 40 pages x ~15-25 items x
plusieurs pages de détail chacun, sur 3 sites). Ça peut prendre du temps et risque
de se faire limiter/bloquer si c'est trop agressif : commence avec --max-pages 10-15
pour un premier essai, augmente ensuite si besoin.
"""

import os
import re
import json
import logging
import argparse
import subprocess
from datetime import datetime, date
from pathlib import Path
from typing import List, Tuple, Optional, NamedTuple
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
LIST_ALLOCINE_URL = "https://www.allocine.fr/video/bandes-annonces/plus-recentes/"
LIST_ALLOCINE_SERIES_URL = "https://www.allocine.fr/series/video/recentes/"

TMDB_API_KEY = "2cf75db44f938aeaf1e7d873a38fdcaa"
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_ENDPOINTS = ["upcoming", "now_playing"]

MAX_SYNOPSIS_LEN = 500
MAX_CARDS_FILE = 100

# Plafond quotidien (mode normal, sans --backfill) : inchangé par rapport à la v2
MAX_NEW_PER_SOURCE_PER_RUN = 8

# Limites de pagination par défaut en mode quotidien (inchangées vs v2)
MAX_PAGES_CINE = 15
MAX_PAGES_ALLOCINE = 15
MAX_PAGES_ALLOCINE_SERIES = 6
MAX_PAGES_TMDB = 5

# Limites par défaut en mode --backfill (surchargées par --max-pages si fourni)
BACKFILL_MAX_PAGES_CINE = 40
BACKFILL_MAX_PAGES_ALLOCINE = 40
BACKFILL_MAX_PAGES_ALLOCINE_SERIES = 15
BACKFILL_MAX_PAGES_TMDB = 10

REQUEST_TIMEOUT = 10
PAGE_TIMEOUT = 15000

ALLOCINE_FILM_LINK_RE = re.compile(r"player_gen_cmedia=(\d+)&cfilm=(\d+)")
ALLOCINE_SERIE_LINK_RE = re.compile(r"player_gen_cmedia=(\d+)&cserie=(\d+)")

FR_MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}

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
# STRUCTURE DE DONNÉES
# ------------------------------

class ScrapedItem(NamedTuple):
    html: str
    identifiant: str
    date_sortie: str  # texte libre tel que récupéré depuis la source

# ------------------------------
# OUTILS GÉNÉRIQUES
# ------------------------------

def clean_text(text: str) -> str:
    if not text:
        return ""
    return ' '.join(text.strip().split())

def summarize_synopsis(synopsis: str, max_len: int = MAX_SYNOPSIS_LEN) -> str:
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

def parse_release_date(date_str: str) -> Optional[date]:
    """
    Best-effort : convertit le texte libre de date_sortie en objet date, pour
    pouvoir filtrer par --since en mode backfill. Retourne None si illisible
    (ex: "Date inconnue").
    Formats gérés :
      - "20 novembre 2026"          -> date(2026, 11, 20)
      - "Série 2026" / "Série TV 2022" -> date(2026, 1, 1) / date(2022, 1, 1)
      - tout le reste                -> None
    """
    if not date_str:
        return None
    date_str = clean_text(date_str)

    m = re.match(r"(?:S[ée]rie(?:\s+TV)?)\s+(\d{4})", date_str, re.IGNORECASE)
    if m:
        return date(int(m.group(1)), 1, 1)

    m = re.match(r"(\d{1,2})\s+([A-Za-zéûîôâÀ-ÿ]+)\s+(\d{4})", date_str)
    if m:
        day = int(m.group(1))
        month = FR_MONTHS.get(m.group(2).lower())
        year = int(m.group(3))
        if month:
            try:
                return date(year, month, day)
            except ValueError:
                try:
                    return date(year, month, 1)
                except ValueError:
                    return None
    return None

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

def scrape_cinehorizons(log, page, max_pages: int = MAX_PAGES_CINE) -> List[ScrapedItem]:
    """
    Parcourt les pages de la liste CineHorizons (triée par date d'ajout décroissante).
    S'arrête dès qu'une page entière ne contient plus aucun film inconnu du log,
    ou après max_pages pages par sécurité (log vide en mode backfill -> tout est
    "inconnu", donc max_pages devient la vraie limite dans ce cas).
    """
    logger.info("Démarrage scraping CineHorizons...")
    items: List[ScrapedItem] = []
    date_ajout = datetime.now().strftime("%d %B %Y")

    for page_index in range(max_pages):
        list_url = LIST_CINE_URL if page_index == 0 else f"{LIST_CINE_URL}?page={page_index}"
        try:
            page.goto(list_url, timeout=PAGE_TIMEOUT)
        except Exception as e:
            logger.warning(f"Erreur chargement page liste CineHorizons ({list_url}): {e}")
            break

        logger.info(f"Page CineHorizons chargée: {list_url}")
        soup = BeautifulSoup(page.content(), "html.parser")
        blocs = soup.select(".view-content .views-row")
        if not blocs:
            logger.info("Plus aucun bloc trouvé, fin de pagination CineHorizons")
            break
        logger.info(f"{len(blocs)} blocs détectés sur la page {page_index + 1}")

        nouveaux_sur_cette_page = 0
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
            items.append(ScrapedItem(article_html, identifiant, details["date_sortie"]))
            nouveaux_sur_cette_page += 1
            logger.info(f"Article ajouté CineHorizons: {titre}")

        if nouveaux_sur_cette_page == 0:
            logger.info("Aucune nouveauté sur cette page, on arrête la pagination CineHorizons")
            break

    logger.info(f"Scraping CineHorizons terminé ({len(items)} items)")
    return items

# ------------------------------
# SCRAPER ALLOCINÉ (films + séries)
# ------------------------------

def extract_allocine_video_season_info(page, cmedia, cserie):
    video_url = f"https://www.allocine.fr/video/player_gen_cmedia={cmedia}&cserie={cserie}.html"
    try:
        page.goto(video_url, timeout=PAGE_TIMEOUT)
        page.wait_for_selector("figure[data-model]", timeout=8000)
    except Exception as e:
        logger.warning(f"Erreur chargement page vidéo Allociné (cmedia={cmedia}): {e}")
        return None, None

    detail = BeautifulSoup(page.content(), "html.parser")
    figure = detail.select_one("figure[data-model]")
    if not figure or not figure.get("data-model"):
        logger.warning(f"data-model introuvable sur la page vidéo (cmedia={cmedia})")
        return None, None
    try:
        model = json.loads(figure["data-model"])
        metas = model.get("videos", [{}])[0].get("metas", {})
        return metas.get("id_main_season"), metas.get("main_season_number")
    except Exception as e:
        logger.warning(f"Erreur parsing data-model vidéo Allociné (cmedia={cmedia}): {e}")
        return None, None

def extract_allocine_season_release_date(page, cserie, season_id):
    if not season_id:
        return None
    season_url = f"https://www.allocine.fr/series/ficheserie-{cserie}/saison-{season_id}/"
    try:
        page.goto(season_url, timeout=PAGE_TIMEOUT)
        page.wait_for_selector("body", timeout=8000)
    except Exception as e:
        logger.warning(f"Erreur chargement page saison Allociné ({season_url}): {e}")
        return None

    texte_page = BeautifulSoup(page.content(), "html.parser").get_text(" ", strip=True)
    for pattern in (
        r"Diffus[ée]e?\s*à partir de\s*:?\s*(\d{1,2}\s+[A-Za-zéûîôâÀ-ÿ]+\s+\d{4})",
        r"Diffus[ée]e?\s+le\s*:?\s*(\d{1,2}\s+[A-Za-zéûîôâÀ-ÿ]+\s+\d{4})",
        r"Diffusion\s*:?\s*(\d{1,2}\s+[A-Za-zéûîôâÀ-ÿ]+\s+\d{4})",
    ):
        match = re.search(pattern, texte_page)
        if match:
            return clean_text(match.group(1))
    return None

def extract_allocine_detail(page, content_id, cmedia, content_type):
    if content_type == "serie":
        detail_url = f"https://www.allocine.fr/series/ficheserie_gen_cserie={content_id}.html"
    else:
        detail_url = f"https://www.allocine.fr/film/fichefilm_gen_cfilm={content_id}.html"

    try:
        page.goto(detail_url, timeout=PAGE_TIMEOUT)
        page.wait_for_selector('meta[property="og:title"]', timeout=8000, state="attached")
    except Exception as e:
        logger.warning(f"Erreur chargement fiche Allociné ({content_type} id={content_id}): {e}")
        return None

    detail = BeautifulSoup(page.content(), "html.parser")

    titre_tag = detail.select_one('meta[property="og:title"]')
    titre = clean_text(titre_tag["content"]) if titre_tag and titre_tag.get("content") else None
    if not titre:
        logger.warning(f"Titre introuvable pour {content_type} id={content_id}, ignoré")
        return None

    desc_tag = detail.select_one('meta[property="og:description"]')
    synopsis = summarize_synopsis(desc_tag["content"]) if desc_tag and desc_tag.get("content") else "Pas de synopsis"

    if content_type == "serie":
        season_id, season_number = extract_allocine_video_season_info(page, cmedia, content_id)
        date_sortie = extract_allocine_season_release_date(page, content_id, season_id)
        if not date_sortie:
            texte_page = detail.get_text(" ", strip=True)
            annee_match = re.search(r"Série TV (\d{4})", texte_page)
            date_sortie = f"Série {annee_match.group(1)}" if annee_match else "Date inconnue"
        titre = f"{titre} (saison {season_number})" if season_number else f"{titre} (série)"
    else:
        texte_page = detail.get_text(" ", strip=True)
        date_match = re.search(r"(\d{1,2}\s+[A-Za-zéûîôâ]+\s+\d{4})\s+en\s+salle", texte_page)
        date_sortie = clean_text(date_match.group(1)) if date_match else "Date inconnue"

    iframe_html = (
        f'<iframe width="560" height="315" src="https://player.allocine.fr/{cmedia}.html" '
        f'frameborder="0" allowfullscreen></iframe>'
    )
    return {"titre": titre, "date_sortie": date_sortie, "synopsis": synopsis, "iframe_html": iframe_html}

def _scrape_allocine_listing(log, page, list_url_base, link_re, id_prefix, content_type, max_pages) -> List[ScrapedItem]:
    items: List[ScrapedItem] = []
    date_ajout = datetime.now().strftime("%d %B %Y")

    # FIX : dédoublonnage sur (cmedia, content_id) valable pour TOUT le run
    # (pas remis à zéro à chaque page). Comme visiter une page en détail prend
    # du temps (chaque fiche est chargée une par une), Allociné ajoute parfois
    # de nouvelles vidéos entre deux chargements de page, ce qui décale le
    # contenu et fait réapparaître les mêmes vidéos sur la page suivante
    # (ex: un titre vu page 3 se retrouve aussi sur la page 4). Sans ça, la
    # même vidéo pouvait être traitée deux fois pendant un seul run.
    vus_ce_run = set()

    for page_index in range(1, max_pages + 1):
        list_url = list_url_base if page_index == 1 else f"{list_url_base}?page={page_index}"
        try:
            page.goto(list_url, timeout=PAGE_TIMEOUT)
            page.wait_for_selector('a[href*="player_gen_cmedia"]', timeout=8000)
        except Exception as e:
            logger.warning(f"Erreur chargement page liste Allociné ({list_url}): {e}")
            break

        logger.info(f"Page Allociné chargée: {list_url}")
        soup = BeautifulSoup(page.content(), "html.parser")
        liens = soup.select('a[href*="player_gen_cmedia"]')
        if not liens:
            logger.info("Plus aucune vidéo trouvée, fin de pagination Allociné")
            break

        nouveaux_sur_cette_page = 0

        for lien in liens:
            match = link_re.search(lien.get("href", ""))
            if not match:
                continue
            cmedia, content_id = match.group(1), match.group(2)
            if (cmedia, content_id) in vus_ce_run:
                continue
            vus_ce_run.add((cmedia, content_id))

            identifiant = f"{id_prefix}::{content_id}::{cmedia}"
            if identifiant in log:
                logger.debug(f"{id_prefix} id={content_id}/cmedia={cmedia} déjà présent dans le log, ignoré")
                continue

            details = extract_allocine_detail(page, content_id, cmedia, content_type)
            if not details:
                continue

            article_html = generate_article_html(
                details["titre"], details["date_sortie"], details["synopsis"],
                details["iframe_html"], date_ajout, True
            )
            items.append(ScrapedItem(article_html, identifiant, details["date_sortie"]))
            nouveaux_sur_cette_page += 1
            logger.info(f"Article ajouté Allociné ({content_type}): {details['titre']}")

        if nouveaux_sur_cette_page == 0:
            logger.info("Aucune nouveauté sur cette page, on arrête la pagination Allociné")
            break

    return items

def scrape_allocine(log, page, max_pages: int = MAX_PAGES_ALLOCINE) -> List[ScrapedItem]:
    logger.info("Démarrage scraping Allociné (films)...")
    items = _scrape_allocine_listing(
        log, page, LIST_ALLOCINE_URL, ALLOCINE_FILM_LINK_RE, "allocine", "film", max_pages
    )
    logger.info(f"Scraping Allociné (films) terminé ({len(items)} items)")
    return items

def scrape_allocine_series(log, page, max_pages: int = MAX_PAGES_ALLOCINE_SERIES) -> List[ScrapedItem]:
    logger.info("Démarrage scraping Allociné (séries)...")
    items = _scrape_allocine_listing(
        log, page, LIST_ALLOCINE_SERIES_URL, ALLOCINE_SERIE_LINK_RE, "allocine_serie", "serie", max_pages
    )
    logger.info(f"Scraping Allociné (séries) terminé ({len(items)} items)")
    return items

# ------------------------------
# SCRAPER TMDB
# ------------------------------

def fetch_tmdb_trailer(session, movie_id):
    logger.debug(f"Récupération trailer TMDb film ID={movie_id}")
    try:
        r = session.get(
            f"{TMDB_BASE_URL}/movie/{movie_id}/videos",
            params={"api_key": TMDB_API_KEY, "language": "fr-FR"},
            timeout=REQUEST_TIMEOUT,
        )
        videos = r.json().get("results", [])
        trailer = next((v for v in videos if v.get("type") == "Trailer" and v.get("site") == "YouTube"), None)
        if not trailer:
            r = session.get(
                f"{TMDB_BASE_URL}/movie/{movie_id}/videos",
                params={"api_key": TMDB_API_KEY},
                timeout=REQUEST_TIMEOUT,
            )
            videos = r.json().get("results", [])
            trailer = next((v for v in videos if v.get("type") == "Trailer" and v.get("site") == "YouTube"), None)
        return trailer.get("key") if trailer else None
    except Exception as e:
        logger.warning(f"Erreur récupération trailer TMDb: {e}")
        return None

def scrape_tmdb(log, max_pages: int = MAX_PAGES_TMDB) -> List[ScrapedItem]:
    logger.info("Démarrage scraping TMDb...")
    items: List[ScrapedItem] = []
    date_ajout = datetime.now().strftime("%d %B %Y")

    with get_requests_session() as session:
        for endpoint in TMDB_ENDPOINTS:
            for page_num in range(1, max_pages + 1):
                try:
                    r = session.get(
                        f"{TMDB_BASE_URL}/movie/{endpoint}",
                        params={"api_key": TMDB_API_KEY, "language": "fr-FR", "region": "FR", "page": page_num},
                        timeout=REQUEST_TIMEOUT,
                    )
                    data = r.json()
                except Exception as e:
                    logger.warning(f"Erreur requête TMDb ({endpoint}, page {page_num}): {e}")
                    break

                movies = data.get("results", [])
                total_pages = data.get("total_pages", 1)
                if not movies:
                    logger.info(f"TMDb {endpoint} page {page_num}: aucun film, arrêt de cet endpoint")
                    break
                logger.info(f"{len(movies)} films récupérés depuis TMDb ({endpoint}, page {page_num}/{total_pages})")

                for movie in movies:
                    titre = movie.get("title")
                    movie_id = movie.get("id")
                    identifiant = f"tmdb::id::{movie_id}"
                    if identifiant in log:
                        logger.debug(f"{titre} (id={movie_id}) déjà dans le log, ignoré")
                        continue
                    video_id = fetch_tmdb_trailer(session, movie_id)
                    if not video_id:
                        logger.debug(f"{titre} sans trailer, ignoré")
                        continue
                    iframe_html = f'<iframe width="560" height="315" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>'
                    synopsis = summarize_synopsis(movie.get("overview", ""))
                    date_sortie = format_date(movie.get("release_date"))
                    article_html = generate_article_html(titre, date_sortie, synopsis, iframe_html, date_ajout, True)
                    items.append(ScrapedItem(article_html, identifiant, date_sortie))
                    logger.info(f"Article ajouté TMDb ({endpoint}): {titre}")

                if page_num >= total_pages:
                    break

    logger.info(f"Scraping TMDb terminé ({len(items)} items)")
    return items

# ------------------------------
# HTML UTILS
# ------------------------------

def remove_badge_from_article(article_html):
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
        subprocess.run(["git", "add", "."], check=True)
        try:
            subprocess.run(["git", "commit", "-m", "MAJ automatique bandes annonces"], check=True)
        except subprocess.CalledProcessError:
            logger.info("Rien à commiter, le répertoire est propre.")
            return True
        subprocess.run(["git", "push", "-f", "origin", "main"], check=True)
        logger.info("Push GitHub FORCE réussi")
        return True
    except Exception as e:
        logger.error(f"Erreur push GitHub: {e}")
        return False

# ------------------------------
# MÉLANGE DES SOURCES
# ------------------------------

def interleave_sources(*sources: List[ScrapedItem]) -> List[ScrapedItem]:
    """
    Mélange plusieurs sources en alternance round-robin (au lieu de les empiler
    bloc par bloc), pour que chaque source place ses items les plus récents
    au fil du fichier plutôt qu'une seule source ne domine tout le haut de la grille.
    """
    result: List[ScrapedItem] = []
    max_len = max((len(s) for s in sources), default=0)
    for idx in range(max_len):
        for s in sources:
            if idx < len(s):
                result.append(s[idx])
    return result

# ------------------------------
# MAIN
# ------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Scraper de bandes-annonces (v3, avec mode --backfill)")
    parser.add_argument("--backfill", action="store_true",
                         help="Reconstruit ENTIÈREMENT bande_annonces_blocs.html depuis toutes les sources "
                              "(ignore le log existant, écrase le fichier de sortie)")
    parser.add_argument("--since", default="2025-01-01",
                         help="En mode --backfill : ne garder que les sorties à partir de cette date (def: 2025-01-01)")
    parser.add_argument("--max-pages", type=int, default=None,
                         help="Nombre de pages à parcourir par source en mode --backfill (def: 40 films/séries, 10 TMDb)")
    parser.add_argument("--keep-unknown-dates", action="store_true",
                         help="En mode --backfill : garder aussi les entrées à la date illisible, en fin de fichier")
    return parser.parse_args()

def main():
    logger.info("==== Début du script bandes-annonces ====")
    args = parse_args()

    since_date = datetime.strptime(args.since, "%Y-%m-%d").date()
    log = [] if args.backfill else load_log()

    if args.backfill:
        logger.warning(f"MODE BACKFILL ACTIVÉ — reconstruction complète depuis {since_date}, "
                        f"le fichier {OUTPUT_FILE} va être écrasé.")

    max_pages_cine = args.max_pages or (BACKFILL_MAX_PAGES_CINE if args.backfill else MAX_PAGES_CINE)
    max_pages_allocine = args.max_pages or (BACKFILL_MAX_PAGES_ALLOCINE if args.backfill else MAX_PAGES_ALLOCINE)
    max_pages_allocine_series = args.max_pages or (BACKFILL_MAX_PAGES_ALLOCINE_SERIES if args.backfill else MAX_PAGES_ALLOCINE_SERIES)
    max_pages_tmdb = args.max_pages or (BACKFILL_MAX_PAGES_TMDB if args.backfill else MAX_PAGES_TMDB)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        cine_all = scrape_cinehorizons(log, page, max_pages_cine)
        allocine_all = scrape_allocine(log, page, max_pages_allocine)
        allocine_series_all = scrape_allocine_series(log, page, max_pages_allocine_series)

        browser.close()

    tmdb_all = scrape_tmdb(log, max_pages_tmdb)

    if args.backfill:
        def keep(item: ScrapedItem) -> bool:
            d = parse_release_date(item.date_sortie)
            if d is None:
                return args.keep_unknown_dates
            return d >= since_date

        cine_items = [i for i in cine_all if keep(i)]
        allocine_items = [i for i in allocine_all if keep(i)]
        allocine_series_items = [i for i in allocine_series_all if keep(i)]
        tmdb_items = [i for i in tmdb_all if keep(i)]

        logger.info(
            f"Après filtre date >= {since_date}: "
            f"cine {len(cine_items)}/{len(cine_all)}, "
            f"allocine {len(allocine_items)}/{len(allocine_all)}, "
            f"allocine_series {len(allocine_series_items)}/{len(allocine_series_all)}, "
            f"tmdb {len(tmdb_items)}/{len(tmdb_all)}"
        )
    else:
        cine_items = cine_all[:MAX_NEW_PER_SOURCE_PER_RUN]
        allocine_items = allocine_all[:MAX_NEW_PER_SOURCE_PER_RUN]
        allocine_series_items = allocine_series_all[:MAX_NEW_PER_SOURCE_PER_RUN]
        tmdb_items = tmdb_all[:MAX_NEW_PER_SOURCE_PER_RUN]

    nouveaux_items = interleave_sources(cine_items, allocine_items, allocine_series_items, tmdb_items)
    logger.info(f"{len(nouveaux_items)} articles retenus pour ce run")

    if not nouveaux_items:
        logger.info("Aucun article à écrire, arrêt")
        return

    if args.backfill:
        # Reconstruction complète : on écrase, pas de reprise de l'ancien fichier
        # (potentiellement plein de liens cassés).
        articles_finaux = [item.html for item in nouveaux_items][:MAX_CARDS_FILE]
    else:
        ancien_contenu = OUTPUT_FILE.read_text(encoding="utf-8") if OUTPUT_FILE.exists() else ""
        anciens_articles = extract_articles_from_html(ancien_contenu)
        anciens_articles = [remove_badge_from_article(a) for a in anciens_articles]

        all_articles = [item.html for item in nouveaux_items] + anciens_articles
        articles_finaux = []
        for i, article in enumerate(all_articles):
            if i >= 6:
                article = remove_badge_from_article(article)
            articles_finaux.append(article)
        # Plus de troncature ici : on garde TOUTES les anciennes bandes-annonces,
        # le fichier grossit au fil du temps au lieu de perdre les plus vieilles.

    OUTPUT_FILE.write_text("\n\n".join(articles_finaux), encoding="utf-8")
    logger.info(f"{len(articles_finaux)} articles sauvegardés dans {OUTPUT_FILE}")

    if args.backfill:
        # On marque comme "connu" TOUT ce qui a été vu pendant le backfill (même les
        # items exclus par le filtre de date), pour que les prochains runs quotidiens
        # (sans --backfill) ne rescrapent pas tout l'historique à chaque fois.
        all_seen_ids = [i.identifiant for i in (cine_all + allocine_all + allocine_series_all + tmdb_all)]
        save_log(all_seen_ids)
    else:
        # FIX : on ne loggue plus seulement les identifiants des quelques items
        # retenus pour l'affichage (nouveaux_items, plafonnés à
        # MAX_NEW_PER_SOURCE_PER_RUN par source). On loggue TOUT ce qui a été vu
        # pendant le scraping de ce run (cine_all/allocine_all/...), même les
        # items au-delà du plafond d'affichage. Sinon, tout ce qui dépasse le
        # plafond n'était jamais mémorisé et se faisait redétecter comme
        # "nouveau" indéfiniment aux runs suivants (boucle infinie observée).
        all_seen_ids = [i.identifiant for i in (cine_all + allocine_all + allocine_series_all + tmdb_all)]
        save_log(list(dict.fromkeys(log + all_seen_ids)))  # dédoublonné, ordre préservé

    push_to_github()
    logger.info("==== Fin du script bandes-annonces ====")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.getLogger(__name__).warning("Interruption utilisateur")
    except Exception as e:
        logging.getLogger(__name__).critical(f"Erreur critique: {e}", exc_info=True)
        exit(1)