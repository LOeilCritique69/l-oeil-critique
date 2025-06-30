import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json, os, re
from datetime import datetime

from playwright.sync_api import sync_playwright

# CONSTANTES ET FICHIERS
BASE_CINE_URL = 'https://www.cinehorizons.net'
LIST_CINE_URL = BASE_CINE_URL + '/bandes-annonces-prochains-films'

TMDB_API_KEY = "2cf75db44f938aeaf1e7d873a38fdcaa"
TMDB_UPCOMING_URL = "https://api.themoviedb.org/3/movie/upcoming"

LOG_FILE = 'scripts/bande_annonces_log.json'
OUTPUT_FILE = 'bande_annonces_blocs.html'
DATE_FILE = 'bande_annonces_maj.html'

MAX_BANDES_CINE = 3
MAX_BANDES_TMDB = 3
MAX_ARTICLES_VISIBLE = 9
MAX_SYNOPSIS_LEN = 500


def clean_text(text):
    return ' '.join(text.strip().split())


def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_log(log):
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def summarize_synopsis(synopsis):
    return synopsis if len(synopsis) <= MAX_SYNOPSIS_LEN else synopsis[:MAX_SYNOPSIS_LEN].rstrip() + '...'


def masquer_ancienne_premiere(contenu):
    """
    Cache le premier article marqué NOUVEAU en le passant en hidden-card
    (pour ne pas garder trop d'anciens articles visibles)
    """
    pattern = r'(<article class="card-bande"(?!.*hidden-card)[^>]*>.*?<span class="badge-nouveau">NOUVEAU</span>.*?)</article>'
    def repl(m):
        article_html = m.group(1)
        if 'hidden-card' not in article_html:
            article_html_mod = article_html.replace('class="card-bande"', 'class="card-bande hidden-card"', 1)
            # Supprime le badge NOUVEAU quand caché
            article_html_mod = article_html_mod.replace('<span class="badge-nouveau">NOUVEAU</span>', '')
            return article_html_mod + '</article>'
        return m.group(0)
    return re.sub(pattern, repl, contenu, count=1, flags=re.DOTALL)


def extract_youtube_id(src):
    if not src:
        return None
    if 'youtube.com/embed/' in src:
        return src.split('youtube.com/embed/')[-1].split('?')[0]
    return None


def scrape_cinehorizons():
    nouveaux_articles, nouveaux_ids = [], []
    log = load_log()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        page.goto(LIST_CINE_URL)
        page.wait_for_selector('.inside2')
        soup_list = BeautifulSoup(page.content(), 'html.parser')
        blocs = soup_list.select('.inside2')[:MAX_BANDES_CINE]

        date_ajout = datetime.now().strftime('%d %B %Y')

        for bloc in blocs:
            titre_tag = bloc.select_one('[itemprop="name"]')
            titre = clean_text(titre_tag.text) if titre_tag else "Titre inconnu"
            link_tag = bloc.select_one('.field-content a[href]')
            if not link_tag:
                print(f"[SKIP Cinehorizons] Pas de lien pour : {titre}")
                continue

            detail_url = urljoin(BASE_CINE_URL, link_tag['href'])
            page.goto(detail_url)
            page.wait_for_selector('.movie-release, .player')
            detail_soup = BeautifulSoup(page.content(), 'html.parser')

            date_tag = detail_soup.select_one('.movie-release')
            date_sortie_raw = clean_text(date_tag.text.split(':')[-1]) if date_tag else "Date inconnue"

            # Nettoyage date sortie : retirer parenthèses, garder que date brute
            date_sortie = re.sub(r'\s*\(.*?\)', '', date_sortie_raw).strip()

            iframe_html, video_id = '<!-- iframe non trouvé -->', None
            iframe = detail_soup.select_one('.player iframe')
            if iframe and iframe.has_attr('src'):
                src = 'https:' + iframe['src'] if iframe['src'].startswith('//') else iframe['src']
                video_id = extract_youtube_id(src)
                iframe_html = f'''<iframe width="1920" height="750" src="{src}" title="{titre} (Trailer)" frameborder="0" allowfullscreen></iframe>'''.strip()

            identifiant = f"cinehorizons::{titre}::{video_id if video_id else detail_url}"
            if identifiant in log:
                print(f"[DOUBLON Cinehorizons] {titre}")
                continue

            synopsis = "Pas de synopsis"
            try:
                menu_links = detail_soup.select('.menu a[href*="/film/"]')
                for menu_tag in menu_links:
                    if 'Sommaire' in menu_tag.text:
                        page.goto(urljoin(BASE_CINE_URL, menu_tag['href']))
                        page.wait_for_selector('.block-synopsis')
                        syn_soup = BeautifulSoup(page.content(), 'html.parser')
                        syn_tag = syn_soup.select_one('.block-synopsis .field-item.even p')
                        if syn_tag:
                            synopsis = clean_text(syn_tag.text)
                        break
            except Exception as e:
                print(f"[WARN Cinehorizons] {titre} — {e}")

            synopsis = summarize_synopsis(synopsis)
            # Suppression du badge NOUVEAU ici
            article = f'''<article class="card-bande"><h2>{titre}</h2><p class="date-sortie">Sortie prévue : {date_sortie}</p><p class="ajout-site">Ajouté le : {date_ajout}</p><p class="synopsis">{synopsis}</p><div class="video-responsive">{iframe_html}</div></article>'''.strip()
            nouveaux_articles.append(article)
            nouveaux_ids.append(identifiant)
            print(f"[OK Cinehorizons] Ajouté : {titre}")

        browser.close()

    return nouveaux_articles, nouveaux_ids


def scrape_tmdb():
    nouveaux_articles, nouveaux_ids = [], []
    log = load_log()

    params = {
        "api_key": TMDB_API_KEY,
        "language": "fr-FR",
        "region": "FR",
        "page": 1
    }

    try:
        response = requests.get(TMDB_UPCOMING_URL, params=params)
        movies = response.json().get("results", [])
    except Exception as e:
        print(f"[Erreur TMDb] Échec requête upcoming : {e}")
        return nouveaux_articles, nouveaux_ids

    date_ajout = datetime.now().strftime('%d %B %Y')

    for movie in movies:
        if len(nouveaux_articles) >= MAX_BANDES_TMDB:
            break
        movie_id = movie["id"]
        titre = movie.get("title") or movie.get("original_title") or "Titre inconnu"
        date_sortie = movie.get("release_date", "Date inconnue")
        # Garder uniquement la date (AAAA-MM-JJ) et reformater en français
        try:
            date_sortie = datetime.strptime(date_sortie, '%Y-%m-%d').strftime('%d %B %Y')
        except Exception:
            pass

        # Récupérer vidéos TMDb (trailer uniquement)
        videos_url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos"
        try:
            res = requests.get(videos_url, params={"api_key": TMDB_API_KEY, "language": "fr-FR"})
            videos = res.json().get("results", [])
        except Exception as e:
            print(f"[Erreur TMDb] Requête vidéos pour {titre} : {e}")
            continue

        trailer_youtube = None
        for v in videos:
            if v["site"] == "YouTube" and v["type"] == "Trailer":
                trailer_youtube = v
                break

        if not trailer_youtube:
            continue

        video_key = trailer_youtube["key"]
        iframe_src = f"https://www.youtube.com/embed/{video_key}"

        identifiant = f"tmdb::{titre}::{video_key}"
        if identifiant in log:
            print(f"[DOUBLON TMDb] {titre}")
            continue

        synopsis = movie.get("overview", "Pas de synopsis")
        synopsis = summarize_synopsis(synopsis)

        iframe_html = f'''<iframe width="1920" height="750" src="{iframe_src}" title="{titre} (Trailer TMDb)" frameborder="0" allowfullscreen></iframe>'''.strip()
        # Suppression du badge NOUVEAU ici
        article = f'''<article class="card-bande"><h2>{titre}</h2><p class="date-sortie">Sortie prévue : {date_sortie}</p><p class="ajout-site">Ajouté le : {date_ajout}</p><p class="synopsis">{synopsis}</p><div class="video-responsive">{iframe_html}</div></article>'''.strip()

        nouveaux_articles.append(article)
        nouveaux_ids.append(identifiant)
        print(f"[OK TMDb] Ajouté : {titre}")

    return nouveaux_articles, nouveaux_ids


def limiter_articles(articles_html):
    """
    Limite à MAX_ARTICLES_VISIBLE articles visibles (sans hidden-card).
    Les autres sont cachés (classe hidden-card) et on enlève badge NOUVEAU.
    """
    if len(articles_html) <= MAX_ARTICLES_VISIBLE:
        return articles_html

    visibles = articles_html[:MAX_ARTICLES_VISIBLE]
    caches = articles_html[MAX_ARTICLES_VISIBLE:]

    # Modifier les caches
    caches_mod = []
    for art in caches:
        art_mod = art.replace('class="card-bande"', 'class="card-bande hidden-card"')
        art_mod = art_mod.replace('<span class="badge-nouveau">NOUVEAU</span>', '')
        caches_mod.append(art_mod)

    return visibles + caches_mod


def main():
    log = load_log()
    cine_articles, cine_ids = scrape_cinehorizons()
    tmdb_articles, tmdb_ids = scrape_tmdb()

    # Récupérer ancien contenu (HTML complet)
    ancien = ''
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            ancien = f.read()

    # Nettoyage total des badges "NOUVEAU" dans ancien contenu
    ancien_sans_nouveau = re.sub(r'<span class="badge-nouveau">NOUVEAU</span>', '', ancien)

    # Nettoyage des hidden-card dans ancien pour que les articles anciens ne restent pas cachés
    ancien_sans_cache = re.sub(r'class="card-bande hidden-card"', 'class="card-bande"', ancien_sans_nouveau)

    # Extraction des anciens articles (si tu veux les garder)
    anciens_articles = re.findall(r'(<article class="card-bande"[^>]*>.*?</article>)', ancien_sans_cache, flags=re.DOTALL)

    # Combine anciens + nouveaux articles
    all_articles = anciens_articles + cine_articles + tmdb_articles

    # Fonction pour ajouter le badge NOUVEAU aux n premiers articles
    def ajouter_badge_nouveau(articles, n=6):
        articles_mod = []
        for i, art in enumerate(articles):
            # Nettoyer tout badge existant
            art = re.sub(r'<span class="badge-nouveau">NOUVEAU</span>', '', art)
            if i < n:
                art = art.replace('<article class="card-bande">', '<article class="card-bande"><span class="badge-nouveau">NOUVEAU</span>', 1)
            articles_mod.append(art)
        return articles_mod

    all_articles = ajouter_badge_nouveau(all_articles, n=6)

    # Mise à jour du log avec nouveaux identifiants (éviter doublons)
    log.extend(cine_ids + tmdb_ids)

    # Limiter le nombre d'articles visibles à 9, masquer les autres et supprimer badge NOUVEAU des cachés
    all_articles = limiter_articles(all_articles)

    # Ne pas masquer d'anciens articles ici, on a déjà nettoyé les anciens badges
    ancien_modifie = ''

    contenu_final = '\n\n'.join(all_articles) + '\n\n' + ancien_modifie

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(contenu_final)
    save_log(log)

    date_maj = datetime.now().strftime('%d %B %Y')
    with open(DATE_FILE, 'w', encoding='utf-8') as f:
        f.write(f'<p class="maj-annonces">Dernière mise à jour : {date_maj}</p>')

    print(f"\n✅ {len(cine_articles)} bande(s) Cinehorizons, {len(tmdb_articles)} bandes TMDb")
    print("✅ Mise à jour réussie.")



if __name__ == "__main__":
    main()
