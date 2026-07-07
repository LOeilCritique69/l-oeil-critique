#!/usr/bin/env python3
"""
SpideyTrack — Daily Guess Runner
════════════════════════════════════════════════════════════════════════════

Joue automatiquement le Marveldle du jour pour les 3 variantes de Spider-Man
suivies (Tom Holland, Andrew Garfield, Tobey Maguire), et persiste le résultat
dans une base de données JSON unique.

ARCHITECTURE (v2)
------------------
Avant, chaque personnage avait son propre fichier de "jour" (day.txt,
day-andrew.txt, day_tobey.txt), son propre results_*.json, plus un
history.csv et un last_run.txt séparés. Résultat : ces fichiers pouvaient
diverger silencieusement (ce qui est arrivé : le workflow GitHub Actions
ne commitait jamais history.csv ni last_run.txt, qui sont restés bloqués
pendant que results.json continuait d'avancer).

Ce script repose maintenant sur exactement DEUX fichiers, tous les deux
sous marveldle/ :

  - state.json      → { "current_day": int, "last_run_date": "YYYY-MM-DD" }
                       LE compteur de jour, partagé par les 3 personnages
                       (ils jouent toujours le même numéro de jour).

  - database.json    → { "days": { "<day>": { "date": ..., "chars": {
                         "tom": {...}, "andrew": {...}, "tobey": {...} } } } }
                       LA base de données unique, lue directement par le
                       frontend (plus d'injection HTML fragile par regex).

Un vrai système de vérification protège contre la dérive :
  1. Avant de jouer : le jour "attendu" est recalculé depuis database.json
     (max des jours déjà enregistrés + 1). Si state.json ne correspond
     pas, on se corrige automatiquement et on log un WARNING.
  2. Après écriture : on relit database.json depuis le disque et on
     vérifie que le jour joué est bien présent avec les bonnes clés.
     Si ce n'est pas le cas, on n'avance PAS state.json et on sort en
     erreur (code 1) — le run GitHub Actions passe au rouge au lieu de
     dériver en silence.

USAGE
-----
    python tweet.py                  Run normal (1 jour, les 3 persos)
    python tweet.py --dry-run        Simule sans rien écrire ni jouer
    python tweet.py --force          Ignore le garde-fou "déjà joué aujourd'hui"
    python tweet.py --only tom       Ne joue qu'un seul personnage
    python tweet.py --day 150        Force un numéro de jour (rattrapage/debug)
    python tweet.py --export-csv out.csv   Exporte database.json en CSV
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from typing import Optional

from playwright.sync_api import sync_playwright, Page

# ════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════

URL = "https://marveldle.com/character/audiovisual/guess"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(SCRIPT_DIR, "marveldle")
STATE_FILE = os.path.join(DB_DIR, "state.json")
DATABASE_FILE = os.path.join(DB_DIR, "database.json")
HTML_FILE = os.path.join(DB_DIR, "marveldle.html")

MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = (3, 8)  # backoff croissant entre tentatives
SQUARE_WAIT_TIMEOUT = 10        # secondes d'attente des 7 cases de similarité
POST_GUESS_ANIMATION_WAIT = 10  # secondes d'attente de l'animation du site
MIN_SCREENSHOT_BYTES = 2048     # en dessous de ça, le screenshot est suspect


@dataclass(frozen=True)
class CharacterConfig:
    key: str            # clé interne stable (tom / andrew / tobey)
    label: str          # nom affiché
    prefix: str         # texte tapé dans le champ de recherche
    option: str         # libellé exact de l'option à cliquer
    images_dir: str     # dossier des screenshots (relatif à marveldle/)


CHARACTERS: tuple[CharacterConfig, ...] = (
    CharacterConfig(
        key="tom", label="Tom Holland", prefix="Spider-Ma",
        option="Spider-Man", images_dir="images",
    ),
    CharacterConfig(
        key="andrew", label="Andrew Garfield", prefix="Spider-Man (R",
        option="Spider-Man (Rageful Vigilante Spider-Man Universe)",
        images_dir="images_andrew",
    ),
    CharacterConfig(
        key="tobey", label="Tobey Maguire", prefix="Spider-Man (O",
        option="Spider-Man (Organic Webbing Spider-Man Universe)",
        images_dir="images_tobey",
    ),
)
CHARACTERS_BY_KEY = {c.key: c for c in CHARACTERS}


# ════════════════════════════════════════════════════════════════════════
# LOGGING
# ════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("spideytrack")


# ════════════════════════════════════════════════════════════════════════
# ÉTAT (state.json) — le compteur de jour unique
# ════════════════════════════════════════════════════════════════════════

def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        log.warning("state.json introuvable, initialisation à day=1.")
        return {"current_day": 1, "last_run_date": None}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            log.error("state.json corrompu — réinitialisation à day=1.")
            return {"current_day": 1, "last_run_date": None}


def save_state(state: dict) -> None:
    os.makedirs(DB_DIR, exist_ok=True)
    tmp_path = STATE_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, STATE_FILE)  # écriture atomique


# ════════════════════════════════════════════════════════════════════════
# BASE DE DONNÉES (database.json)
# ════════════════════════════════════════════════════════════════════════

def load_database() -> dict:
    if not os.path.exists(DATABASE_FILE):
        return {"meta": {"version": 2}, "days": {}}
    with open(DATABASE_FILE, "r", encoding="utf-8") as f:
        raw = f.read().strip()
        if not raw:
            return {"meta": {"version": 2}, "days": {}}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            log.error("database.json corrompu — abandon (ne rien écraser).")
            raise


def save_database(db: dict) -> None:
    os.makedirs(DB_DIR, exist_ok=True)
    tmp_path = DATABASE_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, DATABASE_FILE)


def expected_next_day(db: dict) -> int:
    """Le prochain jour à jouer, déduit des données réellement enregistrées.

    C'est la SOURCE DE VÉRITÉ. state.json n'est qu'un cache de cette valeur ;
    s'il diverge, on lui fait confiance à database.json, pas l'inverse.
    """
    days = db.get("days", {})
    if not days:
        return 1
    return max(int(k) for k in days.keys()) + 1


def reconcile_day(state: dict, db: dict) -> int:
    """Vérifie state.json contre database.json et se corrige si besoin.

    Retourne le jour à jouer aujourd'hui.
    """
    expected = expected_next_day(db)
    recorded = state.get("current_day")
    if recorded != expected:
        log.warning(
            "⚠️  Incohérence détectée : state.json annonçait le jour %s, "
            "mais database.json indique que le prochain jour attendu est %s. "
            "Auto-correction sur la base de database.json (source de vérité).",
            recorded, expected,
        )
        state["current_day"] = expected
    return expected


# ════════════════════════════════════════════════════════════════════════
# SCRAPING D'UN PERSONNAGE
# ════════════════════════════════════════════════════════════════════════

@dataclass
class GuessResult:
    success: bool
    is_match: Optional[bool] = None
    exact: int = 0
    partial: int = 0
    screenshot: Optional[str] = None
    error: Optional[str] = None


def detect_false_positive(page: Page) -> bool:
    """Andrew Garfield et Tobey Maguire partagent des attributs identiques
    dans le jeu : un 7/7 exacts ne suffit donc pas à confirmer qu'on a
    trouvé LE bon personnage. Le site affiche une bannière dédiée quand
    ce n'est pas le bon Spider-Man malgré un score parfait — on la
    cherche dans le texte de la page.
    """
    page_text = page.inner_text("body").lower()
    return (
        "pas celui que l'on cherche" in page_text
        or "today's character isn't this one" in page_text
    )


def play_character(char: CharacterConfig, day: int, is_ci: bool) -> GuessResult:
    """Joue le Marveldle du jour pour un personnage donné, avec retries."""
    images_dir = os.path.join(DB_DIR, char.images_dir)
    os.makedirs(images_dir, exist_ok=True)
    shot_path = os.path.join(images_dir, f"day_{day:03}.png")
    shot_rel_path = f"marveldle/{char.images_dir}/day_{day:03}.png"
    if os.path.exists(shot_path):
        os.remove(shot_path)

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        if attempt > 0:
            wait = RETRY_BACKOFF_SECONDS[min(attempt - 1, len(RETRY_BACKOFF_SECONDS) - 1)]
            log.info("  🔄 Retry #%s dans %ss…", attempt, wait)
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
                page.goto(URL, wait_until="networkidle", timeout=30000)

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

                option_selector = f"span.option-name:has-text('{char.option}')"
                page.wait_for_selector(option_selector, timeout=10000)
                page.click(option_selector)
                time.sleep(0.5)

                page.click("button.btn.btn-primary.search-button")
                page.wait_for_selector("div.guess-row.new")

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

                square_info = []
                for sq in squares:
                    cls = sq.get_attribute("class") or ""
                    title = sq.get_attribute("title") or ""
                    square_info.append((title, cls))
                    log.info("    · %s → %s", title, cls)

                all_exact = all("exact" in cls for _, cls in square_info)
                is_wrong_char = detect_false_positive(page)
                is_match = all_exact and not is_wrong_char
                if all_exact and is_wrong_char:
                    log.info("  ⚠️  7/7 exacts MAIS faux positif détecté — mauvais Spider-Man.")

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
                    screenshot=shot_rel_path,
                )

        except Exception as e:  # noqa: BLE001 — on veut catcher large ici, on retry
            last_error = str(e)
            log.error("  ❌ Erreur : %s", e)
            if attempt == MAX_RETRIES:
                traceback.print_exc()

    return GuessResult(success=False, error=last_error)


# ════════════════════════════════════════════════════════════════════════
# STATS (dérivées de database.json, pour le récap console uniquement —
# le frontend calcule les siennes lui-même à partir de database.json)
# ════════════════════════════════════════════════════════════════════════

def compute_streak(db: dict, key: str) -> int:
    days = sorted(db.get("days", {}).items(), key=lambda kv: -int(kv[0]))
    streak = 0
    for _, entry in days:
        c = entry.get("chars", {}).get(key)
        if c is None:
            continue
        if c.get("result") is True:
            streak += 1
        else:
            break
    return streak


def compute_win_rate(db: dict, key: str) -> tuple[int, int, float]:
    days = db.get("days", {}).values()
    total = sum(1 for d in days if d.get("chars", {}).get(key) is not None)
    wins = sum(1 for d in days if d.get("chars", {}).get(key, {}).get("result") is True)
    rate = round(wins / total * 100, 1) if total else 0.0
    return wins, total, rate


# ════════════════════════════════════════════════════════════════════════
# EXPORT CSV (utilitaire à la demande, pas utilisé dans le run quotidien)
# ════════════════════════════════════════════════════════════════════════

def export_csv(db: dict, out_path: str) -> None:
    import csv
    rows = []
    for day_key, entry in sorted(db.get("days", {}).items(), key=lambda kv: int(kv[0])):
        for char_key, cdata in entry.get("chars", {}).items():
            if cdata is None:
                continue
            rows.append({
                "day": day_key, "date": entry.get("date"),
                "character": CHARACTERS_BY_KEY[char_key].label,
                "result": cdata.get("result"),
                "exact": cdata.get("exact"), "partial": cdata.get("partial"),
                "score": cdata.get("score"), "weighted": cdata.get("weighted"),
                "screenshot": cdata.get("screenshot"),
            })
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "day", "date", "character", "result",
            "exact", "partial", "score", "weighted", "screenshot",
        ])
        writer.writeheader()
        writer.writerows(rows)
    log.info("✅ Export CSV écrit : %s (%s lignes)", out_path, len(rows))


# ════════════════════════════════════════════════════════════════════════
# RUN PRINCIPAL
# ════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SpideyTrack daily runner")
    p.add_argument("--dry-run", action="store_true",
                    help="Simule sans jouer ni écrire aucun fichier.")
    p.add_argument("--force", action="store_true",
                    help="Ignore le garde-fou 'déjà joué aujourd'hui'.")
    p.add_argument("--only", choices=[c.key for c in CHARACTERS],
                    help="Ne joue qu'un seul personnage.")
    p.add_argument("--day", type=int,
                    help="Force un numéro de jour précis (rattrapage / debug).")
    p.add_argument("--export-csv", metavar="PATH",
                    help="N'exécute rien : exporte database.json en CSV vers PATH.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    os.chdir(SCRIPT_DIR)

    if args.export_csv:
        db = load_database()
        export_csv(db, args.export_csv)
        return 0

    today = datetime.date.today()
    today_iso = today.isoformat()
    is_ci = os.environ.get("CI") == "true"

    state = load_state()
    db = load_database()

    # ── 1. Garde-fou "déjà joué aujourd'hui" ────────────────────────────
    if not args.force and state.get("last_run_date") == today_iso:
        log.info("✅ Script déjà lancé aujourd'hui (%s). Rien à faire.", today_iso)
        return 0

    # ── 2. Vérification / auto-correction du jour ───────────────────────
    day = args.day if args.day is not None else reconcile_day(state, db)
    log.info("🎯 Jour à jouer : %s", day)

    if str(day) in db.get("days", {}) and not args.day:
        log.warning("⚠️  Le jour %s est déjà dans database.json — on avance sans rejouer.", day)
        if not args.dry_run:
            state["current_day"] = day + 1
            state["last_run_date"] = today_iso
            save_state(state)
        return 0

    characters = [CHARACTERS_BY_KEY[args.only]] if args.only else list(CHARACTERS)

    if args.dry_run:
        log.info("🧪 --dry-run : aucun run réel, aucune écriture.")
        for char in characters:
            log.info("   [dry-run] jouerait %s pour le jour %s", char.label, day)
        return 0

    # ── 3. Jouer chaque personnage ───────────────────────────────────────
    chars_result: dict[str, Optional[dict]] = {}
    any_success = False
    for char in characters:
        log.info("%s", "═" * 55)
        log.info("  %s", char.label)
        log.info("%s", "═" * 55)

        result = play_character(char, day, is_ci)
        if result.success:
            any_success = True
            weighted = result.exact + result.partial * 0.5
            verdict = "✅ C'est lui !" if result.is_match else "❌ Pas lui."
            log.info("  %s", verdict)
            log.info(
                "  📊 Score : %s/7 exacts, %s/7 partiels (pondéré: %s)",
                result.exact, result.partial, weighted,
            )
            chars_result[char.key] = {
                "result": result.is_match,
                "exact": result.exact,
                "partial": result.partial,
                "score": result.exact,
                "weighted": weighted,
                "screenshot": result.screenshot,
            }
        else:
            log.error("  🚫 Abandon pour %s après %s tentatives : %s",
                      char.label, MAX_RETRIES, result.error)
            chars_result[char.key] = None

    if not any_success:
        log.error("🚫 Aucun personnage n'a pu être joué — rien n'est écrit, state.json inchangé.")
        return 1

    # ── 4. Écriture database.json ────────────────────────────────────────
    db.setdefault("days", {})[str(day)] = {"date": today_iso, "chars": chars_result}
    save_database(db)

    # ── 5. Vérification post-écriture (relecture disque) ─────────────────
    reloaded = load_database()
    entry = reloaded.get("days", {}).get(str(day))
    if not entry or set(entry.get("chars", {}).keys()) < {c.key for c in characters if chars_result.get(c.key)}:
        log.error(
            "🚫 VÉRIFICATION ÉCHOUÉE : le jour %s n'a pas été correctement persisté dans "
            "database.json. state.json n'est PAS avancé. Investigation nécessaire.", day,
        )
        return 1

    log.info("✅ database.json vérifié : jour %s bien enregistré.", day)

    # ── 6. Avancer l'état (seulement si tout est vérifié) ────────────────
    state["current_day"] = day + 1
    state["last_run_date"] = today_iso
    save_state(state)
    log.info("📅 Prochain jour : %s", day + 1)

    # ── 7. Rapport final ──────────────────────────────────────────────────
    log.info("%s", "═" * 55)
    log.info("  📋 RAPPORT DU %s", today_iso)
    log.info("%s", "═" * 55)
    for char in characters:
        r = chars_result.get(char.key)
        if r is None:
            log.info("  🚫 %s — erreur, non enregistré", char.label)
            continue
        icon = "✅" if r["result"] else "❌"
        found = "Trouvé !" if r["result"] else "Pas lui"
        log.info(
            "  %s %s — %s | %s/7 exacts, %s/7 partiels (pondéré: %s)",
            icon, char.label, found, r["exact"], r["partial"], r["weighted"],
        )

    log.info("%s", "─" * 55)
    log.info("  📊 STATS GLOBALES")
    log.info("%s", "─" * 55)
    for char in CHARACTERS:
        wins, total, rate = compute_win_rate(reloaded, char.key)
        streak = compute_streak(reloaded, char.key)
        flame = "🔥" * min(streak, 5) if streak else "—"
        log.info("  %s : %s/%s parties (%s%%) | streak %s %s",
                  char.label, wins, total, rate, streak, flame)

    log.info("🏁 Terminé.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
