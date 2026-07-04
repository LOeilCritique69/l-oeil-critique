import os
import json
import re
import subprocess
import sys
from datetime import datetime
from bs4 import BeautifulSoup

BASE_DIR = os.path.join("l_oeil_critique", "articles")
OUTPUT_FILE = os.path.join("l_oeil_critique", "assets", "data", "articles_index.json")

TYPES = [
    "films",
    "reviews",
    "bande-annonces",
    "series",
    "actualités",
    "bigactualités"
]

articles_index = []

# =========================================================
# IMAGE
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

    return None


def normalize_image_path(img_src):
    if not img_src:
        return None

    img_src = img_src.strip()

    while img_src.startswith("../"):
        img_src = img_src[3:]

    if img_src.startswith("/"):
        return img_src

    if "assets/img" in img_src:
        parts = img_src.split("assets/img")[-1]
        return "/assets/img" + parts

    return "/assets/img/" + img_src


# =========================================================
# DATE
# =========================================================
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


# =========================================================
# DESCRIPTION
# =========================================================
def extract_description(soup):
    meta = soup.find("meta", {"name": "description"})
    if meta and meta.get("content"):
        return meta["content"].strip()
    return ""


# =========================================================
# AUTHOR
# =========================================================
def extract_author(soup):
    meta = soup.find("p", class_="article-meta")
    if not meta:
        return None

    text = meta.get_text(strip=True)

    match = re.search(r"par (.+)", text)
    if match:
        return match.group(1)

    return None


# =========================================================
# RATING (REVIEWS)
# =========================================================
def extract_rating(soup):
    note_block = soup.find("div", class_="note")
    if not note_block:
        return None

    text = note_block.get_text()
    match = re.search(r"Note\s*:\s*([\d/]+)", text)

    if match:
        return match.group(1)

    return None


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
# REVIEW
# =========================================================
def add_review_file(file_path, url_base):
    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else os.path.basename(file_path)

    image = normalize_image_path(extract_image(soup))
    date = extract_date(soup)
    description = extract_description(soup)
    author = extract_author(soup)
    rating = extract_rating(soup)

    articles_index.append({
        "title": title,
        "type": "Review",
        "url": url_base,
        "image": image,
        "date": date,
        "description": description,
        "author": author,
        "rating": rating
    })


# =========================================================
# MAIN LOOP
# =========================================================
for type_folder in TYPES:
    folder_path = os.path.join(BASE_DIR, type_folder)
    if not os.path.exists(folder_path):
        continue

    # -------------------------
    # BANDE-ANNONCES
    # -------------------------
    if type_folder == "bande-annonces":
        for file_name in os.listdir(folder_path):
            if not file_name.endswith(".html") or file_name == "tendances.html":
                continue

            file_path = os.path.join(folder_path, file_name)
            url_base = f"/articles/{type_folder}/{file_name}"

            with open(file_path, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")

            for article in soup.find_all("article", class_="card-bande"):
                h2 = article.find("h2")
                title = h2.get_text(strip=True) if h2 else "Titre inconnu"

                ajout_tag = article.find("p", class_="ajout-site")
                date = None

                if ajout_tag:
                    date_text = ajout_tag.get_text(strip=True)
                    match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", date_text)
                    if match:
                        d = match.group(1)
                        day, month, year = d.split("/")
                        date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

                img_tag = article.find("img")
                image = normalize_image_path(img_tag["src"]) if img_tag and img_tag.get("src") else None

                articles_index.append({
                    "title": title,
                    "type": "Bande-Annonce",
                    "url": f"{url_base}#{title.lower().replace(' ', '-')}",
                    "image": image,
                    "date": date,
                    "description": "",
                    "author": None,
                    "rating": None
                })
        continue

    # -------------------------
    # REVIEWS
    # -------------------------
    if type_folder == "reviews":
        for root, dirs, files in os.walk(folder_path):
            for file_name in files:
                if file_name.endswith(".html") and file_name != "tendances.html":
                    full_path = os.path.join(root, file_name)
                    relative_path = os.path.relpath(full_path, BASE_DIR)
                    url_base = f"/articles/{relative_path.replace(os.sep, '/')}"
                    add_review_file(full_path, url_base)
        continue

    # -------------------------
    # AUTRES
    # -------------------------
    for file_name in os.listdir(folder_path):
        if not file_name.endswith(".html") or file_name == "tendances.html":
            continue

        file_path = os.path.join(folder_path, file_name)
        url_base = f"/articles/{type_folder}/{file_name}"

        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else file_name.replace(".html", "")

        display_type = "BigActualités" if type_folder == "bigactualités" else type_folder.capitalize()

        image = normalize_image_path(extract_image(soup))
        date = extract_date(soup)
        description = extract_description(soup)
        author = extract_author(soup)

        articles_index.append({
            "title": title,
            "type": display_type,
            "url": url_base,
            "image": image,
            "date": date,
            "description": description,
            "author": author,
            "rating": None
        })


# =========================================================
# FINAL
# =========================================================
articles_index = sort_articles(articles_index)
articles_index = assign_ids(articles_index)

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(articles_index, f, ensure_ascii=False, indent=2)

print(f"✅ JSON généré : {len(articles_index)} articles indexés.")

seo_script = os.path.join(os.path.dirname(__file__), "..", "seo_injector.py")
if os.path.exists(seo_script):
    subprocess.run([sys.executable, seo_script], check=False)
