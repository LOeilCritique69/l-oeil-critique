#!/usr/bin/env python3
"""
Comprehensive Migration Script
Handles all file moves and renames according to MIGRATION_MAP.md
"""
import os
import shutil
from pathlib import Path
import json

ROOT = Path(".")
LOEIL = ROOT / "l_oeil_critique"

# Migration mapping: (source, dest)
MIGRATIONS = [
    # Phase 1: Fix typos in filenames
    ("arrticle.py", "scripts/article.py"),
    
    # Phase 2: Rename folders with accents
    # Note: We'll handle these specially since they have content
    
    # Phase 3: Move HTML pages to pages/
    ("l_oeil_critique/A_propos.html", "pages/a-propos.html"),
    ("l_oeil_critique/anecdotes.html", "pages/anecdotes.html"),
    ("l_oeil_critique/bande-annonces.html", "pages/bande-annonces.html"),
    ("l_oeil_critique/contact.html", "pages/contact.html"),
    ("l_oeil_critique/devine-le-film.html", "pages/devine-le-film.html"),
    ("l_oeil_critique/reviews.html", "pages/reviews.html"),
    ("l_oeil_critique/mentions_légales.html", "pages/mentions-legales.html"),
    ("l_oeil_critique/politique-de-confidentialité.html", "pages/politique-de-confidentialite.html"),
    
    # Phase 4: Move images from root to assets/img/
    ("l_oeil_critique/fond-grain-noir.jpg", "assets/img/fond-grain-noir.jpg"),
    ("l_oeil_critique/logo_chef_doeuvre_processed_copy.jpg", "assets/img/logo_chef_doeuvre_processed_copy.jpg"),
    
    # Phase 5: Move Python scripts to scripts/
    ("seo_injector.py", "scripts/seo_injector.py"),
    ("update_pages_webp.py", "scripts/update_pages_webp.py"),
    ("l_oeil_critique/scripts/optimize_images.py", "scripts/optimize_images.py"),
    ("l_oeil_critique/scripts/scraper_bandes_annonces.py", "scripts/scraper_bandes_annonces.py"),
    ("l_oeil_critique/scripts/sitemap_generator.py", "scripts/sitemap_generator.py"),
    ("l_oeil_critique/movies/lb.py", "scripts/movies_lb.py"),
    
    # Phase 6: Move CSS files
    ("l_oeil_critique/css/chef_d_oeuvre.css", "assets/css/chef_d_oeuvre.css"),
    ("l_oeil_critique/css/createblog.css", "assets/css/createblog.css"),
    ("l_oeil_critique/css/createblog_article.css", "assets/css/createblog_article.css"),
    ("l_oeil_critique/css/devise.css", "assets/css/devise.css"),
    ("l_oeil_critique/css/list-pages.css", "assets/css/list-pages.css"),
    ("l_oeil_critique/movies/style.css", "assets/css/movies.css"),
    
    # Phase 7: Move JS files
    ("l_oeil_critique/movies/app.js", "assets/js/movies.js"),
    
    # Phase 8: Move JSON data files
    ("l_oeil_critique/movies/movies.json", "assets/data/movies.json"),
    ("l_oeil_critique/movies/movies_enriched.json", "assets/data/movies_enriched.json"),
    ("l_oeil_critique/movies/tmdb_cache.json", "assets/data/tmdb_cache.json"),
    ("l_oeil_critique/scripts/bande_annonces_log.json", "assets/data/bande_annonces_log.json"),
]

def ensure_dir(path):
    """Ensure parent directory exists"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

def migrate_file(src, dest, dry_run=False):
    """Migrate a single file"""
    src = Path(src)
    dest = Path(dest)
    
    if not src.exists():
        print(f"  ⚠️  SKIP (not found): {src}")
        return False
    
    ensure_dir(dest)
    
    if dry_run:
        print(f"  📋 DRY RUN: {src} → {dest}")
        return True
    
    try:
        shutil.move(str(src), str(dest))
        print(f"  ✓ {src} → {dest}")
        return True
    except Exception as e:
        print(f"  ✗ ERROR: {src} → {dest}: {e}")
        return False

def migrate_folder(src, dest, dry_run=False):
    """Migrate a folder with all contents"""
    src = Path(src)
    dest = Path(dest)
    
    if not src.exists():
        print(f"  ⚠️  SKIP (folder not found): {src}")
        return False
    
    ensure_dir(dest)
    
    if dry_run:
        print(f"  📋 DRY RUN FOLDER: {src} → {dest}")
        return True
    
    try:
        # If dest exists, remove it first
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(src), str(dest))
        print(f"  ✓ FOLDER: {src} → {dest}")
        return True
    except Exception as e:
        print(f"  ✗ ERROR: {src} → {dest}: {e}")
        return False

def run_migration(dry_run=True):
    """Run all migrations"""
    print("=" * 80)
    print(f"MIGRATION PHASE (DRY RUN: {dry_run})")
    print("=" * 80)
    
    success_count = 0
    fail_count = 0
    
    # Phase 1: Individual file migrations
    print("\n1️⃣  MIGRATING INDIVIDUAL FILES")
    for src, dest in MIGRATIONS:
        if migrate_file(src, dest, dry_run):
            success_count += 1
        else:
            fail_count += 1
    
    # Phase 2: Folder migrations
    print("\n2️⃣  MIGRATING FOLDERS WITH ACCENTS")
    folder_migrations = [
        (LOEIL / "articles" / "bigactualités", Path("articles") / "actualites"),
        (LOEIL / "assets" / "img" / "bigactualités", Path("assets") / "img" / "actualites"),
        (LOEIL / "assets" / "img" / "tierlists", Path("assets") / "img" / "tier-lists"),
    ]
    
    for src, dest in folder_migrations:
        if migrate_folder(src, dest, dry_run):
            success_count += 1
        else:
            fail_count += 1
    
    # Phase 3: Folder copy (keep structure)
    print("\n3️⃣  COPYING FOLDER STRUCTURES (from l_oeil_critique to root)")
    folder_copies = [
        (LOEIL / "pages", "pages"),
        (LOEIL / "news", "news"),
        (LOEIL / "articles" / "films", "articles/films"),
        (LOEIL / "articles" / "series", "articles/series"),
        (LOEIL / "articles" / "reviews", "articles/reviews"),
        (LOEIL / "assets" / "js", "assets/js"),
        (LOEIL / "assets" / "img" / "films", "assets/img/films"),
        (LOEIL / "assets" / "img" / "series", "assets/img/series"),
        (LOEIL / "assets" / "img" / "reviews", "assets/img/reviews"),
        (LOEIL / "assets" / "sounds", "assets/sounds"),
        (LOEIL / "assets" / "data", "assets/data"),
        (LOEIL / "movies", "movies"),
    ]
    
    for src, dest in folder_copies:
        if not src.exists():
            print(f"  ℹ️  SKIP (not found): {src}")
            continue
        if Path(dest).exists():
            print(f"  ℹ️  SKIP (already exists): {dest}")
            continue
        if migrate_folder(src, dest, dry_run):
            success_count += 1
        else:
            fail_count += 1
    
    print("\n" + "=" * 80)
    print(f"SUMMARY: {success_count} success, {fail_count} failures")
    print("=" * 80)

if __name__ == "__main__":
    import sys
    
    dry_run = "--execute" not in sys.argv
    
    if dry_run:
        print("\n🟡 DRY RUN MODE - No files will be moved")
        print("Run with --execute flag to actually move files")
        print()
    
    run_migration(dry_run=dry_run)
    
    if dry_run:
        print("\n✓ Dry run complete. Review above and run with --execute to proceed")
