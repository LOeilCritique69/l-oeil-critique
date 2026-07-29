document.addEventListener("DOMContentLoaded", () => {
  console.log("DOMContentLoaded fired");

  // =========================
  // HEADER — structure "diaphragme ouvert"
  // =========================
  const headerHTML = `
    <header>
      <div class="header-utility" id="headerUtility">
        <div class="header-utility__inner">
          <span class="header-utility__time" id="headerClock">—</span>
          <span class="header-utility__tagline">Chaque image mérite un jugement.</span>
        </div>
      </div>

      <div class="header-main">
        <div class="header-content">
          <a href="/index.html" class="logo-link" aria-label="Retour à l'accueil de L'Œil Critique">
            <span class="logo-aperture" aria-hidden="true"></span>
            <img src="/l_oeil_critique/logo_chef_doeuvre_processed_copy.jpg" alt="Logo L'Œil Critique" class="logo">
            <span class="site-title">L'Œil Critique</span>
          </a>

          <nav class="main-nav" id="mainNav" aria-label="Navigation principale">
            <a href="/l_oeil_critique/news/Accueil.html" data-index="01">Actualités</a>
            <a href="/l_oeil_critique/reviews.html" data-index="02">Critiques</a>
            <a href="/l_oeil_critique/bande-annonces.html" data-index="03">Bandes-Annonces</a>
            <a href="/l_oeil_critique/pages/theories.html" data-index="04">Théories</a>
            <a href="/l_oeil_critique/extras.html" data-index="05">Extras</a>
            <a href="/l_oeil_critique/A_propos.html" data-index="06">À Propos</a>
            <a href="/l_oeil_critique/pages/calendrier.html" data-index="07" id="calendarNavLink">Calendrier</a>
          </nav>

          <div class="header-actions">
            <a class="icon-btn" id="calendarBtn" href="/l_oeil_critique/pages/calendrier.html" aria-label="Calendrier des sorties" title="Calendrier des sorties">
              <svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
            </a>

            <button class="icon-btn" id="searchOpenBtn" aria-label="Ouvrir la recherche" aria-haspopup="dialog" aria-expanded="false">
              <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
              <span class="icon-btn__kbd">/</span>
            </button>

            <div class="notif-wrapper">
              <button class="icon-btn" id="notifBtn" aria-label="Notifications" aria-haspopup="true" aria-expanded="false">
                <svg viewBox="0 0 24 24"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>
                <span class="notif-badge hidden" id="notifBadge">0</span>
              </button>
              <div class="notif-panel" id="notifPanel" role="dialog" aria-label="Notifications">
                <div class="notif-panel-header">
                  <span class="notif-panel-title">Notifications</span>
                  <button class="notif-mark-all" id="markAllBtn">Tout marquer lu</button>
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
          <span class="search-overlay__icon">
            <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          </span>
          <input type="text" id="search-input" placeholder="Rechercher un film, une série, un article..." autocomplete="off">
          <button class="search-overlay__close" id="searchCloseBtn" aria-label="Fermer la recherche">✕</button>
        </div>
        <div id="search-results-container" class="search-overlay__results"></div>
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
            <a href="/index.html" class="footer-logo-link" aria-label="Retour à l'accueil de L'Œil Critique">
              <span class="logo-aperture static" aria-hidden="true"></span>
              <img src="/l_oeil_critique/logo_chef_doeuvre_processed_copy.jpg" alt="" class="footer-logo">
              <span class="footer-site-title">L'Œil Critique</span>
            </a>
            <p class="footer-tagline">Chaque image mérite un jugement. Critiques, actualités et théories, sans complaisance.</p>
            <div class="footer-socials">
              <a href="https://letterboxd.com/oni_le_chan/" class="footer-social" aria-label="Suivre sur Letterboxd" target="_blank" rel="noopener">
                <svg viewBox="0 0 24 24"><circle cx="6.5" cy="12" r="3.2"></circle><circle cx="12" cy="12" r="3.2"></circle><circle cx="17.5" cy="12" r="3.2"></circle></svg>
                Letterboxd
              </a>
            </div>
          </div>

          <nav class="footer-col footer-nav-explorer" aria-label="Explorer">
            <span class="footer-col__title">Explorer</span>
            <a href="/l_oeil_critique/news/Accueil.html" data-index="01">Actualités</a>
            <a href="/l_oeil_critique/reviews.html" data-index="02">Critiques</a>
            <a href="/l_oeil_critique/bande-annonces.html" data-index="03">Bandes-Annonces</a>
            <a href="/l_oeil_critique/pages/theories.html" data-index="04">Théories</a>
            <a href="/l_oeil_critique/extras.html" data-index="05">Extras</a>
          </nav>

          <nav class="footer-col" aria-label="Informations">
            <span class="footer-col__title">Informations</span>
            <a href="/l_oeil_critique/A_propos.html">À propos</a>
            <a href="/l_oeil_critique/pages/mises-a-jour.html">Mises à jour</a>
            <a href="/l_oeil_critique/mentions_légales.html">Mentions légales</a>
            <a href="/l_oeil_critique/politique-de-confidentialité.html">Confidentialité</a>
            <a href="/l_oeil_critique/contact.html">Contact</a>
          </nav>
        </div>
      </div>

      <div class="footer-bottom">
        <div class="footer-bottom__inner">
          <p>&copy; 2026 L'Œil Critique. Tous droits réservés.</p>
          <button class="footer-totop" id="footerToTop" aria-label="Retour en haut de page">
            <svg viewBox="0 0 24 24"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg>
            Haut de page
          </button>
        </div>
      </div>
    </footer>
  `;
  document.body.insertAdjacentHTML("beforeend", footerHTML);


  // =========================
  // FOOTER — retour en haut de page
  // =========================
  const footerToTop = document.getElementById("footerToTop");
  footerToTop?.addEventListener("click", () => {
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
  // NOTIFICATION SYSTEM (logique inchangée)
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
    fetch("/l_oeil_critique/assets/data/notifications.json")
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => {
        notifications = Array.isArray(data) ? data : [];
        notifications.forEach((n) => {
          if (readIds.includes(n.id)) {
            n.unread = false;
          }
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
        <div class="notif-item ${n.unread ? "unread" : ""}" data-id="${n.id}">
          <div class="notif-dot"></div>
          <div class="notif-thumb">
            ${n.image ? `<img src="${n.image}" alt="">` : (n.icon || "🔔")}
          </div>
          <div class="notif-body">
            <p class="notif-text">${n.text}</p>
          </div>
        </div>
      `)
      .join("");

    notifList.querySelectorAll(".notif-item").forEach((el) => {
      el.addEventListener("click", () => {
        const id = +el.dataset.id;
        const notif = notifications.find((n) => n.id === id);
        if (notif && notif.unread) {
          notif.unread = false;
          el.classList.remove("unread");
          saveReadId(id);
          renderBadge();
        }
        if (notif && notif.url) {
          window.location.href = notif.url;
        }
      });
    });
  }

  function openPanel() {
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
  } else {
    console.error("[NOTIF] un ou plusieurs éléments notif introuvables — système désactivé", {
      notifBtn, notifBadge, notifPanel, notifList, markAllBtn
    });
  }

  document.addEventListener("click", (e) => {
    if (
      notifPanelOpen &&
      notifPanel &&
      !notifPanel.contains(e.target) &&
      e.target !== notifBtn
    ) {
      closePanel();
    }
  });

  window.NotifSystem = {
    push(notif) {
      notifications.unshift({ id: Date.now(), unread: true, ...notif });
      renderBadge();
      triggerBadgePop();
      if (notifPanelOpen) {
        renderList();
      }
    },
    markAll() {
      notifications.forEach((n) => (n.unread = false));
      saveAllReadIds();
      renderBadge();
      if (notifPanelOpen) {
        renderList();
      }
    },
  };

  loadNotifications();


  // =========================
  // RECHERCHE — overlay plein écran (command palette)
  // =========================
  const searchOpenBtn = document.getElementById("searchOpenBtn");
  const searchOverlay = document.getElementById("searchOverlay");
  const searchBackdrop = document.getElementById("searchBackdrop");
  const searchCloseBtn = document.getElementById("searchCloseBtn");
  const searchInput = document.querySelector("#search-input");
  const resultsContainer = document.querySelector("#search-results-container");
  let articlesIndex = [];
  let searchOverlayOpen = false;

  fetch("/l_oeil_critique/assets/data/articles_index.json")
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

  function renderSearchResults(query) {
    if (!resultsContainer) return;

    if (!query) {
      resultsContainer.innerHTML = '<div class="search-empty">Tapez pour rechercher un film, une série ou un article.</div>';
      return;
    }

    const filtered = articlesIndex
      .filter(
        (a) =>
          a &&
          a.title &&
          typeof a.title === "string" &&
          a.title.toLowerCase().includes(query)
      )
      .slice(0, 10);

    if (filtered.length === 0) {
      resultsContainer.innerHTML = '<div class="search-empty">Aucun résultat pour cette recherche.</div>';
      return;
    }

    resultsContainer.innerHTML = filtered
      .map((a) => {
        const url = typeof a.url === "string" ? a.url : "#";
        const imgSrc = getImageSrc(a.image);
        return `
          <a href="${url}" class="search-link">
            <div class="search-item">
              <div class="search-thumb">${imgSrc ? `<img src="${imgSrc}" alt="">` : ""}</div>
              <div class="search-text">
                <div class="search-title">${a.title || "Sans titre"}</div>
                <div class="search-meta">${a.type || ""}</div>
              </div>
            </div>
          </a>
        `;
      })
      .join("");
  }

  function openSearch() {
    if (!searchOverlay) return;
    searchOverlayOpen = true;
    searchOverlay.classList.add("open");
    searchOpenBtn?.setAttribute("aria-expanded", "true");
    renderSearchResults(searchInput ? searchInput.value.trim().toLowerCase() : "");
    requestAnimationFrame(() => searchInput?.focus());
  }

  function closeSearch() {
    if (!searchOverlay) return;
    searchOverlayOpen = false;
    searchOverlay.classList.remove("open");
    searchOpenBtn?.setAttribute("aria-expanded", "false");
    searchOpenBtn?.focus();
  }

  if (searchOpenBtn && searchOverlay && searchInput && resultsContainer) {
    searchOpenBtn.addEventListener("click", () => {
      searchOverlayOpen ? closeSearch() : openSearch();
    });

    searchCloseBtn?.addEventListener("click", closeSearch);
    searchBackdrop?.addEventListener("click", closeSearch);

    searchInput.addEventListener("input", () => {
      renderSearchResults(searchInput.value.trim().toLowerCase());
    });

    document.addEventListener("keydown", (e) => {
      const tag = document.activeElement?.tagName;
      const isTyping = tag === "INPUT" || tag === "TEXTAREA";

      if (e.key === "/" && !isTyping && !searchOverlayOpen) {
        e.preventDefault();
        openSearch();
      }
      if (e.key === "Escape" && searchOverlayOpen) {
        closeSearch();
      }
    });
  } else {
    console.error("[SEARCH] élément(s) introuvable(s) — recherche désactivée", {
      searchOpenBtn, searchOverlay, searchInput, resultsContainer
    });
  }


  // =========================
  // HEADER SCROLL STATE
  // =========================
  const headerEl = document.querySelector("header");
  if (!headerEl) console.error("[HEADER] <header> introuvable dans le DOM");

  window.addEventListener("scroll", () => {
    const isScrolled = window.scrollY > 50;
    if (headerEl) headerEl.classList.toggle("scrolled", isScrolled);
    document.body.classList.toggle("header-scrolled", isScrolled);
  });


  // =========================
  // BURGER MENU LOGIC (CENTRAL)
  // =========================
  const headerActions = document.querySelector(".header-actions");
  const nav = document.getElementById("mainNav");

  if (!headerActions || !nav || !headerEl) {
    console.error("[BURGER] init annulé — élément(s) manquant(s)", { headerActions, nav, headerEl });
  } else {
    const burgerBtn = document.createElement("button");
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
    console.log("[BURGER] bouton injecté", burgerBtn);

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
      console.log("[BURGER] clic détecté, état actuel:", nav.classList.contains("mobile-open"));
      nav.classList.contains("mobile-open") ? closeMobileNav() : openMobileNav();
    });

    nav.addEventListener("click", (e) => {
      if (e.target === nav) closeMobileNav();
    });

    nav.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", closeMobileNav);
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && nav.classList.contains("mobile-open")) closeMobileNav();
    });
  }

  // Un seul listener de resize (au lieu d'un par lien)
  let resizeTimer;
  window.addEventListener("resize", () => {
    document.body.classList.add("resize-animation-stopper");
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      document.body.classList.remove("resize-animation-stopper");
    }, 400);
  });


  // =========================
  // ACTIVE LINK FIX (ROBUSTE & ISOLÉ — basé sur le chemin complet)
  // Couvre désormais aussi bien la nav du header que la colonne
  // "Explorer" du footer, qui reprend les mêmes rubriques.
  // =========================

  console.log("[ACTIVE LINK] init");

  const normalizePath = (path) => {
    if (!path) return "";
    try {
      const url = new URL(path, window.location.origin + window.location.pathname);
      return decodeURIComponent(url.pathname)
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");
    } catch (e) {
      return (path || "").toLowerCase();
    }
  };

  const currentPath = normalizePath(window.location.pathname);
  console.log("[ACTIVE LINK] currentPath :", currentPath);

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
      keyword: "bande-annonce",
      patterns: [
        "/bande-annonces.html",
        "/bande_annonces_blocs.html"
      ]
    },
    {
      keyword: "th\u00e9ories",
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
      keyword: "propos",
      patterns: ["/a_propos.html"]
    }
  ];

  function matchesGroup(path, group) {
    return group.patterns.some((p) => path.includes(p));
  }

  const links = document.querySelectorAll(".main-nav a, .footer-nav-explorer a");
  console.log("[ACTIVE LINK] links count :", links.length);

  links.forEach((a) => {
    const hrefPath = normalizePath(a.getAttribute("href"));
    const linkText = a.textContent.toLowerCase();

    let isActive = hrefPath === currentPath;

    if (!isActive) {
      const group = NAV_GROUPS.find((g) => linkText.includes(g.keyword));
      if (group && matchesGroup(currentPath, group)) {
        isActive = true;
      }
    }

    a.classList.remove("active");
    if (isActive) {
      a.classList.add("active");
      console.log(`[ACTIVE] ${hrefPath || linkText}`);
    } else {
      console.log(`[SKIP] ${hrefPath || linkText}`);
    }
  });

  // Icône calendrier : mise en avant visuelle si on est déjà sur la page calendrier
  const calendarBtn = document.getElementById("calendarBtn");
  if (calendarBtn && currentPath.includes("/pages/calendrier.html")) {
    calendarBtn.classList.add("active");
  }
});