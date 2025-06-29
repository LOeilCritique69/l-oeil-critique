// js/loadTrailers.js
document.addEventListener('DOMContentLoaded', async () => {
    const container = document.getElementById('grille-bandes');
    const voirPlusBtn = document.getElementById('voir-plus-btn');

    try {
        const response = await fetch('bande_annonces_blocs.html');
        const html = await response.text();
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;

        const allCards = Array.from(tempDiv.querySelectorAll('.card-bande'));

        // Affiche seulement les 6 premières par défaut
        const initialCount = 6;
        allCards.forEach((card, index) => {
            if (index < initialCount) {
                container.appendChild(card);
            } else {
                card.classList.add('hidden-card');
                container.appendChild(card);
            }
        });

        // Gestion du bouton "Voir plus"
        voirPlusBtn.style.display = allCards.length > initialCount ? 'block' : 'none';
        voirPlusBtn.addEventListener('click', () => {
            const hiddenCards = container.querySelectorAll('.card-bande.hidden-card');
            hiddenCards.forEach(card => card.classList.remove('hidden-card'));
            voirPlusBtn.style.display = 'none';
        });

    } catch (err) {
        container.innerHTML = '<p>Impossible de charger les bandes-annonces.</p>';
        console.error(err);
    }
});
