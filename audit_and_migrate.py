#!/usr/bin/env python3
"""
Project Reorganization Audit Script
Generates a comprehensive migration map for all files
"""
import os
import json
from pathlib import Path
from collections import defaultdict

# Define the current and target structure
ROOT = Path(".")
LOEIL_DIR = ROOT / "l_oeil_critique"

# File categories
files_by_type = defaultdict(list)
encoding_issues = []
all_files = []

print("=" * 80)
print("AUDIT PHASE: Scanning all files in the project...")
print("=" * 80)

# Walk through all files
for fpath in sorted(LOEIL_DIR.rglob("*")):
    if not fpath.is_file():
        continue
    
    # Get relative path
    rel_path = fpath.relative_to(ROOT)
    all_files.append(str(rel_path))
    
    # Categorize by extension
    suffix = fpath.suffix.lower()
    if suffix in ['.html']:
        files_by_type['HTML'].append(str(rel_path))
    elif suffix in ['.css']:
        files_by_type['CSS'].append(str(rel_path))
    elif suffix in ['.js']:
        files_by_type['JS'].append(str(rel_path))
    elif suffix in ['.py']:
        files_by_type['Python'].append(str(rel_path))
    elif suffix in ['.json']:
        files_by_type['JSON'].append(str(rel_path))
    elif suffix in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif']:
        files_by_type['Images'].append(str(rel_path))
    elif suffix in ['.mp3', '.wav', '.ogg']:
        files_by_type['Audio'].append(str(rel_path))
    elif suffix in ['.mp4', '.webm', '.avi']:
        files_by_type['Video'].append(str(rel_path))
    else:
        files_by_type['Other'].append(str(rel_path))
    
    # Check for encoding issues (accents in filenames)
    if '#' in str(fpath) or 'U00' in str(fpath):
        encoding_issues.append(str(rel_path))

# Print summary
print("\n" + "=" * 80)
print("FILE INVENTORY BY CATEGORY")
print("=" * 80)

for category in sorted(files_by_type.keys()):
    files = files_by_type[category]
    print(f"\n{category}: {len(files)} files")
    for f in sorted(files)[:15]:  # Show first 15 of each category
        print(f"  - {f}")
    if len(files) > 15:
        print(f"  ... and {len(files) - 15} more")

print(f"\n{'='*80}")
print(f"TOTAL FILES: {len(all_files)}")
print(f"{'='*80}")

if encoding_issues:
    print(f"\n⚠️  FILES WITH ENCODING ISSUES: {len(encoding_issues)}")
    for f in encoding_issues:
        print(f"  - {f}")
else:
    print(f"\n✓ No encoding issues found")

# Print files at root level
print(f"\n{'='*80}")
print("ROOT LEVEL FILES")
print(f"{'='*80}")
for item in sorted(ROOT.glob("*")):
    if item.is_file():
        print(f"  - {item.name}")

# Print directories to check
print(f"\n{'='*80}")
print("MAIN DIRECTORIES")
print(f"{'='*80}")
for item in sorted(ROOT.glob("*")):
    if item.is_dir() and item.name != ".git":
        file_count = len(list(item.rglob("*")))
        print(f"  - {item.name}/ ({file_count} items)")

# Generate migration map
migration_map = {
    'HTML_FILES': files_by_type['HTML'],
    'CSS_FILES': files_by_type['CSS'],
    'JS_FILES': files_by_type['JS'],
    'PYTHON_FILES': files_by_type['Python'],
    'JSON_FILES': files_by_type['JSON'],
    'IMAGE_FILES': len(files_by_type['Images']),
    'ENCODING_ISSUES': encoding_issues,
    'TOTAL_FILES': len(all_files),
}

print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")
print(f"HTML files: {len(files_by_type['HTML'])}")
print(f"CSS files: {len(files_by_type['CSS'])}")
print(f"JS files: {len(files_by_type['JS'])}")
print(f"Python files: {len(files_by_type['Python'])}")
print(f"JSON files: {len(files_by_type['JSON'])}")
print(f"Image files: {len(files_by_type['Images'])}")
print(f"Encoding issues: {len(encoding_issues)}")

print("\n✓ Audit complete!")
