import json
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CANDIDATE_DIRS = [
    SCRIPT_DIR,
    SCRIPT_DIR / "l_oeil_critique",
    Path(r"D:\projet_webs\CHEF D'OEUVRE"),
    Path(r"D:\projet_webs\CHEF D'OEUVRE\l_oeil_critique"),
]

TARGET_ROOT = next((d for d in CANDIDATE_DIRS if (d / "assets").exists()), SCRIPT_DIR)
OUTPUT_FILE = TARGET_ROOT / "assets" / "data" / "jeux.json"
CACHE_FILE = SCRIPT_DIR / "sgdb_posters_cache.json"

SGDB_API_KEY = "7fa6fbc92089665376b8f9e79c219d15"

PLATFORM_MAP = {
    "pc": "PC",
    "ps4": "PS4",
    "ps5": "PS5",
    "playstation": "PlayStation",
    "xbox-360": "Xbox 360",
    "xbox-one": "Xbox One",
    "xbox-series": "Xbox Series",
    "switch": "Switch",
}

STATUS_MAP = {
    "played": "termine",
    "playing": "en-cours",
    "owned": "backlog",
    "dropped": "abandonne",
    "completed": "platine",
}

TITLE_FIXES = {
    "pok-mon-heartgold-version": "Pokémon HeartGold Version",
    "pok-mon-black-version": "Pokémon Black Version",
    "pok-mon-platinum-version": "Pokémon Platinum Version",
    "pok-mon-go": "Pokémon GO",
    "br-tal-legend": "Brütal Legend",
    "assassins-creed": "Assassin's Creed",
    "assassins-creed-ii": "Assassin's Creed II",
    "assassins-creed-iii": "Assassin's Creed III",
    "assassins-creed-iv-black-flag": "Assassin's Creed IV: Black Flag",
    "assassins-creed-revelations": "Assassin's Creed: Revelations",
    "assassins-creed-unity": "Assassin's Creed Unity",
    "assassins-creed-syndicate": "Assassin's Creed Syndicate",
    "assassins-creed-origins": "Assassin's Creed Origins",
    "marvels-spider-man": "Marvel's Spider-Man",
    "marvels-spider-man-remastered": "Marvel's Spider-Man Remastered",
    "marvels-spider-man-miles-morales": "Marvel's Spider-Man: Miles Morales",
    "marvels-spider-man-2": "Marvel's Spider-Man 2",
    "garrys-mod": "Garry's Mod",
    "no-mans-sky": "No Man's Sky",
    "liars-bar": "Liar's Bar",
    "mirrors-edge": "Mirror's Edge",
    "hellblade-senuas-sacrifice": "Hellblade: Senua's Sacrifice",
    "baldurs-gate-iii": "Baldur's Gate III",
    "five-nights-at-freddys": "Five Nights at Freddy's",
    "five-nights-at-freddys-4": "Five Nights at Freddy's 4",
    "devil-may-cry-3-dantes-awakening": "Devil May Cry 3: Dante's Awakening",
}


def find_loadia_file() -> Path:
    search_dirs = [
        SCRIPT_DIR,
        TARGET_ROOT,
        Path(r"D:\projet_webs"),
        Path.home() / "Downloads",
        Path.home() / "Téléchargements",
    ]
    found = []
    for folder in search_dirs:
        if folder.exists():
            found.extend(folder.rglob("*loadia*.json"))

    found = [p for p in found if p.name.lower() not in ("jeux.json", "sgdb_posters_cache.json")]

    if found:
        found.sort(key=lambda p: p.stat().st_mtime)
        return found[-1]

    user_path = input(
        "Fichier Loadia introuvable automatiquement.\n"
        "Glisse ton fichier 'loadia-export-...json' ici et appuie sur Entrée : "
    ).strip().strip('"').strip("'")
    p = Path(user_path)
    if not p.exists():
        raise FileNotFoundError(f"Fichier introuvable : {p}")
    return p


def format_title(game_id: str) -> str:
    if game_id in TITLE_FIXES:
        return TITLE_FIXES[game_id]
    words = game_id.split("-")
    roman = {"i", "ii", "iii", "iv", "v", "vi", "2k18", "2k20", "2k21", "2k22", "2k23", "2k24", "2k25"}
    return " ".join(w.upper() if w.lower() in roman else w.capitalize() for w in words)


def http_get_json(url: str, headers: dict | None = None) -> dict | None:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "LOeilCritique/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(1.5 * (attempt + 1))
                continue
            return None
        except Exception:
            time.sleep(0.5)
    return None


def fetch_sgdb_poster(title: str) -> str:
    headers = {
        "Authorization": f"Bearer {SGDB_API_KEY}",
        "User-Agent": "LOeilCritique/1.0",
    }
    encoded = urllib.parse.quote(title)
    search_url = f"https://www.steamgriddb.com/api/v2/search/autocomplete/{encoded}"
    search_data = http_get_json(search_url, headers)

    hits = (search_data or {}).get("data") or []
    if hits and hits[0].get("id"):
        game_id = hits[0]["id"]
        grids_url = f"https://www.steamgriddb.com/api/v2/grids/game/{game_id}?dimensions=600x900&types=static"
        grids_data = http_get_json(grids_url, headers)
        grids = (grids_data or {}).get("data") or []
        if grids and grids[0].get("url"):
            return grids[0]["url"]

    # Fallback Steam Store
    steam_url = f"https://store.steampowered.com/api/storesearch/?term={encoded}&l=french&cc=FR"
    steam_data = http_get_json(steam_url)
    items = (steam_data or {}).get("items") or []
    if items and items[0].get("id"):
        return f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{items[0]['id']}/library_600x900.jpg"

    return ""


def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    print(f"Dossier cible détecté : {OUTPUT_FILE}")
    input_file = find_loadia_file()
    print(f"Lecture de : {input_file}")

    raw = json.loads(input_file.read_text(encoding="utf-8"))
    private_data = raw.get("privateData", {})
    diary = private_data.get("diary", [])
    library = private_data.get("library", {})

    merged = {}

    for game_id, item in library.items():
        platforms = [PLATFORM_MAP.get(p, p.upper()) for p in item.get("platforms", [])]
        minutes = item.get("playtimeMinutes") or 0
        steam_ids = (item.get("steamImport") or {}).get("appIds") or []
        steam_id = steam_ids[0] if steam_ids else None
        rating_5 = item.get("rating")
        note_10 = round(rating_5 * 2, 1) if isinstance(rating_5, (int, float)) else None

        merged[game_id] = {
            "titre": format_title(game_id),
            "plateformes": list(dict.fromkeys(platforms)),
            "note": note_10,
            "statut": STATUS_MAP.get(item.get("status"), "termine"),
            "heures": round(minutes / 60, 1) if minutes > 0 else None,
            "date": (item.get("updatedAt") or item.get("addedAt") or "")[:7],
            "avis": "",
            **({"steam": steam_id} if steam_id else {}),
        }

    for entry in reversed(diary):
        game_id = entry.get("gameId")
        if not game_id:
            continue
        current = merged.get(game_id, {
            "titre": format_title(game_id),
            "plateformes": [],
            "note": None,
            "statut": "termine",
            "heures": None,
            "date": "",
            "avis": "",
        })
        entry_plats = [PLATFORM_MAP.get(p, p.upper()) for p in entry.get("platforms", [])]
        current["plateformes"] = list(dict.fromkeys(current["plateformes"] + entry_plats))
        if isinstance(entry.get("rating"), (int, float)):
            current["note"] = round(entry["rating"] * 2, 1)
        if entry.get("status"):
            current["statut"] = STATUS_MAP.get(entry["status"], current["statut"])
        if entry.get("date"):
            current["date"] = entry["date"][:7]
        if entry.get("review"):
            current["avis"] = entry["review"].strip()
        merged[game_id] = current

    result = list(merged.values())
    result.sort(key=lambda x: (-(x["note"] if x["note"] is not None else -1), x["titre"]))

    # Récupération des jaquettes SteamGridDB (600x900) avec cache local
    cache = load_cache()
    to_fetch = [g["titre"] for g in result if not g.get("steam") and not cache.get(g["titre"])]
    unique_to_fetch = list(dict.fromkeys(to_fetch))

    if unique_to_fetch:
        print(f"Recherche des jaquettes SteamGridDB pour {len(unique_to_fetch)} jeux...")
        done = 0
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(fetch_sgdb_poster, title): title for title in unique_to_fetch}
            for fut in as_completed(futures):
                title = futures[fut]
                url = fut.result()
                if url:
                    cache[title] = url
                done += 1
                if done % 25 == 0 or done == len(unique_to_fetch):
                    print(f"  -> {done}/{len(unique_to_fetch)} traités")
                    save_cache(cache)

    for g in result:
        if not g.get("steam") and cache.get(g["titre"]):
            g["image"] = cache[g["titre"]]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with_img = sum(1 for g in result if g.get("steam") or g.get("image"))
    print(f"OK -> {len(result)} jeux écrits ({with_img}/{len(result)} avec affiche) dans : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()