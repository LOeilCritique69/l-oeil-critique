import os
import json
import re
import subprocess
import sys
from datetime import datetime
from bs4 import BeautifulSoup

BASE_DIR = os.path.join("l_oeil_critique", "articles")
OUTPUT_FILE = os.path.join("l_oeil_critique", "assets", "data", "articles_index.json")

DEFAULT_LOGO = "/l_oeil_critique/logo_chef_doeuvre_processed_copy.jpg"

TYPES = [
    "films",
    "reviews",
    "series",
    "actualités",
    "bigactualités",
    "theories"
]

DISPLAY_TYPE_OVERRIDES = {
    "bigactualités": "BigActualités",
    "theories": "Théories",
}

# Pages spéciales à inclure en plus des articles
EXTRA_PAGES = [
    {
        "paths": [os.path.join("l_oeil_critique", "pages", "calendrier.html")],
        "url": "/l_oeil_critique/pages/calendrier.html",
        "type": "Outil",
        "image": DEFAULT_LOGO
    },
    {
        "paths": [
            os.path.join("l_oeil_critique", "devine-le-film.html"),
            os.path.join("l_oeil_critique", "pages", "devine-le-film.html")
        ],
        "url": "/l_oeil_critique/devine-le-film.html",
        "type": "Jeu",
        "image": DEFAULT_LOGO
    },
    {
        "paths": [
            os.path.join("l_oeil_critique", "pages", "jeux-video.html"),
            os.path.join("l_oeil_critique", "pages", "jeux-videos.html")
        ],
        "url": "/l_oeil_critique/pages/jeux-video.html",
        "type": "Critiques",
        "image": DEFAULT_LOGO
    },
    {
        "paths": [
            os.path.join("l_oeil_critique", "spideytrack", "marveldle.html"),
            os.path.join("l_oeil_critique", "spideytrack", "marveldle", "index.html"),
            os.path.join("l_oeil_critique", "pages", "marveldle.html"),
            os.path.join("l_oeil_critique", "marveldle.html"),
            os.path.join("spideytrack", "marveldle.html")
        ],
        "url": None,
        "type": "Jeu",
        "image": DEFAULT_LOGO
    }
]

articles_index = []


# =========================================================
# EXTRACTION DES MÉTADONNÉES
# =========================================================
def extract_image(soup):
    container = soup.find("div", class_="article-image")
    if container:
        img = container.find("img")
        if img and img.get("src"):
            return img["src"]

    content = soup.find("div", class_="article-content")
    if content:
        img = content.find("img")
        if img and img.get("src"):
            return img["src"]

    og_image = soup.find("meta", attrs={"property": "og:image"})
    if og_image and og_image.get("content"):
        return og_image["content"]

    icon = soup.find("link", rel=lambda r: r and "icon" in r)
    if icon and icon.get("href"):
        return icon["href"]

    return None


def normalize_image_path(img_src):
    if not img_src:
        return DEFAULT_LOGO

    img_src = img_src.strip()

    # Si c'est le logo du site (peu importe le sous-dossier), on renvoie le vrai chemin
    if "logo_chef_doeuvre_processed_copy.jpg" in img_src:
        return DEFAULT_LOGO

    if img_src.startswith(("http://", "https://")):
        if "l-oeil-critique.com/l_oeil_critique/" in img_src:
            return "/l_oeil_critique/" + img_src.split("l-oeil-critique.com/l_oeil_critique/", 1)[1]
        return img_src

    while img_src.startswith("../"):
        img_src = img_src[3:]

    if img_src.startswith("/l_oeil_critique/"):
        return img_src

    if img_src.startswith("l_oeil_critique/"):
        return "/" + img_src

    if "assets/img" in img_src:
        parts = img_src.split("assets/img")[-1]
        return "/l_oeil_critique/assets/img" + parts

    return "/l_oeil_critique/assets/img/" + img_src

def extract_date(soup):
    meta = soup.find("p", class_="article-meta")
    if not meta:
        return None

    text = meta.get_text(strip=True)

    match = re.search(r"Publié le (\d{1,2} \w+ \d{4})", text)
    if not match:
        return None

    raw_date = match.group(1)

    months = {
        "janvier": "01", "février": "02", "mars": "03",
        "avril": "04", "mai": "05", "juin": "06",
        "juillet": "07", "août": "08", "septembre": "09",
        "octobre": "10", "novembre": "11", "décembre": "12"
    }

    day, month_str, year = raw_date.split()
    month = months.get(month_str.lower())

    if not month:
        return None

    return f"{year}-{month}-{day.zfill(2)}"


def extract_description(soup):
    meta = soup.find("meta", {"name": "description"})
    if meta and meta.get("content"):
        return meta["content"].strip()
    return ""


def extract_author(soup):
    meta = soup.find("p", class_="article-meta")
    if not meta:
        return None

    text = meta.get_text(strip=True)

    match = re.search(r"par (.+)", text)
    if match:
        return match.group(1)

    return None


def extract_rating(soup):
    note_block = soup.find("div", class_="note")
    if not note_block:
        return None

    text = note_block.get_text()
    match = re.search(r"Note\s*:\s*([\d/]+)", text)

    if match:
        return match.group(1)

    return None


def clean_title(raw_title):
    if not raw_title:
        return ""
    return re.sub(r"\s*[–—|-]\s*L'Œil Critique\s*$", "", raw_title, flags=re.IGNORECASE).strip()


# =========================================================
# AJOUT D'UN ARTICLE OU D'UNE PAGE
# =========================================================
def parse_html_file(file_path, url_base, item_type, include_rating=False, fallback_image=None):
    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    title_tag = soup.find("title")
    raw_title = title_tag.get_text(strip=True) if title_tag else os.path.basename(file_path).replace(".html", "")
    title = clean_title(raw_title)

    raw_img = extract_image(soup) or fallback_image
    image = normalize_image_path(raw_img)
    date = extract_date(soup)
    description = extract_description(soup)
    author = extract_author(soup)
    rating = extract_rating(soup) if include_rating else None

    articles_index.append({
        "title": title,
        "type": item_type,
        "url": url_base,
        "image": image,
        "date": date,
        "description": description,
        "author": author,
        "rating": rating
    })


# =========================================================
# TRI + ID
# =========================================================
def sort_articles(articles):
    def parse_date(article):
        if article.get("date"):
            return datetime.fromisoformat(article["date"])
        return datetime.min

    return sorted(articles, key=parse_date, reverse=True)


def assign_ids(articles):
    for i, article in enumerate(articles, start=1):
        article["id"] = i
    return articles


# =========================================================
# BOUCLE PRINCIPALE : ARTICLES UNIQUEMENT
# =========================================================
for type_folder in TYPES:
    folder_path = os.path.join(BASE_DIR, type_folder)
    if not os.path.exists(folder_path):
        continue

    if type_folder == "reviews":
        for root, dirs, files in os.walk(folder_path):
            for file_name in files:
                if file_name.endswith(".html") and file_name != "tendances.html":
                    full_path = os.path.join(root, file_name)
                    relative_path = os.path.relpath(full_path, BASE_DIR)
                    url_base = f"/l_oeil_critique/articles/{relative_path.replace(os.sep, '/')}"
                    parse_html_file(full_path, url_base, "Review", include_rating=True)
        continue

    display_type = DISPLAY_TYPE_OVERRIDES.get(type_folder, type_folder.capitalize())

    for file_name in os.listdir(folder_path):
        if not file_name.endswith(".html") or file_name == "tendances.html":
            continue

        file_path = os.path.join(folder_path, file_name)
        url_base = f"/l_oeil_critique/articles/{type_folder}/{file_name}"
        parse_html_file(file_path, url_base, display_type, include_rating=False)


# =========================================================
# PAGES SPÉCIALES (calendrier, devine-le-film, jeux-video, marveldle)
# =========================================================
for page in EXTRA_PAGES:
    found_path = next((p for p in page["paths"] if os.path.exists(p)), None)
    if not found_path:
        print(f"⚠️ Page introuvable (ignorée) : {page['paths'][0]}")
        continue

    url_base = page["url"] or ("/" + found_path.replace(os.sep, "/"))
    parse_html_file(
        found_path,
        url_base,
        page["type"],
        include_rating=False,
        fallback_image=page.get("image", DEFAULT_LOGO)
    )


# =========================================================
# FINAL
# =========================================================
articles_index = sort_articles(articles_index)
articles_index = assign_ids(articles_index)

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(articles_index, f, ensure_ascii=False, indent=2)

print(f"✅ JSON généré : {len(articles_index)} entrées indexées.")

seo_script = os.path.join(os.path.dirname(__file__), "..", "seo_injector.py")
if os.path.exists(seo_script):
    subprocess.run([sys.executable, seo_script], check=False)