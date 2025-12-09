import os
import json
from bs4 import BeautifulSoup

# Chemin vers le dossier articles
BASE_DIR = os.path.join("l_oeil_critique", "articles")
OUTPUT_FILE = os.path.join("l_oeil_critique", "articles_index.json")

# Sous-dossiers à parcourir
TYPES = ["films", "reviews", "bande-annonces", "series", "actualités", "bigactualités"]

articles_index = []

for type_folder in TYPES:
    folder_path = os.path.join(BASE_DIR, type_folder)
    if not os.path.exists(folder_path):
        continue

    for file_name in os.listdir(folder_path):
        if file_name.endswith(".html"):
            file_path = os.path.join(folder_path, file_name)
            url_base = f"/l_oeil_critique/articles/{type_folder}/{file_name}"

            with open(file_path, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")

            if type_folder == "bande-annonces":
                # Pour chaque <article class="card-bande">
                for article in soup.find_all("article", class_="card-bande"):
                    h2 = article.find("h2")
                    title = h2.get_text(strip=True) if h2 else "Titre inconnu"

                    # Optionnel : récupérer la date d'ajout
                    ajout_tag = article.find("p", class_="ajout-site")
                    date_ajout = ajout_tag.get_text(strip=True) if ajout_tag else ""

                    # Crée l'URL vers la section spécifique de l'article (facultatif)
                    article_id = title.lower().replace(" ", "-")
                    url = f"{url_base}#{article_id}"

                    articles_index.append({
                        "title": title,
                        "type": "Bande-Annonce",
                        "url": url,
                        "added": date_ajout
                    })
            else:
                # Lecture classique du <title>
                title_tag = soup.find("title")
                title = title_tag.get_text(strip=True) if title_tag else file_name.replace(".html", "")
                display_type = type_folder.capitalize() if type_folder != "bigactualités" else "BigActualités"
                articles_index.append({
                    "title": title,
                    "type": display_type,
                    "url": url_base
                })

# Écrire le JSON
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(articles_index, f, ensure_ascii=False, indent=2)

print(f"✅ JSON généré avec {len(articles_index)} articles !")
