document.addEventListener('DOMContentLoaded', () => {
    const sliderContainer = document.querySelector('.slider-container');
    if (!sliderContainer) {
        console.error('Slider container not found!');
        return;
    }

    const items = document.querySelectorAll('.slider-item');
    const prevBtn = document.querySelector('.slider-prev');
    const nextBtn = document.querySelector('.slider-next');
    const dotsContainer = document.querySelector('.slider-dots');

    if (!items.length || !prevBtn || !nextBtn || !dotsContainer) {
        console.error('Missing slider elements (items, buttons, or dots)');
        return;
    }

    let currentIndex = 0;
    const totalItems = items.length;
    let autoSlideInterval; // Variable pour l'intervalle de défilement automatique

    function createDots() {
        dotsContainer.innerHTML = ''; // Nettoie les points existants
        for (let i = 0; i < totalItems; i++) {
            const dot = document.createElement('span');
            dot.classList.add('dot');
            dot.dataset.index = i;
            dot.addEventListener('click', () => showSlide(i));
            dotsContainer.appendChild(dot);
        }
    }

    function updateDots() {
        const dots = document.querySelectorAll('.dot');
        dots.forEach((dot, i) => {
            dot.classList.toggle('active', i === currentIndex);
        });
    }

    function showSlide(index) {
        if (index >= totalItems) {
            currentIndex = 0;
        } else if (index < 0) {
            currentIndex = totalItems - 1;
        } else {
            currentIndex = index;
        }

        // Applique la classe 'active' seulement à l'élément courant
        items.forEach((item, i) => {
            if (i === currentIndex) {
                item.classList.add('active');
                item.style.display = 'flex'; // S'assure qu'il est visible en flex
            } else {
                item.classList.remove('active');
                item.style.display = 'none'; // S'assure qu'il est caché
            }
        });
        updateDots();
    }

    function nextSlide() {
        showSlide(currentIndex + 1);
    }

    function prevSlide() {
        showSlide(currentIndex - 1);
    }

    function startAutoSlide() {
        // Empêche de créer plusieurs intervalles si déjà en cours
        if (autoSlideInterval) clearInterval(autoSlideInterval);
        autoSlideInterval = setInterval(nextSlide, 5000); // Change de slide toutes les 5 secondes
    }

    function stopAutoSlide() {
        clearInterval(autoSlideInterval);
    }

    // Événements des boutons
    prevBtn.addEventListener('click', () => {
        stopAutoSlide(); // Arrête le défilement auto lors d'une interaction manuelle
        prevSlide();
        startAutoSlide(); // Redémarre après un court délai
    });

    nextBtn.addEventListener('click', () => {
        stopAutoSlide(); // Arrête le défilement auto lors d'une interaction manuelle
        nextSlide();
        startAutoSlide(); // Redémarre après un court délai
    });

    // Initialisation
    createDots();
    showSlide(currentIndex);
    startAutoSlide(); // Commence le défilement automatique
});