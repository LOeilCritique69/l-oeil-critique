/* ========================================================================
   article-enhance.js — L'Œil Critique
   Amélioration progressive des pages articles. Ne modifie pas le contenu,
   n'ajoute rien de bloquant : si ce script échoue ou n'est pas chargé,
   la page reste parfaitement lisible avec le CSS seul.

   Ce script :
   1) Dessine l'œil de notation dans .note à partir du texte « X/5 »
   2) Génère le sommaire (.toc-nav) à partir des <h2> de .critique
   3) Anime une barre de progression de lecture
   4) Révèle les sections au défilement (repli gracieux inclus)
   ======================================================================== */

document.addEventListener('DOMContentLoaded', () => {
  if (!document.body.classList.contains('article-page')) return;

  buildRatingEye();
  buildTableOfContents();
  buildReadingProgress();
  enableScrollReveal();
});

/* 1) Œil de notation ---------------------------------------------------- */
function buildRatingEye() {
  const note = document.querySelector('.note');
  if (!note) return;

  const h3 = note.querySelector('h3');
  const p = note.querySelector('p');
  if (!h3) return;

  const match = h3.textContent.match(/(\d+(?:[.,]\d+)?)\s*\/\s*5/);
  const rating = match ? parseFloat(match[1].replace(',', '.')) : 3;
  const openness = Math.max(0.06, Math.min(1, rating / 5)); // 0.06 = jamais totalement fermé

  const maxH = 24;
  const h = openness * maxH;
  const eyePath = `M6,30 Q50,${30 - h} 94,30 Q50,${30 + h} 6,30 Z`;
  const pupilR = 6 + openness * 6;

  const svg = `
    <svg viewBox="0 0 100 60" role="img" aria-label="Note illustrée : ${rating} sur 5">
      <path class="eye-outline" d="${eyePath}"></path>
      <circle class="eye-pupil" cx="50" cy="30" r="${pupilR}"></circle>
      <circle class="eye-highlight" cx="${52 + openness}" cy="${27 - openness}" r="1.6"></circle>
    </svg>
  `;

  // Réorganise .note en deux blocs : l'œil + le texte
  const wrapEye = document.createElement('div');
  wrapEye.className = 'note-eye';
  wrapEye.innerHTML = svg;

  const wrapBody = document.createElement('div');
  wrapBody.className = 'note-body';
  wrapBody.appendChild(h3);
  if (p) wrapBody.appendChild(p);

  note.innerHTML = '';
  note.appendChild(wrapEye);
  note.appendChild(wrapBody);
  note.classList.add('note--enhanced');
}

/* 2) Sommaire ------------------------------------------------------------ */
function buildTableOfContents() {
  const critique = document.querySelector('.critique');
  if (!critique) return;

  const headings = Array.from(critique.querySelectorAll('h2'));
  if (headings.length < 2) return;

  const used = new Set();
  const slugify = (text) => {
    let base = text
      .toLowerCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/(^-|-$)/g, '') || 'section';
    let slug = base, n = 2;
    while (used.has(slug)) { slug = `${base}-${n++}`; }
    used.add(slug);
    return slug;
  };

  const items = headings.map((h) => {
    if (!h.id) h.id = slugify(h.textContent);
    return `<li><a href="#${h.id}">${h.textContent}</a></li>`;
  }).join('');

  const nav = document.createElement('nav');
  nav.className = 'toc-nav';
  nav.setAttribute('aria-label', 'Sommaire de la critique');
  nav.innerHTML = `<p>Sommaire</p><ol>${items}</ol>`;

  const anchor = document.querySelector('.spoiler-warning') || document.querySelector('.note');
  if (anchor) {
    anchor.insertAdjacentElement('afterend', nav);
  } else {
    critique.insertAdjacentElement('beforebegin', nav);
  }
}

/* 3) Barre de progression ------------------------------------------------ */
function buildReadingProgress() {
  const critique = document.querySelector('.critique');
  if (!critique) return;

  const wrap = document.createElement('div');
  wrap.className = 'reading-progress';
  const bar = document.createElement('div');
  bar.className = 'reading-progress-bar';
  wrap.appendChild(bar);
  document.body.appendChild(wrap);

  const update = () => {
    const rect = critique.getBoundingClientRect();
    const total = rect.height - window.innerHeight;
    const scrolled = Math.min(Math.max(-rect.top, 0), Math.max(total, 1));
    const pct = total > 0 ? (scrolled / total) * 100 : 0;
    bar.style.width = `${Math.min(100, Math.max(0, pct))}%`;
  };

  update();
  window.addEventListener('scroll', update, { passive: true });
  window.addEventListener('resize', update);
}

/* 4) Révélation au défilement -------------------------------------------- */
function enableScrollReveal() {
  const targets = document.querySelectorAll('.critique h2, .critique figure');
  if (!targets.length || !('IntersectionObserver' in window)) return;

  document.documentElement.classList.add('js-enhanced');

  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });

  targets.forEach((t) => io.observe(t));
}