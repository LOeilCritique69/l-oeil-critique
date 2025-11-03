document.addEventListener("DOMContentLoaded", () => {
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
      </div>
    </header>
  `;

  // Injecte le header tout en haut du body
  document.body.insertAdjacentHTML("afterbegin", headerHTML);

  // === Gestion du lien actif ===
  const currentPath = window.location.pathname;
  document.querySelectorAll(".main-nav a").forEach(link => {
    if (currentPath.endsWith(link.getAttribute("href").split("/").pop())) {
      link.classList.add("active");
    }
  });

  // === Gestion du sticky (si tu veux foncer le header au scroll) ===
  const header = document.querySelector("header");
  window.addEventListener("scroll", () => {
    if (window.scrollY > 50) header.classList.add("scrolled");
    else header.classList.remove("scrolled");
  });

  // === Sécurité mobile : ferme le menu au clic ===
  const burgerToggle = document.querySelector("#nav-toggle");
  const navLinks = document.querySelectorAll(".main-nav a");
  navLinks.forEach(link =>
    link.addEventListener("click", () => {
      burgerToggle.checked = false;
    })
  );
});
