from playwright.sync_api import sync_playwright
import os
import json
import time
import datetime
import csv
import traceback

URL = "https://marveldle.com/character/audiovisual/guess"

# ════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════
CHARACTERS = [
    {
        "key":         "tom",
        "label":       "Tom Holland",
        "prefix":      "Spider-Ma",
        "option":      "Spider-Man",
        "color":       "#e8503a",
        "images_dir":  "marveldle/images",
        "results_file":"marveldle/results.json",
        "day_file":    "day.txt",
    },
    {
        "key":         "andrew",
        "label":       "Andrew Garfield",
        "prefix":      "Spider-Man (R",
        "option":      "Spider-Man (Rageful Vigilante Spider-Man Universe)",
        "color":       "#3a8be8",
        "images_dir":  "marveldle/images_andrew",
        "results_file":"marveldle/results_andrew.json",
        "day_file":    "day-andrew.txt",
    },
    {
        "key":         "tobey",
        "label":       "Tobey Maguire",
        "prefix":      "Spider-Man (O",
        "option":      "Spider-Man (Organic Webbing Spider-Man Universe)",
        "color":       "#3ae87a",
        "images_dir":  "marveldle/images_tobey",
        "results_file":"marveldle/results_tobey.json",
        "day_file":    "day_tobey.txt",
    },
]

TODAY_FILE  = "last_run.txt"
CSV_FILE    = "marveldle/history.csv"
MAX_RETRIES = 2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

today     = datetime.date.today()
today_iso = today.isoformat()

# ════════════════════════════════════════════════════════════════
# UTILITAIRES
# ════════════════════════════════════════════════════════════════

def weighted_score(exact, partial):
    """Score sur 7 : exacts = 1pt, partiels = 0.5pt"""
    return exact + partial * 0.5

def compute_streak(results: dict) -> int:
    """Nombre de jours consécutifs (depuis le dernier) où result=True."""
    if not results:
        return 0
    days_sorted = sorted(results.items(), key=lambda x: int(x[0]), reverse=True)
    streak = 0
    for _, val in days_sorted:
        if val.get("result") is True:
            streak += 1
        else:
            break
    return streak

def compute_best_streak(results: dict) -> int:
    """Meilleur streak historique."""
    if not results:
        return 0
    days_sorted = sorted(results.items(), key=lambda x: int(x[0]))
    best = cur = 0
    for _, val in days_sorted:
        if val.get("result") is True:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best

def compute_avg_score(results: dict) -> float:
    scores = [v.get("score", 0) for v in results.values() if v.get("score", 0) > 0]
    return round(sum(scores) / len(scores), 2) if scores else 0.0

def append_csv(row: dict):
    """Ajoute une ligne dans le CSV global."""
    os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
    file_exists = os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "date", "character", "day", "result",
            "exact", "partial", "score", "weighted_score", "screenshot"
        ])
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

# ════════════════════════════════════════════════════════════════
# 1. VÉRIFIER si déjà lancé aujourd'hui
# ════════════════════════════════════════════════════════════════
if os.path.exists(TODAY_FILE):
    with open(TODAY_FILE, "r") as f:
        if f.read().strip() == today_iso:
            print("✅ Script déjà lancé aujourd'hui. Rien à faire.")
            exit()

# ════════════════════════════════════════════════════════════════
# 2. JOUER chaque personnage (avec retry)
# ════════════════════════════════════════════════════════════════
is_ci = os.environ.get('CI') == 'true'
run_report = []  # rapport final

for char in CHARACTERS:
    print(f"\n{'═'*55}")
    print(f"  {char['label']}")
    print(f"{'═'*55}")

    # Lire le jour actuel
    if os.path.exists(char["day_file"]):
        with open(char["day_file"], "r") as f:
            today_day = int(f.read().strip())
    else:
        today_day = 1 if char["key"] != "tom" else 56

    print(f"  🎯 Jour : {today_day}")

    # Charger results.json
    results = {}
    if os.path.exists(char["results_file"]):
        with open(char["results_file"], "r", encoding="utf-8") as f:
            raw = f.read().strip()
            if raw:
                try:
                    results = json.loads(raw)
                except json.JSONDecodeError:
                    print(f"  ⚠️ JSON corrompu dans {char['results_file']}, réinitialisation.")
                    results = {}

    # Vérifier doublon
    if str(today_day) in results:
        print(f"  ⚠️  Jour {today_day} déjà dans {char['results_file']} — skip.")
        with open(char["day_file"], "w") as f:
            f.write(str(today_day + 1))
        print(f"  📅 Prochain jour {char['label']} : {today_day + 1}")
        run_report.append({
            "char": char["label"], "day": today_day,
            "status": "skipped", "result": None, "score": None
        })
        continue

    os.makedirs(char["images_dir"], exist_ok=True)
    shot_path = f"{char['images_dir']}/day_{today_day:03}.png"
    if os.path.exists(shot_path):
        os.remove(shot_path)

    # Tentatives avec retry
    square_info = []
    is_match    = False
    attempt     = 0
    success     = False

    while attempt <= MAX_RETRIES and not success:
        if attempt > 0:
            print(f"  🔄 Retry #{attempt}…")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=is_ci,
                    args=['--no-sandbox', '--disable-setuid-sandbox',
                          '--disable-blink-features=AutomationControlled']
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
                    char["prefix"], delay=80
                )
                time.sleep(1.5)

                option_selector = f"span.option-name:has-text('{char['option']}')"
                page.wait_for_selector(option_selector, timeout=10000)
                page.click(option_selector)
                time.sleep(0.5)

                page.click("button.btn.btn-primary.search-button")
                page.wait_for_selector("div.guess-row.new")

                squares    = []
                start_time = time.time()
                while True:
                    squares = page.query_selector_all("div.guess-row.new > div.similarity")
                    if len(squares) == 7:
                        break
                    if time.time() - start_time > 10:
                        print("  ⏱ Timeout attente squares")
                        break
                    time.sleep(0.2)

                if len(squares) < 7:
                    raise RuntimeError(f"Seulement {len(squares)}/7 squares trouvés")

                print("  ⏳ Attente animation (10s)…")
                time.sleep(10)

                square_info = []
                for sq in squares:
                    cls   = sq.get_attribute("class")
                    title = sq.get_attribute("title")
                    square_info.append((title, cls))
                    print(f"    · {title} → {cls}")

                # ── FIX FAUX POSITIF ────────────────────────────────
                # Andrew et Tobey ont les mêmes caractéristiques :
                # 7/7 exacts ne suffit pas. On lit tout le texte de la page
                # pour détecter la bannière "pas celui que l'on cherche".
                all_exact = all("exact" in cls for _, cls in square_info)

                page_text = page.inner_text("body")
                is_wrong_char = (
                    "pas celui que l'on cherche" in page_text
                    or "today's character isn't this one" in page_text.lower()
                )
                print(f"  🔍 Bannière faux positif : {'OUI' if is_wrong_char else 'NON'}")

                is_match = all_exact and not is_wrong_char

                if all_exact and is_wrong_char:
                    print(f"  ⚠️  7/7 exacts MAIS faux positif — mauvais Spider-Man")
                # ────────────────────────────────────────────────────
                page.screenshot(path=shot_path)
                print(f"  📸 {shot_path}")
                context.close()
                browser.close()
                success = True

        except Exception as e:
            attempt += 1
            print(f"  ❌ Erreur : {e}")
            if attempt > MAX_RETRIES:
                print(f"  🚫 Abandon après {MAX_RETRIES} retries.")
                traceback.print_exc()
            else:
                time.sleep(3)

    if not success:
        run_report.append({
            "char": char["label"], "day": today_day,
            "status": "error", "result": None, "score": None
        })
        continue

    # Calculs
    exact_count   = sum(1 for _, cls in square_info if "exact"   in cls)
    partial_count = sum(1 for _, cls in square_info if "partial" in cls)
    score         = exact_count
    w_score       = weighted_score(exact_count, partial_count)
    verdict       = "✅ C'est lui !" if is_match else "❌ Pas lui."
    print(f"  {verdict}")
    print(f"  📊 Score : {exact_count}/7 exacts, {partial_count}/7 partiels (pondéré: {w_score})")

    # Sauvegarde JSON
    results[str(today_day)] = {
        "date":           today_iso,
        "result":         is_match,
        "screenshot":     shot_path,
        "score":          score,
        "exact":          exact_count,
        "partial":        partial_count,
        "weighted_score": w_score,
    }
    with open(char["results_file"], "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"  ✅ {char['results_file']} mis à jour.")

    # Export CSV
    append_csv({
        "date":           today_iso,
        "character":      char["label"],
        "day":            today_day,
        "result":         is_match,
        "exact":          exact_count,
        "partial":        partial_count,
        "score":          score,
        "weighted_score": w_score,
        "screenshot":     shot_path,
    })
    print(f"  📄 CSV mis à jour ({CSV_FILE})")

    # Incrémenter le jour
    with open(char["day_file"], "w") as f:
        f.write(str(today_day + 1))
    print(f"  📅 Prochain jour {char['label']} : {today_day + 1}")

    run_report.append({
        "char": char["label"], "day": today_day,
        "status": "ok", "result": is_match,
        "score": score, "weighted": w_score,
        "exact": exact_count, "partial": partial_count,
    })

# ════════════════════════════════════════════════════════════════
# 3. STATS ENRICHIES pour injection HTML
# ════════════════════════════════════════════════════════════════
def build_stats_payload():
    """
    Construit un objet JS avec toutes les données enrichies pour le site :
    - TOP5 mis à jour (score pondéré)
    - Streaks par personnage
    - Historique complet (pour graphiques + timeline)
    - Comparatif
    """
    all_candidates = []
    char_stats = {}

    for char in CHARACTERS:
        if not os.path.exists(char["results_file"]):
            char_stats[char["key"]] = {}
            continue

        with open(char["results_file"], "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception:
                char_stats[char["key"]] = {}
                continue

        streak      = compute_streak(data)
        best_streak = compute_best_streak(data)
        avg_score   = compute_avg_score(data)
        wins        = sum(1 for v in data.values() if v.get("result") is True)
        total       = len(data)

        # Historique trié pour graphiques
        history = []
        for k, v in sorted(data.items(), key=lambda x: int(x[0])):
            history.append({
                "day":     int(k),
                "date":    v.get("date", ""),
                "result":  v.get("result", False),
                "score":   v.get("score", 0),
                "exact":   v.get("exact", 0),
                "partial": v.get("partial", 0),
                "w":       v.get("weighted_score", v.get("score", 0)),
                "img":     v.get("screenshot", ""),
            })

        char_stats[char["key"]] = {
            "streak":      streak,
            "best_streak": best_streak,
            "avg_score":   avg_score,
            "wins":        wins,
            "total":       total,
            "win_rate":    round(wins / total * 100, 1) if total else 0,
            "history":     history,
        }

        # Candidats top5
        for day_key, val in data.items():
            score   = val.get("score", 0)
            partial = val.get("partial", 0)
            w       = val.get("weighted_score", score)
            if score == 0:
                continue
            caption = f"Jour {day_key} · {char['label']} · {score}/7 exacts"
            if partial > 0:
                caption += f", {partial}/7 partiels"
            all_candidates.append({
                "screenshot": val.get("screenshot", ""),
                "caption":    caption,
                "day":        int(day_key),
                "score":      score,
                "partial":    partial,
                "w":          w,
            })

    # TOP 5 pondéré
    sorted_top = sorted(
        all_candidates,
        key=lambda x: (x["w"], x["partial"]),
        reverse=True
    )[:5]

    return sorted_top, char_stats


# ════════════════════════════════════════════════════════════════
# 4. METTRE À JOUR LE HTML
# ════════════════════════════════════════════════════════════════
def update_html():
    html_file = "marveldle/marveldle.html"
    if not os.path.exists(html_file):
        print("⚠️ marveldle.html introuvable.")
        return

    import re
    top5, char_stats = build_stats_payload()

    with open(html_file, "r", encoding="utf-8") as f:
        html_content = f.read()

    # ── TOP5 ────────────────────────────────────────────────────
    js_lines = []
    for i, entry in enumerate(top5):
        comma = "," if i < len(top5) - 1 else ""
        js_lines.append(
            f'    {{ screenshot: "{entry["screenshot"]}", caption: "{entry["caption"]}", '
            f'day: {entry["day"]}, score: {entry["score"]}, w: {entry["w"]} }}{comma}'
        )
    new_top5 = "const TOP5 = [\n" + "\n".join(js_lines) + "\n];"
    html_content = re.sub(r'const TOP\d\s*=\s*\[.*?\];', new_top5, html_content, flags=re.DOTALL)

    # ── CHAR_STATS (streaks, win_rate, avg_score, history) ──────
    stats_json = json.dumps(char_stats, ensure_ascii=False, separators=(',', ':'))
    new_stats  = f"const CHAR_STATS = {stats_json};"

    if "const CHAR_STATS" in html_content:
        html_content = re.sub(r'const CHAR_STATS\s*=\s*\{.*?\};', new_stats, html_content, flags=re.DOTALL)
    else:
        # Injecter juste avant la fermeture du 1er <script>
        html_content = html_content.replace(
            "const MANUAL_RESULTS",
            new_stats + "\n\nconst MANUAL_RESULTS"
        )

    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ HTML mis à jour (TOP5 + CHAR_STATS).")
    print(f"   Streaks : " + " | ".join(
        f"{c['label']}: {char_stats.get(c['key'], {}).get('streak', 0)} 🔥"
        for c in CHARACTERS
    ))

update_html()

# ════════════════════════════════════════════════════════════════
# 5. RAPPORT FINAL EN CONSOLE
# ════════════════════════════════════════════════════════════════
print(f"\n{'═'*55}")
print(f"  📋 RAPPORT DU {today_iso}")
print(f"{'═'*55}")
for r in run_report:
    if r["status"] == "skipped":
        print(f"  ⏭  {r['char']} jour {r['day']} — déjà fait")
    elif r["status"] == "error":
        print(f"  🚫 {r['char']} jour {r['day']} — ERREUR")
    else:
        icon   = "✅" if r["result"] else "❌"
        found  = "Trouvé !" if r["result"] else "Pas lui"
        print(f"  {icon} {r['char']} jour {r['day']} — {found} | {r['exact']}/7 exacts, {r['partial']}/7 partiels (pondéré: {r['weighted']})")

# Stats globales depuis les fichiers
print(f"\n{'─'*55}")
print("  📊 STATS GLOBALES")
print(f"{'─'*55}")
_, char_stats = build_stats_payload()
for char in CHARACTERS:
    s = char_stats.get(char["key"], {})
    if not s:
        continue
    streak = s.get("streak", 0)
    flame  = "🔥" * min(streak, 5) if streak > 0 else "—"
    print(f"  {char['label']}")
    print(f"    Parties : {s.get('total', 0)} | Wins : {s.get('wins', 0)} ({s.get('win_rate', 0)}%)")
    print(f"    Score moyen : {s.get('avg_score', 0)}/7 | Streak actuel : {streak} {flame} | Meilleur streak : {s.get('best_streak', 0)}")
print(f"{'─'*55}")

# ════════════════════════════════════════════════════════════════
# 6. MARQUER last_run.txt
# ════════════════════════════════════════════════════════════════
with open(TODAY_FILE, "w") as f:
    f.write(today_iso)

print("\n🏁 Terminé.")