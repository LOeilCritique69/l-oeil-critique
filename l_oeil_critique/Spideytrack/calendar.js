/* ============================================================
   SPIDEYTRACK — ARCHIVES CALENDRIER
   Vue mensuelle + moteur de recherche des identifications.
============================================================ */
(function () {
  'use strict';

  const CFG = {
    tom:    { label: 'Tom',    color: '#ff1f3d' },
    andrew: { label: 'Andrew', color: '#2e9dff' },
    tobey:  { label: 'Tobey',  color: '#b13bff' }
  };
  const KEYS = ['tom', 'andrew', 'tobey'];

  let rows = [];
  let cursor = new Date();
  let filter = 'all';

  // Index de toutes les identifications (résultat === true), construit
  // une seule fois au chargement des données. C'est ce qui permet de
  // sauter directement à un jour trouvé sans naviguer mois par mois.
  let identIndex = [];
  let finderChip = 'all';
  let finderFocus = -1;

  function isoDate(y, m, d) {
    return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
  }
  function monthName(date) {
    return date.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
  }
  function formatLong(iso) {
    if (!iso) return 'Date inconnue';
    return new Date(`${iso}T12:00:00`).toLocaleDateString('fr-FR', { weekday:'long', day:'numeric', month:'long', year:'numeric' });
  }
  function formatShort(iso) {
    if (!iso) return '—';
    return new Date(`${iso}T12:00:00`).toLocaleDateString('fr-FR', { day:'numeric', month:'short', year:'numeric' });
  }
  function normalize(s) {
    return (s || '').toString()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .toLowerCase();
  }
  function rowForDate(iso) { return rows.find(r => r.date === iso); }
  function matches(r) {
    if (filter === 'all') return true;
    if (filter === 'identified') return KEYS.some(k => r.chars[k]?.result === true);
    if (filter === 'none') return r && !KEYS.some(k => r.chars[k]?.result === true);
    return true;
  }
  function score(c) {
    return c ? `${c.exact ?? 0}/7` : '—';
  }

  function buildIdentIndex() {
    const list = [];
    rows.forEach(r => {
      KEYS.forEach(k => {
        const c = r.chars[k];
        if (c && c.result === true) {
          list.push({
            iso: r.date,
            day: r.day,
            key: k,
            exact: c.exact || 0,
            partial: c.partial || 0
          });
        }
      });
    });
    return list.sort((a, b) => new Date(b.iso) - new Date(a.iso));
  }

  function render() {
    const root = document.getElementById('calendar-wrap');
    if (!root) return;
    const y = cursor.getFullYear();
    const m = cursor.getMonth();
    const first = new Date(y, m, 1);
    const last = new Date(y, m + 1, 0);
    const offset = (first.getDay() + 6) % 7;
    const cells = [];

    for (let i = 0; i < offset; i++) cells.push('<div class="cal-day cal-day-empty" aria-hidden="true"></div>');
    for (let d = 1; d <= last.getDate(); d++) {
      const iso = isoDate(y, m, d);
      const r = rowForDate(iso);
      const visible = r && matches(r);
      const classes = ['cal-day'];
      if (r) classes.push('has-entry');
      if (r && !visible) classes.push('is-filtered');
      const today = iso === new Date().toISOString().slice(0,10);
      if (today) classes.push('is-today');

      const dots = r ? KEYS.map(k => {
        const c = r.chars[k];
        if (!c) return `<span class="cal-dot cal-dot-empty" aria-hidden="true"></span>`;
        const state = c.result === true ? 'win' : 'miss';
        return `<span class="cal-dot ${state}" style="--dot:${CFG[k].color}" title="${CFG[k].label} : ${c.result === true ? 'identifié' : 'pas lui'} — ${score(c)}"></span>`;
      }).join('') : '';

      const total = r ? KEYS.reduce((s,k) => s + (r.chars[k]?.weighted || 0), 0) : 0;
      const label = r ? `Jour ${r.day} — ${formatLong(iso)}` : formatLong(iso);
      cells.push(`<button class="${classes.join(' ')}" type="button" ${r && visible ? '' : 'disabled'} data-iso="${iso}" aria-label="${label}">
        <span class="cal-number">${d}</span>
        ${r && visible ? `<span class="cal-day-id">J${r.day}</span><span class="cal-dots">${dots}</span><span class="cal-total">${total.toFixed(1)}</span>` : ''}
      </button>`);
    }

    root.innerHTML = `
      <div class="calendar-toolbar">
        <div class="calendar-nav">
          <button class="cal-nav-btn" id="cal-prev" type="button" aria-label="Mois précédent">‹</button>
          <div class="calendar-title-wrap">
            <span class="calendar-kicker">Chronologie des enquêtes</span>
            <h3 class="calendar-title">${monthName(cursor)}</h3>
          </div>
          <button class="cal-nav-btn" id="cal-next" type="button" aria-label="Mois suivant">›</button>
          <button class="cal-today-btn" id="cal-today" type="button">Aujourd'hui</button>
        </div>
        <div class="calendar-filters" role="group" aria-label="Filtrer les archives">
          <button class="cal-filter ${filter==='all'?'active':''}" data-filter="all" type="button">Toutes</button>
          <button class="cal-filter ${filter==='identified'?'active':''}" data-filter="identified" type="button">✓ Identifié</button>
          <button class="cal-filter ${filter==='none'?'active':''}" data-filter="none" type="button">✗ Aucun</button>
        </div>
      </div>

      <div class="calendar-finder">
        <div class="finder-input-wrap">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2"/>
            <line x1="16.2" y1="16.2" x2="21" y2="21" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
          <input
            type="search"
            id="cal-finder-input"
            class="finder-input"
            placeholder="Rechercher une identification — nom, jour, date…"
            autocomplete="off"
            aria-label="Rechercher une journée où un Spider-Man a été identifié"
          >
          <span class="finder-count" id="finder-count">${identIndex.length} identification${identIndex.length > 1 ? 's' : ''}</span>
          <button class="finder-random" id="finder-random" type="button" ${identIndex.length ? '' : 'disabled'}>🎲 Jour au hasard</button>
        </div>
        <div class="finder-chips" role="group" aria-label="Filtrer la recherche par personnage">
          <button class="finder-chip ${finderChip==='all'?'active':''}" data-chip="all" type="button">Tous</button>
          ${KEYS.map(k => `<button class="finder-chip ${finderChip===k?'active':''}" data-chip="${k}" type="button" style="--chip:${CFG[k].color}">${CFG[k].label}</button>`).join('')}
        </div>
        <div class="finder-results" id="finder-results" hidden></div>
      </div>

      <div class="calendar-legend">
        ${KEYS.map(k => `<span><i style="--dot:${CFG[k].color}"></i>${CFG[k].label}</span>`).join('')}
        <span class="legend-note">Cliquez sur une journée pour ouvrir le dossier</span>
      </div>
      <div class="calendar-grid" role="grid" aria-label="Calendrier des archives">
        ${['Lun','Mar','Mer','Jeu','Ven','Sam','Dim'].map(d => `<div class="cal-weekday">${d}</div>`).join('')}
        ${cells.join('')}
      </div>
      <div class="calendar-detail" id="calendar-detail" aria-live="polite"></div>
    `;

    root.querySelector('#cal-prev').addEventListener('click', () => { cursor.setMonth(cursor.getMonth() - 1); render(); });
    root.querySelector('#cal-next').addEventListener('click', () => { cursor.setMonth(cursor.getMonth() + 1); render(); });
    root.querySelector('#cal-today').addEventListener('click', () => { cursor = new Date(); render(); });
    root.querySelectorAll('.cal-filter').forEach(btn => btn.addEventListener('click', () => {
      filter = btn.dataset.filter;
      render();
    }));
    root.querySelectorAll('.cal-day.has-entry:not(.is-filtered)').forEach(btn => btn.addEventListener('click', () => showDetail(btn.dataset.iso)));

    initFinder(root);

    const count = document.getElementById('db-count');
    if (count) count.textContent = `${rows.length} jours archivés`;
  }

  // ── Moteur de recherche ──────────────────────────────────────────
  function initFinder(root) {
    const input   = root.querySelector('#cal-finder-input');
    const results = root.querySelector('#finder-results');
    const randomBtn = root.querySelector('#finder-random');

    root.querySelectorAll('.finder-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        finderChip = chip.dataset.chip;
        root.querySelectorAll('.finder-chip').forEach(c => c.classList.toggle('active', c === chip));
        finderFocus = -1;
        renderFinderResults(input.value);
      });
    });

    input.addEventListener('input', () => { finderFocus = -1; renderFinderResults(input.value); });
    input.addEventListener('focus', () => renderFinderResults(input.value));
    input.addEventListener('keydown', (e) => {
      const items = results.querySelectorAll('.finder-result');
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (!items.length) return;
        finderFocus = Math.min(finderFocus + 1, items.length - 1);
        highlightFocus(items);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (!items.length) return;
        finderFocus = Math.max(finderFocus - 1, 0);
        highlightFocus(items);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const target = items[finderFocus] || items[0];
        if (target) target.click();
      } else if (e.key === 'Escape') {
        input.value = '';
        results.hidden = true;
        input.blur();
      }
    });

    document.addEventListener('click', (e) => {
      if (!root.contains(e.target)) return;
      if (!e.target.closest('.calendar-finder')) results.hidden = true;
    }, { once: false });

    if (randomBtn) {
      randomBtn.addEventListener('click', () => {
        if (!identIndex.length) return;
        const pick = identIndex[Math.floor(Math.random() * identIndex.length)];
        jumpTo(pick.iso, pick.key);
      });
    }
  }

  function highlightFocus(items) {
    items.forEach((it, i) => it.classList.toggle('focused', i === finderFocus));
    if (items[finderFocus]) items[finderFocus].scrollIntoView({ block: 'nearest' });
  }

  function renderFinderResults(query) {
    const results = document.getElementById('finder-results');
    if (!results) return;
    const q = normalize(query);

    let pool = identIndex;
    if (finderChip !== 'all') pool = pool.filter(it => it.key === finderChip);

    if (q) {
      pool = pool.filter(it => {
        const haystack = normalize(`${CFG[it.key].label} jour ${it.day} ${it.iso} ${formatShort(it.iso)} ${formatLong(it.iso)}`);
        return haystack.includes(q);
      });
    }

    if (!q && finderChip === 'all') {
      // Pas de recherche active : on propose les identifications les plus récentes.
      pool = pool.slice(0, 8);
    } else {
      pool = pool.slice(0, 20);
    }

    if (!pool.length) {
      results.innerHTML = `<div class="finder-empty">Aucune identification ne correspond à cette recherche.</div>`;
      results.hidden = false;
      return;
    }

    results.innerHTML = pool.map(it => `
      <button class="finder-result" type="button" data-iso="${it.iso}" data-key="${it.key}">
        <span class="finder-result-dot" style="--dot:${CFG[it.key].color}"></span>
        <span class="finder-result-main">
          <span class="finder-result-name">${CFG[it.key].label} — Jour ${it.day}</span>
          <span class="finder-result-date">${formatLong(it.iso)}</span>
        </span>
        <span class="finder-result-score">${it.exact}/7${it.partial ? ` · ${it.partial}p` : ''}</span>
      </button>
    `).join('');
    results.hidden = false;

    results.querySelectorAll('.finder-result').forEach(btn => {
      btn.addEventListener('click', () => jumpTo(btn.dataset.iso, btn.dataset.key));
    });
  }

  function jumpTo(iso, key) {
    const [y, m] = iso.split('-').map(Number);
    cursor = new Date(y, m - 1, 1);
    filter = 'all';
    render();

    const root = document.getElementById('calendar-wrap');
    const cell = root && root.querySelector(`.cal-day[data-iso="${iso}"]`);
    if (cell) {
      cell.classList.add('jump-highlight');
      cell.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setTimeout(() => cell.classList.remove('jump-highlight'), 1800);
    }
    showDetail(iso, key);

    const input = root && root.querySelector('#cal-finder-input');
    const results = root && root.querySelector('#finder-results');
    if (input) input.value = '';
    if (results) results.hidden = true;
  }

  function showDetail(iso, highlightKey) {
    const r = rowForDate(iso);
    const detail = document.getElementById('calendar-detail');
    if (!r || !detail) return;
    const cards = KEYS.map(k => {
      const c = r.chars[k];
      if (!c) return `<div class="cal-detail-card missing"><strong>${CFG[k].label}</strong><span>Pas de données</span></div>`;
      const status = c.result === true ? 'IDENTIFIÉ' : 'PAS LUI';
      const shots = c.screenshot ? `<button class="cal-shot" type="button" data-shot="${c.screenshot}" data-caption="${CFG[k].label} — jour ${r.day}"><img src="${c.screenshot}" alt="Capture ${CFG[k].label}, jour ${r.day}" loading="lazy"></button>` : '';
      return `<div class="cal-detail-card" style="--person:${CFG[k].color}">
        ${shots}
        <div class="cal-detail-name">${CFG[k].label}</div>
        <div class="cal-detail-status">${status}</div>
        <div class="cal-detail-score">${score(c)} exacts${c.partial ? ` · ${c.partial}/7 partiels` : ''}</div>
      </div>`;
    }).join('');
    detail.innerHTML = `<div class="detail-head"><div><span class="calendar-kicker">Pièce d'archive</span><h4>Jour ${r.day}</h4><p>${formatLong(iso)}</p></div><button type="button" class="detail-close" aria-label="Fermer">×</button></div><div class="cal-detail-cards">${cards}</div>`;
    detail.classList.add('open');
    detail.querySelector('.detail-close').addEventListener('click', () => detail.classList.remove('open'));
    detail.querySelectorAll('.cal-shot').forEach(b => b.addEventListener('click', () => {
      if (typeof window.openLightbox === 'function') window.openLightbox(b.dataset.shot, b.dataset.caption);
    }));
    detail.scrollIntoView({ behavior:'smooth', block:'nearest' });
  }

  window.SpideyCalendar = {
    init(data) {
      rows = Array.isArray(data) ? data : [];
      identIndex = buildIdentIndex();
      const latest = rows.find(r => r.date);
      if (latest?.date) cursor = new Date(`${latest.date}T12:00:00`);
      render();
    }
  };
})();