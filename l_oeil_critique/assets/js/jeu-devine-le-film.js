// -------------------------------------
    // JAVASCRIPT DU JEU (L'Œil Critique)
    // -------------------------------------

    const API_KEY = "c733ef0d6713d6a5b282beff57cd6343";
    const BASE_URL = "https://api.themoviedb.org/3";
    const IMG_URL = "https://image.tmdb.org/t/p/w500";
    const MAX_ROUNDS = 10;
    const START_TIME = 15;
    const HINT_PENALTY = 5; // Pénalité de points pour l'indice

    let movies = [];
    let score = 0;
    let currentMovie = null;
    let timeLeft = START_TIME;
    let timer;
    let roundActive = false;
    let currentRound = 0;
    let maxPoints = 10;
    let initialBlur = 15; // Défaut sur Facile
    let hintUsed = false;

    // Éléments du DOM
    const poster = document.getElementById("poster");
    const suggestionsDiv = document.getElementById("suggestions");
    const feedback = document.getElementById("feedback");
    const nextBtn = document.getElementById("nextBtn");
    const scoreDisplay = document.getElementById("score");
    const timerDisplay = document.getElementById("timer");
    const roundCountDisplay = document.getElementById("round-count");
    const hintText = document.getElementById("hint-text");
    const hintBtn = document.getElementById("hintBtn");
    const container = document.getElementById("gameContainer");
    const difficultyOptions = document.getElementById("difficulty-options"); // Le conteneur des boutons radio
    const endGameModal = document.getElementById("endGameModal");
    const finalScoreDisplay = document.getElementById("finalScore");
    const scoreMessage = document.getElementById("scoreMessage");
    const restartBtn = document.getElementById("restartBtn");

    // Événement pour le sélecteur de difficulté (Boutons radio)
    difficultyOptions.addEventListener("change", (e) => {
        if (e.target.type === 'radio') {
            initialBlur = parseInt(e.target.getAttribute('data-blur'));
            if (!roundActive && currentRound === 0) {
                poster.style.filter = `blur(${initialBlur}px)`;
            }
        }
    });

    // Initialiser le blur (prend la valeur par défaut du premier bouton radio "checked")
    const checkedRadio = document.querySelector('#difficulty-options input:checked');
    if (checkedRadio) {
        initialBlur = parseInt(checkedRadio.getAttribute('data-blur'));
    }

    // 1. Fetch Movies (Récupération des films)
    async function fetchMovies() {
        movies = [];
        try {
            // Récupérer plus de films pour avoir plus de choix
            for (let page = 1; movies.length < 200; page++) {
                const res = await fetch(`${BASE_URL}/movie/popular?api_key=${API_KEY}&language=fr-FR&page=${page}`);
                if (!res.ok) throw new Error("Erreur de l'API TMDb");
                const data = await res.json();
                // Filtrer les films sans poster
                const validMovies = data.results.filter(m => m.poster_path && m.overview); // Exiger un overview pour l'indice
                movies = movies.concat(validMovies);
                if (page >= data.total_pages || movies.length >= 200) break;
            }
            movies = movies.slice(0, 200); // Limite de 200 films
            if (movies.length === 0) throw new Error("Aucun film valide récupéré.");
            startGame();
        } catch (error) {
            console.error("Erreur de chargement des films :", error);
            feedback.textContent = "Erreur de chargement des données. Veuillez vérifier la console.";
        }
    }

    // 2. Démarrage du jeu
    function startGame() {
        score = 0;
        currentRound = 0;
        scoreDisplay.innerHTML = `<i class="fas fa-trophy"></i> Score : ${score}`;
        endGameModal.style.display = "none";
        nextMovie();
    }

    // 3. Nouveau film (Manche suivante)
    function nextMovie() {
        if (currentRound >= MAX_ROUNDS) {
            return showEndGameModal();
        }

        clearInterval(timer);
        timeLeft = START_TIME;
        roundActive = true;
        maxPoints = 10;
        currentRound++;
        hintUsed = false;

        // Réinitialisation de l'affichage
        feedback.textContent = "";
        feedback.className = "feedback";
        nextBtn.disabled = true;
        suggestionsDiv.innerHTML = "";
        timerDisplay.innerHTML = `<i class="fas fa-clock"></i> Temps : ${timeLeft}s`;
        roundCountDisplay.innerHTML = `<i class="fas fa-star"></i> Manche : ${currentRound} / ${MAX_ROUNDS}`;

        // Réinitialisation de l'indice
        hintText.textContent = `Indice : Cliquez sur le bouton !`;
        hintText.classList.add("hidden-hint");
        hintBtn.disabled = false;
        hintBtn.textContent = `Indice (-${HINT_PENALTY} pts)`;
        
        // Choisir un film aléatoire et le retirer de la liste des potentiels futurs
        const movieIndex = Math.floor(Math.random() * movies.length);
        currentMovie = movies[movieIndex];
        movies.splice(movieIndex, 1); // Pour ne pas répéter les films dans la partie

        poster.src = IMG_URL + currentMovie.poster_path;
        poster.style.filter = `blur(${initialBlur}px)`;
        poster.style.transform = "scale(1)"; // Réinitialiser l'animation

        generateSuggestions();
        startTimer();
    }

    // 4. Timer et Flou
    function startTimer() {
        clearInterval(timer);
        timer = setInterval(() => {
            if (!roundActive) return;

            timeLeft--;
            timerDisplay.innerHTML = `<i class="fas fa-clock"></i> Temps : ${timeLeft}s`;

            // Diminution progressive du flou, proportionnelle au temps restant
            const blurReduction = initialBlur - (initialBlur * (timeLeft / START_TIME));
            poster.style.filter = `blur(${Math.max(initialBlur - blurReduction, 0)}px)`;

            if (timeLeft <= 0) {
                clearInterval(timer);
                endRound(false, `❌ Le temps est écoulé ! Le film était : ${currentMovie.title}`);
            }
        }, 1000);
    }

    // 5. Utilisation et Affichage de l'indice (Mot clé aléatoire)
    function revealHint() {
        if (!roundActive || hintUsed) return;

        // Pénalité
        score = Math.max(0, score - HINT_PENALTY);
        scoreDisplay.innerHTML = `<i class="fas fa-trophy"></i> Score : ${score}`;
        hintUsed = true;
        hintBtn.disabled = true;
        hintBtn.textContent = "Indice utilisé";
        showFeedback(false, `⚠️ -${HINT_PENALTY} points !`);

        const overview = currentMovie.overview || "Aucune description disponible.";
        const words = overview.replace(/[.,\/#!$%\^&\*;:{}=\-_`~()]/g,"").toLowerCase().split(/\s+/);
        
        // Filtrer les mots très courts (articles, prépositions)
        const meaningfulWords = words.filter(w => w.length > 4);
        
        let hintWord = "Intrigue inconnue";
        if (meaningfulWords.length > 0) {
            // Choisir un mot clé aléatoire parmi les mots significatifs
            hintWord = meaningfulWords[Math.floor(Math.random() * meaningfulWords.length)];
        }
        
        // Afficher l'indice
        hintText.textContent = `Indice : Mot clé : "${hintWord.toUpperCase()}"`;
        hintText.classList.remove("hidden-hint");
    }

    // 6. Vérification de la supposition
    function checkGuess(title) {
        if (!roundActive) return;

        // Désactiver tous les boutons pour cette manche, y compris l'indice
        document.querySelectorAll(".suggestion-buttons button").forEach(b => b.disabled = true);
        hintBtn.disabled = true;

        if (title === currentMovie.title) {
            // Calcul des points basé sur le temps restant et si l'indice a été utilisé
            let pts = Math.max(2, Math.floor(maxPoints * (timeLeft / START_TIME)));
            
            score += pts;
            scoreDisplay.innerHTML = `<i class="fas fa-trophy"></i> Score : ${score}`;
            poster.style.filter = "blur(0)";
            poster.style.transform = "scale(1.05)"; // Petit effet de zoom à la victoire

            endRound(true, `✅ Correct ! ${currentMovie.title} (+${pts} pts)`);
        } else {
            // ... (logique d'affichage des boutons correct/incorrect)
            const buttons = document.querySelectorAll(".suggestion-buttons button");
            buttons.forEach(b => {
                if (b.textContent === title) {
                    b.classList.add("wrong-guess");
                }
                if (b.textContent === currentMovie.title) {
                    b.classList.add("correct-answer");
                }
            });
            endRound(false, `❌ Faux ! C'était : ${currentMovie.title}`);
        }
    }

    // 7. Fin de la manche
    function endRound(correct, text) {
        roundActive = false;
        clearInterval(timer);
        showFeedback(correct, text);
        nextBtn.disabled = false;
        hintBtn.disabled = true;
        if (correct) triggerConfetti();
    }

    // 8. Affichage du Feedback
    function showFeedback(correct, text) {
        feedback.textContent = text;
        feedback.className = "feedback " + (correct ? "correct" : "wrong");
    }

    // 9. Génération des 4 choix de films (Inchanggée)
    function generateSuggestions() {
        let options = [currentMovie.title];
        let availableTitles = movies.map(m => m.title);

        while (options.length < 4) {
            const randomIndex = Math.floor(Math.random() * availableTitles.length);
            let opt = availableTitles[randomIndex];

            if (!options.includes(opt)) {
                options.push(opt);
            }
            availableTitles.splice(randomIndex, 1);
        }

        shuffleArray(options).forEach(opt => {
            const btn = document.createElement("button");
            btn.textContent = opt;
            btn.addEventListener("click", () => checkGuess(opt));
            suggestionsDiv.appendChild(btn);
        });
    }

    // 10. Mélange de tableau (Inchanggée)
    function shuffleArray(arr) {
        for (let i = arr.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [arr[i], arr[j]] = [arr[j], arr[i]];
        }
        return arr;
    }

    // 11. Modal de Fin de Partie (Inchanggée)
    function showEndGameModal() {
        finalScoreDisplay.textContent = score;
        let message = "";
        if (score >= 80) {
            message = "Un vrai critique de cinéma ! 🤩";
        } else if (score >= 50) {
            message = "Très bonne performance ! 👏";
        } else if (score >= 20) {
            message = "Pas mal, continuez ! 👍";
        } else {
            message = "Réessayez pour affûter votre œil ! 😉";
        }
        scoreMessage.textContent = message;
        endGameModal.style.display = "flex";
    }

    // 12. Confettis (Inchanggée)
    function triggerConfetti() {
        for (let i = 0; i < 50; i++) {
            const c = document.createElement("div");
            c.className = "confetti";
            c.style.left = Math.random() * container.offsetWidth + "px";
            c.style.top = -20 + "px";
            c.style.animationDuration = Math.random() * 2 + 1 + "s";
            c.style.animationDelay = Math.random() * 0.5 + "s";
            c.style.setProperty('--rand-x', (Math.random() * 4 - 2).toFixed(2)); // Variable CSS pour dispersion
            c.style.background = `hsl(${Math.random() * 360}, 80%, 60%)`;
            container.appendChild(c);
            setTimeout(() => c.remove(), 3500);
        }
    }

    // Événements
    nextBtn.addEventListener("click", nextMovie);
    restartBtn.addEventListener("click", fetchMovies);
    hintBtn.addEventListener("click", revealHint); // Nouvel événement

    // Initialisation
    fetchMovies();