document.addEventListener("DOMContentLoaded", () => {
    // 1. Définition du Header HTML avec la barre de recherche
    const headerHTML = `
      <header>
        <div class="header-content">
          <a href="/index.html" class="logo-link" aria-label="Retour à l'accueil de L'Œil Critique">
            <img src="/l_oeil_critique/assets/img/logo_chef_doeuvre_processed_copy.jpg" alt="Logo L'Œil Critique" class="logo">
            <h1 class="site-title"><a href="/index.html" class="site-title-link">L'Œil Critique</a></h1>
          </a>

          <input type="checkbox" id="nav-toggle" hidden>
          <label for="nav-toggle" class="burger-menu" aria-label="Menu">
            <span></span><span></span><span></span>
          </label>

          <nav class="main-nav" aria-label="Navigation principale du site">
            <a href="/l_oeil_critique/films.html">Films</a>
            <a href="/l_oeil_critique/series.html">Séries</a>
            <a href="/l_oeil_critique/actualités.html">Actualités</a>
            <a href="/l_oeil_critique/reviews.html">Reviews</a>
            <a href="/l_oeil_critique/bande-annonces.html">Bandes-Annonces</a>
            <a href="/l_oeil_critique/A_propos.html">À Propos</a>
          </nav>

          <div class="search-container">
            <input type="text" id="search-input" placeholder="Rechercher..." aria-label="Champ de recherche">
            <button id="search-button" aria-label="Lancer la recherche">🔍</button>
            <div id="search-results-container" class="search-results"></div>
          </div>

        </div>
      </header>
    `;

    // 2. Injection du header
    document.body.insertAdjacentHTML("afterbegin", headerHTML);

    // FOOTER
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

    // 2. Injection du footer

    document.body.insertAdjacentHTML("beforeend", footerHTML);

     // =========================
    // SEARCH SYSTEM
    // =========================
    const searchInput = document.querySelector("#search-input");
    const resultsContainer = document.querySelector("#search-results-container");

    let articlesIndex = [];

    fetch("/l_oeil_critique/assets/data/articles_index.json")
        .then(r => r.ok ? r.json() : [])
        .then(data => {
            articlesIndex = Array.isArray(data) ? data : [];
        })
        .catch(() => {
            articlesIndex = [];
        });

    function getImageSrc(img) {
        if (!img) return null;

        // si string simple
        if (typeof img === "string") return img;

        // si objet
        if (typeof img === "object") {
            return img.src || null;
        }

        return null;
    }

    searchInput.addEventListener("input", () => {

        const query = searchInput.value.trim().toLowerCase();
        resultsContainer.innerHTML = "";

        if (!query) {
            resultsContainer.classList.remove("active");
            return;
        }

        const filtered = articlesIndex
            .filter(a =>
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

                        <div class="search-thumb">
                            ${imgSrc ? `<img src="${imgSrc}" alt="">` : ""}
                        </div>

                        <div class="search-text">
                            <div class="search-title">
                                ${a.title || "Sans titre"}
                            </div>
                            <div class="search-meta">
                                ${a.type || ""}
                            </div>
                        </div>

                    </div>
                </a>
            `;

            resultsContainer.appendChild(div);
        }

        resultsContainer.classList.toggle("active", filtered.length > 0);
    });

    // fermeture click extérieur
    document.addEventListener("click", (e) => {
        if (!document.querySelector(".search-container").contains(e.target)) {
            resultsContainer.classList.remove("active");
        }
    });

    // ESC
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            resultsContainer.classList.remove("active");
        }
    });

    // =========================
    // ACTIVE LINK FIX
    // =========================
    const current = window.location.pathname.split("/").pop();

    document.querySelectorAll(".main-nav a").forEach(a => {
        const link = a.getAttribute("href").split("/").pop();
        if (link === current) a.classList.add("active");
    });

    // burger close
    const burger = document.querySelector("#nav-toggle");
    document.querySelectorAll(".main-nav a").forEach(a => {
        a.addEventListener("click", () => burger.checked = false);
    });
});