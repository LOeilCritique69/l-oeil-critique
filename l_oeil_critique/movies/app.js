/* Mes Films — L'Œil Critique */
(() => {
  const $ = id => document.getElementById(id);

  const list = $("film-list"), search = $("search"), sortSel = $("sort"), sortGroup = $("sort-group"),
        decadeSel = $("decade-filter"), genreSel = $("genre-filter"), genreGroup = $("genre-group"),
        minRating = $("rating-filter"), ratingVal = $("rating-val"),
        counter = $("film-count"), sentinel = $("scroll-sentinel"), more = $("load-more-indicator"),
        resetBtn = $("reset-filters");

  const btnMasterpieces = $("filter-masterpieces"), btnFirstWatch = $("filter-firstwatch"),
        btnUnrated = $("filter-unrated"), btnRewatch = $("filter-rewatch"), btnReviewed = $("filter-reviewed"),
        btnRandom = $("btn-random-film"),
        countMasterpieces = $("count-masterpieces"), countFirstWatch = $("count-firstwatch"),
        countUnrated = $("count-unrated"), countRewatch = $("count-rewatch"), countReviewed = $("count-reviewed");

  const listView = $("list-view"), calendarView = $("calendar-view"), statsView = $("stats-view"),
        statsDashboard = $("stats-dashboard"),
        btnViewList = $("btn-view-list"), btnViewCal = $("btn-view-calendar"), btnViewStats = $("btn-view-stats"),
        calMonthSel = $("cal-month-select"), calYearSel = $("cal-year-select"),
        calGrid = $("calendar-grid"), calMonthCount = $("cal-month-count"),
        calPrev = $("cal-prev"), calNext = $("cal-next"), calToday = $("cal-today"),
        calMatchesBar = $("cal-matches-bar"), calMatchesLabel = $("cal-matches-label"), calMatchesList = $("cal-matches-list"),
        calModal = $("cal-modal"), calModalTitle = $("cal-modal-title"), calModalBody = $("cal-modal-body");

  const PAGE = 40;
  const CACHE_KEY = "oc_omdb_posters_v1";
  const MAX_REAL_MOVIES_PER_DAY = 5;
  const API_BASE = ["127.0.0.1", "localhost"].includes(window.location.hostname) && window.location.port !== "8888"
    ? "https://l-oeil-critique.netlify.app"
    : "";

  const MONTHS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"];
  const MONTHS_SHORT = ["Janv.", "Févr.", "Mars", "Avr.", "Mai", "Juin", "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc."];

  let catalogFilms = [];
  let diaryEntries = [];
  let shownList = [];
  let shownCal = [];
  let page = 0;
  let currentView = "list";
  let calYear = new Date().getFullYear(), calMonth = new Date().getMonth();
  let onlyMasterpieces = false, onlyFirstWatch = false, onlyUnrated = false, onlyRewatch = false, onlyReviewed = false;

  const norm = s => String(s ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = n => String(n).replace(".", ",");
  const movieKey = (name, year) => `${norm(name)}|${Number(year) || 0}`;

  const isFiltered = () =>
    Boolean(search.value.trim()) ||
    decadeSel.value !== "all" ||
    genreSel.value !== "all" ||
    (parseFloat(minRating.value) || 0) > 0 ||
    onlyMasterpieces || onlyFirstWatch || onlyUnrated || onlyRewatch || onlyReviewed;

  /* ---------- Cache & récupération OMDb via /.netlify/functions/poster ---------- */
  let posterCache = {};
  try {
    posterCache = JSON.parse(localStorage.getItem(CACHE_KEY) || "{}");
  } catch {
    posterCache = {};
  }

  function savePosterCache() {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify(posterCache));
    } catch { /* quota localStorage atteint */ }
  }

  const inflightRequests = new Map();

  async function resolvePoster(film) {
    if (film.poster) return film.poster;
    const key = movieKey(film.name, film.year);

    if (Object.prototype.hasOwnProperty.call(posterCache, key) && posterCache[key]) {
      film.poster = posterCache[key];
      return film.poster;
    }

    if (inflightRequests.has(key)) {
      const url = await inflightRequests.get(key);
      film.poster = url;
      return url;
    }

    const req = (async () => {
      try {
        const query = async (withYear) => {
          const params = new URLSearchParams({ t: film.name });
          if (withYear && film.year) params.set("y", String(film.year));
          const res = await fetch(`${API_BASE}/.netlify/functions/poster?${params.toString()}`);
          if (!res.ok) return null;
          return res.json();
        };

        let data = await query(true);
        if ((!data || data.Response === "False") && film.year) {
          data = await query(false);
        }

        const url = data && data.Response === "True" && data.Poster && data.Poster !== "N/A"
          ? data.Poster
          : null;

        if (url) {
          posterCache[key] = url;
          savePosterCache();
        }
        return url;
      } catch {
        return null;
      } finally {
        inflightRequests.delete(key);
      }
    })();

    inflightRequests.set(key, req);
    film.poster = await req;
    return film.poster;
  }

  /* ---------- Nettoyage & normalisation des données ---------- */
  function cleanEntries(raw, isFallbackWatched = false) {
    return (raw || []).filter(f => f && String(f.Name ?? "").trim()).map(f => {
      let r = Number(f.Rating);
      if (!isFinite(r)) r = 0;
      if (r > 5) r /= 2;
      r = Math.round(Math.max(0, Math.min(5, r)) * 2) / 2;

      const rawDate = String(f.Date || "").trim();
      const dateStr = /^\d{4}-\d{2}-\d{2}$/.test(rawDate) ? rawDate : null;
      const d = dateStr ? Date.parse(dateStr + "T12:00:00") : 0;

      const name = String(f.Name).trim();
      const year = Number(f.Year) || 0;
      const key = movieKey(name, year);

      const jsonPoster = f.poster_url || (f.poster_path ? "https://image.tmdb.org/t/p/w500" + f.poster_path : null);
      const poster = jsonPoster || posterCache[key] || null;
      const genres = Array.isArray(f.Genres) ? f.Genres.map(g => String(g).trim()).filter(Boolean) : [];

      return {
        name,
        year,
        date: isFinite(d) ? d : 0,
        dateStr,
        rating: r,
        rewatch: Boolean(f.Rewatch) || (Number(f.RewatchCount) || 0) > 1,
        review: String(f.Review || "").trim(),
        director: String(f.Director || "").trim(),
        actors: String(f.Actors || "").trim(),
        genres,
        runtime: Number(f.Runtime) || 0,
        poster,
        link: /^https?:\/\//.test(f["Letterboxd URI"] || "") ? f["Letterboxd URI"] : null,
        tmdb: f.tmdb_id || null,
        fromWatched: isFallbackWatched
      };
    });
  }

  function dedupe(films) {
    const map = new Map();
    for (const f of films) {
      const k = f.tmdb ? "t" + f.tmdb : "n" + movieKey(f.name, f.year);
      const cur = map.get(k);
      if (!cur || f.date > cur.date) map.set(k, f);
    }
    return [...map.values()];
  }

  const sorters = {
    recent: (a, b) => b.date - a.date || a.name.localeCompare(b.name),
    rating: (a, b) => b.rating - a.rating || b.date - a.date,
    year: (a, b) => b.year - a.year || a.name.localeCompare(b.name),
    "year-asc": (a, b) => a.year - b.year || a.name.localeCompare(b.name),
    runtime: (a, b) => b.runtime - a.runtime || a.name.localeCompare(b.name),
    title: (a, b) => a.name.localeCompare(b.name, "fr")
  };

  /* ---------- Rendu Grille / Liste ---------- */
  function buildPosterImg(url, altText, className = "film-poster") {
    const img = document.createElement("img");
    img.className = className;
    img.loading = "lazy";
    img.decoding = "async";
    img.alt = altText;
    img.src = url;
    if (url.includes("image.tmdb.org/t/p/w500/")) {
      img.srcset = `${url.replace("/w500/", "/w342/")} 342w, ${url} 500w`;
      img.sizes = "(max-width:640px) 45vw, 200px";
    }
    return img;
  }

  function card(f) {
    const el = document.createElement(f.link ? "a" : "article");
    el.className = "film-card";
    if (f.link) {
      el.href = f.link;
      el.target = "_blank";
      el.rel = "noopener noreferrer";
    }

    const badge = f.rating
      ? `<span class="poster-rating">${fmt(f.rating)}</span>`
      : `<span class="poster-rating poster-rating--unrated">Sans note</span>`;
    const rewatchTag = f.rewatch ? `<span class="poster-rewatch" title="Film revu">↻</span>` : "";

    el.innerHTML = `
      <div class="film-poster-wrap">
        <div class="film-poster film-poster--none">${esc(f.name)}</div>
        ${badge}${rewatchTag}
      </div>
      <div class="film-card-inner">
        <div class="film-title" title="${esc(f.name)}">${esc(f.name)}</div>
        ${f.director ? `<div class="film-director" title="${esc(f.director)}">${esc(f.director)}</div>` : ""}
        ${f.rating
          ? `<span class="stars" style="--r:${f.rating}" role="img" aria-label="Note : ${fmt(f.rating)} sur 5">★★★★★</span>`
          : `<span class="unrated-label">Vu · Non noté</span>`}
        <div class="film-meta"><span>${f.year || "—"}${f.runtime ? ` · ${f.runtime}m` : ""}</span>${f.link ? '<span class="film-lb">Letterboxd ↗</span>' : ""}</div>
      </div>`;

    const wrap = el.querySelector(".film-poster-wrap");
    const placeholder = wrap.querySelector(".film-poster--none");

    const mountImage = url => {
      if (!url) return;
      const img = buildPosterImg(url, `Affiche de ${f.name}`);
      img.addEventListener("error", () => img.replaceWith(placeholder), { once: true });
      placeholder.replaceWith(img);
    };

    if (f.poster) {
      mountImage(f.poster);
    } else {
      resolvePoster(f).then(mountImage);
    }

    return el;
  }

  function renderPage() {
    const slice = shownList.slice(page * PAGE, (page + 1) * PAGE);
    if (!slice.length) return;
    const frag = document.createDocumentFragment();
    slice.forEach(f => frag.appendChild(card(f)));
    list.appendChild(frag);
    page++;
    updateCounter();
  }

  function updateCounter() {
    if (currentView === "stats") {
      counter.textContent = `Analyse statistique sur ${catalogFilms.length} films`;
      return;
    }
    if (currentView === "calendar") {
      const dated = shownCal.filter(f => f.dateStr).length;
      counter.textContent = isFiltered()
        ? (dated ? `${dated} entrée${dated > 1 ? "s" : ""} trouvée${dated > 1 ? "s" : ""}` : "Aucune entrée datée trouvée")
        : `${dated} film${dated > 1 ? "s" : ""} daté${dated > 1 ? "s" : ""} dans le calendrier`;
      return;
    }
    if (!shownList.length) { counter.textContent = "0 film"; return; }
    const visible = Math.min(page * PAGE, shownList.length);
    counter.textContent = visible < shownList.length
      ? `${visible} / ${shownList.length} films`
      : `${shownList.length} film${shownList.length > 1 ? "s" : ""}`;
  }

  function renderAll() {
    list.innerHTML = "";
    page = 0;
    if (!shownList.length) {
      list.innerHTML = '<div class="empty-state"><p>Aucun résultat pour ces critères.</p></div>';
      updateCounter();
      return;
    }
    renderPage();
    rearm();
  }

  function rearm() { observer.unobserve(sentinel); observer.observe(sentinel); }
  const observer = new IntersectionObserver(([e]) => {
    if (currentView !== "list" || !e.isIntersecting || page * PAGE >= shownList.length) return;
    more.hidden = false;
    requestAnimationFrame(() => { renderPage(); more.hidden = true; rearm(); });
  }, { rootMargin: "500px" });

  /* ---------- Rendu Calendrier ---------- */
  function initCalendarSelectors() {
    calMonthSel.innerHTML = MONTHS_FR.map((m, idx) => `<option value="${idx}">${m}</option>`).join("");
    const years = new Set([new Date().getFullYear()]);
    for (const f of diaryEntries) {
      if (f.dateStr) years.add(Number(f.dateStr.slice(0, 4)));
    }
    calYearSel.innerHTML = [...years].sort((a, b) => b - a).map(y => `<option value="${y}">${y}</option>`).join("");
  }

  function syncCalendarSelectors() {
    calMonthSel.value = String(calMonth);
    if (![...calYearSel.options].some(o => Number(o.value) === calYear)) {
      const opt = document.createElement("option");
      opt.value = String(calYear);
      opt.textContent = String(calYear);
      calYearSel.appendChild(opt);
    }
    calYearSel.value = String(calYear);
  }

  function getMatchingMonths() {
    const map = new Map();
    for (const f of shownCal) {
      if (!f.dateStr) continue;
      const ym = f.dateStr.slice(0, 7);
      if (!map.has(ym)) {
        const [y, m] = ym.split("-").map(Number);
        map.set(ym, { ym, year: y, month: m - 1, count: 0, titles: [] });
      }
      const entry = map.get(ym);
      entry.count++;
      if (!entry.titles.includes(f.name)) entry.titles.push(f.name);
    }
    return [...map.values()].sort((a, b) => b.ym.localeCompare(a.ym));
  }

  function renderMatchingMonthsBar(matchingMonths) {
    if (!isFiltered()) {
      calMatchesBar.hidden = true;
      calMatchesList.innerHTML = "";
      return;
    }
    calMatchesBar.hidden = false;
    if (!matchingMonths.length) {
      calMatchesLabel.textContent = "Aucun visionnage daté pour ce filtre.";
      calMatchesList.innerHTML = "";
      return;
    }

    const totalMatches = matchingMonths.reduce((sum, m) => sum + m.count, 0);
    calMatchesLabel.textContent = `${totalMatches} visionnage${totalMatches > 1 ? "s" : ""} sur ${matchingMonths.length} mois :`;

    const currentYm = `${calYear}-${String(calMonth + 1).padStart(2, "0")}`;
    calMatchesList.innerHTML = matchingMonths.map(m => {
      const preview = m.titles.slice(0, 3).join(", ") + (m.titles.length > 3 ? "…" : "");
      return `
        <button type="button" class="cal-match-pill ${m.ym === currentYm ? "active" : ""}"
                data-year="${m.year}" data-month="${m.month}" title="${esc(preview)}">
          <span>${MONTHS_SHORT[m.month]} ${m.year}</span>
          <strong>${m.count}</strong>
        </button>`;
    }).join("");

    calMatchesList.querySelectorAll(".cal-match-pill").forEach(btn => {
      btn.addEventListener("click", () => {
        calYear = Number(btn.dataset.year);
        calMonth = Number(btn.dataset.month);
        renderCalendar(false);
      });
    });
  }

  function renderCalendar(autoJumpToMatch = false) {
    const matchingMonths = getMatchingMonths();
    if (autoJumpToMatch && isFiltered() && matchingMonths.length) {
      const currentYm = `${calYear}-${String(calMonth + 1).padStart(2, "0")}`;
      if (!matchingMonths.some(m => m.ym === currentYm)) {
        calYear = matchingMonths[0].year;
        calMonth = matchingMonths[0].month;
      }
    }

    syncCalendarSelectors();
    renderMatchingMonthsBar(matchingMonths);

    const monthPrefix = `${calYear}-${String(calMonth + 1).padStart(2, "0")}`;
    const byDay = new Map();
    let monthTotal = 0;

    for (const f of shownCal) {
      if (!f.dateStr || !f.dateStr.startsWith(monthPrefix)) continue;
      monthTotal++;
      if (!byDay.has(f.dateStr)) byDay.set(f.dateStr, []);
      byDay.get(f.dateStr).push(f);
    }

    calMonthCount.textContent = `${monthTotal} film${monthTotal > 1 ? "s" : ""} vu${monthTotal > 1 ? "s" : ""} ce mois-ci`;
    updateCounter();

    const firstDay = new Date(calYear, calMonth, 1);
    const startOffset = (firstDay.getDay() + 6) % 7;
    const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
    const now = new Date();
    const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;

    const frag = document.createDocumentFragment();

    for (let i = 0; i < startOffset; i++) {
      const empty = document.createElement("div");
      empty.className = "cal-day cal-day--empty";
      frag.appendChild(empty);
    }

    for (let day = 1; day <= daysInMonth; day++) {
      const dateKey = `${monthPrefix}-${String(day).padStart(2, "0")}`;
      const films = byDay.get(dateKey) || [];
      const cell = document.createElement("div");
      cell.className = "cal-day"
        + (films.length ? " cal-day--has-films" : "")
        + (dateKey === todayStr ? " cal-day--today" : "");

      if (!films.length) {
        cell.innerHTML = `<div class="cal-day-head"><span class="cal-day-num">${day}</span></div>`;
        frag.appendChild(cell);
        continue;
      }

      const main = films[0];
      const badges = [
        main.rating ? `<span class="cal-rating-pill">★ ${fmt(main.rating)}</span>` : "",
        main.review ? `<span class="cal-review-dot" title="Critique écrite">✎</span>` : "",
        main.rewatch ? `<span class="cal-day-rewatch" title="Rewatch">↻</span>` : "",
        films.length > 1 ? `<span class="cal-day-badge">+${films.length - 1}</span>` : ""
      ].join("");

      cell.innerHTML = `
        <div class="cal-day-head">
          <span class="cal-day-num">${day}</span>
          <div class="cal-day-badges">${badges}</div>
        </div>
        <div class="cal-day-center">${esc(main.name)}</div>
        <div class="cal-day-foot">
          <div class="cal-day-title" title="${esc(films.map(x => x.name).join(" • "))}">${esc(main.name)}</div>
        </div>
        <span class="cal-mobile-dot" aria-hidden="true">${films.length > 1 ? films.length : ""}</span>`;

      const applyBgPoster = url => {
        if (!url) return;
        const img = document.createElement("img");
        img.className = "cal-day-bg";
        img.loading = "lazy";
        img.alt = main.name;
        img.src = url.includes("image.tmdb.org/t/p/w500/") ? url.replace("/w500/", "/w342/") : url;
        img.addEventListener("error", () => {
          img.remove();
          cell.classList.remove("cal-day--has-poster");
        }, { once: true });
        cell.classList.add("cal-day--has-poster");
        const center = cell.querySelector(".cal-day-center");
        if (center) center.textContent = "";
        cell.prepend(img);
      };

      if (main.poster) {
        applyBgPoster(main.poster);
      } else {
        resolvePoster(main).then(applyBgPoster);
      }

      cell.setAttribute("role", "button");
      cell.setAttribute("tabindex", "0");
      cell.setAttribute("aria-label", `${day} ${MONTHS_FR[calMonth]} : ${films.map(x => x.name).join(", ")}`);
      cell.addEventListener("click", () => openDayModal(dateKey, films));
      cell.addEventListener("keydown", e => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openDayModal(dateKey, films); }
      });

      frag.appendChild(cell);
    }

    calGrid.innerHTML = "";
    calGrid.appendChild(frag);
  }

  function renderFilmModalItems(films) {
    return films.map(f => {
      const tag = f.link ? "a" : "div";
      const attrs = f.link ? `href="${esc(f.link)}" target="_blank" rel="noopener noreferrer"` : "";
      const reviewBlock = f.review
        ? `<blockquote class="cal-modal-review">${esc(f.review).replace(/\r?\n/g, "<br>")}</blockquote>`
        : "";
      const thumb = f.poster
        ? `<img src="${esc(f.poster.includes("/w500/") ? f.poster.replace("/w500/", "/w185/") : f.poster)}" alt="${esc(f.name)}">`
        : `<div class="cal-modal-no-poster">🎬</div>`;
      const subParts = [f.director, f.runtime ? `${f.runtime} min` : "", f.genres.slice(0, 2).join(", ")].filter(Boolean);

      return `
        <${tag} class="cal-modal-item" ${attrs}>
          ${thumb}
          <div class="cal-modal-info">
            <div class="cal-modal-name">
              ${esc(f.name)} <span class="cal-modal-year">(${f.year || "—"})</span>
              ${f.rewatch ? `<span class="cal-modal-rewatch-tag">↻ Rewatch</span>` : ""}
              ${f.fromWatched ? `<span class="cal-modal-import-tag" title="Ajouté depuis watched.csv">Import</span>` : ""}
            </div>
            ${subParts.length ? `<div class="cal-modal-sub">${esc(subParts.join(" · "))}</div>` : ""}
            <div class="cal-modal-rating">${f.rating ? `★ ${fmt(f.rating)} / 5` : "Vu · Sans note"}</div>
            ${reviewBlock}
            ${f.link ? `<span class="cal-modal-link">Voir sur Letterboxd ↗</span>` : ""}
          </div>
        </${tag}>`;
    }).join("");
  }

  async function openDayModal(dateKey, films) {
    const [y, m, d] = dateKey.split("-");
    calModalTitle.textContent = `${Number(d)} ${MONTHS_FR[Number(m) - 1]} ${y} · ${films.length} film${films.length > 1 ? "s" : ""}`;
    await Promise.all(films.map(f => resolvePoster(f)));
    calModalBody.innerHTML = renderFilmModalItems(films);
    calModal.hidden = false;
  }

  async function openRandomModal() {
    const pool = shownList.length ? shownList : catalogFilms;
    if (!pool.length) return;
    const pick = pool[Math.floor(Math.random() * pool.length)];
    await resolvePoster(pick);

    calModalTitle.textContent = `🎲 Tirage au hasard (${pool.length} film${pool.length > 1 ? "s" : ""} éligibles)`;
    calModalBody.innerHTML = `
      ${renderFilmModalItems([pick])}
      <button type="button" class="random-reroll-btn" id="reroll-btn">🎲 Relancer un tirage</button>`;
    calModal.hidden = false;

    const reroll = $("reroll-btn");
    if (reroll) reroll.addEventListener("click", openRandomModal, { once: true });
  }

  function closeDayModal() { calModal.hidden = true; }

  /* ---------- Rendu Onglet Stats & Profil ---------- */
  function renderStatsDashboard() {
    // 1. Répartition des notes (0.5 à 5)
    const ratingSteps = [5, 4.5, 4, 3.5, 3, 2.5, 2, 1.5, 1, 0.5];
    const ratingCounts = new Map(ratingSteps.map(r => [r, 0]));
    for (const f of catalogFilms) {
      if (f.rating > 0 && ratingCounts.has(f.rating)) {
        ratingCounts.set(f.rating, ratingCounts.get(f.rating) + 1);
      }
    }
    const maxRatingCount = Math.max(1, ...ratingCounts.values());

    // 2. Rythme mensuel sur les 12 derniers mois actifs (hors imports > 5 films/jour)
    const countByDay = new Map();
    for (const f of diaryEntries) {
      if (f.dateStr) countByDay.set(f.dateStr, (countByDay.get(f.dateStr) || 0) + 1);
    }
    const monthCounts = new Map();
    for (const f of diaryEntries) {
      if (!f.dateStr || (countByDay.get(f.dateStr) || 0) > MAX_REAL_MOVIES_PER_DAY) continue;
      const ym = f.dateStr.slice(0, 7);
      monthCounts.set(ym, (monthCounts.get(ym) || 0) + 1);
    }
    const recentMonths = [...monthCounts.entries()].sort((a, b) => a[0].localeCompare(b[0])).slice(-12);
    const maxMonthCount = Math.max(1, ...recentMonths.map(x => x[1]));

    // 3. Top Réalisateurs (min 2 films vus)
    const dirMap = new Map();
    for (const f of catalogFilms) {
      if (!f.director) continue;
      for (const d of f.director.split(",").map(s => s.trim()).filter(Boolean)) {
        if (!dirMap.has(d)) dirMap.set(d, { count: 0, sum: 0, rated: 0 });
        const item = dirMap.get(d);
        item.count++;
        if (f.rating > 0) { item.sum += f.rating; item.rated++; }
      }
    }
    const topDirectors = [...dirMap.entries()]
      .filter(([, v]) => v.count >= 2)
      .sort((a, b) => b[1].count - a[1].count || (b[1].sum / (b[1].rated || 1)) - (a[1].sum / (a[1].rated || 1)))
      .slice(0, 8);
    const maxDirCount = Math.max(1, ...topDirectors.map(x => x[1].count));

    // 4. Top Genres
    const genreMap = new Map();
    for (const f of catalogFilms) {
      for (const g of f.genres) {
        genreMap.set(g, (genreMap.get(g) || 0) + 1);
      }
    }
    const topGenres = [...genreMap.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
    const maxGenreCount = Math.max(1, ...topGenres.map(x => x[1]));

    statsDashboard.innerHTML = `
      <article class="stats-card">
        <div class="stats-card-title">Répartition des notes <span class="stats-card-sub">sur ${catalogFilms.filter(f => f.rating > 0).length} films notés</span></div>
        <div class="bar-list">
          ${ratingSteps.map(r => {
            const c = ratingCounts.get(r) || 0;
            const pct = Math.round((c / maxRatingCount) * 100);
            return `
              <div class="bar-row">
                <span class="bar-label">★ ${fmt(r)}</span>
                <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
                <span class="bar-val">${c}</span>
              </div>`;
          }).join("")}
        </div>
      </article>

      <article class="stats-card">
        <div class="stats-card-title">Rythme mensuel <span class="stats-card-sub">12 derniers mois (hors imports)</span></div>
        <div class="bar-list">
          ${recentMonths.length ? recentMonths.map(([ym, c]) => {
            const [y, m] = ym.split("-").map(Number);
            const pct = Math.round((c / maxMonthCount) * 100);
            return `
              <div class="bar-row">
                <span class="bar-label">${MONTHS_SHORT[m - 1]} ${y}</span>
                <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
                <span class="bar-val">${c}</span>
              </div>`;
          }).join("") : '<p class="cal-modal-sub">Pas assez de visionnages datés.</p>'}
        </div>
      </article>

      <article class="stats-card">
        <div class="stats-card-title">Réalisateurs les plus vus <span class="stats-card-sub">min. 2 films</span></div>
        <div class="bar-list">
          ${topDirectors.length ? topDirectors.map(([name, info]) => {
            const pct = Math.round((info.count / maxDirCount) * 100);
            const avg = info.rated ? ` · ★${fmt((info.sum / info.rated).toFixed(1))}` : "";
            return `
              <div class="bar-row bar-row--wide-label">
                <span class="bar-label" title="${esc(name)}">${esc(name)}</span>
                <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
                <span class="bar-val">${info.count}${avg}</span>
              </div>`;
          }).join("") : '<p class="cal-modal-sub">Lance lb.py avec OMDB_KEY pour afficher les réalisateurs.</p>'}
        </div>
      </article>

      <article class="stats-card">
        <div class="stats-card-title">Genres favoris <span class="stats-card-sub">top 8</span></div>
        <div class="bar-list">
          ${topGenres.length ? topGenres.map(([g, c]) => {
            const pct = Math.round((c / maxGenreCount) * 100);
            return `
              <div class="bar-row bar-row--wide-label">
                <span class="bar-label">${esc(g)}</span>
                <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
                <span class="bar-val">${c}</span>
              </div>`;
          }).join("") : '<p class="cal-modal-sub">Lance lb.py avec OMDB_KEY pour afficher les genres.</p>'}
        </div>
      </article>`;
  }

  /* ---------- Navigation & Filtres ---------- */
  function syncUrlState() {
    const url = new URL(window.location.href);
    const setParam = (k, v) => v ? url.searchParams.set(k, v) : url.searchParams.delete(k);
    setParam("q", search.value.trim());
    setParam("decade", decadeSel.value !== "all" ? decadeSel.value : "");
    setParam("genre", genreSel.value !== "all" ? genreSel.value : "");
    setParam("min", Number(minRating.value) > 0 ? minRating.value : "");
    url.hash = currentView === "list" ? "" : `#${currentView}`;
    history.replaceState(null, "", url.pathname + url.search + url.hash);
  }

  function setView(view, updateUrl = true) {
    currentView = view;
    const isList = view === "list";
    const isCal = view === "calendar";
    const isStats = view === "stats";

    btnViewList.classList.toggle("active", isList);
    btnViewCal.classList.toggle("active", isCal);
    btnViewStats.classList.toggle("active", isStats);

    listView.hidden = !isList;
    calendarView.hidden = !isCal;
    statsView.hidden = !isStats;
    sortGroup.style.display = isList ? "" : "none";

    if (updateUrl) syncUrlState();
    if (isCal) renderCalendar(true);
    else if (isStats) { renderStatsDashboard(); updateCounter(); }
    else renderAll();
  }

  function stepMonth(delta) {
    calMonth += delta;
    if (calMonth < 0) { calMonth = 11; calYear--; }
    else if (calMonth > 11) { calMonth = 0; calYear++; }
    renderCalendar(false);
  }

  function jumpToLatestMovie() {
    const dated = shownCal.filter(f => f.dateStr).sort((a, b) => b.date - a.date);
    if (!dated.length) return;
    const [y, m] = dated[0].dateStr.split("-").map(Number);
    calYear = y;
    calMonth = m - 1;
    renderCalendar(false);
  }

  function initGenreSelector() {
    const counts = new Map();
    for (const f of catalogFilms) {
      for (const g of f.genres) counts.set(g, (counts.get(g) || 0) + 1);
    }
    if (!counts.size) return;
    genreGroup.hidden = false;
    const sorted = [...counts.entries()].sort((a, b) => b[1] - a[1]);
    genreSel.innerHTML = `<option value="all">Tous les genres</option>` +
      sorted.map(([g, c]) => `<option value="${esc(g)}">${esc(g)} (${c})</option>`).join("");
  }

  function updateQuickPillCounts() {
    countMasterpieces.textContent = catalogFilms.filter(f => f.rating >= 4.5).length;
    countFirstWatch.textContent = catalogFilms.filter(f => !f.rewatch).length;
    countUnrated.textContent = catalogFilms.filter(f => !f.rating).length;
    countRewatch.textContent = diaryEntries.filter(f => f.rewatch).length;
    countReviewed.textContent = diaryEntries.filter(f => f.review).length;
  }

  function matchesDecade(year, decade) {
    if (decade === "all") return true;
    if (!year) return false;
    if (decade === "classic") return year < 1990;
    const start = Number(decade);
    return year >= start && year < start + 10;
  }

  function apply(syncUrl = true) {
    const q = norm(search.value.trim());
    const min = parseFloat(minRating.value) || 0;
    const decade = decadeSel.value;
    const genre = genreSel.value;

    btnMasterpieces.classList.toggle("active", onlyMasterpieces);
    btnFirstWatch.classList.toggle("active", onlyFirstWatch);
    btnUnrated.classList.toggle("active", onlyUnrated);
    btnRewatch.classList.toggle("active", onlyRewatch);
    btnReviewed.classList.toggle("active", onlyReviewed);
    resetBtn.hidden = !isFiltered();

    const matchesFilter = f => {
      if (q) {
        const hay = `${norm(f.name)} ${norm(f.director)} ${norm(f.actors)}`;
        if (!hay.includes(q)) return false;
      }
      if (!matchesDecade(f.year, decade)) return false;
      if (genre !== "all" && !f.genres.includes(genre)) return false;
      if (onlyUnrated && f.rating !== 0) return false;
      if (onlyMasterpieces && f.rating < 4.5) return false;
      if (min > 0 && f.rating < min) return false;
      if (onlyFirstWatch && f.rewatch) return false;
      if (onlyRewatch && !f.rewatch) return false;
      if (onlyReviewed && !f.review) return false;
      return true;
    };

    shownList = catalogFilms.filter(matchesFilter).sort(sorters[sortSel.value] || sorters.recent);
    shownCal = diaryEntries.filter(matchesFilter).sort(sorters.recent);

    if (syncUrl) syncUrlState();
    if (currentView === "calendar") renderCalendar(true);
    else if (currentView === "stats") { renderStatsDashboard(); updateCounter(); }
    else renderAll();
  }

  function stats() {
    const rated = catalogFilms.filter(f => f.rating > 0);
    const currentYear = new Date().getFullYear();
    const top = [...rated].sort((a, b) => b.rating - a.rating || b.date - a.date)[0];

    const countByDay = new Map();
    for (const f of diaryEntries) {
      if (f.dateStr) countByDay.set(f.dateStr, (countByDay.get(f.dateStr) || 0) + 1);
    }

    const validEntriesByMonth = new Map();
    let validThisYear = 0;

    for (const f of diaryEntries) {
      if (!f.dateStr || (countByDay.get(f.dateStr) || 0) > MAX_REAL_MOVIES_PER_DAY) continue;
      const ym = f.dateStr.slice(0, 7);
      validEntriesByMonth.set(ym, (validEntriesByMonth.get(ym) || 0) + 1);
      if (Number(f.dateStr.slice(0, 4)) === currentYear) validThisYear++;
    }

    let bestYm = null;
    let bestCount = 0;
    for (const [ym, count] of validEntriesByMonth.entries()) {
      if (count > bestCount || (count === bestCount && ym > (bestYm || ""))) {
        bestCount = count;
        bestYm = ym;
      }
    }

    let bestMonthText = "—";
    if (bestYm && bestCount > 0) {
      const [y, m] = bestYm.split("-").map(Number);
      bestMonthText = `${bestCount} (${MONTHS_SHORT[m - 1]} ${y})`;
    }

    const totalMinutes = catalogFilms.reduce((sum, f) => sum + (f.runtime || 0), 0);
    if (totalMinutes > 0) {
      const hours = Math.round(totalMinutes / 60);
      $("stat-hours-div").hidden = false;
      $("stat-hours-item").hidden = false;
      $("stat-hours").textContent = `${hours} h`;
    }

    $("stat-total").textContent = catalogFilms.length;
    $("stat-avg").textContent = rated.length ? fmt((rated.reduce((s, f) => s + f.rating, 0) / rated.length).toFixed(1)) + " / 5" : "—";
    $("stat-top").textContent = top ? top.name : "—";
    $("stat-best-month").textContent = bestMonthText;
    $("stat-year").textContent = validThisYear;
  }

  let debounceTimer;
  search.addEventListener("input", () => { clearTimeout(debounceTimer); debounceTimer = setTimeout(() => apply(true), 140); });
  sortSel.addEventListener("change", () => apply(true));
  decadeSel.addEventListener("change", () => apply(true));
  genreSel.addEventListener("change", () => apply(true));

  minRating.addEventListener("input", () => {
    const val = Number(minRating.value);
    if (val > 0) onlyUnrated = false;
    if (val < 4.5) onlyMasterpieces = false;
    ratingVal.textContent = fmt(minRating.value);
    apply(true);
  });

  btnMasterpieces.addEventListener("click", () => {
    onlyMasterpieces = !onlyMasterpieces;
    if (onlyMasterpieces) {
      onlyUnrated = false;
      minRating.value = "4.5";
      ratingVal.textContent = "4,5";
    } else if (Number(minRating.value) === 4.5) {
      minRating.value = "0";
      ratingVal.textContent = "0";
    }
    apply(true);
  });

  btnFirstWatch.addEventListener("click", () => {
    onlyFirstWatch = !onlyFirstWatch;
    if (onlyFirstWatch) onlyRewatch = false;
    apply(true);
  });

  btnRewatch.addEventListener("click", () => {
    onlyRewatch = !onlyRewatch;
    if (onlyRewatch) onlyFirstWatch = false;
    apply(true);
  });

  btnReviewed.addEventListener("click", () => { onlyReviewed = !onlyReviewed; apply(true); });

  btnUnrated.addEventListener("click", () => {
    onlyUnrated = !onlyUnrated;
    if (onlyUnrated) {
      onlyMasterpieces = false;
      minRating.value = "0";
      ratingVal.textContent = "0";
    }
    apply(true);
  });

  btnRandom.addEventListener("click", openRandomModal);

  resetBtn.addEventListener("click", () => {
    search.value = "";
    decadeSel.value = "all";
    genreSel.value = "all";
    minRating.value = "0";
    ratingVal.textContent = "0";
    onlyMasterpieces = onlyFirstWatch = onlyUnrated = onlyRewatch = onlyReviewed = false;
    apply(true);
  });

  btnViewList.addEventListener("click", () => setView("list"));
  btnViewCal.addEventListener("click", () => setView("calendar"));
  btnViewStats.addEventListener("click", () => setView("stats"));
  calPrev.addEventListener("click", () => stepMonth(-1));
  calNext.addEventListener("click", () => stepMonth(1));
  calMonthSel.addEventListener("change", () => { calMonth = Number(calMonthSel.value); renderCalendar(false); });
  calYearSel.addEventListener("change", () => { calYear = Number(calYearSel.value); renderCalendar(false); });
  calToday.addEventListener("click", jumpToLatestMovie);

  $("cal-modal-close").addEventListener("click", closeDayModal);
  $("cal-modal-close-bg").addEventListener("click", closeDayModal);

  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && !calModal.hidden) { closeDayModal(); return; }
    if (currentView === "calendar" && calModal.hidden && !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) {
      if (e.key === "ArrowLeft") { e.preventDefault(); stepMonth(-1); }
      else if (e.key === "ArrowRight") { e.preventDefault(); stepMonth(1); }
    }
  });

  /* ---------- Initialisation ---------- */
  (async () => {
    list.innerHTML = '<div class="loader"><div class="loader-spinner"></div>Chargement des films…</div>';
    try {
      const res = await fetch("movies.json", { cache: "no-cache" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();

      if (Array.isArray(data)) {
        const cleaned = cleanEntries(data);
        catalogFilms = dedupe(cleaned);
        diaryEntries = cleaned;
      } else {
        catalogFilms = dedupe(cleanEntries(data.catalog || []));
        const loggedDiary = cleanEntries(data.diary || []);
        const reviewedKeys = new Set(loggedDiary.filter(d => d.review).map(d => movieKey(d.name, d.year)));
        catalogFilms.forEach(f => {
          if (reviewedKeys.has(movieKey(f.name, f.year))) f.review = "1";
        });

        const diaryKeys = new Set(loggedDiary.map(d => movieKey(d.name, d.year)));
        const fallbackWatched = cleanEntries(data.catalog || [], true)
          .filter(f => f.dateStr && !diaryKeys.has(movieKey(f.name, f.year)));
        diaryEntries = [...loggedDiary, ...fallbackWatched];
      }

      stats();
      initGenreSelector();
      updateQuickPillCounts();
      initCalendarSelectors();

      // Restaure les paramètres depuis l'URL si présents
      const params = new URLSearchParams(window.location.search);
      if (params.get("q")) search.value = params.get("q");
      if (params.get("decade")) decadeSel.value = params.get("decade");
      if (params.get("genre")) genreSel.value = params.get("genre");
      if (params.get("min")) {
        minRating.value = params.get("min");
        ratingVal.textContent = fmt(params.get("min"));
      }

      const latest = [...diaryEntries].filter(f => f.dateStr).sort((a, b) => b.date - a.date)[0];
      if (latest) {
        const [y, m] = latest.dateStr.split("-").map(Number);
        calYear = y;
        calMonth = m - 1;
      }

      const hashView = window.location.hash.replace("#", "");
      const initialView = ["calendar", "stats"].includes(hashView) ? hashView : "list";
      apply(false);
      if (initialView !== "list") setView(initialView, false);
    } catch (e) {
      console.error("[movies]", e);
      list.innerHTML = '<div class="empty-state"><p>Erreur de chargement des films.</p></div>';
      counter.textContent = "";
    }
  })();
})();