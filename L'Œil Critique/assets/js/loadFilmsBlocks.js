window.addEventListener("DOMContentLoaded", () => {
  const container = document.querySelector(".latest-news-grid");

  if (!container) {
    console.error("Conteneur .latest-news-grid introuvable dans la page.");
    return;
  }

  fetch("articles/blocs_films.html")
    .then(response => {
      if (!response.ok) {
        throw new Error(`Erreur HTTP : ${response.status}`);
      }
      return response.text();
    })
    .then(html => {
      container.innerHTML = html;
    })
    .catch(error => {
      console.error("Erreur lors du chargement des articles :", error);
      container.innerHTML = `
        <p style="color: red; font-weight: bold;">
          ⚠️ Impossible de charger les dernières actualités pour le moment.
        </p>`;
    });
});
