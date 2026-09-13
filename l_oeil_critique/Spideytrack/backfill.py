#!/usr/bin/env python3
"""
SpideyTrack — Backfill des archives Marveldle
════════════════════════════════════════════════════════════════════════════

Rejoue automatiquement chaque jour d'archive Marveldle, du 1er janvier 2025
jusqu'à aujourd'hui (ou jusqu'à --end), pour les 3 variantes de Spider-Man
suivies, et fusionne le résultat dans le database.json existant utilisé par
le site (même schéma que tweet.py, aucune modification du frontend requise).

À PLACER DANS LE MÊME DOSSIER QUE tweet.py.
Ce script importe tweet.py pour réutiliser : la config des personnages, les
chemins (marveldle/state.json, marveldle/database.json), le scraping des
7 cases de similarité, la détection de faux positif Andrew/Tobey, et la
validation de structure de la base.

URL D'ARCHIVE
-------------
Marveldle expose chaque jour passé à :
    https://marveldle.com/character/audiovisual/guess/archive/{M}%2F{D}%2F{Y}%2012:00:00%20AM
Exemples (mois et jour SANS zéro de tête) :
    25/08/2025 → .../archive/8%2F25%2F2025%2012:00:00%20AM
    24/08/2025 → .../archive/8%2F24%2F2025%2012:00:00%20AM
    16/07/2025 → .../archive/7%2F16%2F2025%2012:00:00%20AM

STRATÉGIE EN 2 PHASES (reprenable après interruption)
------------------------------------------------------
1. SCRAPE  : pour chaque date manquante (absente de database.json), on
   scrape les personnages demandés et on écrit le résultat au fur et à
   mesure dans marveldle/backfill_cache.json (clé = date ISO). Une
   interruption (Ctrl+C, crash, rate-limit) ne perd donc pas le travail
   déjà fait : relancer le script reprend là où il s'est arrêté.
2. MERGE   : une fois le scraping terminé (ou via --merge-only), on
   fusionne le cache dans database.json, on TRIE toutes les entrées par
   date et on réattribue des numéros de "jour" strictement chronologiques
   (1 = la date la plus ancienne connue). Les screenshots existants sont
   renommés pour suivre leur nouveau numéro de jour. state.json est mis à
   jour (current_day = dernier jour + 1) sans toucher à last_run_date.

Le cache n'est vidé qu'après une fusion réussie et validée.

USAGE
-----
    python backfill.py                          Scrape tout depuis 2025-01-01 jusqu'à hier, puis fusionne
    python backfill.py --limit 15                Ne traite que 15 dates manquantes ce run (recommandé en cron)
    python backfill.py --start 2025-03-01 --end 2025-03-31
    python backfill.py --only tom
    python backfill.py --dry-run                 Liste les dates manquantes sans rien scraper/écrire
    python backfill.py --scrape-only              Scrape et cache, ne fusionne pas encore
    python backfill.py --merge-only               Ne scrape rien, fusionne juste le cache existant
    python backfill.py --force                    Rescrape même les dates déjà en cache ou en base
    python backfill.py --sleep-min 5 --sleep-max 12   Délai (secondes) entre deux requêtes au site

⚠️  Sois raisonnable sur le rythme (--limit + délais) : ce script tape sur
    le serveur de Marveldle pour chaque jour × chaque personnage. Enchaîner
    des centaines de requêtes d'un coup est le meilleur moyen de se faire
    bloquer.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import json
import os
import random
import sys
import threading
import time
import traceback
from typing import Optional

# On réutilise tout ce qui peut l'être depuis tweet.py — une seule source de
# vérité pour la config des personnages, les chemins et le scraping.
import tweet as base
from tweet import (
    CHARACTERS,
    CHARACTERS_BY_KEY,
    CharacterConfig,
    DB_DIR,
    GuessResult,
    MAX_RETRIES,
    MIN_SCREENSHOT_BYTES,
    POST_GUESS_ANIMATION_WAIT,
    NAV_TIMEOUT_MS,
    SCRIPT_DIR,
    SQUARE_WAIT_TIMEOUT,
    detect_false_positive,
    load_database,
    load_state,
    save_database,
    save_state,
    setup_logging,
    validate_database,
)
from playwright.sync_api import sync_playwright

URL = base.URL  # https://marveldle.com/character/audiovisual/guess
CACHE_FILE = os.path.join(DB_DIR, "backfill_cache.json")
CACHE_IMAGES_DIR = os.path.join(DB_DIR, "backfill_cache_images")

DEFAULT_START = datetime.date(2025, 1, 1)

log = None  # initialisé dans main() via setup_logging
_cache_lock = threading.Lock()  # le cache (dict + fichier) est partagé entre threads en mode --workers


# ════════════════════════════════════════════════════════════════════════
# DATES & URL D'ARCHIVE
# ════════════════════════════════════════════════════════════════════════

def parse_date(s: str) -> datetime.date:
    return datetime.datetime.strptime(s, "%Y-%m-%d").date()


def iso(d: datetime.date) -> str:
    return d.isoformat()


def date_range(start: datetime.date, end: datetime.date):
    d = start
    while d <= end:
        yield d
        d += datetime.timedelta(days=1)


def archive_url(d: datetime.date) -> str:
    # Pas de zéro de tête sur mois/jour — conforme aux exemples fournis.
    return f"{URL}/archive/{d.month}%2F{d.day}%2F{d.year}%2012:00:00%20AM"


# ════════════════════════════════════════════════════════════════════════
# CACHE DE REPRISE (marveldle/backfill_cache.json)
# ════════════════════════════════════════════════════════════════════════

def load_cache() -> dict:
    if not os.path.exists(CACHE_FILE):
        return {"dates": {}}
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        raw = f.read().strip()
        if not raw:
            return {"dates": {}}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            log.error("backfill_cache.json corrompu — on repart d'un cache vide.")
            return {"dates": {}}
    data.setdefault("dates", {})
    return data


def save_cache(cache: dict) -> None:
    os.makedirs(DB_DIR, exist_ok=True)
    tmp_path = CACHE_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, CACHE_FILE)


def cache_set_char(cache: dict, date_iso: str, key: str, value: Optional[dict]) -> None:
    with _cache_lock:
        entry = cache["dates"].setdefault(date_iso, {"chars": {}})
        entry["chars"][key] = value
        save_cache(cache)


def existing_dates_in_db(db: dict) -> set[str]:
    return {
        entry.get("date")
        for entry in db.get("days", {}).values()
        if entry.get("date")
    }


# ════════════════════════════════════════════════════════════════════════
# SCRAPING D'UN JOUR D'ARCHIVE POUR UN PERSONNAGE
# (copie adaptée de tweet.play_character : mêmes sélecteurs / mêmes
#  vérifications, mais pointée vers l'URL d'archive et un screenshot
#  temporaire nommé par date plutôt que par numéro de jour — le numéro de
#  jour définitif n'est connu qu'après la fusion chronologique.)
# ════════════════════════════════════════════════════════════════════════

def play_archive_day(char: CharacterConfig, day_date: datetime.date, is_ci: bool) -> GuessResult:
    images_dir = os.path.join(CACHE_IMAGES_DIR, char.images_dir)
    os.makedirs(images_dir, exist_ok=True)
    shot_path = os.path.join(images_dir, f"{iso(day_date)}.png")
    if os.path.exists(shot_path):
        os.remove(shot_path)

    target_url = archive_url(day_date)
    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        if attempt > 0:
            wait = base._retry_wait(attempt)
            log.info("  🔄 Retry #%s dans %.1fs…", attempt, wait)
            time.sleep(wait)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=is_ci,
                    args=[
                        "--no-sandbox", "--disable-setuid-sandbox",
                        "--disable-blink-features=AutomationControlled",
                    ],
                )
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 800},
                )
                page = context.new_page()
                page.goto(target_url, wait_until="networkidle", timeout=NAV_TIMEOUT_MS)

                page.wait_for_selector(
                    "input[placeholder=\"Guess today's character\"]", timeout=15000
                )
                time.sleep(1)

                page.click("input[placeholder=\"Guess today's character\"]")
                page.type(
                    "input[placeholder=\"Guess today's character\"]",
                    char.prefix, delay=80,
                )
                time.sleep(1.5)

                option_selector = f"span.option-name:text-is('{char.option}')"
                page.wait_for_selector(option_selector, timeout=10000)
                page.click(option_selector)
                time.sleep(0.5)

                page.click("button.btn.btn-primary.search-button")
                page.wait_for_selector("div.guess-row.new")

                guessed_img = page.query_selector("div.guess-row.new img.square.image")
                described_by = (
                    guessed_img.get_attribute("aria-describedby") if guessed_img else None
                )
                guessed_label = None
                if described_by:
                    tooltip = page.query_selector(f"#{described_by}")
                    guessed_label = tooltip.inner_text().strip() if tooltip else None
                if guessed_label and guessed_label != char.option:
                    raise RuntimeError(
                        f"Mauvais personnage deviné : attendu '{char.option}', "
                        f"obtenu '{guessed_label}'"
                    )

                squares = []
                start_time = time.time()
                while True:
                    squares = page.query_selector_all("div.guess-row.new > div.similarity")
                    if len(squares) == 7:
                        break
                    if time.time() - start_time > SQUARE_WAIT_TIMEOUT:
                        break
                    time.sleep(0.2)

                if len(squares) < 7:
                    raise RuntimeError(f"Seulement {len(squares)}/7 cases trouvées")

                time.sleep(POST_GUESS_ANIMATION_WAIT)

                squares = page.query_selector_all("div.guess-row.new > div.similarity")
                if len(squares) != 7:
                    raise RuntimeError(f"Perte de cases après l'animation : {len(squares)}/7")

                square_info = []
                for sq in squares:
                    cls = sq.get_attribute("class") or ""
                    title = sq.get_attribute("title") or ""
                    square_info.append((title, cls))

                all_exact = all("exact" in cls for _, cls in square_info)
                is_wrong_char = detect_false_positive(page)
                is_match = all_exact and not is_wrong_char

                page.screenshot(path=shot_path)
                context.close()
                browser.close()

                if not os.path.exists(shot_path) or os.path.getsize(shot_path) < MIN_SCREENSHOT_BYTES:
                    raise RuntimeError(
                        f"Screenshot suspect (absent ou < {MIN_SCREENSHOT_BYTES} octets)"
                    )

                exact_count = sum(1 for _, cls in square_info if "exact" in cls)
                partial_count = sum(1 for _, cls in square_info if "partial" in cls)

                return GuessResult(
                    success=True, is_match=is_match,
                    exact=exact_count, partial=partial_count,
                    screenshot=shot_path,  # chemin ABSOLU temporaire — finalisé lors de la fusion
                )

        except Exception as e:  # noqa: BLE001
            last_error = str(e)
            log.error("  ❌ Erreur (%s, %s) : %s", char.label, iso(day_date), e)
            if attempt == MAX_RETRIES:
                traceback.print_exc()

    return GuessResult(success=False, error=last_error)


# ════════════════════════════════════════════════════════════════════════
# PHASE 1 — SCRAPE
# ════════════════════════════════════════════════════════════════════════

def missing_dates(db: dict, cache: dict, start: datetime.date, end: datetime.date,
                   characters: list[CharacterConfig], force: bool) -> list[datetime.date]:
    done_in_db = existing_dates_in_db(db)
    out = []
    for d in date_range(start, end):
        key = iso(d)
        if not force and key in done_in_db:
            continue
        if not force:
            cached = cache["dates"].get(key, {}).get("chars", {})
            if all(c.key in cached and cached[c.key] is not None for c in characters):
                continue
        out.append(d)
    return out


def _scrape_one(task: tuple[datetime.date, CharacterConfig], cache: dict, is_ci: bool,
                 sleep_min: float, sleep_max: float) -> None:
    d, char = task
    key = iso(d)
    log.info("▶️  %s — %s…", key, char.label)
    result = play_archive_day(char, d, is_ci)
    if result.success:
        weighted = result.exact + result.partial * 0.5
        verdict = "✅ C'est lui !" if result.is_match else "❌ Pas lui."
        log.info("✔️  %s — %s : %s (%s/7 exacts, %s/7 partiels)",
                  key, char.label, verdict, result.exact, result.partial)
        cache_set_char(cache, key, char.key, {
            "result": result.is_match,
            "exact": result.exact,
            "partial": result.partial,
            "score": result.exact,
            "weighted": weighted,
            "screenshot": result.screenshot,  # chemin absolu temporaire
        })
    else:
        log.error("🚫 %s — %s : abandon (%s)", key, char.label, result.error)
        cache_set_char(cache, key, char.key, None)

    # Petit délai poli même en parallèle, décalé aléatoirement pour ne pas
    # faire retomber tous les workers en même temps sur la requête suivante.
    time.sleep(random.uniform(sleep_min, sleep_max))


def run_scrape(db: dict, cache: dict, targets: list[datetime.date],
               characters: list[CharacterConfig], is_ci: bool,
               sleep_min: float, sleep_max: float, force: bool, workers: int) -> None:
    tasks: list[tuple[datetime.date, CharacterConfig]] = []
    for d in targets:
        key = iso(d)
        for char in characters:
            already = cache["dates"].get(key, {}).get("chars", {}).get(char.key)
            if already is not None and not force:
                continue
            tasks.append((d, char))

    if not tasks:
        return

    log.info("🧵 %s tâche(s) (date × personnage) à traiter avec %s worker(s) en parallèle.",
              len(tasks), workers)

    if workers <= 1:
        for t in tasks:
            _scrape_one(t, cache, is_ci, sleep_min, sleep_max)
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_scrape_one, t, cache, is_ci, sleep_min, sleep_max) for t in tasks]
        for f in concurrent.futures.as_completed(futures):
            exc = f.exception()
            if exc:
                log.error("🚫 Tâche échouée dans un worker : %s", exc)


# ════════════════════════════════════════════════════════════════════════
# PHASE 2 — MERGE & RENUMÉROTATION CHRONOLOGIQUE
# ════════════════════════════════════════════════════════════════════════

def run_merge(db: dict, cache: dict) -> tuple[dict, int]:
    """Fusionne le cache dans db, renumérote tout par date, renomme les
    screenshots en conséquence. Retourne (nouvelle_db, nb_dates_fusionnees).
    Ne modifie PAS db en place tant que tout n'a pas réussi (return only)."""

    # 1. Reconstituer un index date -> {date, chars} à partir de la base actuelle.
    by_date: dict[str, dict] = {}
    for entry in db.get("days", {}).values():
        d = entry.get("date")
        if not d:
            continue
        slot = by_date.setdefault(d, {"date": d, "chars": {}})
        slot["chars"].update({k: v for k, v in (entry.get("chars") or {}).items() if v})

    # 2. Fusionner le cache : on ne fusionne une date que si au moins un
    #    personnage y a un résultat exploitable, et on ne remplace jamais un
    #    résultat déjà validé en base par un résultat du cache (la base fait foi).
    merged_count = 0
    for date_iso, centry in cache.get("dates", {}).items():
        chars = centry.get("chars", {})
        if not any(c for c in chars.values()):
            continue  # rien d'exploitable pour cette date, on la laisse en cache pour retry
        slot = by_date.setdefault(date_iso, {"date": date_iso, "chars": {}})
        added_here = False
        for key, c in chars.items():
            if c is None:
                continue
            if slot["chars"].get(key):
                continue  # déjà présent (venant de la base), on ne l'écrase pas
            slot["chars"][key] = c
            added_here = True
        if added_here:
            merged_count += 1

    if not by_date:
        return db, 0

    # 3. Trier chronologiquement et réattribuer des numéros de jour 1..N.
    ordered_dates = sorted(by_date.keys())

    # 4. Renommer les screenshots en 2 passes (temp puis final) pour éviter
    #    tout écrasement croisé pendant la renumérotation.
    temp_moves: list[tuple[str, str]] = []   # (temp_abs, final_abs)
    for new_day, date_iso in enumerate(ordered_dates, start=1):
        slot = by_date[date_iso]
        for key, c in slot["chars"].items():
            char = CHARACTERS_BY_KEY[key]
            old_path = c.get("screenshot")
            if not old_path:
                continue
            old_abs = old_path if os.path.isabs(old_path) else os.path.join(SCRIPT_DIR, old_path)
            final_rel = f"marveldle/{char.images_dir}/day_{new_day:03}.png"
            final_abs = os.path.join(SCRIPT_DIR, final_rel)
            if not os.path.exists(old_abs):
                log.warning("  ⚠️  Screenshot manquant sur disque, ignoré : %s", old_abs)
                c["screenshot"] = final_rel  # on garde quand même la référence attendue
                continue
            if os.path.abspath(old_abs) == os.path.abspath(final_abs):
                continue
            tmp_abs = final_abs + f".tmp{new_day}"
            os.makedirs(os.path.dirname(final_abs), exist_ok=True)
            os.replace(old_abs, tmp_abs)
            temp_moves.append((tmp_abs, final_abs))
            c["screenshot"] = final_rel

    for tmp_abs, final_abs in temp_moves:
        os.replace(tmp_abs, final_abs)

    # 5. Construire la nouvelle base.
    new_db = {"meta": db.get("meta", {"version": 2}), "days": {}}
    for new_day, date_iso in enumerate(ordered_dates, start=1):
        slot = by_date[date_iso]
        new_db["days"][str(new_day)] = {"date": slot["date"], "chars": slot["chars"]}

    validate_database(new_db)
    return new_db, merged_count


# ════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SpideyTrack — backfill des archives Marveldle")
    p.add_argument("--start", default=iso(DEFAULT_START), help="Date de début (YYYY-MM-DD), défaut 2025-01-01.")
    p.add_argument("--end", default=None, help="Date de fin (YYYY-MM-DD), défaut hier.")
    p.add_argument("--only", choices=[c.key for c in CHARACTERS], help="Ne traiter qu'un seul personnage.")
    p.add_argument("--limit", type=int, default=None, help="Nombre max de dates à scraper ce run.")
    p.add_argument("--dry-run", action="store_true", help="Liste les dates manquantes sans rien faire.")
    p.add_argument("--scrape-only", action="store_true", help="Scrape et met en cache sans fusionner.")
    p.add_argument("--merge-only", action="store_true", help="Fusionne le cache existant sans scraper.")
    p.add_argument("--force", action="store_true", help="Rescrape même si déjà en cache/base.")
    p.add_argument("--sleep-min", type=float, default=5.0, help="Délai minimum (s) entre deux requêtes, par worker.")
    p.add_argument("--sleep-max", type=float, default=12.0, help="Délai maximum (s) entre deux requêtes, par worker.")
    p.add_argument("--workers", type=int, default=1,
                   help="Nombre de scrapes en parallèle (chacun avec son propre navigateur). "
                        "Défaut 1 (séquentiel). 3 est un bon compromis (un par personnage). "
                        "Au-delà, risque accru de rate-limit / blocage par Marveldle.")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    global log
    log = setup_logging(args.verbose)
    os.chdir(SCRIPT_DIR)

    start = parse_date(args.start)
    end = parse_date(args.end) if args.end else (datetime.date.today() - datetime.timedelta(days=1))
    if end < start:
        log.error("🚫 --end (%s) est antérieur à --start (%s).", end, start)
        return 1

    characters = [CHARACTERS_BY_KEY[args.only]] if args.only else list(CHARACTERS)
    is_ci = os.environ.get("CI") == "true"

    try:
        db = load_database()
    except (ValueError, json.JSONDecodeError):
        log.error("🚫 database.json invalide — abandon sans rien écraser.")
        return 1
    cache = load_cache()

    if not args.merge_only:
        targets = missing_dates(db, cache, start, end, characters, args.force)
        if args.limit is not None:
            targets = targets[: args.limit]

        log.info("🎯 %s date(s) à traiter entre %s et %s.", len(targets), start, end)
        if args.dry_run:
            for d in targets:
                log.info("   [dry-run] %s → %s", iso(d), archive_url(d))
            return 0

        if targets:
            run_scrape(db, cache, targets, characters, is_ci, args.sleep_min, args.sleep_max,
                       args.force, max(1, args.workers))
        else:
            log.info("✅ Rien à scraper (tout est déjà en base ou en cache).")

    if args.scrape_only:
        log.info("🧪 --scrape-only : pas de fusion. Relance avec --merge-only quand tu es prêt.")
        return 0

    log.info("%s", "─" * 55)
    log.info("  🔀 FUSION dans database.json")
    log.info("%s", "─" * 55)
    try:
        new_db, merged_count = run_merge(db, cache)
    except ValueError as e:
        log.error("🚫 Fusion refusée, structure invalide : %s", e)
        return 1

    if merged_count == 0 and new_db == db:
        log.info("ℹ️  Rien de nouveau à fusionner.")
        return 0

    save_database(new_db)

    reloaded = load_database()
    if reloaded != new_db:
        log.error("🚫 VÉRIFICATION ÉCHOUÉE après écriture — investigation nécessaire, cache conservé.")
        return 1

    total_days = len(new_db["days"])
    state = load_state()
    state["current_day"] = total_days + 1
    save_state(state)

    # Cache vidé uniquement après fusion + vérification réussies.
    save_cache({"dates": {}})

    log.info("✅ %s date(s) fusionnée(s). Base = %s jours au total. Prochain jour live : %s.",
              merged_count, total_days, total_days + 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())