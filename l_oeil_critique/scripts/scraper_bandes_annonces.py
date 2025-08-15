import os
import re
import json
import subprocess
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
from playwright.sync_api import sync_playwright

# ------------------------------
# CONSTANTES
# ------------------------------
BASE_CINE_URL = 'https://www.cinehorizons.net'
LIST_CINE_URL = f"{BASE_CINE_URL}/bandes-annonces-prochains-films"
ALLOCINE_URL = "https://www.allocine.fr/video/bandes-annonces/plus-recentes/"

TMDB_API_KEY = "2cf75db44f938aeaf1e7d873a38fdcaa"
TMDB_UPCOMING_URL = "https://api.themoviedb.org/3/movie/upcoming"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, 'bande_annonces_log.json')
OUTPUT_FILE = os.path.join(SCRIPT_DIR, '..', 'bande_annonces_blocs.html')
DATE_FILE = os.path.join(SCRIPT_DIR, '..', 'bande_annonces_maj.html')

MAX_BANDES_CINE = 3
MAX_BANDES_ALLO = 3
MAX_BANDES_TMDB = 3
TMDB_PAGES = 2
MAX_ARTICLES_VISIBLE = 9
MAX_SYNOPSIS_LEN = 500

# ------------------------------
# OUTILS
# ------------------------------
def clean_text(text: str) -> str:
    return ' '.join(text.strip().split())

def load_log() -> list:
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_log(log: list) -> None:
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def summarize_synopsis(synopsis: str) -> str:
    return synopsis if len(synopsis) <= MAX_SYNOPSIS_LEN else synopsis[:MAX_SYNOPSIS_LEN].rstrip() + '...'

def extract_youtube_id(src: str) -> str | None:
    if src and 'youtube.com/embed/' in src:
        return src.split('youtube.com/embed/')[-1].split('?')[0]
    return None

# ------------------------------
# SCRAPER CINEHORIZONS OPTIMISÉ
# ------------------------------
def scrape_cinehorizons():
    articles, ids = [], []
    log = load_log()
    date_ajout = datetime.now().strftime('%d %B %Y')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(LIST_CINE_URL, timeout=8000)
            page.wait_for_selector('.inside2', timeout=5000)
        except Exception as e:
            print(f"[ERREUR Cinehorizons] {e}")
            browser.close()
            return articles, ids

        soup_list = BeautifulSoup(page.content(), 'html.parser')
        blocs = soup_list.select('.inside2')[:MAX_BANDES_CINE]

        for bloc in blocs:
            titre_tag = bloc.select_one('[itemprop="name"]')
            titre = clean_text(titre_tag.text) if titre_tag else "Titre inconnu"

            link_tag = bloc.select_one('.field-content a[href]')
            if not link_tag:
                continue
            detail_url = urljoin(BASE_CINE_URL, link_tag['href'])

            try:
                page.goto(detail_url, timeout=8000)
                page.wait_for_selector('.movie-release, .player', timeout=5000)
            except:
                continue

            detail_soup = BeautifulSoup(page.content(), 'html.parser')
            date_tag = detail_soup.select_one('.movie-release')
            date_sortie_raw = clean_text(date_tag.text.split(':')[-1]) if date_tag else "Date inconnue"
            date_sortie = re.sub(r'\s*\(.*?\)', '', date_sortie_raw).strip()

            iframe_html, video_id = '<!-- iframe non trouvé -->', None
            iframe = detail_soup.select_one('.player iframe')
            if iframe and iframe.has_attr('src'):
                src = iframe['src']
                if src.startswith('//'):
                    src = 'https:' + src
                video_id = extract_youtube_id(src)
                if video_id:
                    iframe_html = (
                        f'<video class="youtube-placeholder" '
                        f'data-src="https://www.youtube.com/embed/{video_id}?autoplay=1" '
                        f'style="background-image:url(\'https://img.youtube.com/vi/{video_id}/hqdefault.jpg\');" '
                        f'role="button" aria-label="Lire la bande annonce {titre}">'
                        f'<button class="play-button"></button>'
                        f'</video>'
                    )

            identifiant = f"cinehorizons::{titre}::{video_id or detail_url}"
            if identifiant in log:
                continue

            synopsis = "Pas de synopsis"
            syn_tag = detail_soup.select_one('.block-synopsis .field-item.even p')
            if syn_tag:
                synopsis = clean_text(syn_tag.text)

            article_html = (
                f'<article class="card-bande">'
                f'<h2>{titre}</h2>'
                f'<p class="date-sortie">Sortie prévue : {date_sortie}</p>'
                f'<p class="ajout-site">Ajouté le : {date_ajout}</p>'
                f'<p class="synopsis">{summarize_synopsis(synopsis)}</p>'
                f'<div class="video-responsive">{iframe_html}</div>'
                f'</article>'
            )

            articles.append(article_html)
            ids.append(identifiant)

        browser.close()
    return articles, ids

# ------------------------------
# SCRAPER ALLOCINÉ (3 dernières)
# ------------------------------
def scrape_allocine():
    articles, ids = [], []
    log = load_log()
    date_ajout = datetime.now().strftime('%d %B %Y')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(ALLOCINE_URL, timeout=20000)
            page.wait_for_selector('main#content-layout', timeout=10000)
        except Exception as e:
            print(f"[ERREUR AlloCiné] {e}")
            browser.close()
            return articles, ids

        soup = BeautifulSoup(page.content(), 'html.parser')
        thumbs = soup.select('main#content-layout .thumbnail-container.thumbnail-link')[:MAX_BANDES_ALLO]

        for thumb in thumbs:
            link_tag = thumb.select_one('a[href]')
            if not link_tag:
                continue
            detail_url = urljoin("https://www.allocine.fr", link_tag['href'])

            try:
                page.goto(detail_url, timeout=15000)
                page.wait_for_selector('figure.player.js-player', timeout=8000)
            except:
                continue

            detail_soup = BeautifulSoup(page.content(), 'html.parser')
            titre_tag = detail_soup.select_one('a.titlebar-link')
            titre = clean_text(titre_tag.text) if titre_tag else "Titre inconnu"

            iframe_html, video_id = '<!-- iframe non trouvé -->', None
            figure = detail_soup.select_one('figure.player.js-player')
            if figure and figure.has_attr('data-model'):
                try:
                    data_model = json.loads(figure['data-model'].replace('&quot;', '"'))
                    video_info = data_model['videos'][0]
                    video_id = video_info.get('idDailymotion')
                    thumb_img = video_info.get('image')
                    iframe_html = (
                        f'<video class="dailymotion-placeholder" '
                        f'data-src="https://geo.dailymotion.com/player/{video_id}.html?video={video_id}" '
                        f'style="background-image:url(\'https://fr.web.img2.acsta.net{thumb_img}\');" '
                        f'role="button" aria-label="Lire la bande annonce {titre}">'
                        f'<button class="play-button" aria-hidden="true"></button>'
                        f'</video>'
                    )
                except Exception as e:
                    print(f"[WARN AlloCiné] JSON figure pour {titre} : {e}")

            identifiant = f"allocine::{titre}::{video_id or detail_url}"
            if identifiant in log:
                continue

            article_html = (
                f'<article class="card-bande">'
                f'<h2>{titre}</h2>'
                f'<p class="ajout-site">Ajouté le : {date_ajout}</p>'
                f'<div class="video-responsive">{iframe_html}</div>'
                f'</article>'
            )

            articles.append(article_html)
            ids.append(identifiant)

        browser.close()
    return articles, ids

# ------------------------------
# SCRAPER TMDB (2 pages)
# ------------------------------
def scrape_tmdb():
    articles, ids = [], []
    log = load_log()
    date_ajout = datetime.now().strftime('%d %B %Y')

    for page_num in range(1, TMDB_PAGES + 1):
        params = {"api_key": TMDB_API_KEY, "language": "fr-FR", "region": "FR", "page": page_num}
        try:
            movies = requests.get(TMDB_UPCOMING_URL, params=params).json().get("results", [])
        except Exception as e:
            print(f"[ERREUR TMDb] {e}")
            continue

        for movie in movies[:MAX_BANDES_TMDB]:
            titre = movie.get("title") or movie.get("original_title", "Titre inconnu")
            date_sortie = movie.get("release_date", "Date inconnue")
            try:
                date_sortie = datetime.strptime(date_sortie, '%Y-%m-%d').strftime('%d %B %Y')
            except:
                pass

            videos_url = f"https://api.themoviedb.org/3/movie/{movie['id']}/videos"
            try:
                videos = requests.get(videos_url, params={"api_key": TMDB_API_KEY, "language": "fr-FR"}).json().get("results", [])
            except:
                continue

            trailer = next((v for v in videos if v["site"] == "YouTube" and v["type"] == "Trailer"), None)
            if not trailer:
                continue

            identifiant = f"tmdb::{titre}::{trailer['key']}"
            if identifiant in log:
                continue

            video_id = trailer['key']
            iframe_html = (
                f'<video class="youtube-placeholder" '
                f'data-src="https://www.youtube.com/embed/{video_id}?autoplay=1" '
                f'style="background-image:url(\'https://img.youtube.com/vi/{video_id}/hqdefault.jpg\');" '
                f'role="button" aria-label="Lire la bande annonce {titre}">'
                f'<button class="play-button"></button>'
                f'</video>'
            )

            synopsis = summarize_synopsis(movie.get("overview", "Pas de synopsis"))
            article_html = (
                f'<article class="card-bande">'
                f'<h2>{titre}</h2>'
                f'<p class="date-sortie">Sortie prévue : {date_sortie}</p>'
                f'<p class="ajout-site">Ajouté le : {date_ajout}</p>'
                f'<p class="synopsis">{synopsis}</p>'
                f'<div class="video-responsive">{iframe_html}</div>'
                f'</article>'
            )

            articles.append(article_html)
            ids.append(identifiant)
    return articles, ids

# ------------------------------
# LIMITATION ET BADGES
# ------------------------------
def limiter_articles(articles_html):
    if len(articles_html) <= MAX_ARTICLES_VISIBLE:
        return articles_html
    visibles = articles_html[:MAX_ARTICLES_VISIBLE]
    caches = [
        art.replace('class="card-bande"', 'class="card-bande hidden-card"')
           .replace('<span class="badge-nouveau">NOUVEAU</span>', '')
        for art in articles_html[MAX_ARTICLES_VISIBLE:]
    ]
    return visibles + caches

def ajouter_badge_nouveau(articles, n=6):
    articles_mod = []
    for i, art in enumerate(articles):
        art = re.sub(r'<span class="badge-nouveau">NOUVEAU</span>', '', art)
        if i < n:
            art = art.replace('<article class="card-bande">',
                              '<article class="card-bande"><span class="badge-nouveau">NOUVEAU</span>', 1)
        articles_mod.append(art)
    return articles_mod

# ------------------------------
# MAIN
# ------------------------------
def main():
    log = load_log()

    cine_articles, cine_ids = scrape_cinehorizons()
    allo_articles, allo_ids = scrape_allocine()
    tmdb_articles, tmdb_ids = scrape_tmdb()

    ancien_contenu = ''
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            ancien_contenu = f.read()
    ancien_contenu = re.sub(r'<span class="badge-nouveau">NOUVEAU</span>', '', ancien_contenu)
    ancien_contenu = re.sub(r'class="card-bande hidden-card"', 'class="card-bande"', ancien_contenu)
    anciens_articles = re.findall(r'(<article class="card-bande"[^>]*>.*?</article>)',
                                  ancien_contenu, flags=re.DOTALL)

    all_articles = cine_articles + allo_articles + tmdb_articles + anciens_articles
    all_articles = ajouter_badge_nouveau(all_articles, n=6)
    log.extend(cine_ids + allo_ids + tmdb_ids)
    all_articles = limiter_articles(all_articles)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(all_articles))
    save_log(log)

    date_maj = datetime.now().strftime('%d %B %Y')
    with open(DATE_FILE, 'w', encoding='utf-8') as f:
        f.write(f'<p class="maj-annonces">Dernière mise à jour : {date_maj}</p>')

    print(f"\n✅ {len(cine_articles)} Cinehorizons, {len(allo_articles)} AlloCiné, {len(tmdb_articles)} TMDb")

# ------------------------------
# PUSH GITHUB
# ------------------------------
def push_to_github():
    try:
        repo_root = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
        os.chdir(repo_root)
        subprocess.run(["git", "config", "user.name", "LOeilCritique69"], check=True)
        subprocess.run(["git", "config", "user.email", "yanisfoa69@gmail.com"], check=True)
        subprocess.run([
            "git", "add",
            "l_oeil_critique/bande_annonces_blocs.html",
            "l_oeil_critique/bande_annonces_maj.html",
            "l_oeil_critique/scripts/bande_annonces_log.json"
        ], check=True)
        status_result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if status_result.stdout.strip():
            subprocess.run(["git", "commit", "-m", "MAJ automatique des bandes-annonces"], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)
            print("✅ Push GitHub réussi.")
        else:
            print("ℹ️ Aucun changement détecté.")
    except Exception as e:
        print(f"❌ Erreur GitHub : {e}")

if __name__ == "__main__":
    main()
    push_to_github()
    