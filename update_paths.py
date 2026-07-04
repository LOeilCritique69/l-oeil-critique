#!/usr/bin/env python3
"""
Update all path references in HTML, CSS, and JS files
"""
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(".")

# Path replacements mapping
PATH_REPLACEMENTS = [
    # CSS paths
    (r'(\.\./)+css/(?!.*actualites)', lambda m: m.group(0).replace('/css/', '/assets/css/')),
    (r'(\.\./)+css/', lambda m: '../assets/css/'),
    
    # Image paths with accents
    (r'assets/img/bigactualités/', 'assets/img/actualites/'),
    (r'(?<=\.\.)\..*?/img/bigactualités/', '../assets/img/actualites/'),
    (r'(?<=\.\.)(?:\.\./)*assets/img/bigactualités/', '../assets/img/actualites/'),
    (r'../../assets/img/bigactualités/', '../../assets/img/actualites/'),
    (r'../assets/img/bigactualités/', '../assets/img/actualites/'),
    (r'/assets/img/bigactualités/', '/assets/img/actualites/'),
    (r'img/bigactualités/', 'img/actualites/'),
    
    # Article links with accents
    (r'\.\./bigactualités/', '../actualites/'),
    (r'../bigactualités/', '../actualites/'),
    (r'./articles/bigactualités/', './articles/actualites/'),
    (r'articles/bigactualités/', 'articles/actualites/'),
    
    # Remove l_oeil_critique from paths
    (r'l_oeil_critique/', ''),
    (r'l_oeil_critique\\', ''),
    
    # Movies paths
    (r'movies/app\.js', 'assets/js/movies.js'),
    (r'movies/style\.css', 'assets/css/movies.css'),
    (r'movies/movies\.json', 'assets/data/movies.json'),
    (r'movies/movies_enriched\.json', 'assets/data/movies_enriched.json'),
    (r'movies/tmdb_cache\.json', 'assets/data/tmdb_cache.json'),
    (r'movies/lb\.py', 'scripts/movies_lb.py'),
]

def replace_paths_in_file(filepath):
    """Replace all path references in a file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return 0
    
    original_content = content
    
    # Apply all replacements
    for old, new in PATH_REPLACEMENTS:
        if callable(new):
            content = re.sub(old, new, content)
        else:
            content = content.replace(old, new)
    
    # Write back if changed
    if content != original_content:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return 1
        except:
            return 0
    
    return 0

# Process all relevant files
print("=" * 80)
print("UPDATING PATH REFERENCES")
print("=" * 80)

file_types = {
    'HTML': 0,
    'CSS': 0,
    'JS': 0,
    'Python': 0,
}

# Update HTML files
print("\n1️⃣  Updating HTML files...")
for html_file in ROOT.rglob("*.html"):
    if replace_paths_in_file(html_file):
        file_types['HTML'] += 1
        print(f"  ✓ {html_file.relative_to(ROOT)}")

# Update CSS files
print("\n2️⃣  Updating CSS files...")
for css_file in ROOT.rglob("*.css"):
    if replace_paths_in_file(css_file):
        file_types['CSS'] += 1
        print(f"  ✓ {css_file.relative_to(ROOT)}")

# Update JS files
print("\n3️⃣  Updating JavaScript files...")
for js_file in ROOT.rglob("*.js"):
    if replace_paths_in_file(js_file):
        file_types['JS'] += 1
        print(f"  ✓ {js_file.relative_to(ROOT)}")

# Update Python files
print("\n4️⃣  Updating Python files...")
for py_file in ROOT.rglob("*.py"):
    if py_file.name in ['audit_and_migrate.py', 'migrate_files.py', 'migrate_remaining.py', 'scan_paths.py', 'update_paths.py']:
        continue  # Skip helper scripts
    if replace_paths_in_file(py_file):
        file_types['Python'] += 1
        print(f"  ✓ {py_file.relative_to(ROOT)}")

# Summary
print("\n" + "=" * 80)
print("PATH UPDATE SUMMARY")
print("=" * 80)
total = sum(file_types.values())
for ftype, count in file_types.items():
    if count > 0:
        print(f"{ftype}: {count} files updated")

print(f"\nTotal: {total} files updated")
print("=" * 80)
