// -------------------------------------
// JAVASCRIPT DU JEU (L'Œil Critique) - V3.0 (AMÉLIORÉ)
// -------------------------------------

const API_KEY = "c733ef0d6713d6a5b282beff57cd6343";
const BASE_URL = "https://api.themoviedb.org/3";
const IMG_URL = "https://image.tmdb.org/t/p/w500";
const MAX_ROUNDS = 10;
const START_TIME = 15;
const HINT_PENALTY_1 = 5; // Pénalité de points pour l'indice 1 (Genre)
const HINT_PENALTY_2 = 15; // NOUVEAU: Pénalité pour l'indice 2 (Synopsis)
const COMBO_BONUS = 5; // NOUVEAU: Points bonus par combo

// Genres TMDb
const GENRES = {
    28: "Action", 12: "Aventure", 16: "Animation", 35: "Comédie", 80: "Crime",
    99: "Documentaire", 18: "Drame", 10751: "Familial", 14: "Fantastique",
    36: "Histoire", 27: "Horreur", 10402: "Musique", 9648: "Mystère",
    10749: "Romance", 878: "Science-Fiction", 10770: "Téléfilm", 53: "Thriller",
    10752: "Guerre", 37: "Western"
};

// --- Variables de Jeu Globales ---
let moviesByGenre = {}; 
let score = 0;
let currentMovie = null;
let timeLeft = START_TIME;
let timer;
let roundActive = false;
let currentRound = 0;
let initialBlur = 15; 
let hintLevel = 0; // NOUVEAU: 0: aucun, 1: genre, 2: synopsis
let currentPenalty = 0; // NOUVEAU: Total des pénalités pour la manche
let currentCombo = 0; // NOUVEAU: Compteur de victoires consécutives
let difficultyLevel = 'facile'; 

// --- Éléments du DOM ---
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
const endGameModal = document.getElementById("endGameModal");
const finalScoreDisplay = document.getElementById("finalScore");
const scoreMessage = document.getElementById("scoreMessage");
const restartBtn = document.getElementById("restartBtn");
const appContainer = document.querySelector('.movie-game-app');
const introModal = document.getElementById('introModal');
const startGameBtn = document.getElementById('startGameBtn');
const difficultyOptionsIntro = document.getElementById('difficulty-options-intro');
const scoreDropDisplay = document.getElementById('scoreDrop'); 
// const closeIntroBtn = document.getElementById('closeIntroBtn'); // N'est pas dans le HTML fourni, on l'ignore


// ===================================================================
// 1. GESTION DU DÉMARRAGE ET DE L'API
// ===================================================================

async function initApp() {
    // Crée l'élément pour l'affichage de la baisse de score s'il n'existe pas
    if (!document.getElementById('scoreDrop')) {
        const dropDiv = document.createElement('div');
        dropDiv.id = 'scoreDrop';
        dropDiv.className = 'score-drop';
        const scoreInfo = document.querySelector('.score-timer-info');
        if (scoreInfo) {
            scoreInfo.appendChild(dropDiv);
        }
    }
    
    // Crée l'élément pour le classement s'il n'existe pas
    let leaderboardDiv = document.getElementById('leaderboard-display');
    if (!leaderboardDiv) {
        leaderboardDiv = document.createElement('div');
        leaderboardDiv.id = 'leaderboard-display';
        const modalContent = endGameModal.querySelector('.modal-content');
        if (modalContent) {
            modalContent.insertBefore(leaderboardDiv, restartBtn);
        }
    }

    await fetchMovies();
    loadLeaderboard();
}

/**
 * Récupère ~100 films populaires par genre ET quelques nouveautés. (MODIFIÉE)
 */
async function fetchMovies() {
    console.log("Chargement des films par genre et des nouveautés...");
    moviesByGenre = {};
    const genreIds = Object.keys(GENRES);

    try {
        // 1. Récupération des films populaires par genre (comme avant)
        const promises = genreIds.map(async (genreId) => {
            const url = `${BASE_URL}/discover/movie?api_key=${API_KEY}&language=fr-FR&sort_by=popularity.desc&with_genres=${genreId}&page=1`;
            const res = await fetch(url);
            if (!res.ok) throw new Error(`Erreur de l'API pour le genre ${GENRES[genreId]}`);
            
            const data = await res.json();
            let validMovies = data.results.filter(m => m.poster_path && m.overview);

            // Tente de récupérer plus de films (Page 2)
            if (validMovies.length < 100 && data.total_pages > 1) {
                const urlPage2 = `${BASE_URL}/discover/movie?api_key=${API_KEY}&language=fr-FR&sort_by=popularity.desc&with_genres=${genreId}&page=2`;
                const res2 = await fetch(urlPage2);
                if (res2.ok) {
                    const data2 = await res2.json();
                    validMovies.push(...data2.results.filter(m => m.poster_path && m.overview));
                }
            }
            moviesByGenre[genreId] = validMovies.slice(0, 100);
        });

        await Promise.all(promises);
        
        // 2. NOUVEAU: Ajout des films "Now Playing" (actuellement à l'affiche) dans un genre spécial (ID 0)
        const nowPlayingUrl = `${BASE_URL}/movie/now_playing?api_key=${API_KEY}&language=fr-FR&page=1`;
        const resNowPlaying = await fetch(nowPlayingUrl);
        if (resNowPlaying.ok) {
            const dataNowPlaying = await resNowPlaying.json();
            const nowPlayingMovies = dataNowPlaying.results.filter(m => m.poster_path && m.overview).slice(0, 50); // 50 films
            // Ajout des films récents à tous les films disponibles
            // Nous n'utilisons pas un genre 0, mais nous les mélangeons dans la liste globale
            Object.keys(moviesByGenre).forEach(genreId => {
                 if (moviesByGenre[genreId] && moviesByGenre[genreId].length > 0) {
                     // Ajoute une petite quantité de films récents pour varier
                     const filmsToAdd = nowPlayingMovies.filter(m => m.genre_ids.includes(parseInt(genreId))).slice(0, 5); 
                     moviesByGenre[genreId].push(...filmsToAdd);
                     shuffleArray(moviesByGenre[genreId]); // Mélange pour ne pas avoir les récents en fin de liste
                 }
            });
        }


        console.log("Films chargés. Nombre total de films (approximatif) :", Object.values(moviesByGenre).flat().length);

    } catch (error) {
        console.error("Erreur de chargement des films :", error);
        feedback.textContent = "Erreur de chargement des données. Veuillez vérifier la console.";
    }
}

/**
 * Fonction pour fermer le modal d'introduction.
 */
function closeIntroScreen() {
    introModal.style.display = 'none';
    appContainer.classList.remove('modal-open');
}


/**
 * Gère l'affichage du modal d'introduction et la sélection de difficulté.
 */
function showIntroScreen() {
    introModal.style.display = 'flex';
    appContainer.classList.add('modal-open');

    startGameBtn.onclick = () => { 
        const selectedDifficultyInput = difficultyOptionsIntro.querySelector('input[name="difficulty-intro"]:checked');
        
        if (selectedDifficultyInput) {
            initialBlur = parseInt(selectedDifficultyInput.dataset.blur);
            difficultyLevel = selectedDifficultyInput.value; 

            // Met à jour l'affichage de la difficulté permanente
            document.getElementById(`diff-${difficultyLevel}`).checked = true;

            closeIntroScreen(); // Utilise la fonction de fermeture
            
            startGame(); 
        } else {
            alert("Veuillez choisir une difficulté pour commencer.");
        }
    };

    // NOUVEAU: Événement pour le bouton de fermeture (si le bouton existe)
    /* if (closeIntroBtn) {
        closeIntroBtn.onclick = closeIntroScreen;
    } */
}


// ===================================================================
// 2. LOGIQUE DU JEU PRINCIPAL
// ===================================================================

function startGame() {
    score = 0;
    currentRound = 0;
    currentCombo = 0; // Réinitialisation
    scoreDisplay.innerHTML = `<i class="fas fa-trophy"></i> Score : ${score}`;
    endGameModal.style.display = "none";
    nextMovie();
}

/**
 * Gère le redémarrage du jeu après la fin de partie.
 */
function restartGame() {
    // 1. Masque le modal de fin de partie
    endGameModal.style.display = "none";
    
    // 2. Affiche l'écran d'introduction pour permettre de choisir la difficulté
    showIntroScreen(); 
}


/**
 * Prépare et lance la manche suivante. Gère l'augmentation de difficulté après chaque manche.
 */
function nextMovie() {
    if (currentRound >= MAX_ROUNDS) {
        return showEndGameModal();
    }

    clearInterval(timer);
    timeLeft = START_TIME;
    roundActive = true;
    hintLevel = 0; // Réinitialisation de l'indice
    currentPenalty = 0; // Réinitialisation de la pénalité totale
    currentRound++;
    
    // Augmentation dynamique de la difficulté (flou) après chaque manche
    if (currentRound > 1) { 
        let baseIncrement = 2; 
        if (difficultyLevel === 'facile') baseIncrement = 1;
        else if (difficultyLevel === 'difficile') baseIncrement = 3;
        else if (difficultyLevel === 'expert') baseIncrement = 4;

        initialBlur = Math.min(35, initialBlur + baseIncrement); // Max blur à 35
    }
    
    // Réinitialisation de l'affichage
    feedback.textContent = "";
    feedback.className = "feedback";
    nextBtn.disabled = true;
    suggestionsDiv.innerHTML = "";
    timerDisplay.innerHTML = `<i class="fas fa-clock"></i> Temps : ${timeLeft}s`;
    roundCountDisplay.innerHTML = `<i class="fas fa-star"></i> Manche : ${currentRound} / ${MAX_ROUNDS}`;

    // Réinitialisation de l'indice
    hintText.textContent = `Indice : Genre du film`;
    hintText.classList.add("hidden-hint");
    hintBtn.disabled = false;
    hintBtn.textContent = `Indice (-${HINT_PENALTY_1} pts)`;
    
    // Affichage du combo
    if (currentCombo > 0) {
        roundCountDisplay.innerHTML += `<span style="margin-left:15px;color:#ffc456;">🔥 Combo x${currentCombo}</span>`;
    }


    // Choix du film
    const availableGenres = Object.keys(moviesByGenre).filter(id => moviesByGenre[id].length > 0);
    if (availableGenres.length === 0) {
        feedback.textContent = "Erreur: Pas assez de films disponibles.";
        return;
    }

    currentGenreId = availableGenres[Math.floor(Math.random() * availableGenres.length)];
    const genreMovies = moviesByGenre[currentGenreId];

    const movieIndex = Math.floor(Math.random() * genreMovies.length);
    currentMovie = genreMovies[movieIndex];
    genreMovies.splice(movieIndex, 1); 

    poster.src = IMG_URL + currentMovie.poster_path;
    poster.style.filter = `blur(${initialBlur}px)`;
    poster.style.transform = "scale(1)";

    generateSuggestions();
    startTimer();
}

/**
 * Gère la diminution progressive du flou et le temps.
 */
function startTimer() {
    clearInterval(timer);
    timer = setInterval(() => {
        if (!roundActive) return;

        timeLeft--;
        timerDisplay.innerHTML = `<i class="fas fa-clock"></i> Temps : ${timeLeft}s`;

        // Réduction progressive du flou (se réduit à 0 à la fin du temps)
        const currentBlur = initialBlur * (timeLeft / START_TIME);
        poster.style.filter = `blur(${Math.max(currentBlur, 0)}px)`;

        if (timeLeft <= 0) {
            clearInterval(timer);
            endRound(false, `❌ Le temps est écoulé ! Le film était : ${currentMovie.title}`);
            currentCombo = 0; // Réinitialisation du combo
        }
    }, 1000);
}

/**
 * Révèle l'indice (Genre puis Synopsis) et applique la pénalité. (MODIFIÉE)
 */
function revealHint() {
    if (!roundActive || hintLevel >= 2) return;

    hintLevel++;
    let penalty = 0;
    let hintTextContent = '';
    let feedbackText = '';
    
    if (hintLevel === 1) {
        penalty = HINT_PENALTY_1;
        const genreName = GENRES[currentGenreId] || "Inconnu";
        hintTextContent = `Indice 1/2 : Le genre est "**${genreName.toUpperCase()}**"`;
        hintBtn.textContent = `Indice 2 (-${HINT_PENALTY_2} pts)`;
        feedbackText = `⚠️ -${HINT_PENALTY_1} points pour l'Indice 1 !`;
    
    } else if (hintLevel === 2) {
        penalty = HINT_PENALTY_2;
        // Coupe le synopsis au premier point pour un indice court
        const shortSynopsis = currentMovie.overview.split('. ')[0] + (currentMovie.overview.includes('.') ? '.' : ''); 
        hintTextContent = `Indice 2/2 : **Synopsis** : ${shortSynopsis}`;
        hintBtn.disabled = true;
        hintBtn.textContent = "Tous les indices sont utilisés";
        feedbackText = `⚠️ -${HINT_PENALTY_2} points pour l'Indice 2 !`;
    }
    
    currentPenalty += penalty;
    score = Math.max(0, score - penalty);
    showScoreDrop(penalty); 
    scoreDisplay.innerHTML = `<i class="fas fa-trophy"></i> Score : ${score}`;
    
    hintText.innerHTML = hintTextContent;
    hintText.classList.remove("hidden-hint");
    showFeedback(false, feedbackText);
}

/**
 * Vérification de la supposition et fin de manche. (MODIFIÉE)
 */
function checkGuess(title) {
    if (!roundActive) return;

    document.querySelectorAll(".suggestion-buttons button").forEach(b => b.disabled = true);
    hintBtn.disabled = true;

    if (title === currentMovie.title) {
        let ptsBase = Math.max(5, Math.floor(20 * (timeLeft / START_TIME))); 
        
        // 1. Pénalité appliquée pour les indices
        ptsBase = Math.max(5, ptsBase - currentPenalty); 
        if (currentPenalty > 0) showScoreDrop(currentPenalty, true); 
        
        // 2. NOUVEAU: Ajout du bonus de combo
        currentCombo++;
        const comboPts = currentCombo * COMBO_BONUS;
        
        const totalPts = ptsBase + comboPts;
        score += totalPts;
        
        scoreDisplay.innerHTML = `<i class="fas fa-trophy"></i> Score : ${score}`;
        poster.style.filter = "blur(0)";
        poster.style.transform = "scale(1.05)"; 
        
        let feedbackMsg = `✅ Correct ! ${currentMovie.title} (+${ptsBase} pts)`;
        if (currentCombo > 1) {
            feedbackMsg += ` +🔥 ${comboPts} pts de COMBO x${currentCombo} !`;
        }
        
        endRound(true, feedbackMsg);
    } else {
        const buttons = document.querySelectorAll(".suggestion-buttons button");
        buttons.forEach(b => {
            if (b.textContent === title) b.classList.add("wrong-guess");
            if (b.textContent === currentMovie.title) b.classList.add("correct-answer");
        });
        endRound(false, `❌ Faux ! C'était : ${currentMovie.title}`);
        currentCombo = 0; // Réinitialisation du combo
    }
}

/**
 * Fin de la manche (arrêt timer, affichage feedback).
 */
function endRound(correct, text) {
    roundActive = false;
    clearInterval(timer);
    showFeedback(correct, text);
    nextBtn.disabled = false;
    hintBtn.disabled = true;
    if (correct) triggerConfetti();
}

/**
 * Génère les 4 choix de films (dont le bon).
 */
function generateSuggestions() {
    let options = [currentMovie.title];
    const allMovies = Object.values(moviesByGenre).flat();
    
    // 1. Choisir d'abord des titres dans le même genre pour plus de difficulté
    let availableTitles = moviesByGenre[currentGenreId]
        ? moviesByGenre[currentGenreId].map(m => m.title).filter(title => title !== currentMovie.title)
        : [];
    
    // 2. Si pas assez de titres du même genre, piocher dans tous les films
    if (availableTitles.length < 3) {
        availableTitles = [...new Set(allMovies.map(m => m.title).filter(title => title !== currentMovie.title))];
    }


    while (options.length < 4 && availableTitles.length > 0) {
        const randomIndex = Math.floor(Math.random() * availableTitles.length);
        let opt = availableTitles[randomIndex];

        if (!options.includes(opt)) {
            options.push(opt);
        }
        availableTitles.splice(randomIndex, 1);
    }
    
    // Assurer qu'il y a toujours 4 options
    if (options.length < 4) {
        while(options.length < 4) {
            options.push(`Film inconnu ${options.length + 1}`);
        }
    }


    shuffleArray(options).forEach(opt => {
        const btn = document.createElement("button");
        btn.textContent = opt;
        btn.addEventListener("click", () => checkGuess(opt));
        suggestionsDiv.appendChild(btn);
    });
}

/**
 * Affichage du Feedback.
 */
function showFeedback(correct, text) {
    feedback.innerHTML = text; // Utilisation de innerHTML pour le formatage du combo
    feedback.className = "feedback " + (correct ? "correct" : "wrong");
}

/**
 * Modal de Fin de Partie (avec sauvegarde du score).
 */
function showEndGameModal() {
    clearInterval(timer);
    
    // Sauvegarde et mise à jour du classement
    saveScore({
        score: score,
        date: new Date().toLocaleDateString('fr-FR'),
        time: new Date().toLocaleTimeString('fr-FR'),
        difficulty: difficultyLevel.toUpperCase()
    });
    loadLeaderboard();

    // Affichage du modal
    finalScoreDisplay.textContent = score;
    let message = "";
    if (score >= 150) {
        message = "Maître Critique ! Un score ÉNORME ! 🏆";
    } else if (score >= 100) {
        message = "Expert de la pellicule ! Bien joué ! 🎬";
    } else if (score >= 50) {
        message = "Très bonne performance ! 👏";
    } else {
        message = "Réessayez pour affûter votre œil ! 😉";
    }
    scoreMessage.textContent = message;
    endGameModal.style.display = "flex";
}


// -------------------------------------
// 3. FONCTIONS UTILITAIRES ET AFFICHAGE
// -------------------------------------

/**
 * Mélange de tableau.
 */
function shuffleArray(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
}

/**
 * Affiche la perte de points de manière visuelle.
 */
function showScoreDrop(amount, isPostGuess = false) {
    const scoreDrop = document.getElementById('scoreDrop');
    if (!scoreDrop) return;
    
    scoreDrop.textContent = `-${amount}`;
    scoreDrop.className = 'score-drop active';

    if (isPostGuess) {
        scoreDrop.style.color = 'orange'; // Pénalité après guess
    } else {
        scoreDrop.style.color = '#bf616a'; // Pénalité au clic sur Indice
    }

    setTimeout(() => {
        scoreDrop.className = 'score-drop'; 
    }, 1500);
}

/**
 * Confettis (Inchanggée).
 */
function triggerConfetti() {
    for (let i = 0; i < 50; i++) {
        const c = document.createElement("div");
        c.className = "confetti";
        c.style.left = Math.random() * container.offsetWidth + "px";
        c.style.top = -20 + "px";
        c.style.animationDuration = Math.random() * 2 + 1 + "s";
        c.style.animationDelay = Math.random() * 0.5 + "s";
        c.style.setProperty('--rand-x', (Math.random() * 4 - 2).toFixed(2));
        c.style.background = `hsl(${Math.random() * 360}, 80%, 60%)`;
        container.appendChild(c);
        setTimeout(() => c.remove(), 3500);
    }
}


// -------------------------------------
// 4. CLASSEMENT LOCAL (LocalStorage)
// -------------------------------------

const STORAGE_KEY = 'movieGuesserLeaderboard';
const MAX_SCORES = 5;

/**
 * Charge le classement depuis le stockage local.
 */
function getLeaderboard() {
    const data = localStorage.getItem(STORAGE_KEY);
    return data ? JSON.parse(data) : [];
}

/**
 * Ajoute le score actuel au classement et le sauvegarde.
 */
function saveScore(newScore) {
    let leaderboard = getLeaderboard();
    
    // Ajout et tri (du plus grand au plus petit)
    leaderboard.push(newScore);
    leaderboard.sort((a, b) => b.score - a.score);
    
    // Ne garder que les 5 meilleurs scores
    leaderboard = leaderboard.slice(0, MAX_SCORES);
    
    localStorage.setItem(STORAGE_KEY, JSON.stringify(leaderboard));
}

/**
 * Affiche le classement dans le modal de fin de partie.
 */
function loadLeaderboard() {
    const leaderboard = getLeaderboard();
    let html = '<h3>Meilleurs Scores (Local)</h3>';
    
    if (leaderboard.length === 0) {
        html += '<p>Pas encore de scores enregistrés.</p>';
    } else {
        html += '<ol class="leaderboard-list">';
        leaderboard.forEach((item, index) => {
            // Utilisation de toLowerCase() pour la classe CSS
            const difficultyClass = item.difficulty.toLowerCase(); 
            html += `
                <li class="score-item rank-${index + 1}">
                    <span>${index + 1}.</span>
                    <strong>${item.score} pts</strong>
                    <span class="difficulty-tag difficulty-${difficultyClass}">${item.difficulty}</span>
                    <small>(${item.date})</small>
                </li>
            `;
        });
        html += '</ol>';
    }

    const leaderboardDiv = document.getElementById('leaderboard-display');
    if (leaderboardDiv) {
        leaderboardDiv.innerHTML = html;
    }
}


// ===================================================================
// DÉMARRAGE
// ===================================================================

// Événements
nextBtn.addEventListener("click", nextMovie);
restartBtn.addEventListener("click", restartGame); 
hintBtn.addEventListener("click", revealHint); 

// Lancement de l'application
document.addEventListener('DOMContentLoaded', () => {
    // Initialisation des données et des éléments DOM
    initApp().then(() => {
        // Une fois que tout est chargé (films), on affiche l'écran d'introduction
        showIntroScreen(); 
    });
});