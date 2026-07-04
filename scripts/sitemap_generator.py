#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Génère un sitemap.xml à partir des pages HTML publiques du dépôt."""

from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List
from xml.sax.saxutils import escape

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_FILE = REPO_ROOT / "sitemap.xml"
SITE_URL = "https://l-oeil-critique.netlify.app"
EXCLUDED_DIRS = {".git", ".github", ".venv", "venv", "node_modules", "__pycache__", "site-packages", "assets", "css", "scripts", "movies"}
EXCLUDED_PATH_SNIPPETS = ("site-packages", "/site-packages/", "/Lib/site-packages/", "/playwright/driver/", "/__pycache__")
EXCLUDED_FILES = {"robots.txt", "sitemap.xml"}


def is_public_html(path: Path) -> bool:
    if not path.is_file() or path.suffix.lower() != ".html":
        return False
    if path.name.lower() in EXCLUDED_FILES:
        return False

    normalized = str(path.as_posix()).lower()
    if any(part.lower() in EXCLUDED_DIRS for part in path.parts):
        return False
    if normalized.startswith(str(REPO_ROOT / ".venv").lower()) or normalized.startswith(str(REPO_ROOT / "venv").lower()):
        return False
    if any(snippet in normalized for snippet in EXCLUDED_PATH_SNIPPETS):
        return False

    rel = path.relative_to(REPO_ROOT).as_posix()
    if rel == "index.html":
        return True
    return rel.startswith("")


def get_git_mtime(path: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(path.relative_to(REPO_ROOT))],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() or datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
    except Exception:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")


def build_url(path: Path) -> str:
    rel = path.relative_to(REPO_ROOT).as_posix()
    if rel == "index.html":
        return SITE_URL + "/"
    return SITE_URL + "/" + rel.replace("\\", "/")


def generate_sitemap() -> str:
    urls = []
    public_roots = [REPO_ROOT / "l_oeil_critique", REPO_ROOT / "index.html"]
    html_files = []
    for root in public_roots:
        if root.is_file():
            html_files.append(root)
        elif root.exists():
            html_files.extend(sorted(root.rglob("*.html")))

    for path in sorted(html_files):
        if not is_public_html(path):
            continue
        if ".venv" in str(path):
            continue
        lastmod = get_git_mtime(path)
        urls.append((build_url(path), lastmod))

    lines = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>", "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"]
    for url, lastmod in urls:
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(url)}</loc>")
        lines.append(f"    <lastmod>{escape(lastmod)}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def main() -> None:
    sitemap = generate_sitemap()
    OUTPUT_FILE.write_text(sitemap, encoding="utf-8")
    print("Sitemap genere : " + str(OUTPUT_FILE))


if __name__ == "__main__":
    main()
