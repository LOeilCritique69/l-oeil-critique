# automate_loeil_critique.py
import os
import re
import time
import random
import requests
from bs4 import BeautifulSoup
from slugify import slugify
from git import Repo
import json
from datetime import datetime, timedelta

REPO_PATH = '.'
ARTICLES_DIR = 'articles'
ASSETS_IMG_DIR = 'assets/img'
FILMS_HTML_PATH = 'films.html'
SERIES_HTML_PATH = 'series.html'
BIGACTUALITES_HTML_PATH = 'actualites.html'
PROCESSED_URLS_FILE = 'processed_urls.json'

SOURCES = {
    'AlloCine': {
        'url': 'https://www.allocine.fr/news/',
        'forced_category': None,
        'language': 'fr'
    },
    'DiscussingFilm_Movies': {
        'url': 'https://discussingfilm.net/category/film/',
        'forced_category': 'film',
        'language': 'en'
    },
    'DiscussingFilm_Series': {
        'url': 'https://discussingfilm.net/category/tv/',
        'forced_category': 'serie',
        'language': 'en'
    },
    'EcranLarge_Films': {
        'url': 'https://www.ecranlarge.com/films',
        'forced_category': 'film',
        'language': 'fr'
    },
    'EcranLarge_Series': {
        'url': 'https://www.ecranlarge.com/series',
        'forced_category': 'serie',
        'language': 'fr'
    },
}

def load_processed_urls():
    if os.path.exists(PROCESSED_URLS_FILE):
        with open(PROCESSED_URLS_FILE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()

def save_processed_urls(urls):
    with open(PROCESSED_URLS_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(urls), f, ensure_ascii=False, indent=2)

def clean_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    for tag in soup(['script', 'style', 'iframe', 'aside', 'noscript', 'footer', 'header', 'nav']):
        tag.decompose()
    return str(soup.body or soup)

def slugify_filename(title):
    return slugify(title, lowercase=True, separator='-')[:50]

def download_image(url, category):
    if not url:
        return None
    ext = url.split('.')[-1].split('?')[0]
    filename = slugify_filename(url) + '.' + ext
    category_img_dir = os.path.join(ASSETS_IMG_DIR, f"{category}s")
    os.makedirs(category_img_dir, exist_ok=True)
    filepath = os.path.join(category_img_dir, filename)

    if not os.path.exists(filepath):
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            with open(filepath, 'wb') as f:
                f.write(resp.content)
            print(f"Téléchargé image: {filepath}")
        except Exception as e:
            print(f"Erreur téléchargement image {url}: {e}")
            return None
    else:
        print(f"Image déjà présente: {filepath}")
    return f"../../{category_img_dir}/{filename}"

def fetch_article_details(url, source_name):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        title = content = image_url = None

        if source_name == 'AlloCine':
            t = soup.find('h1', class_='titlebar-title')
            c = soup.find('div', class_='content-txt')
            img = soup.find('meta', property='og:image')
            title = t.text.strip() if t else None
            content = str(c) if c else None
            image_url = img['content'] if img else None

        elif 'DiscussingFilm' in source_name:
            t = soup.find('h1', class_='entry-title') or soup.find('h1')
            c = soup.find('div', class_='td-post-content') or soup.find('div', class_='entry-content')
            img = soup.find('meta', property='og:image')
            title = t.text.strip() if t else None
            content = str(c) if c else None
            image_url = img['content'] if img else None

        elif 'EcranLarge' in source_name:
            t = soup.find('h1', class_='title') or soup.find('h1')
            c = soup.find('div', class_='article__content') or soup.find('div', itemprop='articleBody')
            img = soup.find('meta', property='og:image')
            title = t.text.strip() if t else None
            content = str(c) if c else None
            image_url = img['content'] if img else None

        else:
            print(f"[fetch] Source non prise en charge : {source_name}")
            return None

        if not title or not content:
            print(f"[fetch] ⚠️ Données manquantes : titre={bool(title)}, contenu={bool(content)} — URL: {url}")
            return None

        return {
            'url': url,
            'title': title,
            'content_html': clean_html(content),
            'image_url': image_url
        }

    except Exception as e:
        print(f"[fetch] Erreur pour {url} : {e}")
        return None


def generate_article_html(article, category):
    slug = slugify_filename(article['title'])
    folder = os.path.join(ARTICLES_DIR, f"{category}s")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{slug}.html")

    img_path = download_image(article.get('image_url'), category)

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>{article['title']} - L'Œil Critique</title>
    <link rel="stylesheet" href="../../chef_d_oeuvre.css" />
    <link rel="stylesheet" href="../../createblog.css" />
</head>
<body>
    <header><h1>{article['title']}</h1></header>
    <main class="container">
        <div class="main-content">
            {'<img src="'+img_path+'" alt="Image">' if img_path else ''}
            {article['content_html']}
        </div>
        <aside class="sidebar"><p>Un article généré automatiquement.</p></aside>
    </main>
</body>
</html>"""

    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Article généré : {path}")
    return path, slug, img_path

def update_category_page(category, slug, title, desc, img_path):
    html_path = {
        'film': FILMS_HTML_PATH,
        'serie': SERIES_HTML_PATH
    }.get(category, BIGACTUALITES_HTML_PATH)

    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')

        article_tag = soup.new_tag('article', **{'class': 'news-item'})
        if img_path:
            article_tag.append(soup.new_tag('img', src=img_path.replace('../../', ''), alt=title))
        article_tag.append(soup.new_tag('h3')).string = title
        article_tag.append(soup.new_tag('p')).string = desc
        link = soup.new_tag('a', href=f'articles/{category}s/{slug}.html', **{'class': 'btn', 'target': '_blank'})
        link.string = 'Lire plus'
        article_tag.append(link)

        grid = soup.find('div', class_='news-grid') or soup.find('section', class_='latest-news-section')
        if grid:
            grid.insert(0, article_tag)
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(str(soup))
            print(f"Page {html_path} mise à jour.")
        else:
            print(f"Aucune section .news-grid trouvée dans {html_path}")
    except Exception as e:
        print(f"Erreur update {html_path} : {e}")

def run_git_commands(message):
    print("Push Git en cours...")
    try:
        repo = Repo(REPO_PATH)
        repo.git.add(all=True)
        repo.index.commit(message)
        token = os.getenv('GH_TOKEN')
        remote_url = repo.remote().url
        if token and 'github.com' in remote_url and 'oauth2' not in remote_url:
            user_repo = remote_url.split('github.com/')[1].replace('.git', '')
            repo.remote().set_url(f'https://oauth2:{token}@github.com/{user_repo}.git')
        repo.git.push()
        print("Push effectué.")
    except Exception as e:
        print(f"Erreur Git : {e}")

def determine_category(title, content, lang='fr', forced_category=None):
    if forced_category:
        return forced_category
    film_kw = ['film', 'cinéma', 'sortie']
    serie_kw = ['série', 'season', 'épisode']
    text = (title + " " + BeautifulSoup(content, 'html.parser').get_text()).lower()
    if any(k in text for k in film_kw): return 'film'
    if any(k in text for k in serie_kw): return 'serie'
    return 'bigactualites'

def main():
    print("Démarrage de l'automatisation de L'Œil Critique...\n")
    processed = load_processed_urls()
    new_count = 0

    for name, cfg in SOURCES.items():
        print(f"Scraping {name}...")
        try:
            r = requests.get(cfg['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')
            links = []

            if name == 'AlloCine':
                for div in soup.find_all('div', class_='news-item'):
                    a = div.find('a')
                    if a and a.get('href', '').startswith('/news/'):
                        links.append("https://www.allocine.fr" + a['href'])

            elif 'DiscussingFilm' in name:
                for h3 in soup.find_all('h3'):
                    a = h3.find('a')
                    if a and 'discussingfilm.net' in a['href']:
                        links.append(a['href'])

            elif 'EcranLarge' in name:
                for div in soup.find_all('div', class_='article-list-item'):
                    a = div.find('a', class_='article-list-item-link')
                    if a:
                        href = a['href']
                        if href.startswith('/'):
                            href = 'https://www.ecranlarge.com' + href
                        links.append(href)

            print(f"DEBUG - {len(links)} liens trouvés")

            for link in links[:5]:  # Limite à 5 pour test
                if link in processed:
                    continue
                article = fetch_article_details(link, name)
                if not article:
                    print(f"Article ignoré : {link}")
                    continue
                category = determine_category(article['title'], article['content_html'], cfg['language'], cfg.get('forced_category'))
                desc = BeautifulSoup(article['content_html'], 'html.parser').get_text(strip=True)[:180] + '...'
                _, slug, img_path = generate_article_html(article, category)
                update_category_page(category, slug, article['title'], desc, img_path)
                processed.add(link)
                new_count += 1
                time.sleep(random.uniform(2, 4))

        except Exception as e:
            print(f"Erreur scraping {name} : {e}")

    save_processed_urls(processed)

    if new_count > 0:
        run_git_commands("Ajout de nouveaux articles via L'Œil Critique")
    else:
        print("Aucun nouvel article détecté.")

if __name__ == "__main__":
    main()
