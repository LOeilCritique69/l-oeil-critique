#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Scraper de bandes-annonces — CineHorizons, Allociné (films + séries), TMDb.
Fusionne le tout dans bande_annonces_blocs.html puis pousse sur GitHub.

============================================================================
 WORKFLOW EN 2 ÉTAPES (c'est le seul truc à retenir)
============================================================================

ÉTAPE 1 — une seule fois, pour repartir propre avec tout l'historique
de l'année en cours :

    python3 scraper_bandes_annonces.py --backfill

    -> Écrase entièrement bande_annonces_blocs.html et le reconstruit à
       partir de TOUTES les sources, en ne gardant que les sorties à partir
       du 1er janvier de l'année en cours (calculé automatiquement, donc pas
       besoin de changer une date en dur chaque année).
       Marque aussi tout ce qui a été vu comme "connu" dans le log, même les
       titres exclus par la date, pour que l'étape 2 ne re-scrape pas tout
       l'historique le lendemain.

ÉTAPE 2 — tous les jours ensuite (ex: tâche planifiée quotidienne) :

    python3 scraper_bandes_annonces.py

    -> Ne regarde QUE ce qui est nouveau depuis le dernier passage (comparé
       au log). Ajoute ces nouveautés en haut du fichier existant, sans
       toucher au reste.

Options utiles pour l'étape 1 :
    --since YYYY-MM-DD       force une date de départ précise (sinon: 1er
                              janvier de l'année en cours, automatique)
    --max-pages N            nombre de pages à parcourir par source (def: 40)
    --keep-unknown-dates     garde aussi les entrées à la date illisible
                              (ex: "Date inconnue"), à la fin du fichier
    --no-push                ne pousse pas sur GitHub à la fin (utile pour
                              tester le rendu de bande_annonces_blocs.html
                              avant de committer pour de vrai)

Options utiles pour l'étape 2 :
    --max-new-per-source N   plafond de nouveautés par source par run
                              (def: 8)
    --no-push                idem
============================================================================
"""

import os
import re
import json
import time
import logging
import argparse
import subprocess
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, NamedTuple, Callable, TypeVar
from urllib.parse import urljoin
from contextlib import contextmanager

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page

# ------------------------------
# CONFIGURATION GLOBALE
# ------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent

# Racine du dépôt git = le dossier qui CONTIENT bande_annonces_blocs.html et
# le .git/. Chez toi c'est D:\projet_webs\test, avec ce script rangé dans
# D:\projet_webs\test\scripts. Si tu déplaces le script ailleurs, corrige
# cette ligne pour qu'elle continue à pointer sur le bon dossier.
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
MAX_CARDS_FILE = 5000

# Plafond quotidien par défaut (étape 2), surchargeable via --max-new-per-source
DEFAULT_MAX_NEW_PER_SOURCE_PER_RUN = 8

# Limites de pagination par défaut en mode quotidien
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
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 2

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

T = TypeVar("T")

def with_retries(func: Callable[[], T], description: str, retries: int = MAX_RETRIES) -> Optional[T]:
    """
    Exécute func() en retentant jusqu'à `retries` fois en cas d'exception,
    avec une petite pause entre les tentatives. Retourne None si tout échoue,
    au lieu de laisser planter tout le run pour un site momentanément lent.
    """
    last_error = None
    for attempt in range(1, retries + 2):
        try:
            return func()
        except Exception as e:
            last_error = e
            if attempt <= retries:
                logger.debug(f"Tentative {attempt} échouée ({description}): {e} — nouvel essai")
                time.sleep(RETRY_DELAY_SECONDS)
    logger.warning(f"Échec définitif après {retries + 1} tentatives ({description}): {last_error}")
    return None

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

def save_log(log_entries: List[str]):
    # dédoublonnage tout en gardant l'ordre d'apparition
    seen = set()
    deduped = []
    for entry in log_entries:
        if entry not in seen:
            seen.add(entry)
            deduped.append(entry)
    logger.info(f"Sauvegarde du log avec {len(deduped)} identifiants")
    with LOG_FILE.open("w", encoding="utf-8") as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)

def format_date(date_str: str, input_format: str = "%Y-%m-%d") -> str:
    try:
        date_obj = datetime.strptime(date_str, input_format)
        mois_fr = [
            "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre"
        ]
        return f"{date_obj.day} {mois_fr[date_obj.month - 1]} {date_obj.year}"
    except Exception:
        logger.warning(f"Impossible de formater la date: {date_str}")
        return date_str

def parse_release_date(date_str: str) -> Optional[date]:
    """
    Best-effort : convertit le texte libre de date_sortie en objet date, pour
    filtrer par --since en mode backfill. Retourne None si illisible
    (ex: "Date inconnue").
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

def goto(page: Page, url: str, wait_selector: Optional[str] = None,
         wait_state: str = "visible", wait_timeout: int = 8000) -> bool:
    """
    Navigue vers une URL avec quelques tentatives, puis attend éventuellement
    un sélecteur précis. Retourne True/False au lieu de laisser fuiter
    l'exception, pour que l'appelant décide simplement "j'ai le contenu ou pas".
    """
    def _do():
        page.goto(url, timeout=PAGE_TIMEOUT)
        if wait_selector:
            page.wait_for_selector(wait_selector, timeout=wait_timeout, state=wait_state)
        return True

    result = with_retries(_do, f"navigation vers {url}")
    return bool(result)

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

def extract_cinehorizons_detail(page: Page, detail_url: str, titre: str) -> Optional[dict]:
    logger.info(f"Extraction détails CineHorizons pour {titre}")
    if not goto(page, detail_url, wait_selector=".block-synopsis", wait_timeout=8000):
        logger.warning(f"Page injoignable pour {titre} ({detail_url})")
        return None

    detail = BeautifulSoup(page.content(), "html.parser")
    date_elem = detail.select_one(".movie-release span")
    date_sortie = clean_text(date_elem.text) if date_elem else "Date inconnue"
    syn_tag = detail.select_one(".block-synopsis .field-item.even p")
    synopsis = summarize_synopsis(syn_tag.text) if syn_tag else "Pas de synopsis"
    iframe = detail.select_one(".ba .player iframe")
    iframe_html = (
        f'<iframe width="560" height="315" src="{iframe["src"]}" frameborder="0" allowfullscreen></iframe>'
        if iframe and iframe.get("src") else ""
    )
    return {"date_sortie": date_sortie, "synopsis": synopsis, "iframe_html": iframe_html}

def scrape_cinehorizons(log_ids: set, page: Page, max_pages: int) -> List[ScrapedItem]:
    """
    Parcourt les pages de la liste CineHorizons (triée par date d'ajout
    décroissante). S'arrête dès qu'une page entière ne contient plus aucun
    film inconnu du log, ou après max_pages pages par sécurité.
    """
    logger.info("Démarrage scraping CineHorizons...")
    items: List[ScrapedItem] = []
    date_ajout = datetime.now().strftime("%d %B %Y")

    for page_index in range(max_pages):
        list_url = LIST_CINE_URL if page_index == 0 else f"{LIST_CINE_URL}?page={page_index}"
        if not goto(page, list_url):
            logger.warning(f"Page liste CineHorizons injoignable ({list_url}), arrêt")
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
            if identifiant in log_ids:
                logger.debug(f"{titre} déjà présent dans le log, ignoré")
                continue
            details = extract_cinehorizons_detail(page, detail_url, titre)
            if not details:
                logger.debug(f"Détails non récupérés pour {titre}, ignoré")
                continue
            article_html = generate_article_html(
                titre, details["date_sortie"], details["synopsis"], details["iframe_html"], date_ajout, True
            )
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

def extract_allocine_video_season_info(page: Page, cmedia: str, cserie: str):
    video_url = f"https://www.allocine.fr/video/player_gen_cmedia={cmedia}&cserie={cserie}.html"
    if not goto(page, video_url, wait_selector="figure[data-model]", wait_timeout=8000):
        logger.warning(f"Page vidéo Allociné injoignable (cmedia={cmedia})")
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

def extract_allocine_season_release_date(page: Page, cserie: str, season_id) -> Optional[str]:
    if not season_id:
        return None
    season_url = f"https://www.allocine.fr/series/ficheserie-{cserie}/saison-{season_id}/"
    if not goto(page, season_url, wait_selector="body", wait_timeout=8000):
        logger.warning(f"Page saison Allociné injoignable ({season_url})")
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

def extract_allocine_detail(page: Page, content_id: str, cmedia: str, content_type: str) -> Optional[dict]:
    if content_type == "serie":
        detail_url = f"https://www.allocine.fr/series/ficheserie_gen_cserie={content_id}.html"
    else:
        detail_url = f"https://www.allocine.fr/film/fichefilm_gen_cfilm={content_id}.html"

    if not goto(page, detail_url, wait_selector='meta[property="og:title"]',
                wait_state="attached", wait_timeout=8000):
        logger.warning(f"Fiche Allociné injoignable ({content_type} id={content_id})")
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

def _scrape_allocine_listing(log_ids: set, page: Page, list_url_base: str, link_re,
                              id_prefix: str, content_type: str, max_pages: int) -> List[ScrapedItem]:
    items: List[ScrapedItem] = []
    date_ajout = datetime.now().strftime("%d %B %Y")

    for page_index in range(1, max_pages + 1):
        list_url = list_url_base if page_index == 1 else f"{list_url_base}?page={page_index}"
        if not goto(page, list_url, wait_selector='a[href*="player_gen_cmedia"]', wait_timeout=8000):
            logger.warning(f"Page liste Allociné injoignable ({list_url}), arrêt")
            break

        logger.info(f"Page Allociné chargée: {list_url}")
        soup = BeautifulSoup(page.content(), "html.parser")
        liens = soup.select('a[href*="player_gen_cmedia"]')
        if not liens:
            logger.info("Plus aucune vidéo trouvée, fin de pagination Allociné")
            break

        vus_sur_page = set()
        nouveaux_sur_cette_page = 0

        for lien in liens:
            match = link_re.search(lien.get("href", ""))
            if not match:
                continue
            cmedia, content_id = match.group(1), match.group(2)
            if (cmedia, content_id) in vus_sur_page:
                continue
            vus_sur_page.add((cmedia, content_id))

            identifiant = f"{id_prefix}::{content_id}::{cmedia}"
            if identifiant in log_ids:
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

def scrape_allocine(log_ids: set, page: Page, max_pages: int) -> List[ScrapedItem]:
    logger.info("Démarrage scraping Allociné (films)...")
    items = _scrape_allocine_listing(
        log_ids, page, LIST_ALLOCINE_URL, ALLOCINE_FILM_LINK_RE, "allocine", "film", max_pages
    )
    logger.info(f"Scraping Allociné (films) terminé ({len(items)} items)")
    return items

def scrape_allocine_series(log_ids: set, page: Page, max_pages: int) -> List[ScrapedItem]:
    logger.info("Démarrage scraping Allociné (séries)...")
    items = _scrape_allocine_listing(
        log_ids, page, LIST_ALLOCINE_SERIES_URL, ALLOCINE_SERIE_LINK_RE, "allocine_serie", "serie", max_pages
    )
    logger.info(f"Scraping Allociné (séries) terminé ({len(items)} items)")
    return items

# ------------------------------
# SCRAPER TMDB
# ------------------------------

def fetch_tmdb_trailer(session: requests.Session, movie_id) -> Optional[str]:
    logger.debug(f"Récupération trailer TMDb film ID={movie_id}")

    def _try(lang_params: dict) -> Optional[str]:
        r = session.get(
            f"{TMDB_BASE_URL}/movie/{movie_id}/videos",
            params={"api_key": TMDB_API_KEY, **lang_params},
            timeout=REQUEST_TIMEOUT,
        )
        videos = r.json().get("results", [])
        trailer = next((v for v in videos if v.get("type") == "Trailer" and v.get("site") == "YouTube"), None)
        return trailer.get("key") if trailer else None

    result = with_retries(lambda: _try({"language": "fr-FR"}), f"trailer TMDb {movie_id} (fr-FR)", retries=1)
    if result:
        return result
    result = with_retries(lambda: _try({}), f"trailer TMDb {movie_id} (default)", retries=1)
    return result

def scrape_tmdb(log_ids: set, max_pages: int) -> List[ScrapedItem]:
    logger.info("Démarrage scraping TMDb...")
    items: List[ScrapedItem] = []
    date_ajout = datetime.now().strftime("%d %B %Y")

    with get_requests_session() as session:
        for endpoint in TMDB_ENDPOINTS:
            for page_num in range(1, max_pages + 1):
                def _fetch_page():
                    r = session.get(
                        f"{TMDB_BASE_URL}/movie/{endpoint}",
                        params={"api_key": TMDB_API_KEY, "language": "fr-FR", "region": "FR", "page": page_num},
                        timeout=REQUEST_TIMEOUT,
                    )
                    return r.json()

                data = with_retries(_fetch_page, f"TMDb {endpoint} page {page_num}")
                if data is None:
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
                    if identifiant in log_ids:
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

def remove_badge_from_article(article_html: str) -> str:
    return re.sub(r'\s*<span class="badge-nouveau">NOUVEAU</span>\s*', '\n', article_html)

def extract_articles_from_html(html_content: str) -> List[str]:
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
    Mélange plusieurs sources en alternance round-robin, pour que chaque
    source place ses items les plus récents au fil du fichier plutôt qu'une
    seule source ne domine tout le haut de la grille.
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

def default_since_date() -> str:
    """1er janvier de l'année en cours, calculé automatiquement chaque année."""
    return date.today().replace(month=1, day=1).isoformat()

def parse_args():
    parser = argparse.ArgumentParser(
        description="Scraper de bandes-annonces — voir le docstring en tête de fichier pour le workflow en 2 étapes."
    )
    parser.add_argument("--backfill", action="store_true",
                         help="ÉTAPE 1 (une fois) : reconstruit ENTIÈREMENT bande_annonces_blocs.html "
                              "depuis toutes les sources, filtré depuis le début de l'année en cours.")
    parser.add_argument("--since", default=None,
                         help="En mode --backfill : ne garder que les sorties à partir de cette date "
                              "(def: 1er janvier de l'année en cours, calculé automatiquement)")
    parser.add_argument("--max-pages", type=int, default=None,
                         help="Nombre de pages à parcourir par source en mode --backfill")
    parser.add_argument("--keep-unknown-dates", action="store_true",
                         help="En mode --backfill : garder aussi les entrées à la date illisible, en fin de fichier")
    parser.add_argument("--max-new-per-source", type=int, default=DEFAULT_MAX_NEW_PER_SOURCE_PER_RUN,
                         help=f"ÉTAPE 2 (quotidien) : plafond de nouveautés par source par run (def: {DEFAULT_MAX_NEW_PER_SOURCE_PER_RUN})")
    parser.add_argument("--no-push", action="store_true",
                         help="Ne pousse pas sur GitHub à la fin (utile pour tester avant de committer pour de vrai)")
    return parser.parse_args()

def run_scraping_sources(log_ids: set, max_pages_cine: int, max_pages_allocine: int,
                          max_pages_allocine_series: int, max_pages_tmdb: int):
    """
    Lance chaque source dans son propre try/except : si une source plante
    complètement (site down, blocage, etc.), les autres continuent quand même
    au lieu de faire échouer tout le run.
    """
    cine_all: List[ScrapedItem] = []
    allocine_all: List[ScrapedItem] = []
    allocine_series_all: List[ScrapedItem] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            cine_all = scrape_cinehorizons(log_ids, page, max_pages_cine)
        except Exception as e:
            logger.error(f"Échec complet du scraping CineHorizons: {e}", exc_info=True)

        try:
            allocine_all = scrape_allocine(log_ids, page, max_pages_allocine)
        except Exception as e:
            logger.error(f"Échec complet du scraping Allociné (films): {e}", exc_info=True)

        try:
            allocine_series_all = scrape_allocine_series(log_ids, page, max_pages_allocine_series)
        except Exception as e:
            logger.error(f"Échec complet du scraping Allociné (séries): {e}", exc_info=True)

        browser.close()

    tmdb_all: List[ScrapedItem] = []
    try:
        tmdb_all = scrape_tmdb(log_ids, max_pages_tmdb)
    except Exception as e:
        logger.error(f"Échec complet du scraping TMDb: {e}", exc_info=True)

    return cine_all, allocine_all, allocine_series_all, tmdb_all

def main():
    logger.info("==== Début du script bandes-annonces ====")
    args = parse_args()

    since_str = args.since or default_since_date()
    since_date = datetime.strptime(since_str, "%Y-%m-%d").date()
    log_list: List[str] = [] if args.backfill else load_log()
    log_ids = set(log_list)

    if args.backfill:
        logger.warning(
            f"MODE BACKFILL (ÉTAPE 1) — reconstruction complète depuis {since_date}, "
            f"le fichier {OUTPUT_FILE} va être écrasé."
        )
    else:
        logger.info(f"Mode quotidien (ÉTAPE 2) — recherche des nouveautés du jour uniquement.")

    max_pages_cine = args.max_pages or (BACKFILL_MAX_PAGES_CINE if args.backfill else MAX_PAGES_CINE)
    max_pages_allocine = args.max_pages or (BACKFILL_MAX_PAGES_ALLOCINE if args.backfill else MAX_PAGES_ALLOCINE)
    max_pages_allocine_series = args.max_pages or (BACKFILL_MAX_PAGES_ALLOCINE_SERIES if args.backfill else MAX_PAGES_ALLOCINE_SERIES)
    max_pages_tmdb = args.max_pages or (BACKFILL_MAX_PAGES_TMDB if args.backfill else MAX_PAGES_TMDB)

    cine_all, allocine_all, allocine_series_all, tmdb_all = run_scraping_sources(
        log_ids, max_pages_cine, max_pages_allocine, max_pages_allocine_series, max_pages_tmdb
    )

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
        cine_items = cine_all[:args.max_new_per_source]
        allocine_items = allocine_all[:args.max_new_per_source]
        allocine_series_items = allocine_series_all[:args.max_new_per_source]
        tmdb_items = tmdb_all[:args.max_new_per_source]

    nouveaux_items = interleave_sources(cine_items, allocine_items, allocine_series_items, tmdb_items)
    logger.info(f"{len(nouveaux_items)} articles retenus pour ce run")

    if not nouveaux_items:
        logger.info("Aucun article à écrire, arrêt")
        return

    if args.backfill:
        # Reconstruction complète : on écrase, pas de reprise de l'ancien fichier.
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
        articles_finaux = articles_finaux[:MAX_CARDS_FILE]

    OUTPUT_FILE.write_text("\n\n".join(articles_finaux), encoding="utf-8")
    logger.info(f"{len(articles_finaux)} articles sauvegardés dans {OUTPUT_FILE}")

    if args.backfill:
        # On marque comme "connu" TOUT ce qui a été vu pendant le backfill (même
        # les items exclus par le filtre de date), pour que l'étape 2 (quotidienne)
        # ne re-scrape pas tout l'historique dès le lendemain.
        all_seen_ids = [i.identifiant for i in (cine_all + allocine_all + allocine_series_all + tmdb_all)]
        save_log(all_seen_ids)
    else:
        save_log(log_list + [i.identifiant for i in nouveaux_items])

    if not args.no_push:
        push_to_github()
    else:
        logger.info("--no-push activé, GitHub non touché.")

    logger.info("==== Fin du script bandes-annonces ====")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.getLogger(__name__).warning("Interruption utilisateur")
    except Exception as e:
        logging.getLogger(__name__).critical(f"Erreur critique: {e}", exc_info=True)
        exit(1)