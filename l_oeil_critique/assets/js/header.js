document.addEventListener("DOMContentLoaded", () => {
  console.log("DOMContentLoaded fired");

  // =========================
  // HEADER (unchanged)
  // =========================
  const headerHTML = `
    <header>
      <div class="header-content">
        <a href="/index.html" class="logo-link" aria-label="Retour à l'accueil de L'Œil Critique">
          <img src="/l_oeil_critique/logo_chef_doeuvre_processed_copy.jpg" alt="Logo L'Œil Critique" class="logo">
        </a>
        <h1 class="site-title">
          <a href="/index.html" class="site-title-link">L'Œil Critique</a>
        </h1>

        <nav class="main-nav" id="mainNav" aria-label="Navigation principale">
          <a href="/l_oeil_critique/news/Accueil.html">Actualités</a>
          <a href="/l_oeil_critique/reviews.html">Critiques</a>
          <a href="/l_oeil_critique/bande-annonces.html">Bandes-Annonces</a>
          <a href="/l_oeil_critique/A_propos.html">À Propos</a>
        </nav>

        <div class="header-actions">
          <div class="notif-wrapper">
            <button class="notif-btn" id="notifBtn" aria-label="Notifications" aria-haspopup="true" aria-expanded="false">
              <span class="notif-icon">🔔</span>
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

          <div class="search-container">
            <input type="text" id="search-input" placeholder="Rechercher..." aria-label="Champ de recherche">
            <button id="search-button" aria-label="Lancer la recherche">🔍</button>
            <div id="search-results-container" class="search-results"></div>
          </div>
        </div>
      </div>
    </header>
  `;

  document.body.insertAdjacentHTML("afterbegin", headerHTML);


  // =========================
  // FOOTER (unchanged)
  // =========================
  const footerHTML = `
    <footer>
      <div class="footer-content">
        <div class="footer-links">
          <a href="/l_oeil_critique/mentions_légales.html">Mentions légales</a>
          <a href="/l_oeil_critique/politique-de-confidentialité.html">Politique de confidentialité</a>
          <a href="/l_oeil_critique/contact.html">Contact</a>
        </div>
        <p>&copy; 2026 L'Œil Critique. Tous droits réservés.</p>
      </div>
    </footer>
  `;
  document.body.insertAdjacentHTML("beforeend", footerHTML);


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

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
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
  // SEARCH SYSTEM
  // =========================
  const searchInput = document.querySelector("#search-input");
  const resultsContainer = document.querySelector("#search-results-container");
  let articlesIndex = [];

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

  if (searchInput && resultsContainer) {
    searchInput.addEventListener("input", () => {
      const query = searchInput.value.trim().toLowerCase();
      resultsContainer.innerHTML = "";
      if (!query) {
        resultsContainer.classList.remove("active");
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

      for (const a of filtered) {
        const url = typeof a.url === "string" ? a.url : "#";
        const imgSrc = getImageSrc(a.image);
        const div = document.createElement("div");
        div.className = "search-result-item";
        div.innerHTML = `
          <a href="${url}">
            <div class="search-item">
              <div class="search-thumb">${imgSrc ? `<img src="${imgSrc}" alt="">` : ""}</div>
              <div class="search-text">
                <div class="search-title">${a.title || "Sans titre"}</div>
                <div class="search-meta">${a.type || ""}</div>
              </div>
            </div>
          </a>
        `;
        resultsContainer.appendChild(div);
      }
      resultsContainer.classList.toggle("active", filtered.length > 0);
    });
  } else {
    console.error("[SEARCH] #search-input ou #search-results-container introuvable", {
      searchInput, resultsContainer
    });
  }

  document.addEventListener("click", (e) => {
    const searchContainer = document.querySelector(".search-container");
    if (searchContainer && resultsContainer && !searchContainer.contains(e.target)) {
      resultsContainer.classList.remove("active");
    }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && resultsContainer) {
      resultsContainer.classList.remove("active");
    }
  });


  // =========================
  // HEADER SCROLL STATE
  // =========================
  const headerEl = document.querySelector("header");
  if (!headerEl) console.error("[HEADER] <header> introuvable dans le DOM");

  window.addEventListener("scroll", () => {
    if (headerEl) headerEl.classList.toggle("scrolled", window.scrollY > 50);
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
      headerEl.classList.add("menu-open");          // ← ajouté
    }

    function closeMobileNav() {
      nav.classList.remove("mobile-open");
      burgerBtn.classList.remove("active");
      burgerBtn.setAttribute("aria-expanded", "false");
      document.body.classList.remove("nav-locked");
      document.body.style.paddingRight = "";
      headerEl.style.paddingRight = "";
      headerEl.classList.remove("menu-open");       // ← ajouté
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
  // =========================

  console.log("[ACTIVE LINK] init");

  // Normalise un chemin (URL ou attribut href) : minuscules, sans accents,
  // sans query/hash, résolu par rapport à l'URL courante.
  const normalizePath = (path) => {
    if (!path) return "";
    try {
      const url = new URL(path, window.location.origin + window.location.pathname);
      return decodeURIComponent(url.pathname)
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, ""); // enlève les accents (é -> e, etc.)
    } catch (e) {
      return (path || "").toLowerCase();
    }
  };

  const currentPath = normalizePath(window.location.pathname);
  console.log("[ACTIVE LINK] currentPath :", currentPath);

  // Chaque groupe = un lien de nav (identifié par un mot-clé dans son texte)
  // + la liste des motifs de chemin qui doivent l'activer.
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
        "/pages/tier-list", // couvre tier-lists.html ET tier-list/*.html
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
      keyword: "propos",
      patterns: ["/a_propos.html"]
    }
  ];

  function matchesGroup(path, group) {
    return group.patterns.some((p) => path.includes(p));
  }

  const links = document.querySelectorAll(".main-nav a");
  console.log("[ACTIVE LINK] links count :", links.length);

  links.forEach((a) => {
    const hrefPath = normalizePath(a.getAttribute("href"));
    const linkText = a.textContent.toLowerCase();

    // 1. Match direct : la page courante EST le lien lui-même
    let isActive = hrefPath === currentPath;

    // 2. Match par groupe : la page courante appartient à la même
    //    rubrique que ce lien (ex : un article d'actu -> lien "Actualités")
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
});