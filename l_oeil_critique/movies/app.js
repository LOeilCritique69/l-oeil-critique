const container = document.getElementById("film-list");
const searchInput = document.getElementById("search");
const counter = document.getElementById("film-count");
const sortSelect = document.getElementById("sort");

let allFilms = [];
let renderToken = 0;

/* =========================
   LOADER VISUEL
========================= */
function showLoading() {
    container.innerHTML = `
        <div class="loader">
            Chargement des films...
        </div>
    `;
}

/* =========================
   LOAD
========================= */
async function loadFilms() {
    try {
        showLoading();

        const response = await fetch("movies.json");
        const data = await response.json();

        let cleaned = cleanFilms(data);
        cleaned = removeDuplicates(cleaned);
        cleaned = sortFilms(cleaned, "recent");

        allFilms = cleaned;

        renderFilms(allFilms);

    } catch (error) {
        container.innerHTML = "<p>Erreur de chargement.</p>";
        console.error(error);
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
            name: String(film.Name || "Sans titre"),
            year: film.Year ? Number(film.Year) : 0,
            date: isNaN(date) ? 0 : date,
            rating,
            link: film["Letterboxd URI"] || "#",
            poster: film.poster_url || film.poster_path || null
        };

    }).filter(f => f.name && !isNaN(f.rating));
}

/* =========================
   DEDOUBLONNAGE
========================= */
function removeDuplicates(films) {
    const seen = new Set();

    return films.filter(f => {
        const key = f.name.toLowerCase();
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
    });
}

/* =========================
   TRI
========================= */
function sortFilms(films, mode) {

    return [...films].sort((a, b) => {

        switch (mode) {

            case "recent":
                return b.date - a.date;

            case "year":
                return b.year - a.year;

            case "year-asc":
                return a.year - b.year;

            case "rating":
            default:
                if (b.rating !== a.rating) return b.rating - a.rating;
                return b.year - a.year;
        }
    });
}

/* =========================
   COMPTEUR
========================= */
function updateCounter(count) {
    counter.textContent = `${count} films`;
}

/* =========================
   RENDER ULTRA OPTIMISÉ
========================= */
function renderFilms(films) {

    const token = ++renderToken;
    container.innerHTML = "";

    updateCounter(films.length);

    if (!films.length) {
        container.innerHTML = "<p>Aucun résultat.</p>";
        return;
    }

    const batchSize = 40;
    let index = 0;

    function renderBatch() {

        if (token !== renderToken) return;

        const slice = films.slice(index, index + batchSize);

        const fragment = document.createDocumentFragment();

        slice.forEach(film => {

            const div = document.createElement("div");
            div.className = "film-card";

            const img = film.poster
                ? `<img class="film-poster" loading="lazy" decoding="async" src="${film.poster}" alt="${film.name}">`
                : `<div class="film-poster placeholder"></div>`;

            div.innerHTML = `
                <div class="film-card-inner">
                    ${img}

                    <div class="film-title">${film.name}</div>
                    <div class="film-year">${film.year || "—"}</div>

                    <div class="film-rating">
                        ${film.rating.toFixed(1)} / 5
                    </div>

                    <a class="film-link" href="${film.link}" target="_blank">
                        Letterboxd
                    </a>
                </div>
            `;

            fragment.appendChild(div);
        });

        container.appendChild(fragment);

        index += batchSize;

        if (index < films.length) {
            requestAnimationFrame(renderBatch);
        }
    }

    requestAnimationFrame(renderBatch);
}

/* =========================
   FILTER + SORT
========================= */
function applyFilters() {

    const searchValue = searchInput.value.toLowerCase().trim();
    const sortMode = sortSelect.value;

    let filtered = allFilms;

    if (searchValue) {
        filtered = filtered.filter(f =>
            f.name.toLowerCase().includes(searchValue)
        );
    }

    filtered = sortFilms(filtered, sortMode);

    renderFilms(filtered);
}

/* =========================
   EVENTS
========================= */
searchInput.addEventListener("input", applyFilters);
sortSelect.addEventListener("change", applyFilters);

/* =========================
   INIT
========================= */
loadFilms();