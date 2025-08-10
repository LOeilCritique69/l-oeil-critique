// js/loadTrailers.js
document.addEventListener('DOMContentLoaded', async () => {
    const container = document.getElementById('grille-bandes');
    const voirPlusBtn = document.getElementById('voir-plus-btn');
    const initialVisibleCount = 9; // Nombre de bandes-annonces visibles par défaut

    if (!container || !voirPlusBtn) {
        console.error('Éléments HTML requis introuvables : #grille-bandes ou #voir-plus-btn');
        return;
    }

    try {
        const response = await fetch('bande_annonces_blocs.html');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const html = await response.text();

        // Création d'un conteneur temporaire pour parser le HTML chargé
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;

        const allCards = Array.from(tempDiv.querySelectorAll('.card-bande'));
        container.innerHTML = ''; // Vide le container avant d'insérer les cartes

        // Ajout des cartes dans le container avec gestion du masquage
        allCards.forEach((card, index) => {
            if (index >= initialVisibleCount) {
                card.classList.add('hidden-card');
            }
            container.appendChild(card);
        });

        // Affiche ou masque le bouton "Voir plus" selon le nombre de cartes cachées
        voirPlusBtn.style.display = allCards.length > initialVisibleCount ? 'block' : 'none';

        // Au clic, révèle toutes les cartes cachées et masque le bouton
        voirPlusBtn.addEventListener('click', () => {
            const hiddenCards = container.querySelectorAll('.card-bande.hidden-card');
            hiddenCards.forEach(card => card.classList.remove('hidden-card'));
            voirPlusBtn.style.display = 'none';
        });

        // Gère le lazy load des vidéos YouTube au clic sur les placeholders
        container.addEventListener('click', (event) => {
            const placeholder = event.target.closest('.youtube-placeholder');
            if (!placeholder) return;

            // Sécurité : éviter de remplacer plusieurs fois
            if (placeholder.tagName.toLowerCase() === 'iframe') return;

            const iframe = document.createElement('iframe');
            iframe.setAttribute('src', placeholder.dataset.src);
            iframe.setAttribute('width', '1920');
            iframe.setAttribute('height', '750');
            iframe.setAttribute('frameborder', '0');
            iframe.setAttribute('allowfullscreen', '');
            iframe.setAttribute('allow', 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; autoplay');
            iframe.setAttribute('title', placeholder.getAttribute('aria-label'));
            iframe.setAttribute('loading', 'lazy');

            placeholder.replaceWith(iframe);
        });

    } catch (err) {
        container.innerHTML = '<p>Impossible de charger les bandes-annonces.</p>';
        console.error('Erreur chargement bandes annonces:', err);
    }
});