# MIGRATION_MAP.md
## Project Reorganization: L'Œil Critique
**Date:** 2026-07-04  
**Branch:** `reorganisation-site`

---

## AUDIT SUMMARY
- **Total Files:** 494
- **HTML Files:** 93
- **CSS Files:** 6
- **JS Files:** 8
- **Python Files:** 4 (root) + 4 (l_oeil_critique)
- **JSON Files:** 6
- **Image Files:** 373
- **Audio Files:** 3

---

## PHASE 1: FILE RENAME (FIX TYPOS & ENCODING)

### Typos to Fix
1. `arrticle.py` → `article.py` (at root)
2. `google9fefd7ab56c78400.html` → `verify_google_ownership.html` (at root, optional cleanup)

### Folder Names with Accents (Web-Friendly Conversion)
1. `l_oeil_critique/articles/bigactualités/` → `l_oeil_critique/articles/actualites/`
2. `l_oeil_critique/assets/img/bigactualités/` → `l_oeil_critique/assets/img/actualites/`

### HTML Files with Accents in Names (Move & Rename)
1. `l_oeil_critique/mentions_légales.html` → `pages/mentions-legales.html`
2. `l_oeil_critique/politique-de-confidentialité.html` → `pages/politique-de-confidentialite.html`

---

## PHASE 2: FILE MOVEMENT PLAN

### Root Level HTML Files → pages/
```
l_oeil_critique/A_propos.html                    → pages/a-propos.html
l_oeil_critique/anecdotes.html                   → pages/anecdotes.html
l_oeil_critique/bande-annonces.html              → pages/bande-annonces.html
l_oeil_critique/contact.html                     → pages/contact.html
l_oeil_critique/devine-le-film.html              → pages/devine-le-film.html
l_oeil_critique/reviews.html                     → pages/reviews.html
l_oeil_critique/mentions_légales.html            → pages/mentions-legales.html
l_oeil_critique/politique-de-confidentialité.html → pages/politique-de-confidentialite.html
```

### Existing pages/ Content Relocation
```
l_oeil_critique/pages/critique-films.html        → pages/critique-films.html (no change)
l_oeil_critique/pages/critique-series.html       → pages/critique-series.html (no change)
l_oeil_critique/pages/tier-lists.html            → pages/tier-lists.html (no change)
l_oeil_critique/pages/tier-list/                 → pages/tier-list/ (no change)
```

### Root HTML Files → news/
```
(Currently, news/ has: Accueil.html, actualites.html, films.html, series.html)
(These stay as-is)
```

### Articles Reorganization
```
l_oeil_critique/articles/blocs_films.html        → assets/data/blocs_films.html (or keep where?)
l_oeil_critique/articles/blocs_series.html       → assets/data/blocs_series.html (or keep where?)
l_oeil_critique/articles/bigactualités/          → articles/actualites/
l_oeil_critique/articles/films/                  → articles/films/ (no change)
l_oeil_critique/articles/series/                 → articles/series/ (no change)
l_oeil_critique/articles/reviews/                → articles/reviews/ (no change)
```

### CSS Files → assets/css/
```
l_oeil_critique/css/chef_d_oeuvre.css            → assets/css/chef_d_oeuvre.css
l_oeil_critique/css/createblog.css               → assets/css/createblog.css
l_oeil_critique/css/createblog_article.css       → assets/css/createblog_article.css
l_oeil_critique/css/devise.css                   → assets/css/devine.css (fix typo?)
l_oeil_critique/css/list-pages.css               → assets/css/list-pages.css
l_oeil_critique/movies/style.css                 → assets/css/movies.css
```

### JavaScript Files → assets/js/
```
l_oeil_critique/assets/js/header.js              → assets/js/header.js (no change)
l_oeil_critique/assets/js/jeu-devine-le-film.js  → assets/js/jeu-devine-le-film.js (no change)
l_oeil_critique/assets/js/loadFilmsBlocks.js     → assets/js/loadFilmsBlocks.js (no change)
l_oeil_critique/assets/js/loadSeriesBlocks.js    → assets/js/loadSeriesBlocks.js (no change)
l_oeil_critique/assets/js/loadTrailers.js        → assets/js/loadTrailers.js (no change)
l_oeil_critique/assets/js/main.js                → assets/js/main.js (no change)
l_oeil_critique/assets/js/slider.js              → assets/js/slider.js (no change)
l_oeil_critique/movies/app.js                    → assets/js/movies.js
```

### Python Scripts → scripts/
```
arrticle.py                                       → scripts/article.py (also at root → scripts)
seo_injector.py                                   → scripts/seo_injector.py (at root → scripts)
update_pages_webp.py                              → scripts/update_pages_webp.py (at root → scripts)
l_oeil_critique/scripts/optimize_images.py       → scripts/optimize_images.py
l_oeil_critique/scripts/scraper_bandes_annonces.py → scripts/scraper_bandes_annonces.py
l_oeil_critique/scripts/sitemap_generator.py     → scripts/sitemap_generator.py
l_oeil_critique/movies/lb.py                     → scripts/movies_lb.py (or movies/lb.py, keep separate)
```

### JSON Data Files → assets/data/
```
l_oeil_critique/assets/data/articles_index.json  → assets/data/articles_index.json (no change)
l_oeil_critique/assets/data/notifications.json   → assets/data/notifications.json (no change)
l_oeil_critique/movies/movies.json               → assets/data/movies.json
l_oeil_critique/movies/movies_enriched.json      → assets/data/movies_enriched.json
l_oeil_critique/movies/tmdb_cache.json           → assets/data/tmdb_cache.json
l_oeil_critique/scripts/bande_annonces_log.json  → assets/data/bande_annonces_log.json
```

### Movies Mini-App
```
l_oeil_critique/movies/movies.html               → movies/movies.html (keep as is)
l_oeil_critique/movies/app.js                    → assets/js/movies.js
l_oeil_critique/movies/style.css                 → assets/css/movies.css
l_oeil_critique/movies/*.json                    → assets/data/
```

### Images → assets/img/
```
l_oeil_critique/assets/img/bigactualités/        → assets/img/actualites/
l_oeil_critique/assets/img/films/                → assets/img/films/ (no change)
l_oeil_critique/assets/img/series/               → assets/img/series/ (no change)
l_oeil_critique/assets/img/tierlists/            → assets/img/tier-lists/ (snake_case → kebab-case)
l_oeil_critique/assets/img/reviews/              → assets/img/reviews/ (no change)
```

### Root Images
```
l_oeil_critique/fond-grain-noir.jpg              → assets/img/fond-grain-noir.jpg
l_oeil_critique/logo_chef_doeuvre_processed_copy.jpg → assets/img/logo_chef_doeuvre_processed_copy.jpg
```

### Audio Files → assets/sounds/
```
l_oeil_critique/assets/sounds/*.mp3              → assets/sounds/ (no change)
```

---

## PHASE 3: PATH UPDATES REQUIRED

### HTML Files Needing Updates
- All `<link href="...">` paths to CSS files
- All `<script src="...">` paths to JS files
- All `<img src="...">` paths to image files
- All `<a href="...">` paths to other HTML pages
- All `<source src="...">` paths for audio/video

### CSS Files Needing Updates
- `@import` statements
- `background-image: url()` statements
- All relative paths in CSS

### JavaScript Files Needing Updates
- `fetch()` calls to JSON files
- `import` statements
- File path string references
- Script inclusions

### Python Scripts Needing Updates
- File path operations (open(), Path(), os.path)
- Imports referencing other scripts
- Hard-coded folder references

### Workflow File
```
.github/workflows/run_bande_annonce.yml:
  - python l_oeil_critique/scripts/scraper_bandes_annonces.py → python scripts/scraper_bandes_annonces.py
  - python l_oeil_critique/movies/lb.py → python scripts/movies_lb.py (or keep as-is if movies stays)
  - python l_oeil_critique/scripts/optimize_images.py → python scripts/optimize_images.py
  - python l_oeil_critique/scripts/sitemap_generator.py → python scripts/sitemap_generator.py
```

---

## PHASE 4: TARGET STRUCTURE

```
/
├── index.html
├── robots.txt
├── sitemap.xml
├── ads.txt
├── requirements.txt
├── readme.md
│
├── .github/workflows/
│   └── run_bande_annonce.yml
│
├── pages/
│   ├── a-propos.html
│   ├── contact.html
│   ├── mentions-legales.html
│   ├── politique-de-confidentialite.html
│   ├── anecdotes.html
│   ├── reviews.html
│   ├── devine-le-film.html
│   ├── bande-annonces.html
│   ├── critique-films.html
│   ├── critique-series.html
│   ├── tier-lists.html
│   └── tier-list/
│       ├── 28.html
│       ├── DCAMU.html
│       ├── Harry-Potter.html
│       └── ...
│
├── news/
│   ├── accueil.html
│   ├── actualites.html
│   ├── films.html
│   └── series.html
│
├── articles/
│   ├── actualites/             (ex "bigactualités")
│   ├── films/
│   ├── series/
│   ├── reviews/
│   │   ├── films/
│   │   └── series/
│   ├── blocs_films.html
│   └── blocs_series.html
│
├── movies/
│   └── movies.html
│
├── assets/
│   ├── css/
│   │   ├── chef_d_oeuvre.css
│   │   ├── createblog.css
│   │   ├── createblog_article.css
│   │   ├── devine.css
│   │   ├── list-pages.css
│   │   └── movies.css
│   ├── js/
│   │   ├── header.js
│   │   ├── jeu-devine-le-film.js
│   │   ├── loadFilmsBlocks.js
│   │   ├── loadSeriesBlocks.js
│   │   ├── loadTrailers.js
│   │   ├── main.js
│   │   ├── slider.js
│   │   └── movies.js
│   ├── img/
│   │   ├── actualites/
│   │   ├── films/
│   │   ├── series/
│   │   ├── tier-lists/
│   │   ├── reviews/
│   │   ├── fond-grain-noir.jpg
│   │   └── logo_chef_doeuvre_processed_copy.jpg
│   ├── data/
│   │   ├── articles_index.json
│   │   ├── notifications.json
│   │   ├── movies.json
│   │   ├── movies_enriched.json
│   │   ├── tmdb_cache.json
│   │   └── bande_annonces_log.json
│   └── sounds/
│       ├── 5000000-music-mp3cut.mp3
│       ├── correct-answer-sound-effect-19.mp3
│       └── incorrect.swf.mp3
│
└── scripts/
    ├── article.py
    ├── seo_injector.py
    ├── update_pages_webp.py
    ├── optimize_images.py
    ├── scraper_bandes_annonces.py
    ├── sitemap_generator.py
    ├── movies_lb.py
    └── bande_annonces_log.json
```

---

## EXECUTION PLAN

### Commit Strategy
1. **Commit 1:** Fix filenames & folder names (typos + accents)
2. **Commit 2:** Move CSS files to assets/css/
3. **Commit 3:** Move JS files to assets/js/
4. **Commit 4:** Move Python scripts to scripts/
5. **Commit 5:** Move JSON data to assets/data/
6. **Commit 6:** Move HTML pages to pages/ and news/
7. **Commit 7:** Move images to assets/img/
8. **Commit 8:** Update all paths in HTML/CSS/JS
9. **Commit 9:** Update Python scripts with new paths
10. **Commit 10:** Update GitHub workflows
11. **Commit 11:** Final cleanup & verification

---

## NOTES
- The `l_oeil_critique/` prefix will be removed once all files are moved
- All new paths will be relative to project root
- Backward compatibility: if old paths are referenced anywhere, they must be updated
- Testing required: run all Python scripts to verify path handling
- Testing required: serve site locally to verify URL paths work correctly
