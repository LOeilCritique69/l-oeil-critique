#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
from datetime import datetime
from pathlib import Path
from typing import List
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import requests
from playwright.sync_api import sync_playwright
import subprocess

# ------------------------------
# CONSTANTES / CONFIG
# ------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
LOG_FILE = SCRIPT_DIR / 'bande_annonces_log.json'
OUTPUT_FILE = SCRIPT_DIR.parent / 'bande_annonces_blocs.html'

MAX_BANDES_CINE = 3
MAX_BANDES_TMDB = 3
MAX_SYNOPSIS_LEN = 500

LIST_CINE_URL = "https://www.cinehorizons.net/bandes-annonces-prochains-films"
TMDB_API_KEY = "2cf75db44f938aeaf1e7d873a38fdcaa"
TMDB_UPCOMING_URL = "https://api.themoviedb.org/3/movie/upcoming"

# ------------------------------
# OUTILS
# ------------------------------
def clean_text(text: str) -> str:
    return ' '.join(text.strip().split())

def summarize_synopsis(synopsis: str) -> str:
    return synopsis if len(synopsis) <= MAX_SYNOPSIS_LEN else synopsis[:MAX_SYNOPSIS_LEN].rstrip() + '...'

def load_log() -> List[str]:
    if LOG_FILE.exists():
        with LOG_FILE.open('r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_log(log: List[str]) -> None:
    with LOG_FILE.open('w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

# ------------------------------
# SCRAPER CINEHORIZONS
# ------------------------------
def scrape_cinehorizons(log: List[str]) -> (List[str], List[str]):
    articles, ids = [], []
    date_ajout = datetime.now().strftime('%d %B %Y')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(LIST_CINE_URL, timeout=15000)
            page.wait_for_selector('.view-content .views-row', timeout=10000)
        except:
            browser.close()
            return articles, ids

        soup_list = BeautifulSoup(page.content(), 'html.parser')
        blocs = soup_list.select('.view-content .views-row')[:MAX_BANDES_CINE]

        for bloc in blocs:
            link_tag = bloc.select_one('h3[itemprop="name"] a[href]')
            if not link_tag:
                continue
            titre = clean_text(link_tag.text)
            detail_url = urljoin(LIST_CINE_URL, link_tag['href'])

            try:
                page.goto(detail_url, timeout=10000)
                page.wait_for_selector('.block-synopsis', timeout=8000)
            except:
                continue

            detail_soup = BeautifulSoup(page.content(), 'html.parser')

            # Date de sortie CineHorizons
            date_sortie = "Date inconnue"
            date_tag = detail_soup.select_one('.movie-release span')
            if date_tag:
                date_sortie = clean_text(date_tag.text)

            # Synopsis
            syn_tag = detail_soup.select_one('.block-synopsis .field-item.even p')
            synopsis = summarize_synopsis(clean_text(syn_tag.text)) if syn_tag else "Pas de synopsis"

            # Bande-annonce iframe
            iframe_html = '<!-- iframe non trouvé -->'
            iframe_tag = detail_soup.select_one('.ba .player iframe')
            if iframe_tag and iframe_tag.has_attr('src'):
                src = iframe_tag['src']
                if src.startswith('//'):
                    src = 'https:' + src
                iframe_html = f'<iframe width="560" height="315" src="{src}" frameborder="0" allowfullscreen></iframe>'

            identifiant = f"cinehorizons::{titre}::{detail_url}"
            if identifiant in log:
                continue

            article_html = (
                '<article class="card-bande">'
                '<span class="badge-nouveau">NOUVEAU</span>'
                f'<h2>{titre}</h2>'
                f'<p class="date-sortie">Sortie prévue : {date_sortie}</p>'
                f'<p class="ajout-site">Ajouté le : {date_ajout}</p>'
                f'<p class="synopsis">{synopsis}</p>'
                f'<div class="video-responsive">{iframe_html}</div>'
                '</article>'
            )

            articles.append(article_html)
            ids.append(identifiant)

        browser.close()
    return articles, ids

# ------------------------------
# SCRAPER TMDB (3 dernières trailers)
# ------------------------------
def scrape_tmdb(log: List[str]) -> (List[str], List[str]):
    articles, ids = [], []
    date_ajout = datetime.now().strftime('%d %B %Y')
    session = requests.Session()
    try:
        r = session.get(TMDB_UPCOMING_URL, params={"api_key": TMDB_API_KEY, "language": "fr-FR", "region": "FR"})
        r.raise_for_status()
        movies = r.json().get("results", [])[:MAX_BANDES_TMDB]
    except:
        return articles, ids

    for movie in movies:
        titre = movie.get("title") or movie.get("original_title") or "Titre inconnu"
        date_sortie = movie.get("release_date") or "Date inconnue"
        try:
            date_sortie = datetime.strptime(date_sortie, '%Y-%m-%d').strftime('%d %B %Y')
        except:
            pass

        movie_id = movie.get("id")
        if not movie_id:
            continue

        try:
            rv = session.get(f"https://api.themoviedb.org/3/movie/{movie_id}/videos",
                             params={"api_key": TMDB_API_KEY, "language": "fr-FR"})
            rv.raise_for_status()
            videos = rv.json().get("results", [])
        except:
            continue

        trailer = next((v for v in videos if v.get("type") == "Trailer" and v.get("site") == "YouTube"), None)
        if not trailer:
            continue

        video_id = trailer.get("key")
        identifiant = f"tmdb::{titre}::{video_id}"
        if identifiant in log:
            continue

        iframe_html = f'<iframe width="560" height="315" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>'
        synopsis = summarize_synopsis(movie.get("overview", "Pas de synopsis"))

        article_html = (
            '<article class="card-bande">'
            '<span class="badge-nouveau">NOUVEAU</span>'
            f'<h2>{titre}</h2>'
            f'<p class="date-sortie">Sortie prévue : {date_sortie}</p>'
            f'<p class="ajout-site">Ajouté le : {date_ajout}</p>'
            f'<p class="synopsis">{synopsis}</p>'
            f'<div class="video-responsive">{iframe_html}</div>'
            '</article>'
        )

        articles.append(article_html)
        ids.append(identifiant)

    return articles, ids

# ------------------------------
# PUSH GITHUB
# ------------------------------
def push_to_github():
    try:
        # Racine du dépôt (2 niveaux au-dessus du script)
        repo_root = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
        os.chdir(repo_root)

        # Config utilisateur Git
        subprocess.run(["git", "config", "user.name", "LOeilCritique69"], check=True)
        subprocess.run(["git", "config", "user.email", "yanisfoa69@gmail.com"], check=True)

        # Ajout des fichiers du scraper
        subprocess.run([
            "git", "add",
            "l_oeil_critique/bande_annonces_blocs.html",
            "l_oeil_critique/bande_annonces_maj.html",
            "l_oeil_critique/scripts/bande_annonces_log.json"
        ], check=True)

        # Vérifier s’il y a des changements
        status_result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if status_result.stdout.strip():
            subprocess.run(["git", "commit", "-m", "MAJ automatique des bandes-annonces"], check=True)
            subprocess.run(["git", "push", "-f", "origin", "main"], check=True)
            print("✅ Push GitHub réussi.")
        else:
            print("ℹ️ Aucun changement détecté.")
    except Exception as e:
        print(f"❌ Erreur GitHub : {e}")


# ------------------------------
# MAIN
# ------------------------------
def main():
    log = load_log()
    cine_articles, cine_ids = scrape_cinehorizons(log)
    tmdb_articles, tmdb_ids = scrape_tmdb(log)

    nouveaux_articles = cine_articles + tmdb_articles
    nouveaux_ids = cine_ids + tmdb_ids

    if not nouveaux_articles:
        print("[INFO] Aucune nouvelle bande-annonce trouvée.")
        return

    ancien_contenu = ''
    if OUTPUT_FILE.exists():
        with OUTPUT_FILE.open('r', encoding='utf-8') as f:
            ancien_contenu = f.read()

    anciens_articles = re.findall(r'(<article class="card-bande"[^>]*>.*?</article>)',
                                  ancien_contenu, flags=re.DOTALL)

    all_articles = nouveaux_articles + anciens_articles

    with OUTPUT_FILE.open('w', encoding='utf-8') as f:
        f.write('\n\n'.join(all_articles))

    save_log(log + nouveaux_ids)
    print(f"✅ {len(nouveaux_articles)} nouvelles bandes-annonces ajoutées")

    # Push GitHub
    push_to_github()

if __name__ == "__main__":
    main()
