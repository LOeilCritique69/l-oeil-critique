// ============================================================
// CONFIG
// ============================================================
const CHAR_CONFIG = {
  tom:    { label: 'Tom Holland',     color: '#e8192c' },
  andrew: { label: 'Andrew Garfield', color: '#2f7fe8' },
  tobey:  { label: 'Tobey Maguire',   color: '#8b3ee0' },
};
const CHAR_KEYS = ['tom', 'andrew', 'tobey'];
const DB_URL = 'marveldle/database.json';
const MAX_EXACT = 7; // catégories notées par jour, par personnage — doit matcher l'automatisation

// ============================================================
// LOADER
// ============================================================
const loaderBar    = document.getElementById('loader-bar');
const loaderStatus = document.getElementById('loader-status');
function setProgress(pct, label) { loaderBar.style.width = pct + '%'; if (label) loaderStatus.textContent = label; }
function hideLoader() {
  const screen = document.getElementById('loading-screen');
  screen.classList.add('hidden');
  document.getElementById('app-wrapper').classList.add('visible');
  setTimeout(() => screen.remove(), 700);
}

// ============================================================
// CHARGEMENT
// ============================================================
function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

function showLoadError(show) {
  const el = document.getElementById('load-error');
  el.hidden = !show;
}

async function fetchDatabase() {
  const r = await fetch(DB_URL, { cache: 'no-store' });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function loadDatabase() {
  setProgress(20, 'Ouverture du dossier…');
  let raw = {};
  try {
    raw = await fetchDatabase();
    showLoadError(false);
  } catch (err) {
    console.error('SpideyTrack: échec du chargement de la base', err);
    showLoadError(true);
  }
  setProgress(60, 'Classement des pièces…');

  const days = raw.days || {};
  const rows = Object.entries(days)
    .map(([day, entry]) => ({ day: parseInt(day, 10), date: entry.date, chars: entry.chars || {} }))
    .filter(r => Number.isFinite(r.day))
    .sort((a, b) => b.day - a.day);

  setProgress(85, 'Mise en page…');
  return rows;
}

// ============================================================
// AUJOURD'HUI
// ============================================================
function renderTodayHero(rows) {
  const cardsRow = document.getElementById('today-cards-row');
  cardsRow.innerHTML = '';
  const label = document.getElementById('today-day-label');
  const today = todayISO();
  const entry = rows.find(r => r.date === today);
  const hero = document.getElementById('today-hero');

  if (!entry) { hero.style.display = 'none'; return; }
  hero.style.display = '';
  label.textContent = `Jour ${entry.day}`;

  CHAR_KEYS.forEach(key => {
    const c = entry.chars[key];
    if (!c) return;
    const cfg  = CHAR_CONFIG[key];
    const card = document.createElement('div');
    card.className = `case-card tc-${key}`;

    const stampHtml = c.result === true
      ? `<div class="stamp win">Confirmé</div>`
      : c.result === false
        ? `<div class="stamp lose">Pas lui</div>`
        : `<div class="stamp pending">En attente</div>`;

    const scoreHtml = c.exact > 0
      ? `<div class="cc-score-wrap"><div class="cc-score-bar" style="width:${c.exact/MAX_EXACT*100}%;background:${cfg.color}"></div></div>
         <div class="cc-score-txt">${c.exact}/${MAX_EXACT} exacts${c.partial > 0 ? ` · ${c.partial}/${MAX_EXACT} partiels` : ''}</div>`
      : '';

    const imgHtml = c.screenshot
      ? `<div class="cc-img" role="button" tabindex="0" aria-label="Agrandir la capture — ${cfg.label}, jour ${entry.day}"><img src="${c.screenshot}" alt="" loading="eager"></div>`
      : `<div class="cc-img cc-img-empty"><span>Pas de pièce à conviction</span></div>`;

    card.innerHTML = `
      <div class="cc-tape" aria-hidden="true"></div>
      <div class="cc-pin" aria-hidden="true"></div>
      ${imgHtml}
      <div class="cc-name">${cfg.label}</div>
      <div class="cc-body">${stampHtml}${scoreHtml}</div>`;
    if (c.screenshot) {
      const imgWrap = card.querySelector('.cc-img');
      imgWrap.addEventListener('click', () => openLightbox(c.screenshot, `${cfg.label} — jour ${entry.day}`));
    }
    cardsRow.appendChild(card);
  });

  requestAnimationFrame(drawCaseThread);
}

// ── Fil rouge du tableau d'enquête ──────────────────────────────────
// Relie les épingles des 3 polaroids par un fil pointillé, recalculé
// sur les coordonnées réelles des cartes (donc correct quel que soit
// le nombre de personnages joués ce jour-là). Masqué en CSS sous
// 860px, où le board passe en une colonne et un "fil" n'a plus de sens.
function drawCaseThread() {
  const hero = document.getElementById('today-hero');
  if (!hero) return;
  const cards = hero.querySelectorAll('.case-card');
  let svg = hero.querySelector('.case-thread');
  if (!svg) {
    svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'case-thread');
    svg.setAttribute('aria-hidden', 'true');
    hero.insertBefore(svg, hero.querySelector('.today-cards-row'));
  }
  if (cards.length < 2) { svg.innerHTML = ''; return; }

  const heroRect = hero.getBoundingClientRect();
  svg.setAttribute('width', heroRect.width);
  svg.setAttribute('height', heroRect.height);
  svg.setAttribute('viewBox', `0 0 ${heroRect.width} ${heroRect.height}`);

  const pins = [...cards].map(c => {
    const r = c.getBoundingClientRect();
    return { x: r.left - heroRect.left + r.width / 2, y: r.top - heroRect.top + 3 };
  });

  let d = `M ${pins[0].x} ${pins[0].y}`;
  for (let i = 1; i < pins.length; i++) {
    const prev = pins[i - 1], cur = pins[i];
    const midY = Math.min(prev.y, cur.y) - 22; // léger affaissement du fil entre 2 épingles
    d += ` Q ${(prev.x + cur.x) / 2} ${midY} ${cur.x} ${cur.y}`;
  }
  svg.innerHTML = `<path d="${d}" class="thread-path"/>`
    + pins.map(p => `<circle cx="${p.x}" cy="${p.y}" r="2.5" class="thread-pin"/>`).join('');
}

let threadResizeT = null;
window.addEventListener('resize', () => {
  clearTimeout(threadResizeT);
  threadResizeT = setTimeout(drawCaseThread, 150);
});

// ============================================================
// DASHBOARD
// ============================================================
function renderDashboard(rows) {
  const total = rows.length;
  const winsAny = rows.filter(r => CHAR_KEYS.some(k => r.chars[k]?.result === true)).length;
  const winRate = total ? Math.round(winsAny / total * 100) : 0;

  document.getElementById('dash-total').textContent   = total;
  document.getElementById('dash-winrate').textContent = total ? winRate + '%' : '—';

  const persosWrap = document.getElementById('dash-persos');
  persosWrap.innerHTML = '';
  let bestOfAll = 0;

  CHAR_KEYS.forEach(key => {
    const cfg = CHAR_CONFIG[key];
    let wins = 0, played = 0;
    [...rows].sort((a,b) => a.day - b.day).forEach(r => {
      const c = r.chars[key];
      if (!c) return;
      played++;
      if (c.result === true) wins++;
    });
    let streak = 0;
    for (const r of rows) {
      const c = r.chars[key];
      if (!c) continue;
      if (c.result === true) streak++; else break;
    }
    bestOfAll = Math.max(bestOfAll, streak);
    const rate = played ? Math.round(wins/played*100) : 0;

    const line = document.createElement('div');
    line.className = 'dash-perso-line';
    line.innerHTML = `
      <span class="dpl-name" style="color:${cfg.color}">${cfg.label}</span>
      <span class="dpl-bar-wrap"><span class="dpl-bar" style="width:${rate}%;background:${cfg.color}"></span></span>
      <span class="dpl-stat">${wins}/${played}</span>
      <span class="dpl-stat">${streak > 0 ? streak + ' 🔥' : '—'}</span>`;
    persosWrap.appendChild(line);
  });

  document.getElementById('dash-beststreak').textContent = bestOfAll > 0 ? bestOfAll : '—';
}

// ============================================================
// TOP 5 (priorité aux Spider-Man effectivement identifiés)
// ============================================================
function buildTop5(rows) {
  const items = [];
  rows.forEach(r => {
    CHAR_KEYS.forEach(key => {
      const c = r.chars[key];
      if (!c || !c.screenshot) return;
      items.push({
        screenshot: c.screenshot,
        day: r.day,
        key,
        result: c.result === true,
        exact: c.exact || 0,
        partial: c.partial || 0,
        w: c.weighted || 0,
      });
    });
  });

  // Tri :
  // 1. Les Spider-Man trouvés (result === true) en premier
  // 2. Meilleur score pondéré (w)
  // 3. Nombre de critères exacts
  // 4. Jour le plus récent
  return items.sort((a,b) =>
    (b.result - a.result) ||
    (b.w - a.w) ||
    (b.exact - a.exact) ||
    (b.day - a.day)
  ).slice(0, 5);
}

function renderTop5(items) {
  const container = document.getElementById('top5-container');
  container.innerHTML = '';
  if (!items.length) {
    container.innerHTML = '<div class="top5-empty">Aucune pièce à conviction avec des indices pour l’instant.</div>';
    return;
  }
  items.forEach((item, i) => {
    const cfg = CHAR_CONFIG[item.key];
    let caption = `${cfg.label} · ${item.exact}/${MAX_EXACT} exacts`;
    if (item.partial > 0) caption += `, ${item.partial}/${MAX_EXACT} partiels`;

    const winBadge = item.result ? `<span class="top5-badge">✓ Identifié</span>` : '';

    const card = document.createElement('div');
    card.className = 'top5-card';
    card.innerHTML = `
      <div class="top5-tape" aria-hidden="true"></div>
      <div class="top5-rank" aria-hidden="true">${i+1}</div>
      <div class="top5-img" role="button" tabindex="0" aria-label="Agrandir la capture — ${cfg.label}, jour ${item.day}"><img src="${item.screenshot}" loading="lazy" alt=""></div>
      <div class="top5-body">
        <div class="top5-day" style="color:${cfg.color}">Jour ${item.day} ${winBadge}</div>
        <div class="top5-note">${caption}</div>
      </div>`;
    card.querySelector('.top5-img').addEventListener('click', () => openLightbox(item.screenshot, `${cfg.label} — jour ${item.day}`));
    container.appendChild(card);
  });
}

// ============================================================
// GRAPHIQUES
// ============================================================
let mainChart = null;
let allRows = [];

function switchChart(key, btn) {
  document.querySelectorAll('.chart-tab').forEach(b => { b.classList.remove('active'); b.setAttribute('aria-selected', 'false'); });
  btn.classList.add('active');
  btn.setAttribute('aria-selected', 'true');
  try { renderMainChart(key); } catch (e) { console.error('Chart.js indisponible :', e); }
}

function renderMainChart(key) {
  if (typeof Chart === 'undefined') { console.warn('Chart.js non chargé — graphique ignoré.'); return; }
  const ctx = document.getElementById('main-chart').getContext('2d');
  if (mainChart) { mainChart.destroy(); mainChart = null; }
  const textColor = 'rgba(136,145,166,.6)';
  const gridColor = 'rgba(255,255,255,.04)';
  const sortedAsc = [...allRows].sort((a,b) => a.day - b.day);

  if (key === 'compare') {
    mainChart = new Chart(ctx, {
      type: 'line',
      data: {
        datasets: CHAR_KEYS.map(k => ({
          label: CHAR_CONFIG[k].label,
          data: sortedAsc.filter(r => r.chars[k]).map(r => ({ x: r.day, y: r.chars[k].exact || 0 })),
          borderColor: CHAR_CONFIG[k].color, backgroundColor: 'transparent',
          borderWidth: 1.5, pointRadius: 2, tension: 0.3,
        })),
      },
      options: chartOpts(textColor, gridColor, true),
    });
  } else {
    const filtered = sortedAsc.filter(r => r.chars[key]);
    const c = CHAR_CONFIG[key].color;
    mainChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: filtered.map(r => `J${r.day}`),
        datasets: [
          {
            type: 'bar', label: 'Score exact',
            data: filtered.map(r => r.chars[key].exact || 0),
            backgroundColor: filtered.map(r => r.chars[key].result === true ? c : (r.chars[key].exact >= 4 ? c+'99' : c+'33')),
            borderWidth: 0,
          },
          {
            type: 'line', label: 'Tendance (moy. 7j)',
            data: movingAvg(filtered.map(r => r.chars[key].exact || 0), 7),
            borderColor: c, backgroundColor: 'transparent',
            borderWidth: 2, borderDash: [4,3], pointRadius: 0, tension: 0.4,
          },
        ],
      },
      options: chartOpts(textColor, gridColor, false),
    });
  }
}

function movingAvg(data, w) {
  return data.map((_, i) => {
    const sl = data.slice(Math.max(0, i-w+1), i+1);
    return +(sl.reduce((s,v) => s+v, 0) / sl.length).toFixed(2);
  });
}

function chartOpts(textColor, gridColor, scatter) {
  return {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: textColor, font:{ family:'monospace', size:11 }, boxWidth:10 } },
      tooltip: { backgroundColor:'rgba(10,12,17,.95)', titleFont:{ family:'monospace',size:11 }, bodyFont:{ family:'monospace',size:11 } },
    },
    scales: {
      x: { ticks:{ color:textColor, font:{ family:'monospace',size:9 }, maxTicksLimit:20 }, grid:{ color:gridColor }, type: scatter?'linear':'category' },
      y: { min:0, max:MAX_EXACT, ticks:{ color:textColor, font:{ family:'monospace',size:10 }, stepSize:1 }, grid:{ color:gridColor } },
    },
  };
}

// ============================================================
// DOSSIER COMPLET
// ============================================================
let dbFilterResult = 'all';
let dbSearch = '';
let dbSort = { key: 'day', dir: 'desc' };
let dbPage = 1;
const DB_PAGE_SIZE = 25;

function formatDate(iso) {
  if (!iso) return '—';
  const [y,m,d] = iso.split('-');
  const months = ['jan','fév','mar','avr','mai','juin','juil','aoû','sep','oct','nov','déc'];
  return `${parseInt(d)} ${months[parseInt(m)-1]} ${y}`;
}

function rowWeighted(r) {
  return CHAR_KEYS.reduce((s,k) => s + (r.chars[k]?.weighted || 0), 0);
}

function cellHtml(r, key) {
  const c = r.chars[key];
  if (!c) return '<span class="db-cell-empty">—</span>';
  const icon = c.result === true ? '✓' : '✗';
  const cls  = c.result === true ? 'db-icon-yes' : 'db-icon-no';
  const score = `${c.exact ?? 0}/${MAX_EXACT}`;
  const label = CHAR_CONFIG[key].label;
  const clickable = c.screenshot ? ' role="button" tabindex="0"' : '';
  const ariaLabel = c.screenshot ? ` aria-label="Agrandir la capture — ${label}, jour ${r.day}"` : '';
  const cellClass = c.screenshot ? `db-cell ${cls} db-cell-clickable` : `db-cell ${cls}`;
  return `<span class="${cellClass}"${clickable}${ariaLabel} data-screenshot="${c.screenshot || ''}" data-caption="${label} — jour ${r.day}"><span class="db-cell-icon">${icon}</span><span class="db-cell-score">${score}</span></span>`;
}

function applyDbFilters() { dbPage = 1; renderDbTable(); }

function renderDbTable() {
  const tbody = document.getElementById('db-tbody');
  const empty = document.getElementById('db-empty');
  const search = dbSearch.toLowerCase().trim();

  let filtered = allRows.filter(r => {
    if (dbFilterResult !== 'all') {
      const anyWin = CHAR_KEYS.some(k => r.chars[k]?.result === true);
      if (String(anyWin) !== dbFilterResult) return false;
    }
    if (search) {
      const haystack = `jour ${r.day} ${r.date || ''} ${formatDate(r.date)}`.toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    return true;
  });

  filtered.sort((a, b) => {
    let va, vb;
    if (dbSort.key === 'day') { va = a.day; vb = b.day; }
    else if (dbSort.key === 'date') { va = a.date || ''; vb = b.date || ''; }
    else { va = rowWeighted(a); vb = rowWeighted(b); }
    const cmp = va < vb ? -1 : va > vb ? 1 : 0;
    return dbSort.dir === 'asc' ? cmp : -cmp;
  });

  document.getElementById('db-count').textContent = `${filtered.length} entrées`;

  if (!filtered.length) {
    tbody.innerHTML = '';
    empty.style.display = 'block';
    document.getElementById('db-pager').innerHTML = '';
    return;
  }
  empty.style.display = 'none';

  const totalPages = Math.max(1, Math.ceil(filtered.length / DB_PAGE_SIZE));
  dbPage = Math.min(dbPage, totalPages);
  const start = (dbPage - 1) * DB_PAGE_SIZE;
  const pageRows = filtered.slice(start, start + DB_PAGE_SIZE);

  tbody.innerHTML = pageRows.map(r => `
    <tr>
      <td class="db-day">${r.day}</td>
      <td class="db-date">${formatDate(r.date)}</td>
      <td>${cellHtml(r, 'tom')}</td>
      <td>${cellHtml(r, 'andrew')}</td>
      <td>${cellHtml(r, 'tobey')}</td>
      <td class="db-total">${rowWeighted(r).toFixed(1)}/${MAX_EXACT*3}</td>
    </tr>`).join('');

  tbody.querySelectorAll('.db-cell-clickable').forEach(cell => {
    cell.addEventListener('click', () => openLightbox(cell.dataset.screenshot, cell.dataset.caption));
  });

  renderPager(totalPages);
}

function renderPager(totalPages) {
  const pager = document.getElementById('db-pager');
  if (totalPages <= 1) { pager.innerHTML = ''; return; }
  let html = `<button class="pager-btn" ${dbPage<=1?'disabled':''} data-page="${dbPage-1}">‹ Préc.</button>`;
  html += `<span class="pager-info">Page ${dbPage} / ${totalPages}</span>`;
  html += `<button class="pager-btn" ${dbPage>=totalPages?'disabled':''} data-page="${dbPage+1}">Suiv. ›</button>`;
  pager.innerHTML = html;
  pager.querySelectorAll('[data-page]').forEach(btn => {
    btn.addEventListener('click', () => { dbPage = parseInt(btn.dataset.page, 10); renderDbTable(); document.getElementById('db-wrap')?.scrollIntoView({ block: 'nearest' }); });
  });
}

function debounce(fn, wait) {
  let t = null;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), wait); };
}

function initDbControls() {
  document.querySelectorAll('.db-filters [data-result]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.db-filters [data-result]').forEach(b => { b.classList.remove('active'); b.setAttribute('aria-pressed', 'false'); });
      btn.classList.add('active');
      btn.setAttribute('aria-pressed', 'true');
      dbFilterResult = btn.dataset.result;
      applyDbFilters();
    });
  });
  document.getElementById('db-search').addEventListener('input', debounce(e => { dbSearch = e.target.value; applyDbFilters(); }, 150));
  document.querySelectorAll('.db-table th.sortable').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      if (dbSort.key === key) dbSort.dir = dbSort.dir === 'asc' ? 'desc' : 'asc';
      else dbSort = { key, dir: 'desc' };
      document.querySelectorAll('.db-table th.sortable').forEach(t => {
        t.classList.remove('sort-asc','sort-desc');
        t.setAttribute('aria-sort', 'none');
      });
      th.classList.add(dbSort.dir === 'asc' ? 'sort-asc' : 'sort-desc');
      th.setAttribute('aria-sort', dbSort.dir === 'asc' ? 'ascending' : 'descending');
      renderDbTable();
    });
  });
}

// ============================================================
// UTILITAIRES
// ============================================================
function openLightbox(src, alt) {
  if (!src) return;
  const img = document.getElementById('lightbox-img');
  img.src = src;
  img.alt = alt || 'Screenshot';
  document.getElementById('lightbox').classList.add('open');
}
function closeLightbox()   { document.getElementById('lightbox').classList.remove('open'); document.getElementById('lightbox-img').src=''; }
document.getElementById('lightbox-close').addEventListener('click', closeLightbox);
document.getElementById('lightbox').addEventListener('click', e => { if(e.target===document.getElementById('lightbox')) closeLightbox(); });
document.addEventListener('keydown', e => { if(e.key==='Escape') closeLightbox(); });

// Rend cliquables au clavier tous les éléments role="button" générés
// dynamiquement (photos de polaroids, cellules du dossier).
document.addEventListener('keydown', e => {
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('[role="button"][tabindex]')) {
    e.preventDefault();
    e.target.click();
  }
});

// ============================================================
// VICTOIRE
// ============================================================
function triggerVictory(rows) {
  const today = todayISO();
  const entry = rows.find(r => r.date === today);
  if (!entry) return;
  const winners = CHAR_KEYS.filter(k => entry.chars[k]?.result === true).map(k => CHAR_CONFIG[k].label);
  if (!winners.length) return;
  document.getElementById('victory-sub').textContent = winners.join('\n');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!reduceMotion) startParticles();
  const box = document.getElementById('victory-overlay');
  setTimeout(() => { box.classList.add('open'); document.getElementById('victory-close').focus(); }, reduceMotion ? 0 : 600);
}

// Câblé une seule fois : sans ça, chaque appel à triggerVictory() (par ex.
// après un clic sur "Réessayer") empilerait un nouveau listener sur le
// même bouton.
document.getElementById('victory-close').addEventListener('click', () => {
  document.getElementById('victory-overlay').classList.remove('open');
  stopParticles();
});
let animFrame = null;
function startParticles() {
  const canvas=document.getElementById('victory-canvas'), ctx=canvas.getContext('2d');
  function resize(){canvas.width=window.innerWidth;canvas.height=window.innerHeight;}resize();
  window.addEventListener('resize',resize);
  const colors=['#e8192c','#2f7fe8','#e8edf5','#c9a24a','#8b3ee0','#ff2d42'];
  const P=[];
  for(let i=0;i<200;i++) P.push({x:Math.random()*canvas.width,y:Math.random()*canvas.height-canvas.height,vx:(Math.random()-.5)*4,vy:Math.random()*4+2,size:Math.random()*8+3,color:colors[Math.floor(Math.random()*colors.length)],rot:Math.random()*360,vrot:(Math.random()-.5)*8,shape:Math.random()>.4?'rect':'web',alpha:1});
  function web(ctx,x,y,s){ctx.beginPath();for(let a=0;a<6;a++){const ag=(a/6)*Math.PI*2;ctx.moveTo(x,y);ctx.lineTo(x+Math.cos(ag)*s,y+Math.sin(ag)*s);}for(let r=.33;r<=1;r+=.33){ctx.moveTo(x+Math.cos(0)*s*r,y+Math.sin(0)*s*r);for(let a=1;a<=6;a++){const ag=(a/6)*Math.PI*2;ctx.lineTo(x+Math.cos(ag)*s*r,y+Math.sin(ag)*s*r);}}ctx.strokeStyle=ctx.fillStyle;ctx.lineWidth=1;ctx.stroke();}
  function loop(){ctx.clearRect(0,0,canvas.width,canvas.height);let alive=false;P.forEach(p=>{p.x+=p.vx;p.y+=p.vy;p.rot+=p.vrot;p.vy+=.08;if(p.y<canvas.height+20)alive=true;if(p.y>canvas.height*.7)p.alpha=Math.max(0,1-(p.y-canvas.height*.7)/(canvas.height*.3));ctx.save();ctx.globalAlpha=p.alpha;ctx.translate(p.x,p.y);ctx.rotate(p.rot*Math.PI/180);ctx.fillStyle=p.color;if(p.shape==='rect')ctx.fillRect(-p.size/2,-p.size/4,p.size,p.size/2);else web(ctx,0,0,p.size);ctx.restore();});if(alive)animFrame=requestAnimationFrame(loop);else ctx.clearRect(0,0,canvas.width,canvas.height);}
  loop();
}
function stopParticles(){if(animFrame)cancelAnimationFrame(animFrame);const c=document.getElementById('victory-canvas');c.getContext('2d').clearRect(0,0,c.width,c.height);}

// ============================================================
// DISCLAIMER
// ============================================================
function initDisclaimer(){
  const o=document.getElementById('disclaimer-overlay');
  const close=()=>{o.classList.remove('open');try{localStorage.setItem('disclaimer_seen','true');}catch(e){}};
  let seen=false;try{seen=!!localStorage.getItem('disclaimer_seen');}catch(e){}
  if(!seen)setTimeout(()=>o.classList.add('open'),1200);
  document.getElementById('disclaimer-close').addEventListener('click',close);
  document.getElementById('disclaimer-ok').addEventListener('click',close);
  o.addEventListener('click',e=>{if(e.target===o)close();});
}
initDisclaimer();

// ============================================================
// INIT
// ============================================================
// Câblés une seule fois, indépendamment du nombre de tentatives de
// chargement : ce sont des éléments statiques du DOM (pas régénérés à
// chaque render), donc les rappeler depuis init() empilerait des
// listeners dupliqués à chaque clic sur "Réessayer".
initDbControls();

async function init() {
  const rows = await loadDatabase();
  allRows = rows;
  renderTodayHero(rows);
  renderDashboard(rows);
  renderTop5(buildTop5(rows));
  renderDbTable();
  setProgress(96, 'Graphiques…');
  try { renderMainChart('tom'); } catch (e) { console.error('Chart.js indisponible :', e); }
  setProgress(100, 'Dossier prêt.');
  setTimeout(() => { hideLoader(); triggerVictory(rows); }, 450);
}

document.getElementById('load-error-retry').addEventListener('click', () => {
  document.getElementById('loader-status').textContent = 'Nouvelle tentative…';
  init();
});

init();