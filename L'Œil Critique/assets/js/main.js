document.addEventListener('DOMContentLoaded', () => {
    const burgerMenu = document.querySelector('.burger-menu');
    const mainNav = document.querySelector('.main-nav');

    if (burgerMenu && mainNav) {
        burgerMenu.addEventListener('click', () => {
            mainNav.classList.toggle('open');
            burgerMenu.classList.toggle('open'); // Ajoute/enlève la classe pour l'animation du burger
            const isExpanded = burgerMenu.getAttribute('aria-expanded') === 'true';
            burgerMenu.setAttribute('aria-expanded', !isExpanded);
        });
    } else {
        console.error('Burger menu or main navigation not found.');
    }
});