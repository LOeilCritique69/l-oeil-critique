// =========================
// BARRE DE CHARGEMENT DISCRÈTE (style cinéma / YouTube)
// =========================
(function initTopLoader() {
  const bar = document.createElement("div");
  bar.id = "top-page-loader";
  Object.assign(bar.style, {
    position: "fixed",
    top: "0",
    left: "0",
    height: "2px",
    width: "0%",
    backgroundColor: "var(--brass, #d4a949)",
    boxShadow: "0 0 8px var(--brass, #d4a949)",
    zIndex: "99999",
    pointerEvents: "none",
    transition: "width 0.3s ease, opacity 0.35s ease",
    opacity: "1"
  });

  document.documentElement.appendChild(bar);

  requestAnimationFrame(() => { bar.style.width = "35%"; });
  document.addEventListener("DOMContentLoaded", () => { bar.style.width = "75%"; });

  window.addEventListener("load", () => {
    bar.style.width = "100%";
    setTimeout(() => {
      bar.style.opacity = "0";
      setTimeout(() => bar.remove(), 400);
    }, 150);
  });

  document.addEventListener("click", (e) => {
    const link = e.target.closest("a[href]");
    if (!link) return;
    const href = link.getAttribute("href");
    if (
      href &&
      !href.startsWith("#") &&
      !href.startsWith("mailto:") &&
      !href.startsWith("tel:") &&
      link.target !== "_blank" &&
      !e.ctrlKey && !e.metaKey && !e.shiftKey
    ) {
      document.documentElement.appendChild(bar);
      bar.style.opacity = "1";
      bar.style.width = "40%";
    }
  });
})();

document.addEventListener("DOMContentLoaded", () => {
  // Résolution dynamique de la racine du site via <body data-base="../">
  const rawBase = document.body.dataset.base;
  const BASE = rawBase !== undefined ? rawBase : "/l_oeil_critique/";
  const HOME_URL = "/index.html";

  // =========================
  // HEADER — structure "diaphragme ouvert"
  // =========================
  const headerHTML = `
    <header id="siteHeader">
      <div class="header-utility" id="headerUtility">
        <div class="header-utility__inner">
          <span class="header-utility__time" id="headerClock">—</span>
          <span class="header-utility__tagline">Chaque image mérite un jugement.</span>
        </div>
      </div>

      <div class="header-main">
        <div class="header-content">
          <a href="${HOME_URL}" class="logo-link" aria-label="Retour à l'accueil de L'Œil Critique">
            <span class="logo-aperture" aria-hidden="true"></span>
            <img src="/l_oeil_critique/logo_chef_doeuvre_processed_copy.jpg" alt="Logo L'Œil Critique" class="logo">
            <span class="site-title">L'Œil Critique</span>
          </a>

          <nav class="main-nav" id="mainNav" aria-label="Navigation principale">
            <a href="${BASE}news/Accueil.html" data-index="01">Actualités</a>
            <a href="${BASE}reviews.html" data-index="02">Critiques</a>
            <a href="${BASE}bande-annonces.html" data-index="03">Bandes-Annonces</a>
            <a href="${BASE}pages/theories.html" data-index="04">Théories</a>
            <a href="${BASE}extras.html" data-index="05">Extras</a>
            <a href="${BASE}A_propos.html" data-index="06">À Propos</a>
            <a href="${BASE}pages/calendrier.html" data-index="07" id="calendarNavLink">Calendrier</a>
          </nav>

          <div class="header-actions">
            <a class="icon-btn" id="calendarBtn" href="${BASE}pages/calendrier.html" aria-label="Calendrier des sorties" title="Calendrier des sorties">
              <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
            </a>

            <button type="button" class="icon-btn" id="searchOpenBtn" aria-label="Ouvrir la recherche" aria-haspopup="dialog" aria-expanded="false" title="Rechercher (/ ou Ctrl+K)">
              <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
              <span class="icon-btn__kbd" aria-hidden="true">/</span>
            </button>

            <div class="notif-wrapper">
              <button type="button" class="icon-btn" id="notifBtn" aria-label="Notifications" aria-haspopup="true" aria-expanded="false" title="Notifications">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>
                <span class="notif-badge hidden" id="notifBadge">0</span>
              </button>
              <div class="notif-panel" id="notifPanel" role="dialog" aria-label="Notifications">
                <div class="notif-panel-header">
                  <span class="notif-panel-title">Notifications</span>
                  <button type="button" class="notif-mark-all" id="markAllBtn">Tout marquer lu</button>
                </div>
                <div class="notif-list" id="notifList"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>

    <div class="search-overlay" id="searchOverlay" role="dialog" aria-modal="true" aria-label="Recherche">
      <div class="search-overlay__backdrop" id="searchBackdrop"></div>
      <div class="search-overlay__panel">
        <div class="search-overlay__field">
          <span class="search-overlay__icon" aria-hidden="true">
            <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          </span>
          <input type="text" id="search-input" placeholder="Rechercher un film, une série, un article..." autocomplete="off" aria-autocomplete="list" aria-controls="search-results-container">
          
          <button type="button" class="search-overlay__close" id="searchCloseBtn" aria-label="Fermer la recherche">✕</button>
        </div>
        <div id="search-results-container" class="search-overlay__results" role="listbox"></div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("afterbegin", headerHTML);

  // =========================
  // FOOTER — refonte "obturateur final"
  // =========================
  const footerHTML = `
    <footer>
      <div class="footer-aperture" aria-hidden="true"></div>

      <div class="footer-top">
        <div class="footer-grid">
          <div class="footer-brand">
            <a href="${HOME_URL}" class="footer-logo-link" aria-label="Retour à l'accueil de L'Œil Critique">
              <span class="logo-aperture static" aria-hidden="true"></span>
              <img src="/l_oeil_critique/logo_chef_doeuvre_processed_copy.jpg" alt="" class="footer-logo">
              <span class="footer-site-title">L'Œil Critique</span>
            </a>
            <p class="footer-tagline">Chaque image mérite un jugement. Critiques, actualités et théories, sans complaisance.</p>
            <div class="footer-socials">
              <a href="https://letterboxd.com/oni_le_chan/" class="footer-social" aria-label="Suivre sur Letterboxd" target="_blank" rel="noopener noreferrer">
                <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="6.5" cy="12" r="3.2"></circle><circle cx="12" cy="12" r="3.2"></circle><circle cx="17.5" cy="12" r="3.2"></circle></svg>
                Letterboxd
              </a>
              <a href="https://loadia.app/app/profile/bicha?lang=fr" class="footer-social" aria-label="Voir le profil Loadia" target="_blank" rel="noopener noreferrer">
                <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="6" width="20" height="12" rx="4"></rect><line x1="7" y1="12" x2="11" y2="12"></line><line x1="9" y1="10" x2="9" y2="14"></line><circle cx="15.5" cy="11" r="1"></circle><circle cx="17.5" cy="13" r="1"></circle></svg>
                Loadia
              </a>
            </div>
          </div>

          <nav class="footer-col footer-nav-explorer" aria-label="Explorer">
            <span class="footer-col__title">Explorer</span>
            <a href="${BASE}news/Accueil.html" data-index="01">Actualités</a>
            <a href="${BASE}reviews.html" data-index="02">Critiques</a>
            <a href="${BASE}pages/jeux-video.html" data-index="03">Jeux vidéo</a>
            <a href="${BASE}bande-annonces.html" data-index="04">Bandes-Annonces</a>
            <a href="${BASE}pages/theories.html" data-index="05">Théories</a>
            <a href="${BASE}extras.html" data-index="06">Extras</a>
            <a href="${BASE}pages/calendrier.html" data-index="07">Calendrier</a>
          </nav>

          <nav class="footer-col" aria-label="Informations">
            <span class="footer-col__title">Informations</span>
            <a href="${BASE}A_propos.html">À propos</a>
            <a href="${BASE}pages/mises-a-jour.html">Mises à jour</a>
            <a href="${BASE}mentions_légales.html">Mentions légales</a>
            <a href="${BASE}politique-de-confidentialité.html">Confidentialité</a>
            <a href="${BASE}contact.html">Contact</a>
          </nav>
        </div>
      </div>

      <div class="footer-bottom">
        <div class="footer-bottom__inner">
          <p>&copy; 2026 L'Œil Critique. Tous droits réservés.</p>
          <button type="button" class="footer-totop" id="footerToTop" aria-label="Retour en haut de page">
            <svg viewBox="0 0 24 24" aria-hidden="true"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg>
            Haut de page
          </button>
        </div>
      </div>
    </footer>
  `;
  document.body.insertAdjacentHTML("beforeend", footerHTML);

  // =========================
  // UTILITAIRES
  // =========================
  function handleBrokenImages(container, fallbackText) {
    container.querySelectorAll("img").forEach((img) => {
      img.addEventListener(
        "error",
        () => {
          if (fallbackText && img.parentElement) {
            img.parentElement.textContent = fallbackText;
          } else {
            img.remove();
          }
        },
        { once: true }
      );
    });
  }

  function escapeHTML(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // =========================
  // FOOTER — retour en haut de page
  // =========================
  document.getElementById("footerToTop")?.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  // =========================
  // HORLOGE DE LA BANDE UTILITAIRE
  // =========================
  const headerClock = document.getElementById("headerClock");

  function updateClock() {
    if (!headerClock) return;
    const now = new Date();
    const formatted = now.toLocaleDateString("fr-FR", {
      weekday: "long",
      day: "numeric",
      month: "long",
    });
    const time = now.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    headerClock.textContent = `${formatted} — ${time}`;
  }

  updateClock();
  setInterval(updateClock, 30000);

  // =========================
  // NOTIFICATION SYSTEM
  // =========================
  const STORAGE_KEY = "notif_read";
  let notifications = [];
  let notifPanelOpen = false;

  const notifBtn = document.getElementById("notifBtn");
  const notifBadge = document.getElementById("notifBadge");
  const notifPanel = document.getElementById("notifPanel");
  const notifList = document.getElementById("notifList");
  const markAllBtn = document.getElementById("markAllBtn");

  function getReadIds() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    } catch (e) {
      return [];
    }
  }

  function saveReadId(id) {
    const readIds = getReadIds();
    if (!readIds.includes(id)) {
      readIds.push(id);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(readIds));
    }
  }

  function saveAllReadIds() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(notifications.map((n) => n.id)));
  }

  function loadNotifications() {
    const readIds = getReadIds();
    fetch(`${BASE}assets/data/notifications.json`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => {
        notifications = Array.isArray(data) ? data : [];
        notifications.forEach((n) => {
          if (readIds.includes(n.id)) n.unread = false;
        });
        renderBadge();
      })
      .catch(() => {
        notifications = [];
      });
  }

  function unreadCount() {
    return notifications.filter((n) => n.unread).length;
  }

  function renderBadge() {
    if (!notifBadge || !notifBtn) return;
    const count = unreadCount();
    notifBadge.textContent = count > 9 ? "9+" : count;
    notifBadge.classList.toggle("hidden", count === 0);
    notifBtn.setAttribute("aria-expanded", String(notifPanelOpen));
  }

  function triggerBadgePop() {
    if (!notifBadge) return;
    notifBadge.classList.remove("pop");
    void notifBadge.offsetWidth;
    notifBadge.classList.add("pop");
  }

  function renderList() {
    if (!notifList) return;
    if (notifications.length === 0) {
      notifList.innerHTML = '<div class="notif-empty">Aucune notification pour le moment.</div>';
      return;
    }
    notifList.innerHTML = notifications
      .map((n) => `
        <div class="notif-item ${n.unread ? "unread" : ""}" data-id="${n.id}" tabindex="0" role="button">
          <div class="notif-dot"></div>
          <div class="notif-thumb">
            ${n.image ? `<img src="${escapeHTML(n.image)}" alt="">` : (n.icon || "🔔")}
          </div>
          <div class="notif-body">
            <p class="notif-text">${escapeHTML(n.text)}</p>
          </div>
        </div>
      `)
      .join("");

    notifList.querySelectorAll(".notif-item").forEach((el) => {
      const notif = notifications.find((n) => n.id === +el.dataset.id);
      const thumb = el.querySelector(".notif-thumb");
      if (thumb) handleBrokenImages(thumb, (notif && notif.icon) || "🔔");

      const handleActivate = () => {
        const id = +el.dataset.id;
        const current = notifications.find((n) => n.id === id);
        if (current && current.unread) {
          current.unread = false;
          el.classList.remove("unread");
          saveReadId(id);
          renderBadge();
        }
        if (current && current.url) {
          window.location.href = current.url;
        }
      };

      el.addEventListener("click", handleActivate);
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handleActivate();
        }
      });
    });
  }

  function openPanel() {
    if (searchOverlayOpen) closeSearch();
    notifPanelOpen = true;
    notifPanel.classList.add("open");
    notifBtn.setAttribute("aria-expanded", "true");
    renderList();
  }

  function closePanel() {
    notifPanelOpen = false;
    notifPanel.classList.remove("open");
    notifBtn.setAttribute("aria-expanded", "false");
  }

  if (notifBtn && notifBadge && notifPanel && notifList && markAllBtn) {
    notifBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      notifPanelOpen ? closePanel() : openPanel();
    });

    markAllBtn.addEventListener("click", () => {
      notifications.forEach((n) => (n.unread = false));
      saveAllReadIds();
      renderBadge();
      renderList();
    });
  }

  document.addEventListener("click", (e) => {
    if (
      notifPanelOpen &&
      notifPanel &&
      !notifPanel.contains(e.target) &&
      !notifBtn.contains(e.target)
    ) {
      closePanel();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && notifPanelOpen) {
      closePanel();
      notifBtn?.focus();
    }
  });

  window.NotifSystem = {
    push(notif) {
      notifications.unshift({ id: Date.now(), unread: true, ...notif });
      renderBadge();
      triggerBadgePop();
      if (notifPanelOpen) renderList();
    },
    markAll() {
      notifications.forEach((n) => (n.unread = false));
      saveAllReadIds();
      renderBadge();
      if (notifPanelOpen) renderList();
    },
  };

  loadNotifications();

  // =========================
  // RECHERCHE — command palette avec navigation clavier ↑ ↓ ↵
  // =========================
  const searchOpenBtn = document.getElementById("searchOpenBtn");
  const searchOverlay = document.getElementById("searchOverlay");
  const searchBackdrop = document.getElementById("searchBackdrop");
  const searchCloseBtn = document.getElementById("searchCloseBtn");
  const searchInput = document.querySelector("#search-input");
  const resultsContainer = document.querySelector("#search-results-container");
  let articlesIndex = [];
  let searchOverlayOpen = false;
  let activeSearchIndex = -1;

  fetch(`${BASE}assets/data/articles_index.json`)
    .then((r) => (r.ok ? r.json() : []))
    .then((data) => {
      articlesIndex = Array.isArray(data) ? data : [];
    })
    .catch(() => {
      articlesIndex = [];
    });

  function getImageSrc(img) {
    if (!img) return null;
    if (typeof img === "string") return img;
    if (typeof img === "object") return img.src || null;
    return null;
  }

  function updateActiveSearchResult() {
    if (!resultsContainer) return;
    const items = resultsContainer.querySelectorAll(".search-link");
    items.forEach((item, idx) => {
      const isSelected = idx === activeSearchIndex;
      item.classList.toggle("is-selected", isSelected);
      item.setAttribute("aria-selected", String(isSelected));
      if (isSelected) {
        item.scrollIntoView({ block: "nearest" });
      }
    });
  }

  function renderSearchResults(query) {
    if (!resultsContainer) return;
    activeSearchIndex = -1;

    if (!query) {
      resultsContainer.innerHTML = '<div class="search-empty">Tapez pour rechercher un film, une série, un jeu ou un outil.</div>';
      return;
    }

    const normalizedQuery = normalizeText(query);

    const filtered = articlesIndex
      .filter((a) => {
        if (!a || typeof a.title !== "string") return false;
        const titleMatch = normalizeText(a.title).includes(normalizedQuery);
        const typeMatch = a.type && normalizeText(a.type).includes(normalizedQuery);
        const descMatch = a.description && normalizeText(a.description).includes(normalizedQuery);
        return titleMatch || typeMatch || descMatch;
      })
      .slice(0, 10);

    if (filtered.length === 0) {
      resultsContainer.innerHTML = '<div class="search-empty">Aucun résultat pour cette recherche.</div>';
      return;
    }

    resultsContainer.innerHTML = filtered
      .map((a, idx) => {
        const url = typeof a.url === "string" ? a.url : "#";
        const imgSrc = getImageSrc(a.image);
        return `
          <a href="${escapeHTML(url)}" class="search-link" role="option" aria-selected="false" data-idx="${idx}">
            <div class="search-item">
              <div class="search-thumb">${imgSrc ? `<img src="${escapeHTML(imgSrc)}" alt="">` : ""}</div>
              <div class="search-text">
                <div class="search-title">${escapeHTML(a.title || "Sans titre")}</div>
                <div class="search-meta">${escapeHTML(a.type || "")}${a.rating ? ` · ${escapeHTML(a.rating)}` : ""}</div>
              </div>
            </div>
          </a>
        `;
      })
      .join("");

    handleBrokenImages(resultsContainer);
  }

  function openSearch() {
    if (!searchOverlay) return;
    if (notifPanelOpen) closePanel();
    searchOverlayOpen = true;
    searchOverlay.classList.add("open");
    searchOpenBtn?.setAttribute("aria-expanded", "true");
    document.body.classList.add("nav-locked");
    renderSearchResults(searchInput ? searchInput.value.trim() : "");
    requestAnimationFrame(() => searchInput?.focus());
  }

  function closeSearch() {
    if (!searchOverlay) return;
    searchOverlayOpen = false;
    searchOverlay.classList.remove("open");
    searchOpenBtn?.setAttribute("aria-expanded", "false");
    document.body.classList.remove("nav-locked");
    searchOpenBtn?.focus();
  }

  if (searchOpenBtn && searchOverlay && searchInput && resultsContainer) {
    searchOpenBtn.addEventListener("click", () => {
      searchOverlayOpen ? closeSearch() : openSearch();
    });

    searchCloseBtn?.addEventListener("click", closeSearch);
    searchBackdrop?.addEventListener("click", closeSearch);

    searchInput.addEventListener("input", () => {
      renderSearchResults(searchInput.value.trim());
    });

    searchInput.addEventListener("keydown", (e) => {
      const items = resultsContainer.querySelectorAll(".search-link");
      if (!items.length) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        activeSearchIndex = (activeSearchIndex + 1) % items.length;
        updateActiveSearchResult();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        activeSearchIndex = (activeSearchIndex - 1 + items.length) % items.length;
        updateActiveSearchResult();
      } else if (e.key === "Enter" && activeSearchIndex >= 0 && items[activeSearchIndex]) {
        e.preventDefault();
        items[activeSearchIndex].click();
      }
    });

    document.addEventListener("keydown", (e) => {
      const tag = document.activeElement?.tagName;
      const isTyping = tag === "INPUT" || tag === "TEXTAREA" || document.activeElement?.isContentEditable;

      if ((e.key === "/" || ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k")) && !isTyping && !searchOverlayOpen) {
        e.preventDefault();
        openSearch();
      }
      if (e.key === "Escape" && searchOverlayOpen) {
        closeSearch();
      }
    });
  }

  // =========================
  // HEADER SCROLL STATE
  // =========================
  const headerEl = document.getElementById("siteHeader") || document.querySelector("header");

  function syncScrollState() {
    const isScrolled = window.scrollY > 50;
    if (headerEl) headerEl.classList.toggle("scrolled", isScrolled);
    document.body.classList.toggle("header-scrolled", isScrolled);
  }

  syncScrollState();
  window.addEventListener("scroll", syncScrollState, { passive: true });

  // =========================
  // BURGER MENU LOGIC (CENTRAL)
  // =========================
  const headerActions = document.querySelector(".header-actions");
  const nav = document.getElementById("mainNav");

  if (headerActions && nav && headerEl) {
    const burgerBtn = document.createElement("button");
    burgerBtn.type = "button";
    burgerBtn.className = "burger-menu";
    burgerBtn.setAttribute("aria-label", "Menu");
    burgerBtn.setAttribute("aria-haspopup", "true");
    burgerBtn.setAttribute("aria-expanded", "false");
    burgerBtn.setAttribute("aria-controls", "mainNav");
    burgerBtn.innerHTML = `
      <div class="burger-box">
        <span class="burger-line"></span>
        <span class="burger-line"></span>
        <span class="burger-line"></span>
      </div>
    `;

    headerActions.appendChild(burgerBtn);

    function getScrollbarWidth() {
      return window.innerWidth - document.documentElement.clientWidth;
    }

    function openMobileNav() {
      const sbWidth = getScrollbarWidth();
      nav.classList.add("mobile-open");
      burgerBtn.classList.add("active");
      burgerBtn.setAttribute("aria-expanded", "true");
      document.body.classList.add("nav-locked");
      document.body.style.paddingRight = `${sbWidth}px`;
      headerEl.style.paddingRight = `${sbWidth}px`;
      headerEl.classList.add("menu-open");
    }

    function closeMobileNav() {
      nav.classList.remove("mobile-open");
      burgerBtn.classList.remove("active");
      burgerBtn.setAttribute("aria-expanded", "false");
      document.body.classList.remove("nav-locked");
      document.body.style.paddingRight = "";
      headerEl.style.paddingRight = "";
      headerEl.classList.remove("menu-open");
    }

    burgerBtn.addEventListener("click", () => {
      nav.classList.contains("mobile-open") ? closeMobileNav() : openMobileNav();
    });

    nav.addEventListener("click", (e) => {
      if (e.target === nav) closeMobileNav();
    });

    nav.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", closeMobileNav);
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && nav.classList.contains("mobile-open")) {
        closeMobileNav();
        burgerBtn.focus();
      }
    });
  }

  let resizeTimer;
  window.addEventListener("resize", () => {
    document.body.classList.add("resize-animation-stopper");
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      document.body.classList.remove("resize-animation-stopper");
    }, 400);
  });

  // =========================
  // ACTIVE LINK FIX (ROBUSTE & ISOLÉ)
  // =========================
  const normalizeText = (str) =>
    (str || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");

  const normalizePath = (path) => {
    if (!path) return "";
    try {
      const url = new URL(path, window.location.origin + window.location.pathname);
      return normalizeText(decodeURIComponent(url.pathname));
    } catch (e) {
      return normalizeText(path);
    }
  };

  const currentPath = normalizePath(window.location.pathname);

  const NAV_GROUPS = [
    {
      keyword: "actual",
      patterns: [
        "/news/",
        "/articles/films/",
        "/articles/series/",
        "/articles/bigactualites/"
      ]
    },
    {
      keyword: "critique",
      patterns: [
        "/reviews.html",
        "/pages/critique-films.html",
        "/pages/critique-series.html",
        "/pages/tier-list",
        "/articles/reviews/"
      ]
    },
    {
      keyword: "jeux video",
      patterns: ["/pages/jeux-video.html"]
    },
    {
      keyword: "bande-annonce",
      patterns: [
        "/bande-annonces.html",
        "/bande_annonces_blocs.html"
      ]
    },
    {
      keyword: "theories",
      patterns: [
        "/pages/theories.html",
        "/articles/theories/"
      ]
    },
    {
      keyword: "extras",
      patterns: [
        "/extras.html",
        "/devine-le-film.html",
        "/spideytrack/"
      ]
    },
    {
      keyword: "calendrier",
      patterns: ["/pages/calendrier.html"]
    },
    {
      keyword: "propos",
      patterns: ["/a_propos.html"]
    }
  ];

  function matchesGroup(path, group) {
    return group.patterns.some((p) => path.includes(p));
  }

  const links = document.querySelectorAll(".main-nav a, .footer-nav-explorer a");

  links.forEach((a) => {
    const hrefPath = normalizePath(a.getAttribute("href"));
    const linkText = normalizeText(a.textContent);

    let isActive = hrefPath === currentPath;

    if (!isActive) {
      const group = NAV_GROUPS.find((g) => linkText.includes(g.keyword));
      if (group && matchesGroup(currentPath, group)) {
        isActive = true;
      }
    }

    a.classList.toggle("active", isActive);
  });

  const calendarBtn = document.getElementById("calendarBtn");
  if (calendarBtn && currentPath.includes("/pages/calendrier.html")) {
    calendarBtn.classList.add("active");
  }
});