/* ============================================================================
   L'ŒIL CRITIQUE — Tendances automatiques
   ----------------------------------------------------------------------------
   Récupère les articles à la une (hero-duo + featured-card) depuis la home
   et remplit dynamiquement le bloc #tendances-links. Repli sur le contenu
   statique déjà présent dans le HTML si le fetch échoue.
   ============================================================================ */
(function () {
  const TENDANCES_SOURCE = "/index.html";
  const MAX_ITEMS = 4;

  function toAbsolutePath(rawPath, baseUrl) {
    if (!rawPath) return null;
    const cleaned = rawPath.replace(/\\/g, "/"); // corrige les chemins avec antislash
    try {
      return new URL(cleaned, baseUrl).pathname;
    } catch (err) {
      return null;
    }
  }

  function extractCandidate(node, baseUrl) {
    const link = node.querySelector("a.btn") || node.querySelector("a");
    const href = link ? toAbsolutePath(link.getAttribute("href"), baseUrl) : null;
    if (!href) return null;

    const img = node.querySelector("img");
    const src = img ? toAbsolutePath(img.getAttribute("src"), baseUrl) : null;
    const alt = img ? img.getAttribute("alt") || "" : "";

    const titleEl = node.querySelector("h1, h3");
    const title = titleEl ? titleEl.textContent.trim() : "";
    if (!title) return null;

    return { href, src, alt, title };
  }

  function buildItem({ href, src, alt, title }) {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = href;

    if (src) {
      const img = document.createElement("img");
      img.src = src;
      img.alt = alt || title;
      img.loading = "lazy";
      a.appendChild(img);
    }

    const span = document.createElement("span");
    span.textContent = title;
    a.appendChild(span);

    li.appendChild(a);
    return li;
  }

  async function loadTendances() {
    const container = document.getElementById("tendances-list");
    if (!container) return;

    try {
      const response = await fetch(TENDANCES_SOURCE);
      if (!response.ok) throw new Error("Page d'accueil inaccessible.");

      const html = await response.text();
      const doc = new DOMParser().parseFromString(html, "text/html");
      const baseUrl = new URL(TENDANCES_SOURCE, window.location.origin);

      const sourceNodes = [
        ...doc.querySelectorAll(".hero-duo__panel"),
        ...doc.querySelectorAll("article.featured-card"),
      ];

      const currentPath = window.location.pathname;
      const seen = new Set();
      const candidates = [];

      for (const node of sourceNodes) {
        const candidate = extractCandidate(node, baseUrl);
        if (!candidate) continue;
        if (candidate.href === currentPath) continue; // pas d'auto-recommandation
        if (seen.has(candidate.href)) continue;
        seen.add(candidate.href);
        candidates.push(candidate);
        if (candidates.length >= MAX_ITEMS) break;
      }

      if (candidates.length === 0) return; // on garde le repli statique du HTML

      container.innerHTML = "";
      candidates.forEach((c) => container.appendChild(buildItem(c)));
    } catch (err) {
      console.error("Tendances :", err);
      // le contenu statique déjà présent dans le HTML reste affiché
    }
  }

  document.addEventListener("DOMContentLoaded", loadTendances);
})();