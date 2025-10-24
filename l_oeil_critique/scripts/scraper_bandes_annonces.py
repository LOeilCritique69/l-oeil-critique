import os
import re
import json
import subprocess
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError

# ------------------------------
# CONSTANTES
# ------------------------------
BASE_CINE_URL = 'https://www.cinehorizons.net'
LIST_CINE_URL = f"{BASE_CINE_URL}/bandes-annonces-prochainement"
BASE_ALLOCINE_URL = "https://www.allocine.fr"
LIST_ALLOCINE_URL = f"{BASE_ALLOCINE_URL}/video/bandes-annonces/films/"
TMDB_API_URL = "https://api.themoviedb.org/3/movie/upcoming"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

LOG_FILE = "l_oeil_critique/scripts/bande_annonces_log.json"
HTML_BLOC_FILE = "l_oeil_critique/bande_annonces_blocs.html"
HTML_MAJ_FILE = "l_oeil_critique/bande_annonces_maj.html"

# Mode auto : push activé uniquement sur GitHub Actions
DO_PUSH = os.getenv("GITHUB_ACTIONS") == "true"

# ------------------------------
# OUTILS DE LOG
# ------------------------------
def log_console(message: str, level="INFO"):
    prefix = {
        "INFO": "ℹ️",
        "SUCCESS": "✅",
        "ERROR": "❌",
        "WARNING": "⚠️"
    }.get(level, "ℹ️")
    print(f"{prefix} {message}")

# ------------------------------
# CHARGEMENT DU LOG
# ------------------------------
def load_seen_articles():
    if not os.path.exists(LOG_FILE):
        return {"cinehorizons": [], "allocine": [], "tmdb": []}
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_seen_articles(data):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ------------------------------
# SCRAPER CINEHORIZONS
# ------------------------------
def scrape_cinehorizons():
    log_console("Scraping Cinehorizons...", "INFO")
    articles = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(LIST_CINE_URL, timeout=25000)
            page.wait_for_selector(".inside2", timeout=12000)

            soup = BeautifulSoup(page.content(), "html.parser")
            for div in soup.select(".inside2"):
                titre_el = div.select_one("h2 a")
                img_el = div.select_one("img")
                if not titre_el or not img_el:
                    continue

                titre = titre_el.text.strip()
                lien = urljoin(BASE_CINE_URL, titre_el["href"])
                image = urljoin(BASE_CINE_URL, img_el["src"])
                articles.append({
                    "titre": titre,
                    "lien": lien,
                    "image": image
                })
            browser.close()
    except TimeoutError:
        log_console("Timeout sur Cinehorizons", "WARNING")
    except Exception as e:
        log_console(f"Erreur Cinehorizons : {e}", "ERROR")

    return articles

# ------------------------------
# SCRAPER ALLOCINE
# ------------------------------
def scrape_allocine():
    log_console("Scraping AlloCiné...", "INFO")
    articles = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(LIST_ALLOCINE_URL, timeout=25000)
            page.wait_for_selector(".meta-title-link", timeout=12000)

            soup = BeautifulSoup(page.content(), "html.parser")
            for div in soup.select(".video-card"):
                titre_el = div.select_one(".meta-title-link")
                img_el = div.select_one("img")
                if not titre_el or not img_el:
                    continue

                titre = titre_el.text.strip()
                lien = urljoin(BASE_ALLOCINE_URL, titre_el["href"])
                image = img_el.get("data-src") or img_el.get("src")
                if not image:
                    continue
                articles.append({
                    "titre": titre,
                    "lien": lien,
                    "image": image
                })
            browser.close()
    except TimeoutError:
        log_console("Timeout sur AlloCiné", "WARNING")
    except Exception as e:
        log_console(f"Erreur AlloCiné : {e}", "ERROR")

    return articles

# ------------------------------
# SCRAPER TMDB
# ------------------------------
def scrape_tmdb():
    log_console("Scraping TMDb...", "INFO")
    articles = []
    api_key = os.getenv("TMDB_API_KEY")
    if not api_key:
        log_console("Clé API TMDb manquante.", "ERROR")
        return []

    try:
        response = requests.get(TMDB_API_URL, params={"api_key": api_key, "language": "fr-FR"})
        data = response.json()
        for movie in data.get("results", [])[:5]:
            titre = movie.get("title")
            lien = f"https://www.themoviedb.org/movie/{movie['id']}"
            image = TMDB_IMAGE_BASE + movie.get("poster_path", "")
            articles.append({
                "titre": titre,
                "lien": lien,
                "image": image
            })
    except Exception as e:
        log_console(f"Erreur TMDb : {e}", "ERROR")

    return articles

# ------------------------------
# MISE À JOUR HTML
# ------------------------------
def update_html(articles):
    if not articles:
        return

    html_blocs = []
    for art in articles:
        bloc = f"""
        <div class="bande-annonce">
            <a href="{art['lien']}" target="_blank">
                <img src="{art['image']}" alt="{art['titre']}">
                <p>{art['titre']}</p>
            </a>
        </div>
        """
        html_blocs.append(bloc)

    html_content = "\n".join(html_blocs)
    with open(HTML_BLOC_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)

    with open(HTML_MAJ_FILE, "w", encoding="utf-8") as f:
        f.write(f"<p>Dernière mise à jour : {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>")

# ------------------------------
# MAIN
# ------------------------------
if __name__ == "__main__":
    print("\n=== DÉBUT DU SCRAP ===")
    log_console(f"Mode GitHub Actions : {DO_PUSH}", "INFO")

    seen = load_seen_articles()

    cine_data = scrape_cinehorizons()
    allocine_data = scrape_allocine()
    tmdb_data = scrape_tmdb()

    new_cine = [a for a in cine_data if a["titre"] not in seen["cinehorizons"]]
    new_allocine = [a for a in allocine_data if a["titre"] not in seen["allocine"]]
    new_tmdb = [a for a in tmdb_data if a["titre"] not in seen["tmdb"]]

    log_console(f"Cinehorizons → {len(new_cine)} nouveaux articles.", "SUCCESS")
    log_console(f"AlloCiné → {len(new_allocine)} nouveaux articles.", "SUCCESS")
    log_console(f"TMDb → {len(new_tmdb)} nouveaux articles.", "SUCCESS")

    all_new = new_cine + new_allocine + new_tmdb
    if all_new:
        update_html(all_new)
        seen["cinehorizons"] += [a["titre"] for a in new_cine]
        seen["allocine"] += [a["titre"] for a in new_allocine]
        seen["tmdb"] += [a["titre"] for a in new_tmdb]
        save_seen_articles(seen)
    else:
        log_console("Aucun nouvel article trouvé.", "INFO")

    print(f"✅ ✅ Résumé : {len(new_cine)} Cinehorizons | {len(new_allocine)} AlloCiné | {len(new_tmdb)} TMDb")

    if not DO_PUSH:
        log_console("⏸️  Mode test activé – push GitHub désactivé.", "INFO")
    else:
        log_console("🚀 Push automatique activé – synchronisation GitHub...", "INFO")
        try:
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "MAJ automatique des bandes-annonces"], check=False)
            subprocess.run(["git", "push"], check=True)
            log_console("✅ Modifications poussées sur GitHub.", "SUCCESS")
        except Exception as e:
            log_console(f"Erreur lors du push Git : {e}", "ERROR")
