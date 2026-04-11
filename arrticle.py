
import os
import json
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
# IMAGE EXTRACTION (ADAPTÉE À TON TEMPLATE)
# =========================================================
def extract_image(soup):
    # image principale
    container = soup.find("div", class_="article-image")
    if container:
        img = container.find("img")
        if img and img.get("src"):
            return img["src"]

    # fallback : contenu
    content = soup.find("div", class_="article-content")
    if content:
        img = content.find("img")
        if img and img.get("src"):
            return img["src"]

    return None


def clean_image_path(img_src):
    if not img_src:
        return None
    return img_src.replace("../../", "/l_oeil_critique/")


# =========================================================
# REVIEW
# =========================================================
def add_review_file(file_path, url_base):
    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else os.path.basename(file_path)

    image = normalize_image_path(extract_image(soup))

    articles_index.append({
        "title": title,
        "type": "Review",
        "url": url_base,
        "image": image
    })

def normalize_image_path(img_src):
    if not img_src:
        return None

    img_src = img_src.strip()

    # supprimer les traversées de dossiers
    while img_src.startswith("../"):
        img_src = img_src[3:]

    # si déjà absolu site
    if img_src.startswith("/l_oeil_critique/"):
        return img_src

    # si chemin assets détecté
    if "assets/img" in img_src:
        parts = img_src.split("assets/img")[-1]
        return "/l_oeil_critique/assets/img" + parts

    # fallback
    return "/l_oeil_critique/assets/img/" + img_src


# =========================================================
# MAIN LOOP
# =========================================================
for type_folder in TYPES:
    folder_path = os.path.join(BASE_DIR, type_folder)
    if not os.path.exists(folder_path):
        continue

    # --------------------------------------------------------
    # BANDE-ANNONCES
    # --------------------------------------------------------
    if type_folder == "bande-annonces":
        for file_name in os.listdir(folder_path):
            if not file_name.endswith(".html") or file_name == "tendances.html":
                continue

            file_path = os.path.join(folder_path, file_name)
            url_base = f"/l_oeil_critique/articles/{type_folder}/{file_name}"

            with open(file_path, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")

            for article in soup.find_all("article", class_="card-bande"):
                h2 = article.find("h2")
                title = h2.get_text(strip=True) if h2 else "Titre inconnu"

                ajout_tag = article.find("p", class_="ajout-site")
                date_ajout = ajout_tag.get_text(strip=True) if ajout_tag else ""

                img_tag = article.find("img")
                image = clean_image_path(img_tag["src"]) if img_tag and img_tag.get("src") else None

                article_id = title.lower().replace(" ", "-")
                url = f"{url_base}#{article_id}"

                articles_index.append({
                    "title": title,
                    "type": "Bande-Annonce",
                    "url": url,
                    "added": date_ajout,
                    "image": image
                })
        continue

    # --------------------------------------------------------
    # REVIEWS (avec sous-dossiers)
    # --------------------------------------------------------
    if type_folder == "reviews":
        for root, dirs, files in os.walk(folder_path):
            for file_name in files:
                if file_name.endswith(".html") and file_name != "tendances.html":
                    full_path = os.path.join(root, file_name)
                    relative_path = os.path.relpath(full_path, BASE_DIR)
                    url_base = f"/l_oeil_critique/articles/{relative_path.replace(os.sep, '/')}"
                    add_review_file(full_path, url_base)
        continue

    # --------------------------------------------------------
    # AUTRES TYPES
    # --------------------------------------------------------
    for file_name in os.listdir(folder_path):
        if not file_name.endswith(".html") or file_name == "tendances.html":
            continue

        file_path = os.path.join(folder_path, file_name)
        url_base = f"/l_oeil_critique/articles/{type_folder}/{file_name}"

        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else file_name.replace(".html", "")

        display_type = "BigActualités" if type_folder == "bigactualités" else type_folder.capitalize()

        image = clean_image_path(extract_image(soup))

        articles_index.append({
            "title": title,
            "type": display_type,
            "url": url_base,
            "image": image
        })


# =========================================================
# SAVE JSON
# =========================================================
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(articles_index, f, ensure_ascii=False, indent=2)

print(f"✅ JSON généré : {len(articles_index)} articles indexés.")