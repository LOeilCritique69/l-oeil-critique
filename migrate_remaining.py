#!/usr/bin/env python3
"""
Second migration phase - move remaining files
"""
import shutil
from pathlib import Path

ROOT = Path(".")
LOEIL = ROOT / "l_oeil_critique"

def ensure_dir(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

def move_file(src, dest):
    src = Path(src)
    dest = Path(dest)
    
    if not src.exists():
        print(f"  ⚠️  SKIP (not found): {src}")
        return False
    
    ensure_dir(dest)
    
    try:
        shutil.move(str(src), str(dest))
        print(f"  ✓ {src.relative_to(ROOT)} → {dest.relative_to(ROOT)}")
        return True
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        return False

def move_tree(src, dest):
    src = Path(src)
    dest = Path(dest)
    
    if not src.exists():
        print(f"  ⚠️  SKIP (not found): {src}")
        return False
    
    ensure_dir(dest)
    
    try:
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(src), str(dest))
        print(f"  ✓ {src.relative_to(ROOT)} → {dest.relative_to(ROOT)}")
        return True
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        return False

print("=" * 80)
print("MIGRATION PHASE 2: Remaining files in l_oeil_critique")
print("=" * 80)

success = 0

# Move remaining blocs files
print("\n1️⃣  Moving blocs files")
success += move_file(LOEIL / "bande_annonces_blocs.html", "pages/bande-annonces-blocs.html")
success += move_file(LOEIL / "articles/blocs_films.html", "articles/blocs-films.html")
success += move_file(LOEIL / "articles/blocs_series.html", "articles/blocs-series.html")

# Move CSS file
print("\n2️⃣  Moving CSS files")
success += move_file(LOEIL / "css/devise.css", "assets/css/devine.css")

# Move JS files from l_oeil_critique/assets/js to assets/js
print("\n3️⃣  Moving JS files")
for js_file in (LOEIL / "assets" / "js").glob("*.js"):
    if not (ROOT / "assets" / "js" / js_file.name).exists():
        success += move_file(js_file, ROOT / "assets" / "js" / js_file.name)

# Move data files from l_oeil_critique/assets/data to assets/data
print("\n4️⃣  Moving data files")
for data_file in (LOEIL / "assets" / "data").glob("*"):
    if data_file.is_file():
        if not (ROOT / "assets" / "data" / data_file.name).exists():
            success += move_file(data_file, ROOT / "assets" / "data" / data_file.name)

# Move pages from l_oeil_critique/pages to pages
print("\n5️⃣  Moving page files")
# First move non-tier-list files
for page_file in (LOEIL / "pages").glob("*.html"):
    if not (ROOT / "pages" / page_file.name).exists():
        success += move_file(page_file, ROOT / "pages" / page_file.name)

# Move tier-list directory
print("\n6️⃣  Moving tier-list directory")
success += move_tree(LOEIL / "pages" / "tier-list", ROOT / "pages" / "tier-list")

# Move extra image if it exists
print("\n7️⃣  Moving remaining images")
success += move_file(LOEIL / "assets" / "img" / "logo_chef_doeuvre_processed_copy.jpg", 
                     "assets/img/logo_chef_doeuvre_processed_copy.jpg")

print("\n" + "=" * 80)
print(f"Phase 2 complete: {success} items moved")
print("=" * 80)
