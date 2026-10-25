/* Mes Films — lecture de movies.json (généré par lb.py) */
(() => {
  const $ = id => document.getElementById(id);
  const list = $("film-list"), search = $("search"), sortSel = $("sort"), minRating = $("rating-filter"),
        ratingVal = $("rating-val"), counter = $("film-count"), sentinel = $("scroll-sentinel"), more = $("load-more-indicator");
  const PAGE = 40;
  let all = [], shown = [], page = 0;

  const norm = s => String(s ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = n => String(n).replace(".", ",");

  /* ---------- données ---------- */
  function clean(raw) {
    return raw.filter(f => f && String(f.Name ?? "").trim()).map(f => {
      let r = Number(f.Rating); if (!isFinite(r)) r = 0; if (r > 5) r /= 2;
      r = Math.round(Math.max(0, Math.min(5, r)) * 2) / 2;
      const d = f.Date ? Date.parse(f.Date) : 0;
      // On ne montre un poster que s'il est vérifié (pas de tmdb_source "review")
      const poster = f.tmdb_source === "review" ? null : (f.poster_url || (f.poster_path ? "https://image.tmdb.org/t/p/w500" + f.poster_path : null));
      return { name: String(f.Name).trim(), year: Number(f.Year) || 0, date: isFinite(d) ? d : 0, rating: r, poster,
               link: /^https?:\/\//.test(f["Letterboxd URI"] || "") ? f["Letterboxd URI"] : null, tmdb: f.tmdb_id || null };
    });
  }
  // Un même FILM = même identifiant TMDB, sinon même titre + même année (deux films homonymes restent distincts)
  function dedupe(films) {
    const map = new Map();
    for (const f of films) {
      const k = f.tmdb ? "t" + f.tmdb : "n" + norm(f.name) + "|" + f.year;
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
    title: (a, b) => a.name.localeCompare(b.name, "fr"),
  };

  /* ---------- rendu ---------- */
  function card(f) {
    const a = document.createElement(f.link ? "a" : "article");
    a.className = "film-card";
    if (f.link) { a.href = f.link; a.target = "_blank"; a.rel = "noopener noreferrer"; }
    const poster = f.poster
      ? `<img class="film-poster" loading="lazy" decoding="async" width="500" height="750" src="${esc(f.poster)}"
              srcset="${esc(f.poster.replace("/w500/", "/w342/"))} 342w, ${esc(f.poster)} 500w" sizes="(max-width:640px) 45vw, 200px" alt="Affiche de ${esc(f.name)}">`
      : `<div class="film-poster film-poster--none">${esc(f.name)}</div>`;
    a.innerHTML = `
      <div class="film-poster-wrap">${poster}${f.rating ? `<span class="poster-rating">${fmt(f.rating)}</span>` : ""}</div>
      <div class="film-card-inner">
        <div class="film-title" title="${esc(f.name)}">${esc(f.name)}</div>
        ${f.rating ? `<span class="stars" style="--r:${f.rating}" role="img" aria-label="Note : ${fmt(f.rating)} sur 5">★★★★★</span>` : ""}
        <div class="film-meta"><span>${f.year || "—"}</span>${f.link ? '<span class="film-lb">Letterboxd ↗</span>' : ""}</div>
      </div>`;
    const img = a.querySelector("img");   // affiche cassée -> repli propre (pas d'handler inline)
    if (img) img.addEventListener("error", () => img.replaceWith(Object.assign(document.createElement("div"), { className: "film-poster film-poster--none", textContent: f.name })), { once: true });
    return a;
  }
  function renderPage() {
    const slice = shown.slice(page * PAGE, (page + 1) * PAGE);
    if (!slice.length) return;
    const frag = document.createDocumentFragment(); slice.forEach(f => frag.appendChild(card(f)));
    list.appendChild(frag); page++;
    counter.textContent = Math.min(page * PAGE, shown.length) < shown.length
      ? `${Math.min(page * PAGE, shown.length)} / ${shown.length} films` : `${shown.length} film${shown.length > 1 ? "s" : ""}`;
  }
  function renderAll() {
    list.innerHTML = ""; page = 0;
    if (!shown.length) { list.innerHTML = '<div class="empty-state"><p>Aucun résultat.</p></div>'; counter.textContent = "0 film"; return; }
    renderPage(); rearm();
  }
  function rearm() { observer.unobserve(sentinel); observer.observe(sentinel); }   // relance le test si la sentinelle reste visible
  const observer = new IntersectionObserver(([e]) => {
    if (!e.isIntersecting || page * PAGE >= shown.length) return;
    more.hidden = false;
    requestAnimationFrame(() => { renderPage(); more.hidden = true; rearm(); });
  }, { rootMargin: "500px" });

  /* ---------- filtres / stats ---------- */
  function apply() {
    const q = norm(search.value.trim()), min = parseFloat(minRating.value) || 0;
    shown = all.filter(f => (!q || norm(f.name).includes(q)) && f.rating >= min).sort(sorters[sortSel.value] || sorters.recent);
    renderAll();
  }
  function stats() {
    const rated = all.filter(f => f.rating > 0), y = new Date().getFullYear();
    const top = [...rated].sort((a, b) => b.rating - a.rating || b.date - a.date)[0];
    $("stat-total").textContent = all.length;
    $("stat-avg").textContent = rated.length ? fmt((rated.reduce((s, f) => s + f.rating, 0) / rated.length).toFixed(1)) + " / 5" : "—";
    $("stat-top").textContent = top ? top.name : "—";
    $("stat-year").textContent = all.filter(f => f.date && new Date(f.date).getFullYear() === y).length;
  }
  let t; search.addEventListener("input", () => { clearTimeout(t); t = setTimeout(apply, 120); });
  sortSel.addEventListener("change", apply);
  minRating.addEventListener("input", () => { ratingVal.textContent = fmt(minRating.value); apply(); });

  /* ---------- init ---------- */
  (async () => {
    list.innerHTML = '<div class="loader"><div class="loader-spinner"></div>Chargement des films…</div>';
    try {
      const res = await fetch("movies.json", { cache: "no-cache" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      all = dedupe(clean(await res.json()));
      stats(); apply();
    } catch (e) {
      console.error("[movies]", e);
      list.innerHTML = '<div class="empty-state"><p>Erreur de chargement des films.</p></div>';
      counter.textContent = "";
    }
  })();
})();