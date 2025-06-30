from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json, os, re
from datetime import datetime

BASE_URL = 'https://www.cinehorizons.net'
LIST_URL = BASE_URL + '/bandes-annonces-prochains-films'
OUTPUT_FILE = 'bande_annonces_blocs.html'
DATE_FILE = 'bande_annonces_maj.html'
LOG_FILE = 'scripts/bande_annonces_log.json'
MAX_BANDES = 3
MAX_SYNOPSIS_LEN = 500

def clean_text(text):
    return ' '.join(text.strip().split())

def extract_date(text):
    if ':' in text:
        return clean_text(text.split(':', 1)[1].replace('(', '').replace(')', ''))
    return clean_text(text.replace('(', '').replace(')', ''))

def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_log(log):
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def extract_youtube_id(src):
    if not src:
        return None
    if 'youtube.com/embed/' in src:
        return src.split('youtube.com/embed/')[-1].split('?')[0]
    return None

def summarize_synopsis(synopsis):
    if len(synopsis) <= MAX_SYNOPSIS_LEN:
        return synopsis
    return synopsis[:MAX_SYNOPSIS_LEN].rstrip() + '...'

def masquer_ancienne_premiere(contenu):
    pattern = r'(<article class="card-bande"(?!.*hidden-card)[^>]*>.*?<span class="badge-nouveau">NOUVEAU</span>.*?)</article>'
    def repl(m):
        article_html = m.group(1)
        if 'hidden-card' not in article_html:
            article_html_mod = article_html.replace('class="card-bande"', 'class="card-bande hidden-card"', 1)
            return article_html_mod + '</article>'
        return m.group(0)
    return re.sub(pattern, repl, contenu, count=1, flags=re.DOTALL)

def main():
    log = load_log()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(LIST_URL)
        page.wait_for_selector('.inside2')

        soup_list = BeautifulSoup(page.content(), 'html.parser')
        blocs = soup_list.select('.inside2')[:MAX_BANDES]

        if not blocs:
            print("Aucun .inside2 trouvé")
            return

        date_ajout = datetime.now().strftime('%d %B %Y')
        nouveaux_articles, nouveaux_ids = [], []

        for bloc in blocs:
            titre_tag = bloc.select_one('[itemprop="name"]')
            titre = clean_text(titre_tag.text) if titre_tag else "Titre inconnu"

            link_tag = bloc.select_one('.field-content a[href]')
            if not link_tag:
                print(f"[SKIP] Pas de lien bande-annonce pour : {titre}")
                continue

            detail_url = urljoin(BASE_URL, link_tag['href'])
            page.goto(detail_url)
            page.wait_for_selector('.movie-release, .player')

            detail_soup = BeautifulSoup(page.content(), 'html.parser')

            date_tag = detail_soup.select_one('.movie-release')
            date_sortie = extract_date(date_tag.text) if date_tag else "Date inconnue"

            iframe_html = '<!-- iframe non trouvé -->'
            video_id = None
            player_div = detail_soup.select_one('.player')
            if player_div:
                iframe = player_div.find('iframe')
                if iframe and iframe.has_attr('src'):
                    src = iframe['src']
                    if src.startswith('//'):
                        src = 'https:' + src
                    video_id = extract_youtube_id(src)
                    iframe_html = f'''
<iframe width="1920" height="750" src="{src}" title="{titre} (Trailer)" frameborder="0"
allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>
                    '''.strip()

            identifiant = video_id if video_id else detail_url
            if identifiant in log:
                print(f"[DOUBLON] Déjà traité : {titre}")
                continue

            synopsis = "Pas de synopsis"
            try:
                menu_links = detail_soup.select('.menu a[href*="/film/"]')
                for menu_tag in menu_links:
                    if 'Sommaire' in menu_tag.text:
                        synopsis_url = urljoin(BASE_URL, menu_tag['href'])
                        page.goto(synopsis_url)
                        page.wait_for_selector('.block-synopsis')
                        syn_soup = BeautifulSoup(page.content(), 'html.parser')
                        syn_block = syn_soup.select_one('.block-synopsis')
                        if syn_block:
                            syn_items = syn_block.select_one('.field-items')
                            if syn_items:
                                syn_tag = syn_items.select_one('.field-item.even p')
                                if syn_tag:
                                    synopsis = clean_text(syn_tag.text)
                        break
            except Exception as e:
                print(f"[WARN] Synopsis non récupéré pour {titre} — {e}")

            synopsis = summarize_synopsis(synopsis)

            article = f'''
<article class="card-bande">
    <span class="badge-nouveau">NOUVEAU</span>
    <h2>{titre}</h2>
    <p class="date-sortie">Sortie prévue : {date_sortie}</p>
    <p class="ajout-site">Ajouté le : {date_ajout}</p>
    <p class="synopsis">{synopsis}</p>
    <div class="video-responsive">
        {iframe_html}
    </div>
</article>
'''.strip()

            nouveaux_articles.append(article)
            nouveaux_ids.append(identifiant)
            print(f"[OK] Ajouté : {titre}")

        if nouveaux_articles:
            ancien = ''
            if os.path.exists(OUTPUT_FILE):
                with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                    ancien = f.read()
            ancien_modifie = masquer_ancienne_premiere(ancien)
            contenu_final = '\n\n'.join(nouveaux_articles) + '\n\n' + ancien_modifie

            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                f.write(contenu_final)

            log.extend(nouveaux_ids)
            save_log(log)

            # Mise à jour de la date
            date_maj = datetime.now().strftime('%d %B %Y')
            with open(DATE_FILE, 'w', encoding='utf-8') as f:
                f.write(f'<p class="maj-annonces">Dernière mise à jour : {date_maj}</p>')

            print(f"\n✅ {len(nouveaux_articles)} bande(s)-annonce ajoutés) en haut de {OUTPUT_FILE}")
            print(f"✅ Date de mise à jour écrite dans {DATE_FILE}")
        else:
            print("Aucune nouvelle bande-annonce.")

        browser.close()

if __name__ == "__main__":
    main()
