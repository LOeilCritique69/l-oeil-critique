"""
lb.py — Sync Letterboxd RSS → movies.json
- Récupère les nouveaux films via RSS
- Stocke le lien vers la critique perso (tag <link> RSS)
- Enrichit via TMDB (poster, tmdb_id)
- Met à jour les ratings/dates/liens existants
- Ré-enrichit les films sans poster
- Retry automatique en cas d'erreur réseau
"""

import requests
import json
import time
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================
RSS_URL    = "https://letterboxd.com/oni_le_chan/rss/"
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(BASE_DIR, "movies.json")
CACHE_FILE = os.path.join(BASE_DIR, "tmdb_cache.json")

_TMDB_KEY_ENV      = os.environ.get("TMDB_API_KEY", "").strip()
_TMDB_KEY_FALLBACK = "2cf75db44f938aeaf1e7d873a38fdcaa"
TMDB_API_KEY       = _TMDB_KEY_ENV if _TMDB_KEY_ENV else _TMDB_KEY_FALLBACK
TMDB_BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE    = "https://image.tmdb.org/t/p/w500"

TMDB_DELAY  = 0.20
MAX_RETRIES = 3
RETRY_DELAY = 2.0

# ============================================================
# LOG HELPERS
# ============================================================
def log(prefix: str, msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {prefix:4s} {msg}")

def info(msg):  log("INFO", msg)
def ok(msg):    log("OK  ", msg)
def warn(msg):  log("WARN", msg)
def err(msg):   log("ERR ", msg)

# ============================================================
# CACHE TMDB
# ============================================================
def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            warn("Cache TMDB corrompu, réinitialisation.")
    return {}

def save_cache(cache: dict) -> None:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

cache = load_cache()

# ============================================================
# SAFE HELPERS
# ============================================================
def safe_str(v) -> str:
    return str(v).strip() if v is not None else ""

def movie_key(movie: dict) -> str:
    return safe_str(movie.get("Name")).lower()

def is_valid_movie(m: dict) -> bool:
    return bool(m and safe_str(m.get("Name")))

# ============================================================
# LOAD / SAVE LOCAL DB
# ============================================================
def load_movies() -> list:
    if not os.path.exists(INPUT_FILE):
        info("Aucun fichier movies.json trouvé — démarrage à zéro.")
        return []
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        info(f"{len(data)} films chargés depuis movies.json")
        return data
    except (json.JSONDecodeError, IOError) as e:
        err(f"Lecture movies.json impossible : {e}")
        sys.exit(1)

def save_movies(movies: list) -> None:
    with open(INPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(movies, f, indent=2, ensure_ascii=False)

# ============================================================
# HTTP AVEC RETRY
# ============================================================
def http_get(url: str, params: dict = None, retries: int = MAX_RETRIES) -> requests.Response | None:
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if attempt < retries:
                warn(f"Tentative {attempt}/{retries} échouée ({e}), retry dans {RETRY_DELAY}s…")
                time.sleep(RETRY_DELAY)
            else:
                err(f"Échec définitif après {retries} tentatives : {e}")
                return None

# ============================================================
# RSS FETCH + PARSE
# ============================================================
def fetch_rss() -> list[dict]:
    info(f"Récupération du flux RSS : {RSS_URL}")
    r = http_get(RSS_URL)
    if not r:
        err("Impossible de récupérer le flux RSS.")
        sys.exit(1)

    root  = ET.fromstring(r.content)
    items = root.findall(".//item")
    info(f"{len(items)} entrées trouvées dans le RSS.")

    ns    = "https://letterboxd.com"
    films = []

    for item in items:
        def tag(name):
            el = item.find(f"{{{ns}}}{name}")
            return el.text if el is not None else None

        name = safe_str(tag("filmTitle"))
        if not name:
            continue

        year_str = tag("filmYear")
        rating   = tag("memberRating")
        watched  = tag("watchedDate")

        # Le tag <link> RSS pointe vers la critique perso :
        # ex. https://letterboxd.com/oni_le_chan/film/300/
        link_el = item.find("link")
        # ElementTree retourne None pour <link> car c'est un tag vide-style atom ;
        # on essaie aussi le text suivant le tag
        review_link = None
        if link_el is not None and link_el.text:
            review_link = link_el.text.strip()
        else:
            # Fallback : certains parsers mettent le lien dans le tail du tag précédent
            for child in item:
                if child.tag == "link" or child.tag.endswith("}link"):
                    if child.text:
                        review_link = child.text.strip()
                        break
                    if child.tail:
                        review_link = child.tail.strip()
                        break

        # Dernier fallback : construire l'URL depuis le filmSlug ou le titre
        film_url = tag("filmUrl")  # parfois présent dans certaines versions du RSS
        if not review_link and film_url:
            review_link = film_url

        films.append({
            "Name":          name,
            "Year":          int(year_str) if year_str and year_str.isdigit() else None,
            "Date":          watched,
            "Rating":        float(rating) if rating is not None else None,
            "Letterboxd URI": review_link,  # lien critique perso
        })

    return films

# ============================================================
# TMDB SEARCH
# ============================================================
def search_tmdb(title: str, year: int | None) -> dict | None:
    cache_key = f"{title}_{year}"
    if cache_key in cache:
        return cache[cache_key]

    r = http_get(
        f"{TMDB_BASE_URL}/search/movie",
        params={
            "api_key":  TMDB_API_KEY,
            "query":    title,
            "language": "fr-FR",
        }
    )

    if not r:
        cache[cache_key] = None
        return None

    results = r.json().get("results", [])
    if not results:
        cache[cache_key] = None
        return None

    if year:
        for m in results:
            rd = m.get("release_date", "")
            if rd[:4] == str(year):
                cache[cache_key] = m
                return m

    best = max(results, key=lambda x: x.get("popularity", 0))
    cache[cache_key] = best
    return best

# ============================================================
# ENRICH
# ============================================================
def enrich(movie: dict) -> dict:
    result = search_tmdb(movie["Name"], movie.get("Year"))
    if result:
        poster = result.get("poster_path")
        movie["poster_path"] = poster
        movie["poster_url"]  = (IMAGE_BASE + poster) if poster else None
        movie["tmdb_id"]     = result.get("id")
    else:
        movie.setdefault("poster_path", None)
        movie.setdefault("poster_url",  None)
        movie.setdefault("tmdb_id",     None)
    return movie

# ============================================================
# SYNC
# ============================================================
def sync() -> None:
    if _TMDB_KEY_ENV:
        info("Clé TMDB chargée depuis la variable d'environnement.")
    else:
        warn("Variable TMDB_API_KEY absente — utilisation de la clé hardcodée de secours.")

    existing_movies = load_movies()

    index_by_name: dict[str, int] = {
        movie_key(m): i
        for i, m in enumerate(existing_movies)
        if is_valid_movie(m)
    }

    rss_movies = fetch_rss()

    new_movies: list[dict]  = []
    updated_count: int      = 0
    re_enriched_count: int  = 0

    for i, m in enumerate(rss_movies):
        m["Name"] = safe_str(m.get("Name"))
        key = movie_key(m)

        if key in index_by_name:
            idx      = index_by_name[key]
            existing = existing_movies[idx]

            changed = (
                existing.get("Rating")         != m.get("Rating") or
                existing.get("Date")            != m.get("Date")   or
                existing.get("Letterboxd URI")  != m.get("Letterboxd URI")
            )
            if changed:
                existing["Rating"]        = m.get("Rating")
                existing["Date"]          = m.get("Date")
                # Mise à jour du lien si le RSS fournit un meilleur lien
                if m.get("Letterboxd URI"):
                    existing["Letterboxd URI"] = m["Letterboxd URI"]
                updated_count += 1
                info(f"UPD [{i+1}/{len(rss_movies)}] {m['Name']}")

            if not existing.get("poster_url"):
                warn(f"Pas de poster pour « {m['Name']} » → tentative TMDB")
                enrich(existing)
                time.sleep(TMDB_DELAY)
                re_enriched_count += 1

        else:
            info(f"NEW [{i+1}/{len(rss_movies)}] {m['Name']}")
            m = enrich(m)
            new_movies.append(m)
            index_by_name[key] = len(existing_movies) + len(new_movies) - 1
            time.sleep(TMDB_DELAY)

    save_cache(cache)

    final    = existing_movies + new_movies
    modified = len(new_movies) > 0 or updated_count > 0 or re_enriched_count > 0

    if modified:
        save_movies(final)
        ok(
            f"Terminé — "
            f"+{len(new_movies)} ajoutés, "
            f"{updated_count} mis à jour, "
            f"{re_enriched_count} ré-enrichis"
        )
    else:
        ok("Aucune modification nécessaire.")

# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    sync()