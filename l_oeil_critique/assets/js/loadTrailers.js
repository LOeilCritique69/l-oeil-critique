document.addEventListener('DOMContentLoaded', async () => {
    const container = document.getElementById('grille-bandes');
    const voirPlusBtn = document.getElementById('voir-plus-btn');
    const step = 12; // On affiche 10 par 10
    let currentIndex = 0;
    let allCards = [];

    if (!container || !voirPlusBtn) return;

    try {
        const response = await fetch('bande_annonces_blocs.html');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const html = await response.text();
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;
        allCards = Array.from(tempDiv.querySelectorAll('.card-bande'));

        container.innerHTML = ''; 

        // Fonction pour afficher le prochain lot de 10
        const showNextBatch = () => {
            const nextBatch = allCards.slice(currentIndex, currentIndex + step);
            
            nextBatch.forEach(card => {
                card.classList.add('revealed'); // Animation d'apparition
                container.appendChild(card);
            });

            currentIndex += step;

            // Cache le bouton s'il n'y a plus rien à afficher
            if (currentIndex >= allCards.length) {
                voirPlusBtn.style.display = 'none';
            } else {
                voirPlusBtn.style.display = 'block';
            }
        };

        // Premier chargement
        showNextBatch();

        // Clic sur Voir Plus
        voirPlusBtn.addEventListener('click', showNextBatch);

        // --- GESTION DU CHARGEMENT DES VIDÉOS AU CLIC ---
        container.addEventListener('click', (e) => {
            const card = e.target.closest('.card-bande');
            if (!card) return;

            // On cherche le conteneur vidéo (qui contient l'image/placeholder)
            const videoWrapper = card.querySelector('.video-responsive');
            const placeholder = videoWrapper.querySelector('img, .play-button'); // l'élément cliqué

            if (placeholder && videoWrapper.dataset.youtubeId) {
                const youtubeId = videoWrapper.dataset.youtubeId;
                
                // On crée l'iframe SEULEMENT maintenant
                const iframe = document.createElement('iframe');
                iframe.setAttribute('src', `https://www.youtube.com/embed/${youtubeId}?autoplay=1`);
                iframe.setAttribute('frameborder', '0');
                iframe.setAttribute('allow', 'autoplay; encrypted-media; picture-in-picture');
                iframe.setAttribute('allowfullscreen', '');
                
                // On vide le wrapper et on met l'iframe
                videoWrapper.innerHTML = '';
                videoWrapper.appendChild(iframe);
            }
        });

    } catch (err) {
        container.innerHTML = '<p>Erreur de chargement.</p>';
        console.error(err);
    }
});