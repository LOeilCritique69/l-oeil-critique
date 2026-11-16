#!/usr/bin/env python3
"""
lb.py — Génère movies.json pour L'Œil Critique à partir d'un export Letterboxd (.zip ou dossier).
Enrichit chaque film via cache local (poster_cache.json) avec :
  - poster_url, Director, Actors, Genres (liste), Runtime (minutes)
Sources en cascade : OMDb (OMDB_KEY) -> TMDB (TMDB_API_KEY) -> Scraping og:image Letterboxd.
"""

import csv
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CACHE_FILE = BASE_DIR / "poster_cache.json"
LEGACY_CACHE_FILE = BASE_DIR / "tmdb_cache.json"
OUTPUT_FILE = BASE_DIR / "movies.json"

OMDB_KEY = os.environ.get("OMDB_KEY", "").strip()
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "").strip()
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"


def load_cache():
    cache = {}
    for path in (LEGACY_CACHE_FILE, CACHE_FILE):
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for k, v in data.items():
                    if isinstance(v, dict) and (v.get("poster_url") or v.get("poster_path")):
                        cache[k] = v
            except Exception:
                pass
    return cache


def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def norm_key(name, year):
    clean_name = re.sub(r"\s+", " ", str(name or "").strip().lower())
    return f"{clean_name}|{year or ''}"


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_runtime(raw):
    m = re.search(r"(\d+)", str(raw or ""))
    return int(m.group(1)) if m else 0


def split_csv_field(raw):
    if not raw or raw == "N/A":
        return []
    return [x.strip() for x in str(raw).split(",") if x.strip() and x.strip() != "N/A"]


def try_omdb(name, year):
    if not OMDB_KEY:
        return None
    for with_year in ([True, False] if year else [False]):
        params = {"apikey": OMDB_KEY, "t": name}
        if with_year and year:
            params["y"] = str(year)
        url = "https://www.omdbapi.com/?" + urllib.parse.urlencode(params)
        try:
            data = fetch_json(url)
            if data.get("Response") == "True":
                poster = data.get("Poster")
                director = data.get("Director")
                return {
                    "poster_url": poster if poster and poster != "N/A" else None,
                    "Director": director if director and director != "N/A" else "",
                    "Actors": ", ".join(split_csv_field(data.get("Actors"))[:4]),
                    "Genres": split_csv_field(data.get("Genre")),
                    "Runtime": parse_runtime(data.get("Runtime")),
                }
        except Exception:
            pass
    return None


def try_tmdb(name, year):
    if not TMDB_API_KEY:
        return None
    params = {"api_key": TMDB_API_KEY, "query": name, "language": "fr-FR"}
    if year:
        params["year"] = str(year)
    url = "https://api.themoviedb.org/3/search/movie?" + urllib.parse.urlencode(params)
    try:
        data = fetch_json(url)
        results = data.get("results") or []
        if not results and year:
            params.pop("year", None)
            url = "https://api.themoviedb.org/3/search/movie?" + urllib.parse.urlencode(params)
            data = fetch_json(url)
            results = data.get("results") or []
        if results and results[0].get("poster_path"):
            top = results[0]
            movie_id = top.get("id")
            info = {
                "tmdb_id": movie_id,
                "poster_path": top["poster_path"],
                "poster_url": f"https://image.tmdb.org/t/p/w500{top['poster_path']}",
            }
            if movie_id:
                try:
                    detail_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&language=fr-FR&append_to_response=credits"
                    det = fetch_json(detail_url)
                    info["Runtime"] = int(det.get("runtime") or 0)
                    info["Genres"] = [g["name"] for g in (det.get("genres") or []) if g.get("name")]
                    crew = (det.get("credits") or {}).get("crew") or []
                    directors = [c["name"] for c in crew if c.get("job") == "Director"]
                    info["Director"] = ", ".join(directors)
                    cast = (det.get("credits") or {}).get("cast") or []
                    info["Actors"] = ", ".join(c["name"] for c in cast[:4] if c.get("name"))
                except Exception:
                    pass
            return info
    except Exception:
        pass
    return None


def try_letterboxd_scrape(uri):
    if not uri or not uri.startswith("http"):
        return None
    req = urllib.request.Request(uri, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
        if not m:
            m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html)
        dir_m = re.search(r'<meta[^>]+name=["\']twitter:data1["\'][^>]+content=["\']([^"\']+)["\']', html)
        if m:
            img_url = m.group(1).strip()
            if img_url.startswith("http") and "default-share" not in img_url:
                return {
                    "poster_url": img_url,
                    "Director": dir_m.group(1).strip() if dir_m else "",
                }
    except Exception:
        pass
    return None


def fetch_metadata(name, year, uri, cache, stats):
    key = norm_key(name, year)
    cached = cache.get(key)
    # Si déjà en cache avec poster ET métadonnées (Director ou Genres déjà vérifiés), on réutilise
    if cached and cached.get("poster_url") and ("Director" in cached or not OMDB_KEY):
        return cached

    info = try_omdb(name, year) or try_tmdb(name, year) or try_letterboxd_scrape(uri)
    if info and (info.get("poster_url") or cached):
        merged = {**(cached or {}), **{k: v for k, v in info.items() if v not in (None, "", [])}}
        if "Director" not in merged:
            merged["Director"] = ""
        cache[key] = merged
        stats["fetched"] += 1
        print(f"  [+] {name} ({year or '—'})" + (f" · {merged['Director']}" if merged.get("Director") else ""))
        if stats["fetched"] % 25 == 0:
            save_cache(cache)
        time.sleep(0.15)
        return merged

    stats["missing"] += 1
    print(f"  [!] Introuvable : {name} ({year or '—'})")
    time.sleep(0.1)
    return cached or {}


def read_csv_source(source_path, filename):
    p = Path(source_path)
    if p.is_file() and p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p, "r") as zf:
            for member in zf.namelist():
                if member.endswith(filename) and "/" not in member.strip("/"):
                    raw = zf.read(member).decode("utf-8-sig")
                    return list(csv.DictReader(io.StringIO(raw)))
        return []
    target = p / filename
    if target.exists():
        with target.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    return []


def parse_rating(val):
    try:
        r = float(val)
        return round(r * 2) / 2 if r > 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def find_export_source():
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    zips = sorted(BASE_DIR.glob("letterboxd-*.zip"), key=lambda x: x.stat().st_mtime, reverse=True)
    if zips:
        return zips[0]
    return BASE_DIR


def build_movies_json(source_path):
    watched = read_csv_source(source_path, "watched.csv")
    ratings = read_csv_source(source_path, "ratings.csv")
    diary = read_csv_source(source_path, "diary.csv")
    reviews = read_csv_source(source_path, "reviews.csv")

    if not watched and not diary:
        raise FileNotFoundError(f"Aucun export Letterboxd trouvé dans {source_path}")

    cache = load_cache()
    stats = {"fetched": 0, "missing": 0}
    print(f"Cache chargé : {len(cache)} entrées déjà connues.")

    ratings_by_uri = {}
    ratings_by_ny = {}
    for row in ratings:
        uri = (row.get("Letterboxd URI") or "").strip()
        r = parse_rating(row.get("Rating"))
        if uri:
            ratings_by_uri[uri] = r
        ratings_by_ny[norm_key(row.get("Name"), row.get("Year"))] = r

    latest_diary_date = {}
    rewatch_counts = {}
    for row in diary:
        ny = norm_key(row.get("Name"), row.get("Year"))
        wdate = (row.get("Watched Date") or row.get("Date") or "").strip()
        if wdate and (ny not in latest_diary_date or wdate > latest_diary_date[ny]):
            latest_diary_date[ny] = wdate
        rewatch_counts[ny] = rewatch_counts.get(ny, 0) + 1

    catalog = []
    seen_keys = set()
    for row in watched:
        name = (row.get("Name") or "").strip()
        if not name:
            continue
        year = int(row["Year"]) if str(row.get("Year") or "").isdigit() else 0
        uri = (row.get("Letterboxd URI") or "").strip()
        ny = norm_key(name, year)
        if ny in seen_keys:
            continue
        seen_keys.add(ny)

        rating = ratings_by_uri.get(uri, ratings_by_ny.get(ny, 0.0))
        watched_date = latest_diary_date.get(ny) or (row.get("Date") or "").strip()
        meta = fetch_metadata(name, year, uri, cache, stats)

        catalog.append({
            "Name": name,
            "Year": year,
            "Date": watched_date,
            "Letterboxd URI": uri,
            "Rating": rating,
            "RewatchCount": rewatch_counts.get(ny, 1),
            **meta,
        })

    reviews_by_uri = {}
    reviews_by_ny_date = {}
    for row in reviews:
        rev_text = (row.get("Review") or "").strip()
        if not rev_text:
            continue
        uri = (row.get("Letterboxd URI") or "").strip()
        wdate = (row.get("Watched Date") or row.get("Date") or "").strip()
        if uri:
            reviews_by_uri[uri] = rev_text
        reviews_by_ny_date[(norm_key(row.get("Name"), row.get("Year")), wdate)] = rev_text

    diary_entries = []
    for row in diary:
        name = (row.get("Name") or "").strip()
        if not name:
            continue
        year = int(row["Year"]) if str(row.get("Year") or "").isdigit() else 0
        uri = (row.get("Letterboxd URI") or "").strip()
        wdate = (row.get("Watched Date") or row.get("Date") or "").strip()
        ny = norm_key(name, year)
        rating = parse_rating(row.get("Rating"))
        rewatch = str(row.get("Rewatch") or "").strip().lower() == "yes"
        tags = [t.strip() for t in str(row.get("Tags") or "").split(",") if t.strip()]
        review = reviews_by_uri.get(uri) or reviews_by_ny_date.get((ny, wdate)) or ""
        meta = fetch_metadata(name, year, uri, cache, stats)

        diary_entries.append({
            "Name": name,
            "Year": year,
            "Date": wdate,
            "LoggedDate": (row.get("Date") or "").strip(),
            "Letterboxd URI": uri,
            "Rating": rating,
            "Rewatch": rewatch,
            "Tags": tags,
            "Review": review,
            **meta,
        })

    save_cache(cache)

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "catalog": catalog,
        "diary": diary_entries,
    }
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"\nOK : {len(catalog)} films dans catalog, {len(diary_entries)} entrées dans diary "
        f"(+{stats['fetched']} enrichis, {stats['missing']} introuvables) -> {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    build_movies_json(find_export_source())