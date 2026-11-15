/* ═══════════════════════════════════════════════════════════════════════════
   L'Œil Critique — Page Jeux vidéo (/pages/jeux-video.html)
   Charge /assets/data/jeux.json, affiche les cartes par lots de 36,
   récupère dynamiquement les jaquettes (Netlify Function SteamGridDB en prod,
   cascade Wikidata + CheapShark + Wikipedia en local) et gère les longues critiques.
   ═══════════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  var BASE = document.body.getAttribute("data-base") || "../";
  var DATA_URL = new URL(BASE + "assets/data/jeux.json", window.location.href).href;
  var POSTER_FN_URL = "/.netlify/functions/game-poster";
  var CACHE_KEY = "loeil_jeux_visuels_v6";
  var REVIEW_MAX_CHARS = 180;
  var PAGE_SIZE = 36;
  var MAX_CONCURRENT = 6;

  var STATUS_LABELS = {
    termine: "Terminé",
    platine: "100 %",
    "en-cours": "En cours",
    backlog: "Backlog",
    abandonne: "Abandonné",
  };

  var DEMO_GAMES = [
    {
      titre: "Outer Wilds",
      plateformes: ["PC", "PS5"],
      genre: "Exploration · Mystère",
      note: 9.8,
      statut: "termine",
      heures: 24,
      date: "2024-09",
      steam: 753640,
      avis: "Un jeu d'exploration spatiale où la seule progression est ce que tu comprends de l'univers.",
    },
    {
      titre: "Dead Island 2",
      plateformes: ["PC", "PS5"],
      genre: "Action · Survie",
      note: 4,
      statut: "termine",
      date: "2026-08",
      avis: "C'est tellement nul omg. Genre là ya un gouffre entre Dead Island et ce jeu de merde.",
    },
  ];

  var grid = document.getElementById("games-grid");
  if (!grid) return;

  var statsEl = document.getElementById("games-stats");
  var countEl = document.getElementById("games-count");
  var demoBanner = document.getElementById("games-demo");
  var searchInput = document.getElementById("games-search");
  var platformSelect = document.getElementById("games-platform");
  var statusSelect = document.getElementById("games-status");
  var sortSelect = document.getElementById("games-sort");

  var allGames = [];
  var currentFiltered = [];
  var renderedCount = 0;
  var posterCache = loadPosterCache();
  var queuedTitles = {};
  var requestQueue = [];
  var activeRequests = 0;

  var moreWrap = el("div", "games-more");
  moreWrap.style.cssText = "display:flex;justify-content:center;margin-top:2rem;";
  var moreBtn = el("button", "games-loadia__cta", "Charger plus de jeux");
  moreBtn.type = "button";
  moreBtn.style.cursor = "pointer";
  moreBtn.style.border = "none";
  moreWrap.appendChild(moreBtn);
  moreWrap.hidden = true;
  grid.parentNode.insertBefore(moreWrap, grid.nextSibling);

  moreBtn.addEventListener("click", function () {
    appendBatch();
  });

  function loadPosterCache() {
    try {
      return JSON.parse(localStorage.getItem(CACHE_KEY) || "{}");
    } catch (_) {
      return {};
    }
  }

  function savePosterCache() {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify(posterCache));
    } catch (_) {}
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function formatNote(n) {
    if (typeof n !== "number" || isNaN(n)) return "";
    return (Number.isInteger(n) ? String(n) : n.toFixed(1).replace(".", ",")) + "/10";
  }

  function noteTier(n) {
    if (typeof n !== "number" || isNaN(n)) return "";
    if (n >= 9) return "is-chef";
    if (n >= 7.5) return "is-great";
    if (n >= 6) return "is-good";
    return "is-mid";
  }

  function cleanSearchTitle(title) {
    return String(title || "")
      .replace(/\s*\([^)]*\)/g, "")
      .replace(/\s+(Java Edition|Bedrock Edition|Remastered|Definitive Edition|Game of the Year Edition|GOTY|Complete Edition)$/i, "")
      .trim();
  }

  function posterUrl(g) {
    if (g.image) {
      return /^https?:\/\//.test(g.image) ? g.image : BASE + g.image.replace(/^\.?\//, "");
    }
    if (g.steam) {
      return "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/" + encodeURIComponent(g.steam) + "/library_600x900.jpg";
    }
    if (posterCache[g.titre]) {
      return posterCache[g.titre];
    }
    return "";
  }

  /* 1. Fonction Netlify (SteamGridDB 600x900 en production) */
  function fetchFromNetlifyFn(title) {
    var isLocal = window.location.hostname === "localhost" ||
                  window.location.hostname === "127.0.0.1" ||
                  window.location.protocol === "file:";
    if (isLocal) return Promise.resolve("");

    return fetch(POSTER_FN_URL + "?title=" + encodeURIComponent(title))
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) { return (data && data.url) || ""; })
      .catch(function () { return ""; });
  }

  /* 2. CheapShark API (CORS natif -> récupère steamAppID pour affiche Steam 600x900) */
  function fetchFromCheapShark(title) {
    var url = "https://www.cheapshark.com/api/1.0/games?title=" + encodeURIComponent(title) + "&limit=5";
    return fetch(url)
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (items) {
        if (!Array.isArray(items) || !items.length) return "";
        var withSteam = items.find(function (it) { return it.steamAppID; });
        if (withSteam && withSteam.steamAppID) {
          return "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/" + withSteam.steamAppID + "/library_600x900.jpg";
        }
        return items[0].thumb || "";
      })
      .catch(function () { return ""; });
  }

  /* 3. Wikipedia API ciblée jeux vidéo (CORS natif, fonctionne pour toutes les consoles) */
  function fetchFromWikipedia(title) {
    var queries = [title + " (video game)", title];
    function tryQuery(idx) {
      if (idx >= queries.length) return Promise.resolve("");
      var q = encodeURIComponent(queries[idx]);
      var url = "https://en.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch=" + q +
                "&gsrlimit=4&prop=pageimages&pithumbsize=500&format=json&origin=*";
      return fetch(url)
        .then(function (res) { return res.ok ? res.json() : null; })
        .then(function (data) {
          var pages = data && data.query && data.query.pages;
          if (!pages) return tryQuery(idx + 1);
          var list = Object.keys(pages).map(function (k) { return pages[k]; });
          list.sort(function (a, b) { return (a.index || 99) - (b.index || 99); });
          for (var i = 0; i < list.length; i++) {
            var p = list[i];
            if (p && p.thumbnail && p.thumbnail.source && !/\.svg\.png$/i.test(p.thumbnail.source)) {
              return p.thumbnail.source;
            }
          }
          return tryQuery(idx + 1);
        })
        .catch(function () { return tryQuery(idx + 1); });
    }
    return tryQuery(0);
  }

  function applyImageToWrap(wrap, url, title, fallbackSteamId) {
    var img = document.createElement("img");
    img.src = url;
    img.alt = "Jaquette de " + title;
    img.loading = "lazy";
    img.decoding = "async";

    img.addEventListener("load", function () {
      wrap.innerHTML = "";
      wrap.classList.remove("game-card__poster--missing");
      wrap.appendChild(img);
    });

    img.addEventListener("error", function () {
      var steamMatch = url.match(/\/apps\/(\d+)\/library_600x900\.jpg/);
      var idToUse = fallbackSteamId || (steamMatch && steamMatch[1]);
      if (idToUse && !img.dataset.fallback) {
        img.dataset.fallback = "1";
        var headerUrl = "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/" + encodeURIComponent(idToUse) + "/header.jpg";
        posterCache[title] = headerUrl;
        savePosterCache();
        img.src = headerUrl;
        return;
      }
      if (!img.dataset.wikiTried) {
        img.dataset.wikiTried = "1";
        fetchFromWikipedia(cleanSearchTitle(title)).then(function (wikiUrl) {
          if (wikiUrl) {
            posterCache[title] = wikiUrl;
            savePosterCache();
            img.src = wikiUrl;
          }
        });
      }
    });
  }

  function processQueue() {
    while (activeRequests < MAX_CONCURRENT && requestQueue.length > 0) {
      var task = requestQueue.shift();
      runLookup(task.g, task.wrap);
    }
  }

  function runLookup(g, wrap) {
    activeRequests++;
    var cleaned = cleanSearchTitle(g.titre);

    fetchFromNetlifyFn(g.titre)
      .then(function (url) {
        return url || fetchFromCheapShark(cleaned);
      })
      .then(function (url) {
        return url || fetchFromWikipedia(cleaned);
      })
      .then(function (finalUrl) {
        activeRequests--;
        delete queuedTitles[g.titre];
        if (finalUrl) {
          posterCache[g.titre] = finalUrl;
          savePosterCache();
          if (wrap.isConnected) {
            applyImageToWrap(wrap, finalUrl, g.titre, g.steam || null);
          }
        }
        processQueue();
      });
  }

  function resolveMissingPoster(g, wrap) {
    if (posterCache[g.titre] || queuedTitles[g.titre]) return;
    queuedTitles[g.titre] = true;
    requestQueue.push({ g: g, wrap: wrap });
    processQueue();
  }

  function posterNode(g) {
    var wrap = el("div", "game-card__poster");
    var src = posterUrl(g);
    if (!src) {
      wrap.classList.add("game-card__poster--missing");
      wrap.appendChild(el("span", "", g.titre));
      resolveMissingPoster(g, wrap);
      return wrap;
    }
    var img = document.createElement("img");
    img.src = src;
    img.alt = "Jaquette de " + g.titre;
    img.loading = "lazy";
    img.decoding = "async";
    img.addEventListener("error", function () {
      var steamMatch = src.match(/\/apps\/(\d+)\/library_600x900\.jpg/);
      var idToUse = g.steam || (steamMatch && steamMatch[1]);
      if (idToUse && !img.dataset.fallback) {
        img.dataset.fallback = "1";
        var headerUrl = "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/" + encodeURIComponent(idToUse) + "/header.jpg";
        posterCache[g.titre] = headerUrl;
        savePosterCache();
        img.src = headerUrl;
        return;
      }
      wrap.innerHTML = "";
      wrap.classList.add("game-card__poster--missing");
      wrap.appendChild(el("span", "", g.titre));
      delete posterCache[g.titre];
      resolveMissingPoster(g, wrap);
    });
    wrap.appendChild(img);
    return wrap;
  }

  function renderReview(text) {
    var clean = String(text || "").trim();
    var isLong = clean.length > REVIEW_MAX_CHARS || clean.indexOf("\n") !== -1;

    var box = el("div", "game-card__review-wrap");
    var p = el("p", "game-card__review" + (isLong ? " is-clamped" : ""), clean);
    box.appendChild(p);

    if (isLong) {
      var btn = el("button", "game-card__review-toggle", "Lire la critique complète");
      btn.type = "button";
      btn.setAttribute("aria-expanded", "false");

      btn.addEventListener("click", function () {
        var expanded = p.classList.toggle("is-expanded");
        p.classList.toggle("is-clamped", !expanded);
        btn.setAttribute("aria-expanded", String(expanded));
        btn.textContent = expanded ? "Réduire la critique" : "Lire la critique complète";
      });

      box.appendChild(btn);
    }

    return box;
  }

  function renderCard(g) {
    var card = el("article", "game-card");
    card.appendChild(posterNode(g));

    var body = el("div", "game-card__body");
    var top = el("div", "game-card__top");
    top.appendChild(el("h2", "game-card__title", g.titre));
    if (typeof g.note === "number") {
      top.appendChild(el("span", "game-card__note " + noteTier(g.note), formatNote(g.note)));
    }
    body.appendChild(top);

    var meta = el("div", "game-card__meta");
    if (Array.isArray(g.plateformes)) {
      g.plateformes.forEach(function (p) {
        meta.appendChild(el("span", "game-card__tag", p));
      });
    }
    if (g.genre) meta.appendChild(el("span", "game-card__tag", g.genre));
    if (g.statut) {
      meta.appendChild(el("span", "game-card__tag game-card__status--" + g.statut, STATUS_LABELS[g.statut] || g.statut));
    }
    if (typeof g.heures === "number" && g.heures > 0) {
      meta.appendChild(el("span", "game-card__tag", g.heures + " h"));
    }
    if (g.date) meta.appendChild(el("span", "game-card__tag", g.date));
    if (meta.childNodes.length) body.appendChild(meta);

    if (g.avis) {
      body.appendChild(renderReview(g.avis));
    }

    card.appendChild(body);
    return card;
  }

  function renderStats(list) {
    if (!statsEl) return;
    statsEl.innerHTML = "";
    var rated = list.filter(function (g) { return typeof g.note === "number"; });
    var avg = rated.length
      ? rated.reduce(function (sum, g) { return sum + g.note; }, 0) / rated.length
      : null;
    var finished = list.filter(function (g) { return g.statut === "termine" || g.statut === "platine"; }).length;
    var hours = list.reduce(function (sum, g) { return sum + (typeof g.heures === "number" ? g.heures : 0); }, 0);

    var items = [
      { value: String(list.length), label: "Jeux répertoriés" },
      { value: String(finished), label: "Terminés" },
      { value: avg !== null ? avg.toFixed(1).replace(".", ",") + "/10" : "—", label: "Note moyenne" },
      { value: Math.round(hours) + " h", label: "Temps cumulé" },
    ];
    items.forEach(function (it) {
      var box = el("div", "games-stat");
      box.appendChild(el("span", "games-stat__value", it.value));
      box.appendChild(el("span", "games-stat__label", it.label));
      statsEl.appendChild(box);
    });
  }

  function populatePlatforms(list) {
    if (!platformSelect) return;
    var seen = {};
    list.forEach(function (g) {
      (g.plateformes || []).forEach(function (p) { seen[p] = true; });
    });
    Object.keys(seen).sort().forEach(function (p) {
      var opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      platformSelect.appendChild(opt);
    });
  }

  function appendBatch() {
    var slice = currentFiltered.slice(renderedCount, renderedCount + PAGE_SIZE);
    if (!slice.length) return;

    var frag = document.createDocumentFragment();
    slice.forEach(function (g) { frag.appendChild(renderCard(g)); });
    grid.appendChild(frag);
    renderedCount += slice.length;

    var remaining = currentFiltered.length - renderedCount;
    if (remaining > 0) {
      moreWrap.hidden = false;
      moreBtn.textContent = "Charger plus de jeux (" + remaining + " restants)";
    } else {
      moreWrap.hidden = true;
    }
  }

  function applyFilters() {
    var q = (searchInput ? searchInput.value : "").trim().toLowerCase();
    var plat = platformSelect ? platformSelect.value : "";
    var stat = statusSelect ? statusSelect.value : "";
    var sort = sortSelect ? sortSelect.value : "note";

    currentFiltered = allGames.filter(function (g) {
      if (plat && (!g.plateformes || g.plateformes.indexOf(plat) === -1)) return false;
      if (stat && g.statut !== stat) return false;
      if (q) {
        var hay = (g.titre + " " + (g.genre || "") + " " + (g.avis || "") + " " + (g.plateformes || []).join(" ")).toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });

    currentFiltered.sort(function (a, b) {
      if (sort === "recent") return String(b.date || "").localeCompare(String(a.date || ""));
      if (sort === "titre") return String(a.titre || "").localeCompare(String(b.titre || ""), "fr");
      if (sort === "heures") return (b.heures || 0) - (a.heures || 0);
      return (b.note != null ? b.note : -1) - (a.note != null ? a.note : -1);
    });

    grid.innerHTML = "";
    grid.removeAttribute("aria-busy");
    renderedCount = 0;

    if (countEl) {
      countEl.textContent = currentFiltered.length === allGames.length
        ? currentFiltered.length + " jeu" + (currentFiltered.length > 1 ? "x" : "")
        : currentFiltered.length + " sur " + allGames.length + " jeu" + (allGames.length > 1 ? "x" : "");
    }

    if (!currentFiltered.length) {
      moreWrap.hidden = true;
      var empty = el("div", "games-empty");
      empty.appendChild(el("p", "", !allGames.length
        ? "Aucun jeu n'a encore été ajouté dans assets/data/jeux.json."
        : "Aucun jeu ne correspond à ces filtres."));
      grid.appendChild(empty);
      return;
    }

    appendBatch();
  }

  function init(games, isDemo) {
    allGames = Array.isArray(games) ? games : [];
    if (demoBanner) demoBanner.hidden = !isDemo;
    renderStats(allGames);
    populatePlatforms(allGames);
    applyFilters();
  }

  [searchInput, platformSelect, statusSelect, sortSelect].forEach(function (ctrl) {
    if (!ctrl) return;
    ctrl.addEventListener(ctrl.tagName === "INPUT" ? "input" : "change", applyFilters);
  });

  if (location.hash === "#demo") {
    init(DEMO_GAMES, true);
    return;
  }

  fetch(DATA_URL)
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      var list = Array.isArray(data) ? data : (data && Array.isArray(data.jeux) ? data.jeux : []);
      init(list, false);
    })
    .catch(function (err) {
      console.error("Erreur chargement jeux.json :", err);
      grid.innerHTML = "";
      grid.removeAttribute("aria-busy");
      moreWrap.hidden = true;
      var errBox = el("div", "games-empty");
      errBox.appendChild(el("p", "", "Impossible de charger la liste des jeux pour le moment."));
      grid.appendChild(errBox);
    });
})();