/* =========================
   SÉLECTEURS DOM
========================= */
const container      = document.getElementById("film-list");
const searchInput    = document.getElementById("search");
const counter        = document.getElementById("film-count");
const sortSelect     = document.getElementById("sort");
const ratingFilter   = document.getElementById("rating-filter");
const ratingVal      = document.getElementById("rating-val");
const sentinel       = document.getElementById("scroll-sentinel");
const loadIndicator  = document.getElementById("load-more-indicator");

/* Stats */
const statTotal = document.getElementById("stat-total");
const statAvg   = document.getElementById("stat-avg");
const statTop   = document.getElementById("stat-top");
const statYear  = document.getElementById("stat-year");

/* =========================
   ÉTAT
========================= */
let allFilms     = [];   // tous les films nettoyés
let filteredFilms = [];  // après recherche + filtre note
let renderToken  = 0;

const PAGE_SIZE = 40;
let currentPage = 0;
let isLoading   = false;

/* =========================
   LOADER INITIAL
========================= */
function showLoading() {
    container.innerHTML = `<div class="loader">Chargement des films…</div>`;
}

/* =========================
   LOAD
========================= */
async function loadFilms() {
    showLoading();
    try {
        const res  = await fetch("movies.json");
        const data = await res.json();

        let cleaned = cleanFilms(data);
        cleaned = removeDuplicates(cleaned);
        allFilms = sortFilms(cleaned, "recent");

        updateStats(allFilms);
        applyFilters();

    } catch (err) {
        container.innerHTML = `<div class="empty-state"><p>Erreur de chargement.</p></div>`;
        console.error("[loadFilms]", err);
    }
}

/* =========================
   NORMALISATION
========================= */
function cleanFilms(films) {
    return films.map(film => {
        let rating = Number(film.Rating);
        if (rating > 5) rating = rating / 2;
        rating = Math.max(0, Math.min(5, rating));

        const date = film.Date ? Date.parse(film.Date) : 0;

        return {
            name:   String(film.Name ?? "Sans titre").trim(),
            year:   film.Year  ? Number(film.Year)  : 0,
            date:   isNaN(date) ? 0 : date,
            rating,
            link:   film["Letterboxd URI"] || "#",
            poster: film.poster_url || film.poster_path || null
        };
    }).filter(f => f.name && !isNaN(f.rating));
}

/* =========================
   DÉDOUBLONNAGE
========================= */
function removeDuplicates(films) {
    const seen = new Set();
    return films.filter(f => {
        const k = f.name.toLowerCase();
        if (seen.has(k)) return false;
        seen.add(k);
        return true;
    });
}

/* =========================
   TRI
========================= */
function sortFilms(films, mode) {
    return [...films].sort((a, b) => {
        switch (mode) {
            case "recent":    return b.date   - a.date;
            case "year":      return b.year   - a.year;
            case "year-asc":  return a.year   - b.year;
            case "rating":
            default:
                return b.rating !== a.rating
                    ? b.rating - a.rating
                    : b.year   - a.year;
        }
    });
}

/* =========================
   STATS
========================= */
function updateStats(films) {
    if (!films.length) return;

    const rated  = films.filter(f => f.rating > 0);
    const avg    = rated.reduce((s, f) => s + f.rating, 0) / (rated.length || 1);
    const top    = [...rated].sort((a, b) => b.rating - a.rating)[0];
    const curYear = new Date().getFullYear();
    const thisYear = films.filter(f => {
        if (!f.date) return false;
        return new Date(f.date).getFullYear() === curYear;
    }).length;

    if (statTotal) statTotal.textContent = films.length;
    if (statAvg)   statAvg.textContent   = avg.toFixed(2) + " / 5";
    if (statTop)   statTop.textContent   = top ? top.name : "—";
    if (statYear)  statYear.textContent  = thisYear;
}

/* =========================
   COMPTEUR
========================= */
function updateCounter(shown, total) {
    if (!counter) return;
    counter.textContent = shown < total
        ? `${shown} / ${total} films`
        : `${total} film${total > 1 ? "s" : ""}`;
}

/* =========================
   ÉTOILES SVG
========================= */
function buildStars(rating) {
    const MAX = 5;
    let html = '<div class="stars">';
    for (let i = 1; i <= MAX; i++) {
        const diff = rating - (i - 1);
        let cls = "star";
        if (diff >= 1)        cls += " filled";
        else if (diff >= 0.5) cls += " half-filled";
        html += `
          <svg class="${cls}" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
            <path d="M10 1l2.4 4.9 5.4.8-3.9 3.8.9 5.4L10 13.4l-4.8 2.5.9-5.4L2.2 6.7l5.4-.8z"/>
          </svg>`;
    }
    html += '</div>';
    return html;
}

/* =========================
   CRÉATION D'UNE CARD
========================= */
function createCard(film) {
    const div = document.createElement("div");
    div.className = "film-card";

    const posterHTML = film.poster
        ? `<img class="film-poster" loading="lazy" decoding="async"
               src="${film.poster}"
               alt="${film.name}"
               onerror="this.outerHTML='<div class=\\'film-poster placeholder\\'>🎬</div>'">`
        : `<div class="film-poster placeholder">🎬</div>`;

    const ratingBadge = film.rating > 0
        ? `<div class="poster-rating">${film.rating % 1 === 0 ? film.rating + ".0" : film.rating}</div>`
        : "";

    div.innerHTML = `
        <div class="film-poster-wrap">
            ${posterHTML}
            ${ratingBadge}
        </div>
        <div class="film-card-inner">
            <div class="film-title" title="${film.name}">${film.name}</div>
            ${buildStars(film.rating)}
            <div class="film-meta">
                <span class="film-year">${film.year || "—"}</span>
                <a class="film-link" href="${film.link}" target="_blank" rel="noopener" onclick="event.stopPropagation()">
                    Letterboxd ↗
                </a>
            </div>
        </div>`;
    return div;
}

/* =========================
   RENDER (page)
========================= */
function renderPage(films, page) {
    const start = page * PAGE_SIZE;
    const slice = films.slice(start, start + PAGE_SIZE);
    if (!slice.length) return false;

    const fragment = document.createDocumentFragment();
    slice.forEach(film => fragment.appendChild(createCard(film)));
    container.appendChild(fragment);
    return slice.length === PAGE_SIZE; // true = il reste peut-être plus
}

/* =========================
   RENDER COMPLET (reset)
========================= */
function renderFilms(films) {
    ++renderToken;
    container.innerHTML = "";
    currentPage = 0;

    updateCounter(Math.min(PAGE_SIZE, films.length), films.length);

    if (!films.length) {
        container.innerHTML = `
          <div class="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
            </svg>
            <p>Aucun résultat pour cette recherche.</p>
          </div>`;
        return;
    }

    renderPage(films, 0);
    currentPage = 1;
}

/* =========================
   INFINITE SCROLL (IO)
========================= */
const observer = new IntersectionObserver(entries => {
    if (!entries[0].isIntersecting || isLoading) return;
    const start = currentPage * PAGE_SIZE;
    if (start >= filteredFilms.length) return;

    isLoading = true;
    loadIndicator.style.display = "flex";

    // Micro-délai pour le feedback visuel
    requestAnimationFrame(() => {
        const hasMore = renderPage(filteredFilms, currentPage);
        currentPage++;
        updateCounter(Math.min(currentPage * PAGE_SIZE, filteredFilms.length), filteredFilms.length);
        loadIndicator.style.display = "none";
        isLoading = false;
    });
}, { rootMargin: "300px" });

if (sentinel) observer.observe(sentinel);

/* =========================
   FILTRE + TRI
========================= */
function applyFilters() {
    const query     = searchInput.value.toLowerCase().trim();
    const sortMode  = sortSelect.value;
    const minRating = parseFloat(ratingFilter?.value ?? 0);

    let result = allFilms;

    if (query) {
        result = result.filter(f => f.name.toLowerCase().includes(query));
    }

    if (minRating > 0) {
        result = result.filter(f => f.rating >= minRating);
    }

    result = sortFilms(result, sortMode);
    filteredFilms = result;

    renderFilms(filteredFilms);
}

/* =========================
   EVENTS
========================= */
searchInput.addEventListener("input", applyFilters);
sortSelect.addEventListener("change", applyFilters);

if (ratingFilter) {
    ratingFilter.addEventListener("input", () => {
        if (ratingVal) ratingVal.textContent = ratingFilter.value;
        applyFilters();
    });
}

/* =========================
   INIT
========================= */
loadFilms();