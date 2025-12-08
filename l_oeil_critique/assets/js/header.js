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

    // 3. Déclaration des variables et initialisation de la recherche
    const searchInput = document.querySelector("#search-input");
    const resultsContainer = document.querySelector("#search-results-container");
    let articlesIndex = []; // Pour stocker les données du JSON

    // Charger le JSON de l'index des articles
    fetch("/l_oeil_critique/articles_index.json")
        .then(res => {
            if (!res.ok) throw new Error("Erreur de chargement du fichier JSON.");
            return res.json();
        })
        .then(data => articlesIndex = data)
        .catch(err => console.error("Erreur chargement index articles :", err));

    // Logique de recherche au fur et à mesure de la saisie
    searchInput.addEventListener("input", () => {
        const query = searchInput.value.toLowerCase().trim();
        resultsContainer.innerHTML = "";
        
        // Cacher les résultats si la requête est vide
        if (!query) {
            resultsContainer.classList.remove("active");
            return;
        }

        // Filtrage et limitation des résultats (ici à 10)
        const filtered = articlesIndex
            .filter(a => a.title.toLowerCase().includes(query))
            .slice(0, 10);

        filtered.forEach(a => {
            const div = document.createElement("div");
            div.classList.add("search-result-item");
            // Utilisation d'un lien pour naviguer vers l'article
            div.innerHTML = `<a href="${a.url}">${a.title} <span class="result-type">(${a.type})</span></a>`;
            resultsContainer.appendChild(div);
        });

        // Afficher ou cacher le conteneur des résultats
        if (filtered.length > 0) {
            resultsContainer.classList.add("active");
        } else {
            // Optionnel : Afficher un message "Aucun résultat"
            // const noResult = document.createElement("div");
            // noResult.classList.add("search-result-item");
            // noResult.textContent = "Aucun résultat trouvé.";
            // resultsContainer.appendChild(noResult);
            // resultsContainer.classList.add("active"); 
            resultsContainer.classList.remove("active"); 
        }
    });

    // Fermer les résultats lorsque l'utilisateur clique en dehors du conteneur de recherche
    document.addEventListener("click", (e) => {
        const searchContainer = document.querySelector(".search-container");
        if (searchContainer && !searchContainer.contains(e.target)) {
            resultsContainer.classList.remove("active");
        }
    });
    
    // Fermer les résultats si l'utilisateur appuie sur Echap
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            resultsContainer.classList.remove("active");
        }
    });


    // --- Autres fonctionnalités du Header ---

    // 4. Sticky header
    const header = document.querySelector("header");
    window.addEventListener("scroll", () => {
        if (window.scrollY > 50) header.classList.add("scrolled");
        else header.classList.remove("scrolled");
    });

    // 5. Lien actif selon la page
    const currentPath = window.location.pathname;
    document.querySelectorAll(".main-nav a").forEach(link => {
        // Utilisation de la méthode la plus robuste pour vérifier la correspondance
        const linkPath = link.getAttribute("href").split("/").pop();
        const currentFileName = currentPath.split("/").pop();

        if (currentFileName === linkPath && linkPath !== "") {
            link.classList.add("active");
        } else if (currentFileName === "" && linkPath === "index.html") {
             // Cas spécial pour la page d'accueil
             link.classList.add("active");
        }
    });

    // 6. Burger menu : fermeture au clic sur un lien
    const burgerToggle = document.querySelector("#nav-toggle");
    document.querySelectorAll(".main-nav a").forEach(link => {
        link.addEventListener("click", () => {
            // Ferme le menu en décochant la checkbox
            burgerToggle.checked = false;
        });
    });
});