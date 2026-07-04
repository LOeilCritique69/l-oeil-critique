#!/usr/bin/env python3
"""
Scan all files to identify path references that need updating
"""
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(".")

# Patterns to find path references
PATTERNS = {
    'href_css': r'<link[^>]*href=["\']([^"\']*\.css)["\'][^>]*>',
    'src_js': r'<script[^>]*src=["\']([^"\']*\.js)["\'][^>]*>',
    'src_img': r'<img[^>]*src=["\']([^"\']*(?:\.jpg|\.png|\.webp|\.gif|\.jpeg|\.svg|\.avif))["\'][^>]*>',
    'href_a': r'<a[^>]*href=["\']([^"\']*\.html)["\'][^>]*>',
    'url_css': r'url\(["\']?([^\)]*(?:\.jpg|\.png|\.webp|\.gif|\.jpeg|\.svg))["\']?\)',
    'import_css': r'@import\s+["\']([^"\']*\.css)["\']',
    'fetch_json': r'fetch\(["\']([^"\']*\.json)["\']',
    'src_video': r'<source[^>]*src=["\']([^"\']*(?:\.mp4|\.webm))["\']',
    'src_audio': r'<source[^>]*src=["\']([^"\']*(?:\.mp3|\.wav|\.ogg))["\']',
    'data_src': r'data-src=["\']([^"\']*)["\']',
}

# Current paths to search for
OLD_PATHS = [
    'l_oeil_critique/',
    'articles/bigactualités',
    'bigactualités',
    'tierlists',
    '../css/',
    '../scripts/',
    'movies/app.js',
    'movies/style.css',
    'movies/lb.py',
]

def scan_file(filepath):
    """Scan a file for path references"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        return None
    
    findings = defaultdict(list)
    
    for pattern_name, pattern in PATTERNS.items():
        matches = re.finditer(pattern, content)
        for match in matches:
            path_ref = match.group(1)
            if any(old in path_ref for old in OLD_PATHS):
                findings[pattern_name].append(path_ref)
    
    return findings if findings else None

# Scan all relevant files
print("=" * 80)
print("SCANNING FOR PATH REFERENCES NEEDING UPDATES")
print("=" * 80)

file_findings = defaultdict(lambda: defaultdict(list))
total_issues = 0

# Scan HTML files
print("\nScanning HTML files...")
for html_file in ROOT.rglob("*.html"):
    findings = scan_file(html_file)
    if findings:
        rel_path = html_file.relative_to(ROOT)
        for pattern_name, paths in findings.items():
            for path in paths:
                file_findings[str(rel_path)][pattern_name].append(path)
                total_issues += 1

# Scan CSS files
print("Scanning CSS files...")
for css_file in ROOT.rglob("*.css"):
    findings = scan_file(css_file)
    if findings:
        rel_path = css_file.relative_to(ROOT)
        for pattern_name, paths in findings.items():
            for path in paths:
                file_findings[str(rel_path)][pattern_name].append(path)
                total_issues += 1

# Scan JS files
print("Scanning JS files...")
for js_file in ROOT.rglob("*.js"):
    findings = scan_file(js_file)
    if findings:
        rel_path = js_file.relative_to(ROOT)
        for pattern_name, paths in findings.items():
            for path in paths:
                file_findings[str(rel_path)][pattern_name].append(path)
                total_issues += 1

# Print findings
print("\n" + "=" * 80)
print(f"FOUND {total_issues} PATH REFERENCES TO UPDATE")
print("=" * 80)

if file_findings:
    for filepath, patterns in sorted(file_findings.items()):
        print(f"\n📄 {filepath}")
        for pattern_name, paths in patterns.items():
            print(f"  [{pattern_name}]")
            for path in set(paths):
                print(f"    - {path}")
else:
    print("\n✓ No path references found that need updating!")

print("\n" + "=" * 80)
print("END OF SCAN")
print("=" * 80)
