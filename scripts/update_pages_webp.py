import os
import re
from pathlib import Path

root = Path(r"d:\projet_webs\CHEF D'OEUVRE\l_oeil_critique\pages")
asset_root = Path(r"d:\projet_webs\CHEF D'OEUVRE\l_oeil_critique\assets")

# Build map of lowercase basename -> candidate webp assets
webp_assets = {}
for path in asset_root.rglob('*.webp'):
    webp_assets.setdefault(path.name.lower(), []).append(path)

pattern = re.compile(r'((?:src|content)=)(["\'])([^"\']+)(\2)')

for html_file in root.rglob('*.html'):
    text = html_file.read_text(encoding='utf-8')
    original = text

    def repl(match):
        attr = match.group(1)
        quote = match.group(2)
        path = match.group(3)

        if path.startswith(('http://', 'https://', 'data:')):
            return match.group(0)

        if path.lower().endswith('.webp'):
            return match.group(0)

        if not any(path.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.avif']):
            return match.group(0)

        rel_path = path.replace('\\', '/')
        candidate = (html_file.parent / rel_path).resolve()
        stem = candidate.stem if candidate.exists() else Path(rel_path).stem
        candidates = webp_assets.get(f'{stem}.webp'.lower(), [])
        if not candidates:
            return match.group(0)

        # Prefer same directory or same relative subtree when possible
        same_dir = [p for p in candidates if p.parent == candidate.parent]
        chosen = same_dir[0] if same_dir else candidates[0]
        rel = os.path.relpath(chosen, html_file.parent).replace(os.sep, '/')
        return f'{attr}{quote}{rel}{quote}'

    text = pattern.sub(repl, text)
    if text != original:
        html_file.write_text(text, encoding='utf-8')
        print(f'updated {html_file.relative_to(root)}')
