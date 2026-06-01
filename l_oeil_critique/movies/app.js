/* =========================
   SÉLECTEURS DOM
========================= */
const container     = document.getElementById("film-list");
const searchInput   = document.getElementById("search");
const counter       = document.getElementById("film-count");
const sortSelect    = document.getElementById("sort");
const ratingFilter  = document.getElementById("rating-filter");
const ratingVal     = document.getElementById("rating-val");
const sentinel      = document.getElementById("scroll-sentinel");
const loadIndicator = document.getElementById("load-more-indicator");

const statTotal = document.getElementById("stat-total");
const statAvg   = document.getElementById("stat-avg");
const statTop   = document.getElementById("stat-top");
const statYear  = document.getElementById("stat-year");

/* =========================
   ÉTAT
========================= */
let allFilms      = [];
let filteredFilms = [];

const PAGE_SIZE = 40;
let currentPage = 0;
let isLoading   = false;

/* =========================
   LOAD
========================= */
async function loadFilms() {
    container.innerHTML = `<div class="loader"><div class="loader-spinner"></div><span>Chargement des films…</span></div>`;

    try {
        const res  = await fetch("movies.json");
        const data = await res.json();

        let films = cleanFilms(data);
        films     = removeDuplicates(films);
        allFilms  = sortFilms(films, "recent");

        updateStats(allFilms);
        applyFilters();

    } catch (err) {
        container.innerHTML = `<div class="empty-state"><p>Erreur de chargement des films.</p></div>`;
        console.error("[loadFilms]", err);
    }
}

/* =========================
   NORMALISATION
========================= */
function cleanFilms(films) {
    return films
        .map(film => {
            let rating = Number(film.Rating);
            if (isNaN(rating)) rating = 0;
            if (rating > 5) rating = rating / 2;
            rating = Math.round(Math.max(0, Math.min(5, rating)) * 2) / 2; // arrondi au .5

            const date = film.Date ? Date.parse(film.Date) : 0;

            // Le lien Letterboxd doit pointer vers la critique perso.
            // Format attendu depuis le RSS : https://letterboxd.com/oni_le_chan/film/titre/
            // Les anciens films ont un lien court boxd.it — on le conserve comme fallback.
            const link = film["Letterboxd URI"] || "#";

            return {
                name:   String(film.Name ?? "Sans titre").trim(),
                year:   film.Year ? Number(film.Year) : 0,
                date:   isNaN(date) ? 0 : date,
                rating,
                link,
                poster: film.poster_url || null,
            };
        })
        .filter(f => f.name && f.name !== "undefined");
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
            case "recent":   return b.date   - a.date;
            case "year":     return b.year   - a.year;
            case "year-asc": return a.year   - b.year;
            case "rating":
            default:
                return b.rating !== a.rating ? b.rating - a.rating : b.year - a.year;
        }
    });
}

/* =========================
   STATS
========================= */
function updateStats(films) {
    if (!films.length) return;

    const rated    = films.filter(f => f.rating > 0);
    const avg      = rated.length ? rated.reduce((s, f) => s + f.rating, 0) / rated.length : 0;
    const top      = [...rated].sort((a, b) => b.rating - a.rating)[0];
    const curYear  = new Date().getFullYear();
    const thisYear = films.filter(f => f.date && new Date(f.date).getFullYear() === curYear).length;

    if (statTotal) statTotal.textContent = films.length;
    if (statAvg)   statAvg.textContent   = avg.toFixed(1) + " / 5";
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
   ÉTOILES — demi-étoiles Unicode propres
========================= */
function buildStars(rating) {
    const MAX    = 5;
    const filled = Math.floor(rating);
    const half   = (rating - filled) >= 0.5;
    const empty  = MAX - filled - (half ? 1 : 0);

    let html = '<div class="stars" aria-label="Note : ' + rating + ' sur 5">';
    for (let i = 0; i < filled; i++) html += '<span class="star star--full">★</span>';
    if (half)                         html += '<span class="star star--half">½</span>';
    for (let i = 0; i < empty;  i++) html += '<span class="star star--empty">★</span>';
    html += '</div>';
    return html;
}

/* =========================
   CARD
========================= */
function createCard(film) {
    const card = document.createElement("article");
    card.className = "film-card";

    // Clic sur la carte entière → ouvre le lien Letterboxd
    if (film.link && film.link !== "#") {
        card.style.cursor = "pointer";
        card.addEventListener("click", () => {
            window.open(film.link, "_blank", "noopener,noreferrer");
        });
    }

    const posterHTML = film.poster
        ? `<img class="film-poster" loading="lazy" decoding="async"
               src="${film.poster}"
               alt="${escapeAttr(film.name)}"
               onerror="this.parentElement.innerHTML='<div class=\\'film-poster placeholder\\'>🎬</div>'">`
        : `<div class="film-poster placeholder">🎬</div>`;

    const ratingBadge = film.rating > 0
        ? `<div class="poster-rating">${film.rating % 1 === 0 ? film.rating.toFixed(1) : film.rating}</div>`
        : "";

    const yearStr = film.year || "—";

    card.innerHTML = `
        <div class="film-poster-wrap">
            ${posterHTML}
            ${ratingBadge}
        </div>
        <div class="film-card-inner">
            <div class="film-title" title="${escapeAttr(film.name)}">${escapeHTML(film.name)}</div>
            ${buildStars(film.rating)}
            <div class="film-meta">
                <span class="film-year">${yearStr}</span>
                ${film.link && film.link !== "#"
                    ? `<span class="film-lb-badge">Letterboxd ↗</span>`
                    : ""}
            </div>
        </div>`;

    return card;
}

function escapeHTML(str) {
    return str.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}
function escapeAttr(str) {
    return str.replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}

/* =========================
   RENDER — pagination
========================= */
function renderPage(films, page) {
    const slice = films.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
    if (!slice.length) return false;

    const frag = document.createDocumentFragment();
    slice.forEach(f => frag.appendChild(createCard(f)));
    container.appendChild(frag);
    return slice.length === PAGE_SIZE;
}

function renderFilms(films) {
    container.innerHTML = "";
    currentPage = 0;
    updateCounter(Math.min(PAGE_SIZE, films.length), films.length);

    if (!films.length) {
        container.innerHTML = `
          <div class="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
            </svg>
            <p>Aucun résultat.</p>
          </div>`;
        return;
    }

    renderPage(films, 0);
    currentPage = 1;
}

/* =========================
   INFINITE SCROLL
========================= */
const observer = new IntersectionObserver(entries => {
    if (!entries[0].isIntersecting || isLoading) return;
    if (currentPage * PAGE_SIZE >= filteredFilms.length) return;

    isLoading = true;
    if (loadIndicator) loadIndicator.style.display = "flex";

    requestAnimationFrame(() => {
        renderPage(filteredFilms, currentPage);
        currentPage++;
        updateCounter(Math.min(currentPage * PAGE_SIZE, filteredFilms.length), filteredFilms.length);
        if (loadIndicator) loadIndicator.style.display = "none";
        isLoading = false;
    });
}, { rootMargin: "400px" });

if (sentinel) observer.observe(sentinel);

/* =========================
   FILTRES
========================= */
function applyFilters() {
    const query     = searchInput?.value.toLowerCase().trim() ?? "";
    const sortMode  = sortSelect?.value ?? "recent";
    const minRating = parseFloat(ratingFilter?.value ?? 0);

    let result = allFilms;

    if (query)       result = result.filter(f => f.name.toLowerCase().includes(query));
    if (minRating > 0) result = result.filter(f => f.rating >= minRating);

    result        = sortFilms(result, sortMode);
    filteredFilms = result;
    renderFilms(filteredFilms);
}

/* =========================
   EVENTS
========================= */
searchInput?.addEventListener("input", applyFilters);
sortSelect?.addEventListener("change", applyFilters);
ratingFilter?.addEventListener("input", () => {
    if (ratingVal) ratingVal.textContent = ratingFilter.value;
    applyFilters();
});

/* =========================
   INIT
========================= */
loadFilms();