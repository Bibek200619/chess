/* ============================================================
   Deep Chess — app.js
   Wires the premium UI to the Python backend API.
   Board/piece rendering logic is preserved exactly.
   New: move-log panel, animated status, richer modal.
   ============================================================ */

// ── Piece unicode map (preserved) ──────────────────────────────
const PIECES = {
  wk: "♔", wq: "♕", wr: "♖", wb: "♗", wh: "♘", wp: "♙",
  bk: "♚", bq: "♛", br: "♜", bb: "♝", bh: "♞", bp: "♟",
};

const PIECE_NAMES = {
  k: "King", q: "Queen", r: "Rook", b: "Bishop", h: "Knight", p: "Pawn",
};

const MODAL_ICONS = { w: "♔", b: "♚", draw: "🤝" };

// ── DOM refs ───────────────────────────────────────────────────
const boardEl          = document.querySelector("#board");
const messageEl        = document.querySelector("#message");
const turnNameEl       = document.querySelector("#turnName");
const turnOrbEl        = document.querySelector("#turnOrb");
const thinkingBadgeEl  = document.querySelector("#thinkingBadge");
const statusCardEl     = document.querySelector("#statusCard");
const whiteCapturesEl  = document.querySelector("#whiteCaptures");
const blackCapturesEl  = document.querySelector("#blackCaptures");
const friendModeBtn    = document.querySelector("#friendMode");
const aiModeBtn        = document.querySelector("#aiMode");
const premoveBtn       = document.querySelector("#premoveButton");
const resetBtn         = document.querySelector("#resetButton");
const modalResetBtn    = document.querySelector("#modalReset");
const gameOverEl       = document.querySelector("#gameOver");
const gameOverTextEl   = document.querySelector("#gameOverText");
const modalSubEl       = document.querySelector("#modalSub");
const modalIconEl      = document.querySelector("#modalIcon");
const moveLogEl        = document.querySelector("#moveLog");
const moveCountEl      = document.querySelector("#moveCount");
const diffBtns         = [...document.querySelectorAll("[data-level]")];

// ── State ─────────────────────────────────────────────────────
let state     = null;
let pollTimer = null;
let moveLog   = [];   // array of { white, black, num }

// ── API helper ─────────────────────────────────────────────────
async function api(path, payload = null) {
  const opts = payload
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }
    : {};
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

// ── Coordinate helpers ─────────────────────────────────────────
const sq  = (r, c) => `${r},${c}`;
const toSet = (items) => new Set((items || []).map(([r, c]) => sq(r, c)));

// ── Render ─────────────────────────────────────────────────────
function render(next) {
  const prev = state;
  state = next;

  // Track move log
  if (prev && state.lastMove && state.version !== prev.version) {
    recordMove(prev, state);
  }

  renderBoard();
  renderSidebar();
  renderModal();
  renderMoveLog();
  schedulePoll();
}

// ── Board rendering (logic preserved, classes updated) ─────────
function renderBoard() {
  const legal    = toSet(state.legalTargets);
  const selected = state.selected ? sq(...state.selected) : null;
  const check    = state.checkSquare ? sq(...state.checkSquare) : null;
  const preSelec = state.premoveSelected ? sq(...state.premoveSelected) : null;
  const preTarg  = state.premoveTarget  ? sq(...state.premoveTarget)  : null;
  const lastMove = toSet(state.lastMove);

  boardEl.innerHTML = "";

  for (let row = 0; row < 8; row++) {
    for (let col = 0; col < 8; col++) {
      const key    = sq(row, col);
      const square = document.createElement("button");
      square.type  = "button";
      square.className = `square ${(row + col) % 2 === 0 ? "light" : "dark"}`;
      square.dataset.row = row;
      square.dataset.col = col;
      square.setAttribute("aria-label", squareAriaLabel(row, col));

      if (selected === key)                          square.classList.add("selected");
      if (legal.has(key))
        square.classList.add(state.board[row][col] !== "__" ? "capture" : "legal");
      if (check === key)                             square.classList.add("check");
      if (lastMove.has(key))                         square.classList.add("last");
      if (preSelec === key || preTarg === key)       square.classList.add("premove");

      // Piece (preserved)
      const piece = state.board[row][col];
      if (piece !== "__") {
        const pieceEl = document.createElement("span");
        pieceEl.className = `piece ${piece[0] === "w" ? "white" : "black"}`;
        pieceEl.textContent = PIECES[piece];
        pieceEl.setAttribute("aria-label", `${piece[0] === "w" ? "White" : "Black"} ${PIECE_NAMES[piece[1]]}`);
        square.appendChild(pieceEl);
      }

      square.addEventListener("click", () => clickSquare(row, col));
      boardEl.appendChild(square);
    }
  }

  // King-in-check card glow
  statusCardEl.classList.toggle("check", !!state.checkSquare);
}

function squareAriaLabel(row, col) {
  const file = "abcdefgh"[col];
  const rank = 8 - row;
  const piece = state.board[row][col];
  if (piece === "__") return `${file}${rank} empty`;
  return `${piece[0] === "w" ? "White" : "Black"} ${PIECE_NAMES[piece[1]]} on ${file}${rank}`;
}

// ── Sidebar ────────────────────────────────────────────────────
function renderSidebar() {
  // Turn orb + name
  const winner = state.winner;
  if (winner) {
    turnOrbEl.className = `turn-orb ${winner === "draw" ? "" : winner === "w" ? "white" : "black"}`;
    turnNameEl.textContent = winner === "draw" ? "Draw" : `${colorName(winner)} wins`;
  } else {
    turnOrbEl.className = `turn-orb ${state.turn === "w" ? "white" : "black"}`;
    turnNameEl.textContent = state.turnName;
  }

  // Thinking badge
  thinkingBadgeEl.classList.toggle("hidden", !state.aiThinking);

  // Status message
  messageEl.textContent = state.message || "";

  // Mode buttons
  friendModeBtn.classList.toggle("active", state.playMode === "friend");
  aiModeBtn.classList.toggle("active", state.playMode === "ai");

  // Premove
  premoveBtn.classList.toggle("active", state.premoveEnabled);

  // Difficulty buttons
  diffBtns.forEach((btn) => {
    const active = Number(btn.dataset.level) === state.aiLevel;
    btn.classList.toggle("active", active);
  });

  // Captures
  whiteCapturesEl.innerHTML = captureHTML(state.whiteCaptures);
  blackCapturesEl.innerHTML = captureHTML(state.blackCaptures);
}

function captureHTML(captures) {
  if (!captures || captures.length === 0) return "";
  return captures.map((p) => `<span title="${PIECE_NAMES[p[1]]}">${PIECES[p]}</span>`).join("");
}

// ── Modal ──────────────────────────────────────────────────────
function renderModal() {
  const show = !!state.gameOverMessage;
  gameOverEl.classList.toggle("hidden", !show);
  if (!show) return;

  const w = state.winner;
  gameOverTextEl.textContent = state.gameOverMessage;
  modalIconEl.textContent    = MODAL_ICONS[w] || "♙";
  modalSubEl.textContent     = w === "draw"
    ? "A hard-fought draw!"
    : `${colorName(w)} wins the game.`;
}

// ── Move log ───────────────────────────────────────────────────
function recordMove(prev, next) {
  if (!next.lastMove) return;
  const [src, tgt] = next.lastMove;
  const piece = prev.board[src[0]][src[1]];
  if (piece === "__") return;

  const uci  = toUCI(src, tgt);
  const icon = PIECES[piece] || "";
  const entry = icon + uci;

  const lastPair = moveLog[moveLog.length - 1];
  // White moves first (turn was white before the move = prev turn was "w")
  if (prev.turn === "w") {
    moveLog.push({ num: moveLog.length + 1, white: entry, black: "" });
  } else if (lastPair && lastPair.black === "") {
    lastPair.black = entry;
  } else {
    moveLog.push({ num: moveLog.length + 1, white: "", black: entry });
  }
}

function renderMoveLog() {
  if (moveLog.length === 0) {
    moveLogEl.innerHTML = `<div class="move-log-empty">Waiting for moves…</div>`;
    moveCountEl.textContent = "0 moves";
    return;
  }

  moveLogEl.innerHTML = moveLog.map((pair, i) => {
    const isLast = i === moveLog.length - 1;
    return `<div class="move-pair">
      <span class="move-num">${pair.num}.</span>
      <span class="move-cell ${isLast && pair.white ? "latest" : ""}">${pair.white || ""}</span>
      <span class="move-cell ${isLast && pair.black ? "latest" : ""}">${pair.black || ""}</span>
    </div>`;
  }).join("");

  const totalMoves = moveLog.reduce((n, p) => n + (p.white ? 1 : 0) + (p.black ? 1 : 0), 0);
  moveCountEl.textContent = `${totalMoves} move${totalMoves !== 1 ? "s" : ""}`;

  // Scroll to bottom
  moveLogEl.scrollTop = moveLogEl.scrollHeight;
}

function toUCI(src, tgt) {
  return "abcdefgh"[src[1]] + (8 - src[0]) + "abcdefgh"[tgt[1]] + (8 - tgt[0]);
}

// ── Helpers ────────────────────────────────────────────────────
function colorName(c) { return c === "w" ? "White" : "Black"; }

// ── Actions ────────────────────────────────────────────────────
async function clickSquare(row, col) {
  try { render(await api("/api/click", { row, col })); }
  catch (e) { console.error(e); }
}

async function setMode(mode) {
  try { render(await api("/api/mode", { mode })); }
  catch (e) { console.error(e); }
}

async function setLevel(level) {
  try { render(await api("/api/level", { level })); }
  catch (e) { console.error(e); }
}

async function resetGame() {
  moveLog = [];
  try { render(await api("/api/reset", {})); }
  catch (e) { console.error(e); }
}

async function togglePremove() {
  try { render(await api("/api/premove", { enabled: !state?.premoveEnabled })); }
  catch (e) { console.error(e); }
}

// ── Polling (when AI is thinking) ─────────────────────────────
function schedulePoll() {
  clearTimeout(pollTimer);
  pollTimer = null;
  if (!state?.aiThinking) return;
  pollTimer = setTimeout(async () => {
    try { render(await api("/api/state")); }
    catch (e) { console.error(e); }
  }, 200);
}

// ── Event listeners ────────────────────────────────────────────
friendModeBtn.addEventListener("click", () => setMode("friend"));
aiModeBtn.addEventListener("click", () => setMode("ai"));
premoveBtn.addEventListener("click", togglePremove);
resetBtn.addEventListener("click", resetGame);
modalResetBtn.addEventListener("click", resetGame);
diffBtns.forEach((btn) =>
  btn.addEventListener("click", () => setLevel(Number(btn.dataset.level)))
);

document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT") return;
  if (e.key === "1" || e.key === "2" || e.key === "3") setLevel(Number(e.key));
  else if (e.key.toLowerCase() === "p") togglePremove();
  else if (e.key.toLowerCase() === "r") resetGame();
});

// ── Bootstrap ─────────────────────────────────────────────────
api("/api/state")
  .then(render)
  .catch((err) => {
    messageEl.textContent = `⚠ Could not connect to server: ${err.message}`;
  });
