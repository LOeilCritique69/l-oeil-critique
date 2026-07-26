#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script d'automatisation pour récupérer les bandes-annonces depuis CineHorizons, TMDb et Allociné,
les fusionner dans un bloc HTML standardisé, puis pousser automatiquement sur GitHub.

v2 : le script explore désormais PLUSIEURS PAGES par source (au lieu de se limiter aux 3
premiers films) et s'arrête automatiquement dès qu'il retombe sur des films déjà connus,
afin de ne rater aucune nouvelle bande-annonce sans pour autant re-scraper tout l'historique
à chaque exécution. Ajout d'une 3e source : Allociné.

Logs détaillés conservés pour suivi complet.
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

TMDB_API_KEY = "2cf75db44f938aeaf1e7d873a38fdcaa"
TMDB_BASE_URL = "https://api.themoviedb.org/3"
# Plusieurs listes TMDb interrogées pour élargir la base (au lieu du seul "upcoming")
TMDB_ENDPOINTS = ["upcoming", "now_playing"]

MAX_SYNOPSIS_LEN = 500
MAX_CARDS_FILE = 100

# --- Garde-fous anti-boucle infinie / anti-surcharge des sites ---
# (le script s'arrête AVANT ces limites dès qu'une page ne contient plus de nouveauté ;
# ces valeurs ne servent qu'à protéger un premier run sur un log vide)
MAX_PAGES_CINE = 15        # 12 films/page environ -> jusqu'à ~180 films explorés si besoin
MAX_PAGES_ALLOCINE = 15    # 25 films/page environ -> jusqu'à ~375 films explorés si besoin
MAX_PAGES_ALLOCINE_SERIES = 6  # la liste "séries à venir" ne compte que ~4 pages au total
MAX_PAGES_TMDB = 5         # 20 films/page -> jusqu'à 100 films par endpoint

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

def scrape_cinehorizons(log, page) -> Tuple[List[str], List[str]]:
    """
    Parcourt les pages de la liste CineHorizons (triée par date d'ajout décroissante).
    S'arrête dès qu'une page entière ne contient plus aucun film inconnu du log,
    ou après MAX_PAGES_CINE pages par sécurité.
    """
    logger.info("Démarrage scraping CineHorizons...")
    articles, ids = [], []
    date_ajout = datetime.now().strftime("%d %B %Y")

    for page_index in range(MAX_PAGES_CINE):
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
            articles.append(article_html)
            ids.append(identifiant)
            nouveaux_sur_cette_page += 1
            logger.info(f"Article ajouté CineHorizons: {titre}")

        if nouveaux_sur_cette_page == 0:
            logger.info("Aucune nouveauté sur cette page, on arrête la pagination CineHorizons")
            break

    logger.info("Scraping CineHorizons terminé")
    return articles, ids

# ------------------------------
# SCRAPER ALLOCINÉ (films + séries)
# ------------------------------

LIST_ALLOCINE_SERIES_URL = "https://www.allocine.fr/series/video/recentes/"

ALLOCINE_FILM_LINK_RE = re.compile(r"player_gen_cmedia=(\d+)&cfilm=(\d+)")
ALLOCINE_SERIE_LINK_RE = re.compile(r"player_gen_cmedia=(\d+)&cserie=(\d+)")

def extract_allocine_video_season_info(page, cmedia, cserie):
    """
    La fiche série globale ne contient PAS la date de la saison réellement
    teasée par la vidéo (elle ne parle que de la toute première saison).
    Le seul endroit où l'ID interne de la bonne saison est disponible, c'est
    le JSON `data-model` embarqué dans la page de la vidéo elle-même.
    On y va donc chercher `id_main_season` et `main_season_number`.
    """
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
    """
    Va chercher la vraie date de diffusion sur la page dédiée à CETTE saison
    (ex: /series/ficheserie-26596/saison-1000001287/ -> "Diffusée à partir
    de : 20 novembre 2026"), au lieu de la date de la fiche série globale.
    """
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
    """
    Va chercher le titre propre, le synopsis et la date sur la fiche film/série,
    puis construit l'iframe du lecteur Allociné (player.allocine.fr).
    content_type: "film" ou "serie".
    """
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
        # On récupère d'abord l'ID de la VRAIE saison teasée (via la page vidéo),
        # puis sa date de diffusion réelle (via la page de cette saison).
        # /!\ ces deux appels naviguent avec `page`, donc DOIVENT avoir lieu
        # après qu'on a déjà extrait titre/synopsis de `detail` ci-dessus.
        season_id, season_number = extract_allocine_video_season_info(page, cmedia, content_id)
        date_sortie = extract_allocine_season_release_date(page, content_id, season_id)
        if not date_sortie:
            texte_page = detail.get_text(" ", strip=True)
            annee_match = re.search(r"Série TV (\d{4})", texte_page)
            date_sortie = f"Série {annee_match.group(1)}" if annee_match else "Date inconnue"
        titre = f"{titre} (saison {season_number})" if season_number else f"{titre} (série)"
    else:
        # La date de sortie apparaît en texte libre du type "15 juillet 2026 en salle"
        texte_page = detail.get_text(" ", strip=True)
        date_match = re.search(r"(\d{1,2}\s+[A-Za-zéûîôâ]+\s+\d{4})\s+en\s+salle", texte_page)
        date_sortie = clean_text(date_match.group(1)) if date_match else "Date inconnue"

    iframe_html = (
        f'<iframe width="560" height="315" src="https://player.allocine.fr/{cmedia}.html" '
        f'frameborder="0" allowfullscreen></iframe>'
    )
    return {"titre": titre, "date_sortie": date_sortie, "synopsis": synopsis, "iframe_html": iframe_html}

def _scrape_allocine_listing(log, page, list_url_base, link_re, id_prefix, content_type, max_pages):
    """
    Fonction générique de pagination pour les listes Allociné (films ou séries),
    triées par date d'ajout décroissante. S'arrête dès qu'une page entière ne
    contient plus aucune vidéo inconnue du log, ou après max_pages par sécurité.
    """
    articles, ids = [], []
    date_ajout = datetime.now().strftime("%d %B %Y")

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

        # dédoublonnage des (cmedia, id) rencontrés sur la page (même vidéo peut être liée 2x : image + titre)
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
            articles.append(article_html)
            ids.append(identifiant)
            nouveaux_sur_cette_page += 1
            logger.info(f"Article ajouté Allociné ({content_type}): {details['titre']}")

        if nouveaux_sur_cette_page == 0:
            logger.info("Aucune nouveauté sur cette page, on arrête la pagination Allociné")
            break

    return articles, ids

def scrape_allocine(log, page) -> Tuple[List[str], List[str]]:
    """Bandes-annonces de films (Allociné 'Les plus récentes')."""
    logger.info("Démarrage scraping Allociné (films)...")
    articles, ids = _scrape_allocine_listing(
        log, page, LIST_ALLOCINE_URL, ALLOCINE_FILM_LINK_RE, "allocine", "film", MAX_PAGES_ALLOCINE
    )
    logger.info("Scraping Allociné (films) terminé")
    return articles, ids

def scrape_allocine_series(log, page) -> Tuple[List[str], List[str]]:
    """Bandes-annonces de séries à venir (Allociné 'Trailers des nouvelles séries')."""
    logger.info("Démarrage scraping Allociné (séries)...")
    articles, ids = _scrape_allocine_listing(
        log, page, LIST_ALLOCINE_SERIES_URL, ALLOCINE_SERIE_LINK_RE, "allocine_serie", "serie", MAX_PAGES_ALLOCINE_SERIES
    )
    logger.info("Scraping Allociné (séries) terminé")
    return articles, ids

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
            # à défaut de bande-annonce FR, on retente en VO
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

def scrape_tmdb(log) -> Tuple[List[str], List[str]]:
    """
    Interroge plusieurs listes TMDb (upcoming, now_playing) sur plusieurs pages.
    Le dédoublonnage se fait désormais sur l'ID TMDb du film (et non plus sur
    l'ID de la vidéo YouTube), pour éviter qu'un même film ne soit réintroduit
    plusieurs fois simplement parce qu'une bande-annonce différente est remontée.
    """
    logger.info("Démarrage scraping TMDb...")
    articles, ids = [], []
    date_ajout = datetime.now().strftime("%d %B %Y")

    with get_requests_session() as session:
        for endpoint in TMDB_ENDPOINTS:
            for page_num in range(1, MAX_PAGES_TMDB + 1):
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
                    article_html = generate_article_html(titre, format_date(movie.get("release_date")), synopsis, iframe_html, date_ajout, True)
                    articles.append(article_html)
                    ids.append(identifiant)
                    logger.info(f"Article ajouté TMDb ({endpoint}): {titre}")

                if page_num >= total_pages:
                    break

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

def interleave_sources(*sources):
    """
    Mélange plusieurs sources (chacune sous forme (articles, ids)) en alternance
    round-robin, au lieu de les empiler bloc par bloc (tout CineHorizons, puis tout
    Allociné, puis tout TMDb...). Ça évite qu'une seule source ne domine tout le haut
    de la grille quand elle a beaucoup plus de nouveautés qu'une autre.
    """
    paired_lists = [list(zip(articles, ids)) for articles, ids in sources]
    result_articles, result_ids = [], []
    max_len = max((len(p) for p in paired_lists), default=0)
    for idx in range(max_len):
        for p in paired_lists:
            if idx < len(p):
                article, identifiant = p[idx]
                result_articles.append(article)
                result_ids.append(identifiant)
    return result_articles, result_ids

# ------------------------------
# MAIN
# ------------------------------

def main():
    logger.info("==== Début du script bandes-annonces ====")
    log = load_log()

    cine_articles, cine_ids = [], []
    allocine_articles, allocine_ids = [], []
    allocine_series_articles, allocine_series_ids = [], []

    # Un seul navigateur Playwright partagé pour CineHorizons + Allociné (films + séries)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        cine_articles, cine_ids = scrape_cinehorizons(log, page)
        allocine_articles, allocine_ids = scrape_allocine(log, page)
        allocine_series_articles, allocine_series_ids = scrape_allocine_series(log, page)

        browser.close()

    tmdb_articles, tmdb_ids = scrape_tmdb(log)

    nouveaux_articles, nouveaux_ids = interleave_sources(
        (cine_articles, cine_ids),
        (allocine_articles, allocine_ids),
        (allocine_series_articles, allocine_series_ids),
        (tmdb_articles, tmdb_ids),
    )
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
        if i >= 6:
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