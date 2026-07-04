document.addEventListener('DOMContentLoaded', async () => {
    const container = document.getElementById('grille-bandes');
    const voirPlusBtn = document.getElementById('voir-plus-btn');
    const searchInput = document.getElementById('trailers-search');
    
    const step = 12; 
    let currentIndex = 0;
    let allCards = [];
    let filteredCards = []; // Liste dynamique (toutes les cartes ou seulement les recherchées)

    if (!container || !voirPlusBtn) return;

    // --- CHARGEMENT INITIAL ---
    try {
        const response = await fetch('bande_annonces_blocs.html');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const html = await response.text();
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;
        
        allCards = Array.from(tempDiv.querySelectorAll('.card-bande'));
        filteredCards = [...allCards]; // Au départ, pas de filtre

        container.innerHTML = ''; 
        showNextBatch();

    } catch (err) {
        container.innerHTML = '<p class="no-results">Erreur de chargement des bandes-annonces.</p>';
        console.error(err);
    }

    // --- FONCTION D'AFFICHAGE ---
    function showNextBatch() {
        const fragment = document.createDocumentFragment();
        const nextBatch = filteredCards.slice(currentIndex, currentIndex + step);
        
        if (nextBatch.length === 0 && currentIndex === 0) {
            container.innerHTML = '<div class="no-results">Aucun film ne correspond à votre recherche.</div>';
            voirPlusBtn.style.display = 'none';
            return;
        }

        nextBatch.forEach(card => {
            // On s'assure que la carte est visible et on peut ajouter une micro-animation CSS ici
            card.style.display = 'block'; 
            fragment.appendChild(card);
        });

        container.appendChild(fragment);
        currentIndex += step;

        // Gestion de la visibilité du bouton
        voirPlusBtn.style.display = (currentIndex >= filteredCards.length) ? 'none' : 'block';
    }

    // --- GESTION DE LA RECHERCHE ---
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase().trim();
            
            // On réinitialise tout pour la recherche
            container.innerHTML = '';
            currentIndex = 0;

            if (term === '') {
                filteredCards = [...allCards];
            } else {
                filteredCards = allCards.filter(card => {
                    const title = card.querySelector('h2').textContent.toLowerCase();
                    return title.includes(term);
                });
            }
            
            showNextBatch();
        });
    }

    // --- CLIC VOIR PLUS ---
    voirPlusBtn.addEventListener('click', showNextBatch);

    // --- CHARGEMENT VIDÉO AU CLIC (DÉLÉGATION D'ÉVÉNEMENT) ---
    container.addEventListener('click', (e) => {
        const card = e.target.closest('.card-bande');
        if (!card) return;

        const videoWrapper = card.querySelector('.video-responsive');
        // On vérifie si une iframe n'est pas déjà présente
        if (!videoWrapper || videoWrapper.querySelector('iframe')) return;

        // On cherche l'ID YouTube (soit dans data-youtube-id, soit on l'extrait de l'iframe src si présente en texte)
        let youtubeId = videoWrapper.getAttribute('data-youtube-id');
        
        // Sécurité : Si ton script Python a mis l'iframe en brut, on la laisse. 
        // Mais si on veut optimiser, on l'active au clic :
        if (!youtubeId) {
            const staticIframe = videoWrapper.querySelector('iframe');
            if (staticIframe) {
                // Si l'iframe est déjà là, on ne fait rien, elle chargera normalement
                return;
            }
        }

        if (youtubeId) {
            const iframe = document.createElement('iframe');
            iframe.setAttribute('src', `https://www.youtube.com/embed/${youtubeId}?autoplay=1`);
            iframe.setAttribute('frameborder', '0');
            iframe.setAttribute('allow', 'autoplay; encrypted-media; picture-in-picture');
            iframe.setAttribute('allowfullscreen', '');
            
            videoWrapper.innerHTML = ''; // On enlève le placeholder (image)
            videoWrapper.appendChild(iframe);
        }
    });
});