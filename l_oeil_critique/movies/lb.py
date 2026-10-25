"""
lb.py — Letterboxd → movies.json, avec posters TMDB FIABLES

Pourquoi l'ancienne version se trompait de poster :
  elle cherchait par titre et, si l'année ne collait pas, prenait « le plus populaire ».
Ici :
  1. Le flux RSS Letterboxd donne l'identifiant TMDB exact (tmdb:movieId) -> aucune recherche.
  2. Pour les anciens films (export CSV), recherche STRICTE : année à ±1 ET titre quasi identique.
     Sinon le film est mis « à vérifier » (pas de poster plutôt qu'un mauvais) -> a_verifier.json.
  3. overrides.json permet de forcer un identifiant TMDB à la main.

Usage :
  python lb.py                 sync RSS + résout les films sans poster
  python lb.py --rematch-all   re-vérifie TOUS les films hérités de l'export CSV (à faire une fois)
  python lb.py --report        liste les films à vérifier (aucun appel réseau)

Clé API : variable d'environnement TMDB_API_KEY, ou fichier tmdb_key.txt à côté du script.
"""
import argparse, difflib, json, os, re, sys, time, unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
import requests

RSS_URL = "https://letterboxd.com/oni_le_chan/rss/"
BASE = os.path.dirname(os.path.abspath(__file__))
MOVIES_FILE    = os.path.join(BASE, "movies.json")
CACHE_FILE     = os.path.join(BASE, "tmdb_cache_v2.json")   # nouveau cache (l'ancien est pollué)
OVERRIDES_FILE = os.path.join(BASE, "overrides.json")
REVIEW_FILE    = os.path.join(BASE, "a_verifier.json")
KEY_FILE       = os.path.join(BASE, "tmdb_key.txt")

NS_LB, NS_TMDB = "https://letterboxd.com", "https://themoviedb.org"
API, IMG = "https://api.themoviedb.org/3", "https://image.tmdb.org/t/p/w500"
DELAY, RETRIES = 0.2, 3
TRUSTED = {"rss", "override"}            # sources qu'on ne remet jamais en question

def log(p, m): print(f"[{datetime.now():%H:%M:%S}] {p:5s} {m}")

# ---------- utilitaires purs (testables) ----------
def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower().strip()
    s = re.sub(r"^(the|a|an|le|la|les|l)\s+", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def sim(a, b): return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()
def movie_key(m): return f"{norm(m.get('Name'))}|{m.get('Year') or ''}"

def choose_match(name, year, candidates):
    """Retourne (candidat | None, top3). Accepte seulement année ±1 ET titre >= 0.85."""
    scored = []
    for c in candidates:
        ry = (c.get("release_date") or "")[:4]
        dy = abs(int(ry) - int(year)) if ry.isdigit() and year else 99
        s = max(sim(name, c.get("title")), sim(name, c.get("original_title")))
        scored.append((dy, s, c))
    ok = [t for t in scored if t[0] <= 1 and t[1] >= 0.85]
    if ok:
        dy, s, c = min(ok, key=lambda t: (t[0], -t[1], -(t[2].get("popularity") or 0)))
        return c, []
    top = sorted(scored, key=lambda t: (-t[1], t[0]))[:3]
    return None, [{"tmdb_id": c["id"], "title": c.get("title"), "year": (c.get("release_date") or "")[:4],
                   "similarite": round(s, 2)} for _, s, c in top]

# ---------- clé / cache / réseau ----------
def get_key():
    k = os.environ.get("TMDB_API_KEY", "").strip()
    if not k and os.path.exists(KEY_FILE):
        k = open(KEY_FILE, encoding="utf-8").read().strip()
    if not k:
        sys.exit("Clé TMDB manquante : définis TMDB_API_KEY ou crée tmdb_key.txt à côté de lb.py.")
    return k

def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError: return default
    except json.JSONDecodeError: log("WARN", f"{os.path.basename(path)} illisible, ignoré."); return default

def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

class Tmdb:
    def __init__(self, key):
        self.key, self.cache, self.calls = key, read_json(CACHE_FILE, {}), 0
    def save(self): write_json(CACHE_FILE, self.cache)
    def _get(self, path, **params):
        params["api_key"] = self.key
        for i in range(1, RETRIES + 1):
            try:
                r = requests.get(f"{API}{path}", params=params, timeout=10)
                if r.status_code == 401: sys.exit("Clé TMDB refusée (401). Vérifie ta clé.")
                if r.status_code == 429: time.sleep(int(r.headers.get("Retry-After", 2))); continue
                r.raise_for_status(); time.sleep(DELAY)
                self.calls += 1
                if self.calls % 25 == 0: self.save()
                return r.json()
            except requests.RequestException as e:
                log("WARN", f"{path} tentative {i}/{RETRIES} : {e}"); time.sleep(2)
        return None
    def movie(self, tid):
        k = f"movie:{tid}"
        if k not in self.cache:
            d = self._get(f"/movie/{tid}", language="fr-FR")
            if d and not d.get("poster_path"):                     # pas d'affiche FR -> affiche d'origine
                d2 = self._get(f"/movie/{tid}")
                if d2: d["poster_path"] = d2.get("poster_path")
            if d: self.cache[k] = {x: d.get(x) for x in ("id", "title", "original_title", "release_date", "poster_path")}
        return self.cache.get(k)
    def search(self, name, year):
        k = f"search:{norm(name)}|{year or ''}"
        if k not in self.cache:
            d = self._get("/search/movie", query=name, language="en-US", include_adult="false")
            if d is None: return None
            self.cache[k] = [{x: c.get(x) for x in ("id", "title", "original_title", "release_date", "popularity")}
                             for c in d.get("results", [])[:10]]
        return self.cache[k]

# ---------- résolution d'un film ----------
def apply_tmdb(m, tid, source, tmdb):
    d = tmdb.movie(tid)
    if not d: return False
    m.update(tmdb_id=tid, tmdb_source=source, tmdb_title=d.get("title"),
             tmdb_year=(d.get("release_date") or "")[:4] or None,
             poster_path=d.get("poster_path"),
             poster_url=(IMG + d["poster_path"]) if d.get("poster_path") else None)
    return True

def resolve(m, tmdb, overrides, review, force=False):
    key = f"{m.get('Name')}|{m.get('Year')}"
    old = m.get("tmdb_id")
    if key in overrides:
        apply_tmdb(m, int(overrides[key]), "override", tmdb)
    elif m.get("tmdb_source") in TRUSTED and m.get("poster_url") and not force:
        return
    elif m.get("tmdb_source") == "rss" and m.get("tmdb_id"):
        apply_tmdb(m, m["tmdb_id"], "rss", tmdb)
    else:
        cands = tmdb.search(m["Name"], m.get("Year"))
        if cands is None: return
        best, top = choose_match(m["Name"], m.get("Year"), cands)
        if best: apply_tmdb(m, best["id"], "search", tmdb)
        else:
            m.update(tmdb_id=None, tmdb_source="review", poster_path=None, poster_url=None)
            review.append({"cle": key, "Name": m["Name"], "Year": m.get("Year"), "candidats": top})
            log("CHECK", f"{m['Name']} ({m.get('Year')}) : aucun candidat sûr")
            return
    if old and old != m.get("tmdb_id"):
        log("FIX", f"{m['Name']} ({m.get('Year')}) : {old} -> {m.get('tmdb_id')}  ({m.get('tmdb_title')})")

# ---------- RSS ----------
def fetch_rss():
    log("INFO", f"RSS : {RSS_URL}")
    try:
        r = requests.get(RSS_URL, timeout=15); r.raise_for_status()
    except requests.RequestException as e:
        sys.exit(f"RSS inaccessible : {e}")
    out = []
    for item in ET.fromstring(r.content).findall(".//item"):
        g = lambda ns, t: (item.findtext(f"{{{ns}}}{t}") or "").strip() or None
        name = g(NS_LB, "filmTitle")
        if not name: continue
        yr, rt, tid = g(NS_LB, "filmYear"), g(NS_LB, "memberRating"), g(NS_TMDB, "movieId")
        out.append({"Name": name, "Year": int(yr) if yr and yr.isdigit() else None,
                    "Date": g(NS_LB, "watchedDate"), "Rating": float(rt) if rt else None,
                    "Letterboxd URI": (item.findtext("link") or "").strip() or None,
                    "tmdb_id": int(tid) if tid and tid.isdigit() else None})
    log("INFO", f"{len(out)} entrées RSS")
    return out

# ---------- commandes ----------
def report():
    movies = read_json(MOVIES_FILE, [])
    bad = [m for m in movies if m.get("tmdb_source") == "review" or not m.get("poster_url")]
    legacy = [m for m in movies if "tmdb_source" not in m]
    print(f"{len(movies)} films | {len(legacy)} jamais vérifiés (lance --rematch-all) | {len(bad)} sans poster / à vérifier")
    for m in bad: print(f"  - {m['Name']} ({m.get('Year')})")
    if os.path.exists(REVIEW_FILE): print(f"Détails + candidats : {REVIEW_FILE}")

def sync(rematch_all):
    tmdb, overrides = Tmdb(get_key()), read_json(OVERRIDES_FILE, {})
    movies, review = read_json(MOVIES_FILE, []), []
    index = {movie_key(m): m for m in movies if m.get("Name")}
    new = upd = 0
    for r in fetch_rss():
        m = index.get(movie_key(r))
        if m is None:
            m = {k: v for k, v in r.items() if k != "tmdb_id"}
            if r["tmdb_id"]: m["tmdb_id"], m["tmdb_source"] = r["tmdb_id"], "rss"
            movies.append(m); index[movie_key(m)] = m; new += 1; log("NEW", f"{m['Name']} ({m.get('Year')})")
            continue
        if r["Rating"] is not None and r["Rating"] != m.get("Rating"): m["Rating"] = r["Rating"]; upd += 1   # jamais écraser par « sans note »
        if r["Date"] and (m.get("Date") or "") < r["Date"]: m["Date"] = r["Date"]; upd += 1
        if r["Letterboxd URI"] and not m.get("Letterboxd URI"): m["Letterboxd URI"] = r["Letterboxd URI"]
        if r["tmdb_id"] and r["tmdb_id"] != m.get("tmdb_id") or (r["tmdb_id"] and m.get("tmdb_source") != "rss"):
            m["tmdb_id"], m["tmdb_source"], m["poster_url"] = r["tmdb_id"], "rss", None                    # RSS = vérité
    todo = [m for m in movies if rematch_all and m.get("tmdb_source") not in TRUSTED
            or not m.get("poster_url") or m.get("tmdb_source") is None and not m.get("tmdb_id")]
    log("INFO", f"{len(todo)} film(s) à résoudre")
    for i, m in enumerate(todo, 1):
        resolve(m, tmdb, overrides, review, force=rematch_all)
        if i % 25 == 0: write_json(MOVIES_FILE, movies); log("INFO", f"{i}/{len(todo)}")
    tmdb.save(); write_json(MOVIES_FILE, movies); write_json(REVIEW_FILE, review)
    log("OK", f"+{new} nouveaux, {upd} mis à jour, {len(review)} à vérifier (voir a_verifier.json)")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--rematch-all", action="store_true"); ap.add_argument("--report", action="store_true")
    a = ap.parse_args(); report() if a.report else sync(a.rematch_all)