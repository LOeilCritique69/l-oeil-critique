from bs4 import BeautifulSoup

def convert_article(article):
    # --- Récupération des infos
    titre = article.find("h2").get_text(strip=True) if article.find("h2") else "Sans titre"
    date_sortie = article.find("p", class_="date-sortie").get_text(strip=True) if article.find("p", class_="date-sortie") else "Sortie prévue : Inconnue"
    ajout_site = article.find("p", class_="ajout-site").get_text(strip=True) if article.find("p", class_="ajout-site") else "Ajouté le : Inconnu"
    synopsis = article.find("p", class_="synopsis").get_text(strip=True) if article.find("p", class_="synopsis") else "Pas de synopsis"

    # --- Extraction de l'ID YouTube
    iframe = article.find("iframe")
    video_id = None
    if iframe and "youtube.com/embed/" in iframe["src"]:
        video_id = iframe["src"].split("embed/")[1].split("?")[0]

    # --- Création du nouveau bloc vidéo
    if video_id:
        video_block = f"""
        <video class="youtube-placeholder" data-src="https://www.youtube.com/embed/{video_id}?autoplay=1" 
        style="background-image:url('https://img.youtube.com/vi/{video_id}/hqdefault.jpg');" 
        role="button" aria-label="Lire la bande annonce {titre}">
            <button class="play-button"></button>
        </video>
        """
    else:
        video_block = "<p>Pas de bande-annonce disponible</p>"

    # --- Construction du nouvel article
    new_article = f"""
    <article class="card-bande">
        <span class="badge-nouveau">NOUVEAU</span>
        <h2>{titre}</h2>
        <p class="date-sortie">{date_sortie}</p>
        <p class="ajout-site">{ajout_site}</p>
        <p class="synopsis">{synopsis}</p>
        <div class="video-responsive">
            {video_block}
        </div>
    </article>
    """
    return new_article.strip()


def convert_file(input_file, output_file):
    with open(input_file, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    articles = soup.find_all("article", class_="card-bande")
    converted = [convert_article(a) for a in articles]

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n\n".join(converted))

    print(f"✅ Conversion terminée : {len(converted)} articles transformés dans {output_file}")


# === Utilisation directe ===
convert_file("bande_annonces_blocs.html", "bande_annonces_blocs_converti.html")
