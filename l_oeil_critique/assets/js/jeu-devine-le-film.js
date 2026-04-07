// ============================================================
// CONFIG
// ============================================================
const API_KEY = 'c733ef0d6713d6a5b282beff57cd6343';
const BASE = 'https://api.themoviedb.org/3';
const IMG = 'https://image.tmdb.org/t/p/w500';

const MAX_ROUNDS = 10;
const START_TIME = 20;

const GENRES = {
  28:'Action',12:'Aventure',16:'Animation',35:'Comédie',80:'Crime',
  99:'Documentaire',18:'Drame',10751:'Familial',14:'Fantastique',
  36:'Histoire',27:'Horreur',10402:'Musique',9648:'Mystère',
  10749:'Romance',878:'Science-Fiction',53:'Thriller',10752:'Guerre',37:'Western'
};

const DIFFICULTIES = {
  facile:  { blur:14, lives:3, multiplier:1,   label:'Facile' },
  normal:  { blur:22, lives:3, multiplier:1.2, label:'Normal' },
  difficile:{ blur:28, lives:2, multiplier:1.5, label:'Difficile' },
  expert:  { blur:36, lives:1, multiplier:2,   label:'Expert' }
};

// ============================================================
// STATE
// ============================================================
let allMovies = [];
let usedIds = new Set();
let score = 0;
let lives = 3;
let combo = 0;
let round = 0;
let timeLeft = START_TIME;
let timer = null;
let roundActive = false;
let currentMovie = null;
let currentGenre = '';
let hintsUsed = [];
let penaltyAcc = 0;
let diff = 'facile';
let initialBlur = 14;
let multiplier = 1;
let inputMode = 'text'; // 'text' or 'choice'
let acItems = [];
let acIndex = -1;
let loadedCount = 0;
let totalToLoad = 0;

// ============================================================
// DOM
// ============================================================
const $ = id => document.getElementById(id);
const posterImg = $('posterImg');
const hintContent = $('hintContent');
const feedbackLine = $('feedbackLine');
const timerBar = $('timerBar');
const timerVal = $('timerVal');
const blurFill = $('blurFill');
const scoreVal = $('scoreVal');
const livesDisplay = $('livesDisplay');
const roundBadge = $('roundBadge');
const comboBadge = $('comboBadge');
const comboVal = $('comboVal');
const movieInput = $('movieInput');
const acList = $('acList');
const nextBtn = $('nextBtn');
const suggestionsGrid = $('suggestionsGrid');
const streakBanner = $('streakBanner');

// ============================================================
// LOADING
// ============================================================
async function loadMovies() {
  const genreIds = Object.keys(GENRES);
  const pages = 8; // 8 pages × 20 films × 18 genres ≈ 2880 films
  totalToLoad = genreIds.length * pages;
  loadedCount = 0;

  $('loadingBox').style.display = 'block';
  $('startBtn').disabled = true;
  $('startBtn').style.opacity = '0.4';

  const seen = new Set();
  const results = [];

  const tasks = [];
  for (const gId of genreIds) {
    for (let p = 1; p <= pages; p++) {
      tasks.push({ gId, p });
    }
  }

  // Fetch in parallel batches of 20
  const BATCH = 20;
  for (let i = 0; i < tasks.length; i += BATCH) {
    const batch = tasks.slice(i, i + BATCH);
    await Promise.all(batch.map(async ({ gId, p }) => {
      try {
        const url = `${BASE}/discover/movie?api_key=${API_KEY}&language=fr-FR&sort_by=popularity.desc&with_genres=${gId}&page=${p}&vote_count.gte=50`;
        const r = await fetch(url);
        if (r.ok) {
          const d = await r.json();
          for (const m of d.results) {
            if (m.poster_path && m.overview && m.title && !seen.has(m.id)) {
              seen.add(m.id);
              results.push({ ...m, genre_main: gId });
            }
          }
        }
      } catch {}
      loadedCount++;
      updateLoadBar();
    }));
  }

  // Add trending
  try {
    const tr = await fetch(`${BASE}/trending/movie/week?api_key=${API_KEY}&language=fr-FR`);
    if (tr.ok) {
      const td = await tr.json();
      for (const m of td.results) {
        if (m.poster_path && m.overview && !seen.has(m.id)) {
          seen.add(m.id);
          results.push({ ...m, genre_main: m.genre_ids?.[0] || 28 });
        }
      }
    }
  } catch {}

  allMovies = results;
  console.log(`✅ ${allMovies.length} films chargés`);

  $('loadText').textContent = `${allMovies.length} films chargés !`;
  $('loadBar').style.width = '100%';
  $('startBtn').disabled = false;
  $('startBtn').style.opacity = '1';
  $('startBtn').textContent = '🎬 Lancer la partie !';
}

function updateLoadBar() {
  const pct = Math.round((loadedCount / totalToLoad) * 100);
  $('loadBar').style.width = pct + '%';
  $('loadText').textContent = `Chargement… ${pct}%`;
}

// ============================================================
// DIFFICULTY
// ============================================================
function selectDiff(card) {
  document.querySelectorAll('.diff-card').forEach(c => c.classList.remove('selected'));
  card.classList.add('selected');
  diff = card.dataset.diff;
}

// ============================================================
// GAME FLOW
// ============================================================
function startGame() {
  if (allMovies.length === 0) return;
  const cfg = DIFFICULTIES[diff];
  initialBlur = cfg.blur;
  lives = cfg.lives;
  multiplier = cfg.multiplier;
  score = 0;
  combo = 0;
  round = 0;
  usedIds.clear();

  updateScoreDisplay();
  updateLivesDisplay();

  $('introModal').style.display = 'none';
  $('gameArea').style.display = 'grid';
  nextMovie();
}

function nextMovie() {
  if (round >= MAX_ROUNDS) return showEnd();

  clearInterval(timer);
  round++;
  hintsUsed = [];
  penaltyAcc = 0;
  roundActive = true;
  timeLeft = START_TIME;

  // Reset UI
  feedbackLine.textContent = '';
  feedbackLine.className = 'feedback-line';
  nextBtn.disabled = true;
  hintContent.textContent = 'Aucun indice révélé';
  hintContent.className = 'hint-content';
  $('hint1Btn').disabled = false;
  $('hint2Btn').disabled = false;
  $('hint3Btn').disabled = false;
  $('posterOverlay').classList.remove('show');
  $('posterLabel').classList.remove('show');
  movieInput.value = '';
  acList.classList.remove('show');
  acItems = [];

  roundBadge.textContent = `Manche ${round} / ${MAX_ROUNDS}`;

  if (combo >= 2) {
    comboBadge.classList.add('show');
    comboVal.textContent = `×${combo}`;
  } else {
    comboBadge.classList.remove('show');
  }

  // Pick movie
  const pool = allMovies.filter(m => !usedIds.has(m.id));
  if (pool.length === 0) { usedIds.clear(); }
  const available = allMovies.filter(m => !usedIds.has(m.id));
  currentMovie = available[Math.floor(Math.random() * available.length)];
  usedIds.add(currentMovie.id);
  currentGenre = GENRES[currentMovie.genre_main] || GENRES[currentMovie.genre_ids?.[0]] || '?';

  // Poster with instant blur
  posterImg.style.transition = 'none';
  posterImg.style.filter = `blur(${initialBlur}px)`;
  posterImg.style.transform = 'scale(1.04)';
  void posterImg.offsetWidth;
  posterImg.src = IMG + currentMovie.poster_path;
  posterImg.style.transition = 'filter 0.8s ease, transform 0.5s ease';

  blurFill.style.width = '100%';

  // Generate choices if needed
  if (inputMode === 'choice') generateChoices();

  startTimer();
}

function startTimer() {
  clearInterval(timer);
  timerBar.style.transition = 'none';
  timerBar.style.width = '100%';
  timerBar.className = 'timer-bar';
  void timerBar.offsetWidth;
  timerBar.style.transition = 'width 1s linear';

  timer = setInterval(() => {
    if (!roundActive) return;
    timeLeft--;
    timerVal.textContent = timeLeft;

    const pct = (timeLeft / START_TIME) * 100;
    timerBar.style.width = pct + '%';
    if (timeLeft <= 5) timerBar.className = 'timer-bar urgent';

    // Progressive unblur
    const blurNow = initialBlur * (timeLeft / START_TIME);
    posterImg.style.filter = `blur(${Math.max(blurNow, 0)}px)`;
    blurFill.style.width = pct + '%';

    if (timeLeft <= 0) {
      clearInterval(timer);
      loseLife();
      endRound(false, '⏱ Temps écoulé ! C\'était : ' + currentMovie.title);
    }
  }, 1000);
}

function submitGuess() {
  const val = movieInput.value.trim();
  if (!val || !roundActive) return;
  checkGuess(val);
}

function checkGuess(title) {
  if (!roundActive) return;
  roundActive = false;
  clearInterval(timer);

  disableInputs();

  const correct = normalize(title) === normalize(currentMovie.title);

  if (correct) {
    handleCorrect();
  } else {
    // Highlight correct in choice mode
    if (inputMode === 'choice') {
      document.querySelectorAll('.sug-btn').forEach(b => {
        if (normalize(b.dataset.title) === normalize(currentMovie.title)) b.classList.add('correct');
        else if (normalize(b.dataset.title) === normalize(title)) b.classList.add('wrong');
      });
    }
    handleWrong('❌ Faux ! C\'était : ' + currentMovie.title);
  }

  revealPoster();
  nextBtn.disabled = false;
}

function handleCorrect() {
  combo++;
  const timePts = Math.max(5, Math.floor(20 * (timeLeft / START_TIME)));
  const comboPts = combo > 1 ? (combo - 1) * 5 : 0;
  const penaltyFinal = penaltyAcc;
  const rawPts = Math.max(2, timePts - penaltyFinal + comboPts);
  const finalPts = Math.round(rawPts * multiplier);

  score += finalPts;
  updateScoreDisplay();

  floatScore(finalPts, true);

  let msg = `✅ Correct ! +${finalPts} pts`;
  if (penaltyFinal > 0) msg += ` (−${penaltyFinal} indices)`;
  if (combo > 1) msg += ` 🔥 Combo ×${combo}`;
  setFeedback(msg, 'correct');

  if (combo >= 3) showStreak(`🔥 COMBO ×${combo} !`);

  triggerConfetti();
}

function handleWrong(msg) {
  combo = 0;
  loseLife();
  setFeedback(msg, 'wrong');
  floatScore(0, false);
}

function loseLife() {
  if (lives > 0) lives--;
  updateLivesDisplay();
  if (lives <= 0) {
    setTimeout(showEnd, 800);
  }
}

function endRound(correct, msg) {
  if (!correct) {
    loseLife();
    setFeedback(msg, 'wrong');
  }
  revealPoster();
  nextBtn.disabled = false;
  disableInputs();
}

function revealPoster() {
  posterImg.style.filter = 'blur(0px)';
  posterImg.style.transform = 'scale(1)';
  blurFill.style.width = '0%';
  $('posterOverlay').classList.add('show');
  $('posterLabel').textContent = currentMovie.title;
  $('posterLabel').classList.add('show');
}

function disableInputs() {
  $('submitBtn') && ($('submitBtn').disabled = true);
  movieInput.disabled = true;
  $('hint1Btn').disabled = true;
  $('hint2Btn').disabled = true;
  $('hint3Btn').disabled = true;
  document.querySelectorAll('.sug-btn').forEach(b => b.disabled = true);
  acList.classList.remove('show');
}

function restartGame() {
  $('endModal').style.display = 'none';
  $('gameArea').style.display = 'none';
  // Reset and show intro
  score = 0; combo = 0; round = 0; lives = 3;
  updateScoreDisplay();
  $('introModal').style.display = 'flex';
}

function showEnd() {
  clearInterval(timer);
  $('gameArea').style.display = 'none';

  saveScore();
  renderLeaderboard();

  $('finalScore').textContent = score;
  const msgs = [
    [150, '🏆 Maître Critique — score légendaire !'],
    [100, '🎬 Expert de la pellicule !'],
    [60,  '👏 Très bonne performance !'],
    [0,   '🎥 Réessaie pour affûter ton œil !']
  ];
  $('endMsg').textContent = msgs.find(([min]) => score >= min)[1];
  $('endModal').style.display = 'flex';
}

// ============================================================
// HINTS
// ============================================================
function revealHint(n) {
  if (!roundActive || hintsUsed.includes(n)) return;
  hintsUsed.push(n);

  const penalties = { 1: 5, 2: 8, 3: 15 };
  const penalty = penalties[n];
  penaltyAcc += penalty;
  score = Math.max(0, score - penalty);
  updateScoreDisplay();
  floatScore(penalty, false);

  let hintLines = [];
  if (hintsUsed.includes(1)) hintLines.push(`Genre : ${currentGenre}`);
  if (hintsUsed.includes(2)) hintLines.push(`Année : ${(currentMovie.release_date || '????').substring(0,4)}`);
  if (hintsUsed.includes(3)) {
    const syn = currentMovie.overview.split('.')[0] + '.';
    hintLines.push(`Synopsis : ${syn}`);
  }

  hintContent.innerHTML = hintLines.join('<br>');
  hintContent.className = 'hint-content revealed';

  $(`hint${n}Btn`).disabled = true;
  setFeedback(`⚠️ Indice révélé — ${penalty} pts déduits`, 'info');
}

// ============================================================
// MODE (text / choice)
// ============================================================
function setMode(mode) {
  inputMode = mode;
  $('modeText').classList.toggle('active', mode === 'text');
  $('modeChoice').classList.toggle('active', mode === 'choice');
  $('inputSection').style.display = mode === 'text' ? 'block' : 'none';
  $('choiceSection').style.display = mode === 'choice' ? 'block' : 'none';

  if (mode === 'choice' && roundActive) generateChoices();
}

function generateChoices() {
  const pool = allMovies.filter(m => m.id !== currentMovie.id && m.title !== currentMovie.title);
  const shuffled = shuffle([...pool]).slice(0, 3).map(m => m.title);
  const opts = shuffle([currentMovie.title, ...shuffled]);

  suggestionsGrid.innerHTML = '';
  opts.forEach(title => {
    const btn = document.createElement('button');
    btn.className = 'sug-btn';
    btn.textContent = title;
    btn.dataset.title = title;
    btn.onclick = () => { if (roundActive) checkGuess(title); };
    suggestionsGrid.appendChild(btn);
  });
}

// ============================================================
// AUTOCOMPLETE
// ============================================================
function onInputChange() {
  const val = movieInput.value.trim().toLowerCase();
  acIndex = -1;

  if (val.length < 2) { acList.classList.remove('show'); return; }

  const matches = allMovies
    .filter(m => m.title.toLowerCase().includes(val))
    .slice(0, 7);

  acItems = matches.map(m => m.title);

  if (matches.length === 0) { acList.classList.remove('show'); return; }

  acList.innerHTML = matches.map((m, i) => {
    const hi = m.title.replace(new RegExp(`(${escapeRe(val)})`, 'gi'), '<em>$1</em>');
    return `<div class="ac-item" data-i="${i}" onclick="selectAc(${i})">${hi}</div>`;
  }).join('');

  acList.classList.add('show');
}

function onInputKey(e) {
  const items = acList.querySelectorAll('.ac-item');
  if (e.key === 'ArrowDown') {
    acIndex = Math.min(acIndex + 1, items.length - 1);
    items.forEach((it, i) => it.classList.toggle('active', i === acIndex));
    e.preventDefault();
  } else if (e.key === 'ArrowUp') {
    acIndex = Math.max(acIndex - 1, -1);
    items.forEach((it, i) => it.classList.toggle('active', i === acIndex));
    e.preventDefault();
  } else if (e.key === 'Enter') {
    if (acIndex >= 0 && acItems[acIndex]) {
      selectAc(acIndex);
    } else {
      submitGuess();
    }
  } else if (e.key === 'Escape') {
    acList.classList.remove('show');
  }
}

function selectAc(i) {
  movieInput.value = acItems[i];
  acList.classList.remove('show');
  movieInput.focus();
}

// ============================================================
// UI HELPERS
// ============================================================
function setFeedback(msg, type) {
  feedbackLine.textContent = msg;
  feedbackLine.className = 'feedback-line ' + type;
}

function updateScoreDisplay() {
  scoreVal.textContent = score;
}

function updateLivesDisplay() {
    const container = document.getElementById('livesDisplay');
    if (!container) return;

    // On récupère le nombre de vies total selon la difficulté choisie
    const totalMaxLives = DIFFICULTIES[diff].lives; 
    let heartHTML = '';

    for (let i = 0; i < totalMaxLives; i++) {
        // Si l'index i est inférieur aux vies restantes (ex: 1 < 2), le cœur est plein
        // Sinon, on lui donne la classe .lost
        const isLost = i >= lives; 
        heartHTML += `<span class="life ${isLost ? 'lost' : ''}"><i class="fas fa-heart"></i></span>`;
    }

    container.innerHTML = heartHTML;
}

function floatScore(pts, positive) {
  const el = document.createElement('div');
  el.className = 'score-float';
  el.style.color = positive ? '#3dd68c' : '#e84545';
  el.textContent = positive ? `+${pts}` : `−${pts}`;
  el.style.left = (window.innerWidth / 2) + 'px';
  el.style.top = '80px';
  document.body.appendChild(el);
  el.style.animation = 'float-up 1.2s ease forwards';
  setTimeout(() => el.remove(), 1300);
}

function showStreak(msg) {
  streakBanner.textContent = msg;
  streakBanner.classList.add('show');
  setTimeout(() => streakBanner.classList.remove('show'), 2200);
}

function triggerConfetti() {
  const colors = ['#f0c040','#3dd68c','#4d9fff','#e84545','#ffd966','#c084fc'];
  for (let i = 0; i < 60; i++) {
    const el = document.createElement('div');
    el.className = 'confetto';
    el.style.left = Math.random() * 100 + 'vw';
    el.style.top = '-10px';
    el.style.background = colors[Math.floor(Math.random() * colors.length)];
    el.style.animationDuration = (Math.random() * 2 + 1.5) + 's';
    el.style.animationDelay = (Math.random() * 0.8) + 's';
    el.style.borderRadius = Math.random() > 0.5 ? '50%' : '2px';
    el.style.width = el.style.height = (Math.random() * 6 + 5) + 'px';
    el.style.setProperty('--dx', (Math.random() * 200 - 100) + 'px');
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 4000);
  }
}

// ============================================================
// LEADERBOARD (localStorage)
// ============================================================
const LB_KEY = 'cinaguess_lb';

function saveScore() {
  const lb = JSON.parse(localStorage.getItem(LB_KEY) || '[]');
  lb.push({ score, diff, date: new Date().toLocaleDateString('fr-FR') });
  lb.sort((a, b) => b.score - a.score);
  localStorage.setItem(LB_KEY, JSON.stringify(lb.slice(0, 10)));
}

function renderLeaderboard() {
  const lb = JSON.parse(localStorage.getItem(LB_KEY) || '[]');
  if (!lb.length) { $('lbDisplay').innerHTML = ''; return; }
  const medals = ['🥇','🥈','🥉'];
  $('lbDisplay').innerHTML = `
    <div class="lb-list">
      <h4>Meilleurs scores</h4>
      ${lb.map((e, i) => `
        <div class="lb-item">
          <span class="lb-rank${i===0?' first':''}">${medals[i] || (i+1)+'.'}</span>
          <span>${e.date}</span>
          <span class="lb-diff ${e.diff}">${DIFFICULTIES[e.diff]?.label || e.diff}</span>
          <span class="lb-score">${e.score} pts</span>
        </div>
      `).join('')}
    </div>`;
}

// ============================================================
// UTILS
// ============================================================
function normalize(s) {
  return s.trim().toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9 ]/g, '');
}

function shuffle(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

function escapeRe(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Close autocomplete on outside click
document.addEventListener('click', e => {
  if (!e.target.closest('#inputSection')) acList.classList.remove('show');
});

// Keyboard submit
document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.target === movieInput) return; // handled above
});

// ============================================================
// INIT
// ============================================================
window.addEventListener('DOMContentLoaded', () => {
  // Re-enable submit when round is active
  const origSubmit = $('submitBtn');
  origSubmit.addEventListener('click', submitGuess);

  loadMovies();
});