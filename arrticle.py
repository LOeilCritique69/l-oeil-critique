import os
import json
from bs4 import BeautifulSoup

BASE_DIR = os.path.join("l_oeil_critique", "articles")
OUTPUT_FILE = os.path.join("l_oeil_critique", "articles_index.json")

TYPES = [
    "films",
    "reviews",
    "bande-annonces",
    "series",
    "actualités",
    "bigactualités"
]

articles_index = []

def add_review_file(file_path, url_base):
    """Traitement propre d'un fichier review."""
    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else os.path.basename(file_path)

    articles_index.append({
        "title": title,
        "type": "Review",
        "url": url_base
    })

for type_folder in TYPES:
    folder_path = os.path.join(BASE_DIR, type_folder)
    if not os.path.exists(folder_path):
        continue

    # --------------------------------------------------------
    # BANDE-ANNONCES
    # --------------------------------------------------------
    if type_folder == "bande-annonces":
        for file_name in os.listdir(folder_path):
            # EXCLUSION tendances.html
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
                article_id = title.lower().replace(" ", "-")
                url = f"{url_base}#{article_id}"

                articles_index.append({
                    "title": title,
                    "type": "Bande-Annonce",
                    "url": url,
                    "added": date_ajout
                })
        continue

    # --------------------------------------------------------
    # REVIEWS (os.walk pour les sous-dossiers)
    # --------------------------------------------------------
    if type_folder == "reviews":
        for root, dirs, files in os.walk(folder_path):
            for file_name in files:
                # EXCLUSION tendances.html
                if file_name.endswith(".html") and file_name != "tendances.html":
                    full_path = os.path.join(root, file_name)
                    relative_path = os.path.relpath(full_path, BASE_DIR)
                    url_base = f"/l_oeil_critique/articles/{relative_path.replace(os.sep, '/')}"
                    add_review_file(full_path, url_base)
        continue

    # --------------------------------------------------------
    # FILMS / SERIES / ACTUALITÉS / BIGACTUS
    # --------------------------------------------------------
    for file_name in os.listdir(folder_path):
        # EXCLUSION tendances.html
        if not file_name.endswith(".html") or file_name == "tendances.html":
            continue

        file_path = os.path.join(folder_path, file_name)
        url_base = f"/l_oeil_critique/articles/{type_folder}/{file_name}"

        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else file_name.replace(".html", "")
        display_type = "BigActualités" if type_folder == "bigactualités" else type_folder.capitalize()

        articles_index.append({
            "title": title,
            "type": display_type,
            "url": url_base
        })

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(articles_index, f, ensure_ascii=False, indent=2)

print(f"✅ JSON généré avec {len(articles_index)} articles (hors tendances.html).")