/* tier-posters.js
 * Charge les affiches des tier lists depuis OMDb (via la fonction Netlify "poster")
 * et gère la modale d'agrandissement.
 *
 * Utilisation côté HTML :
 *   <div class="tier-item" data-title="Toy Story 3" data-year="2010"></div>
 *   <div class="tier-item" data-title="Loki" data-year="2021" data-type="series"></div>
 *   <div class="tier-item" data-imdb="tt0435761" data-title="Toy Story 3"></div>
 *   data-label = nom affiché (légende / texte alternatif) s'il diffère du titre anglais.
 */
(function () {
  'use strict';

  var API = '/.netlify/functions/poster'; // adapte si ta fonction est ailleurs

  // Mode local (Live Server) : la fonction Netlify n'existe pas, donc on appelle OMDb directement
  // avec une clé stockée UNIQUEMENT dans ton navigateur (jamais dans le code, jamais sur le site).
  // À faire une fois, dans la console du navigateur (F12) sur ta page locale :
  //   localStorage.setItem('OMDB_DEV_KEY', 'TA_CLE')
  var IS_LOCAL = /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
  var DEV_KEY = null;
  try { DEV_KEY = IS_LOCAL ? localStorage.getItem('OMDB_DEV_KEY') : null; } catch (e) { /* ignore */ }
  var CACHE_KEY = 'omdbPosterCache_v2';
  var cache = {};
  try { cache = JSON.parse(localStorage.getItem(CACHE_KEY) || '{}'); } catch (e) { cache = {}; }

  function saveCache() {
    try { localStorage.setItem(CACHE_KEY, JSON.stringify(cache)); } catch (e) { /* quota / mode privé */ }
  }

  // OMDb renvoie une URL Amazon du type ..._V1_QL75_UX380_CR0,1,380,562_.jpg
  // (ou l'ancien format ..._SX300.jpg) -> on change la largeur et on adapte le recadrage
  function resize(url, w) {
    var m = url.match(/_UX(\d+)_CR(\d+),(\d+),(\d+),(\d+)_/);
    if (m) {
      var k = w / +m[1];
      return url.replace(m[0], '_UX' + w + '_CR' + Math.round(m[2] * k) + ',' + Math.round(m[3] * k) +
        ',' + Math.round(m[4] * k) + ',' + Math.round(m[5] * k) + '_');
    }
    return url.replace(/_(SX|UX)\d+/, '_$1' + w);
  }

  function labelOf(d) {
    return d.label || (d.year ? d.title + ' (' + d.year + ')' : d.title);
  }

  // Un appel à la fonction. Retourne { poster } (ou null) ; throw si erreur transitoire.
  async function query(params) {
    var url = DEV_KEY
      ? 'https://www.omdbapi.com/?apikey=' + encodeURIComponent(DEV_KEY) + '&' + params.toString()
      : API + '?' + params.toString();
    var res = await fetch(url);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    var data = await res.json();
    if (data.Response === 'True') {
      if (data.Search) { // résultat d'une recherche (s=) : premier résultat avec affiche
        var hit = data.Search.find(function (r) { return r.Poster && r.Poster !== 'N/A'; });
        return hit ? hit.Poster : null;
      }
      return data.Poster && data.Poster !== 'N/A' ? data.Poster : null;
    }
    if (/not found/i.test(data.Error || '')) return undefined; // introuvable : on pourra réessayer autrement
    throw new Error(data.Error || 'Erreur OMDb'); // limite atteinte, clé invalide...
  }

  async function getPoster(d) {
    var key = d.imdb || [d.type || 'any', d.title, d.year || ''].join('|');
    if (key in cache) return cache[key];

    // Essais successifs, du plus précis au plus tolérant :
    // 1) titre + année  2) titre seul  3) recherche + année  4) recherche seule
    // (la recherche rattrape les titres écrits un peu différemment, ex. "Vol. 2" vs ": Vol. 2")
    var attempts = [];
    function mk(key, withYear) {
      var q = new URLSearchParams();
      q.set(key, d.title);
      if (withYear && d.year) q.set('y', d.year);
      if (d.type) q.set('type', d.type);
      return q;
    }
    if (d.imdb) {
      attempts.push(new URLSearchParams({ i: d.imdb }));
    } else {
      attempts.push(mk('t', true));
      if (d.year) attempts.push(mk('t', false));
      attempts.push(mk('s', true));
      if (d.year) attempts.push(mk('s', false));
    }

    try {
      var poster;
      for (var i = 0; i < attempts.length; i++) {
        poster = await query(attempts[i]);
        if (poster !== undefined) break;
      }
      cache[key] = poster || null;   // null = introuvable, on le retient
      saveCache();
      return poster || null;
    } catch (e) {
      return null;                   // erreur transitoire : pas de mise en cache
    }
  }

  async function loadPoster(el) {
    var d = el.dataset;
    var poster = await getPoster(d);
    if (el.tagName === 'IMG') {            // image de carte (page index) : on remplit le src
      if (!poster) { el.classList.add('tierlist-card__image--missing'); return; }
      if (!el.alt) el.alt = labelOf(d);
      el.decoding = 'async';
      el.src = resize(poster, 342);
      return;
    }
    if (!poster) {
      el.classList.add('tier-item--missing');
      el.textContent = labelOf(d);
      return;
    }
    var img = document.createElement('img');
    img.alt = labelOf(d);
    img.decoding = 'async';
    img.src = resize(poster, 185);
    img.dataset.full = resize(poster, 600);
    el.appendChild(img);
  }

  function init() {
    // Cartes de la page index : peu nombreuses, on les charge directement
    document.querySelectorAll('img.tierlist-card__image[data-title]').forEach(loadPoster);

    var items = document.querySelectorAll('.tier-item[data-title], .tier-item[data-imdb]');
    if (!('IntersectionObserver' in window)) {
      items.forEach(loadPoster);
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { io.unobserve(e.target); loadPoster(e.target); }
      });
    }, { rootMargin: '300px' });
    items.forEach(function (el) { io.observe(el); });
  }

  /* ---------- Modale d'agrandissement (créée ici, plus besoin de la mettre dans le HTML) ---------- */
  function initModal() {
    var modal = document.getElementById('lpImageModal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'lpImageModal';
      modal.className = 'lp-modal';
      modal.setAttribute('role', 'dialog');
      modal.setAttribute('aria-modal', 'true');
      modal.setAttribute('aria-hidden', 'true');
      modal.setAttribute('aria-label', "Agrandissement d'image");
      modal.tabIndex = -1;
      modal.innerHTML =
        '<div class="lp-modal__backdrop" data-close="true"></div>' +
        '<div class="lp-modal__content" role="document">' +
        '<img alt="" class="lp-modal__img" id="lpImageModalImg" src="">' +
        '<div class="lp-modal__caption" id="lpImageModalCaption"></div>' +
        '</div>';
      document.body.appendChild(modal);
    }
    var modalImg = document.getElementById('lpImageModalImg');
    var modalCaption = document.getElementById('lpImageModalCaption');
    var lastTrigger = null;

    function closeModal() {
      modal.classList.remove('is-active');
      modal.setAttribute('aria-hidden', 'true');
      modalImg.removeAttribute('src');
      modalImg.alt = '';
      modalCaption.textContent = '';
      if (lastTrigger && lastTrigger.focus) { lastTrigger.focus(); }
      lastTrigger = null;
    }

    document.addEventListener('click', function (event) {
      var trigger = event.target.closest('.tier-item img');
      if (trigger) {
        event.preventDefault();
        lastTrigger = trigger;
        modalImg.src = trigger.dataset.full || trigger.currentSrc || trigger.src;
        modalImg.alt = trigger.alt || '';
        modalCaption.textContent = trigger.alt || '';
        modal.classList.add('is-active');
        modal.setAttribute('aria-hidden', 'false');
        modal.focus();
        return;
      }
      if (event.target.classList.contains('lp-modal__backdrop') || event.target === modal) {
        closeModal();
      }
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && modal.classList.contains('is-active')) closeModal();
    });
  }

  function start() { initModal(); init(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();