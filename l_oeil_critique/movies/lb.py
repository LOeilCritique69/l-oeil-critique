import requests
import json
import time
import os
import xml.etree.ElementTree as ET

# =========================
# CONFIG
# =========================
RSS_URL = "https://letterboxd.com/oni_le_chan/rss/"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(BASE_DIR, "movies.json")
CACHE_FILE = os.path.join(BASE_DIR, "tmdb_cache.json")

API_KEY = "2cf75db44f938aeaf1e7d873a38fdcaa"
BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

# =========================
# CACHE TMDB
# =========================
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        cache = json.load(f)
else:
    cache = {}

def save_cache():
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

# =========================
# SAFE HELPERS
# =========================
def safe_str(v):
    if v is None:
        return ""
    return str(v).strip()

def safe_name(movie):
    return safe_str(movie.get("Name")).lower()

def is_valid_movie(m):
    return m and m.get("Name") is not None

# =========================
# LOAD LOCAL DB
# =========================
if os.path.exists(INPUT_FILE):
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        existing_movies = json.load(f)
else:
    existing_movies = []

existing_keys = {
    safe_name(m)
    for m in existing_movies
    if is_valid_movie(m)
}

# =========================
# RSS FETCH + PARSE
# =========================
def fetch_rss():
    r = requests.get(RSS_URL)
    r.raise_for_status()

    root = ET.fromstring(r.content)
    items = root.findall(".//item")

    films = []

    for item in items:

        film_title = item.find("{https://letterboxd.com}filmTitle")
        film_year = item.find("{https://letterboxd.com}filmYear")
        rating = item.find("{https://letterboxd.com}memberRating")
        watched = item.find("{https://letterboxd.com}watchedDate")

        name = safe_str(film_title.text if film_title is not None else "")
        year = film_year.text if film_year is not None else None

        if not name:
            continue

        films.append({
            "Name": name,
            "Year": int(year) if year and str(year).isdigit() else None,
            "Date": watched.text if watched is not None else None,
            "Rating": float(rating.text) if rating is not None else None
        })

    return films

# =========================
# TMDB SEARCH
# =========================
def search_movie(title, year=None):
    key = f"{title}_{year}"

    if key in cache:
        return cache[key]

    url = f"{BASE_URL}/search/movie"
    params = {
        "api_key": API_KEY,
        "query": title,
        "language": "fr-FR"
    }

    r = requests.get(url, params=params)

    if r.status_code != 200:
        cache[key] = None
        return None

    data = r.json()
    results = data.get("results", [])

    if not results:
        cache[key] = None
        return None

    if year:
        for m in results:
            rd = m.get("release_date")
            if rd and rd[:4] == str(year):
                cache[key] = m
                return m

    best = max(results, key=lambda x: x.get("popularity", 0))
    cache[key] = best
    return best

# =========================
# ENRICH
# =========================
def enrich(movie):
    result = search_movie(movie["Name"], movie.get("Year"))

    if result:
        poster = result.get("poster_path")
        movie["poster_path"] = poster
        movie["poster_url"] = IMAGE_BASE + poster if poster else None
        movie["tmdb_id"] = result.get("id")

    return movie

# =========================
# SYNC
# =========================
def sync():
    rss_movies = fetch_rss()

    new_movies = []
    updated = False

    for i, m in enumerate(rss_movies):

        key = safe_name(m)

        if key in existing_keys:
            continue

        print(f"NEW [{i+1}/{len(rss_movies)}] {m['Name']}")

        m = enrich(m)

        new_movies.append(m)
        existing_keys.add(key)

        updated = True
        time.sleep(0.2)

    final = existing_movies + new_movies

    save_cache()

    if updated:
        with open(INPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(final, f, indent=2, ensure_ascii=False)

        print(f"OK +{len(new_movies)} films ajoutés")
    else:
        print("Aucune mise à jour")

# =========================
# RUN
# =========================
if __name__ == "__main__":
    sync()