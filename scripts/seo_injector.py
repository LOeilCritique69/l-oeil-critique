#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Injecte automatiquement des métadonnées SEO dans les pages HTML du site."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_URL = "https://www.l-oeil-critique.com"
DEFAULT_IMAGE = "/assets/img/logo_chef_doeuvre_processed_copy.jpg"
EXCLUDED_DIRS = {
    "assets",
    "css",
    "scripts",
    "movies",
    ".git",
    ".github",
    ".venv",
    "node_modules",
}


def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned or "page"


def to_site_url(path: Path) -> str:
    relative = path.relative_to(REPO_ROOT).as_posix()
    if relative == "index.html":
        return SITE_URL + "/"
    if relative.startswith(""):
        rel_path = relative[len(""):]
        return f"{SITE_URL}/{quote(rel_path)}"
    return f"{SITE_URL}/{quote(relative)}"


def get_page_title(soup: BeautifulSoup, path: Path) -> str:
    title_tag = soup.find("title")
    if title_tag and title_tag.get_text(strip=True):
        return clean_text(title_tag.get_text(strip=True))

    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return clean_text(h1.get_text(strip=True))

    return path.stem.replace("-", " ").replace("_", " ").strip().title()


def get_page_description(soup: BeautifulSoup) -> str:
    meta = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
    if meta and meta.get("content"):
        return clean_text(meta["content"])

    first_paragraph = soup.find("p")
    if first_paragraph and first_paragraph.get_text(strip=True):
        return clean_text(first_paragraph.get_text(strip=True))[:160]

    return "Découvrez les dernières critiques cinéma et séries sur L’Œil Critique."


def get_page_image(soup: BeautifulSoup) -> str:
    container = soup.select_one(".article-image img")
    if container and container.get("src"):
        return container["src"]

    first_img = soup.find("img")
    if first_img and first_img.get("src"):
        return first_img["src"]

    return DEFAULT_IMAGE


def get_page_type(path: Path) -> str:
    rel = path.as_posix().lower()
    if rel.endswith("index.html") or path.name == "index.html":
        return "website"
    if "/articles/" in rel or "/news/" in rel:
        return "article"
    return "website"


def extract_article_meta(soup: BeautifulSoup) -> dict:
    meta = soup.find("p", class_="article-meta")
    author = None
    date = None
    if meta:
        text = meta.get_text(" ", strip=True)
        author_match = re.search(r"par\s+(.+)", text)
        if author_match:
            author = author_match.group(1)
        date_match = re.search(r"Publié le\s+(\d{1,2}\s+\w+\s+\d{4})", text)
        if date_match:
            raw = date_match.group(1)
            months = {
                "janvier": "01", "février": "02", "mars": "03", "avril": "04", "mai": "05", "juin": "06",
                "juillet": "07", "août": "08", "septembre": "09", "octobre": "10", "novembre": "11", "décembre": "12"
            }
            day, month_name, year = raw.split()
            month = months.get(month_name.lower())
            if month:
                date = f"{year}-{month}-{int(day):02d}"

    return {"author": author, "date": date}


def extract_review_rating(soup: BeautifulSoup) -> Optional[dict]:
    note_block = soup.find("div", class_="note")
    text = note_block.get_text(" ", strip=True) if note_block else ""
    if not text:
        text = soup.get_text(" ", strip=True)

    matches = re.findall(r"([0-9]+(?:[.,][0-9]+)?)\s*(?:/|sur)\s*([0-9]+)", text)
    if not matches:
        return None

    value, best = matches[0]
    value = value.replace(",", ".")
    return {"@type": "Rating", "ratingValue": value, "bestRating": best}


def build_review_jsonld(soup: BeautifulSoup, title: str, description: str, image: str, path: Path) -> str:
    meta = extract_article_meta(soup)
    rating = extract_review_rating(soup)
    item_type = "TVSeries" if "/reviews/series/" in path.as_posix().lower() or "/series/" in path.as_posix().lower() else "Movie"
    author = meta.get("author") or "L’Œil Critique"
    pub_date = meta.get("date") or ""
    payload = {
        "@context": "https://schema.org",
        "@type": "Review",
        "name": title,
        "description": description,
        "image": image,
        "author": {"@type": "Person", "name": author},
        "itemReviewed": {"@type": item_type, "name": title},
        "reviewBody": description,
    }
    if rating:
        payload["reviewRating"] = rating
    if pub_date:
        payload["datePublished"] = pub_date
    return "<script type=\"application/ld+json\">" + json.dumps(payload, ensure_ascii=False) + "</script>"


def remove_existing_tags(soup: BeautifulSoup) -> None:
    for tag in soup.find_all("meta", attrs={"property": re.compile(r"^(og:|twitter:|article:)")}):
        tag.decompose()
    for tag in soup.find_all("meta", attrs={"name": re.compile(r"^(twitter:card|description)$", re.I)}):
        tag.decompose()
    for tag in soup.find_all("link", attrs={"rel": "canonical"}):
        tag.decompose()
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if tag.get_text(strip=True).startswith("{"):
            tag.decompose()


def inject_head_metadata(path: Path) -> bool:
    html = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    if not soup.head:
        return False

    remove_existing_tags(soup)

    title = get_page_title(soup, path)
    description = get_page_description(soup)
    image = get_page_image(soup)
    page_type = get_page_type(path)
    canonical_url = to_site_url(path)

    meta_tags = [
        ("meta", {"property": "og:title", "content": title}),
        ("meta", {"property": "og:description", "content": description}),
        ("meta", {"property": "og:image", "content": image}),
        ("meta", {"property": "og:type", "content": page_type}),
        ("meta", {"property": "og:locale", "content": "fr_FR"}),
        ("meta", {"name": "twitter:card", "content": "summary_large_image"}),
        ("meta", {"property": "og:url", "content": canonical_url}),
    ]

    for tag_name, attrs in meta_tags:
        tag = soup.new_tag(tag_name)
        for key, value in attrs.items():
            tag[key] = value
        soup.head.append(tag)

    canonical_link = soup.new_tag("link", rel="canonical", href=canonical_url)
    soup.head.append(canonical_link)

    is_review = "/reviews/" in path.as_posix().lower() or "/reviews" in path.as_posix().lower()
    if is_review:
        json_ld = build_review_jsonld(soup, title, description, image, path)
        script_tag = BeautifulSoup(json_ld, "html.parser")
        soup.head.append(script_tag.find("script"))

    new_html = str(soup)
    if "<meta property=\"og:title\"" not in new_html:
        head_html = str(soup.head)
        meta_block = """
        <meta property=\"og:title\" content=\"{title}\">
        <meta property=\"og:description\" content=\"{description}\">
        <meta property=\"og:image\" content=\"{image}\">
        <meta property=\"og:type\" content=\"{page_type}\">
        <meta property=\"og:locale\" content=\"fr_FR\">
        <meta name=\"twitter:card\" content=\"summary_large_image\">
        <meta property=\"og:url\" content=\"{canonical_url}\">
        <link rel=\"canonical\" href=\"{canonical_url}\">
        """.format(title=title, description=description, image=image, page_type=page_type, canonical_url=canonical_url)
        if "<head>" in new_html:
            new_html = new_html.replace("<head>", "<head>" + meta_block, 1)
    
    if new_html != html:
        path.write_text(new_html, encoding="utf-8")
        return True
    return False


def find_html_files() -> List[Path]:
    files = []
    for path in REPO_ROOT.rglob("*.html"):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.name.lower() in {"robots.txt", "sitemap.xml"}:
            continue
        files.append(path)
    return sorted(files)


def process_repo() -> List[Path]:
    changed_files = []
    for path in find_html_files():
        if inject_head_metadata(path):
            changed_files.append(path)
    return changed_files


if __name__ == "__main__":
    changed_files = process_repo()
    print(f"✅ SEO injecté sur {len(changed_files)} pages HTML.")
