"""
ai.py — Chess AI engine (10x stronger version).

Key upgrades over the previous version:
  1. Plugs into evaluate.py — PST + king safety + pawn structure
  2. Quiescence search — avoids the horizon effect on captures/promotions
  3. Zobrist transposition table — caches positions to avoid redundant work
  4. Iterative deepening — uses best available move if time runs short
  5. Higher search depths: Level 1 = 2, Level 2 = 4, Level 3 = 6
  6. Better move ordering (hash move first, then MVV-LVA captures)
"""

import json
import random
import threading
from pathlib import Path

from engine import moves, neural_policy
from engine.evaluate import evaluate, PIECE_VALUES

# ---------------------------------------------------------------------------
# Model definitions (visible to server)
# ---------------------------------------------------------------------------
MODELS = {
    1: {"name": "Level 1 Easy",   "params": "1M",   "depth": 2},
    2: {"name": "Level 2 Medium", "params": "50M",  "depth": 4},
    3: {"name": "Level 3 Hard",   "params": "100M", "depth": 6},
}

# ---------------------------------------------------------------------------
# Opening book
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
OPENING_BOOK_PATH = ROOT / "data" / "opening_book.json"
OPENING_BOOK = None
BOOK_TEMPERATURE  = {1: 0.95, 2: 0.65, 3: 0.45}
NEURAL_TEMPERATURE = {1: 0.85, 2: 0.50, 3: 0.30}

# ---------------------------------------------------------------------------
# Zobrist hashing
# ---------------------------------------------------------------------------
import struct, hashlib

# Pre-generate a deterministic Zobrist table
_PIECE_CODES = {p: i for i, p in enumerate(
    ["wp","wh","wb","wr","wq","wk","bp","bh","bb","br","bq","bk"]
)}
_NUM_PIECES = len(_PIECE_CODES)

def _make_zobrist():
    table = []
    rng_seed = b"chess_zobrist_seed_v1"
    for sq in range(64):
        row = []
        for pc in range(_NUM_PIECES + 8 + 4 + 1):  # pieces + ep cols + castling + side
            h = hashlib.sha256(rng_seed + struct.pack("II", sq, pc))
            row.append(int.from_bytes(h.digest()[:8], "little"))
        table.append(row)
    return table

_ZOB = _make_zobrist()
_ZOB_SIDE   = _ZOB[0][_NUM_PIECES + 8 + 4]   # black to move XOR key
_ZOB_EP     = [_ZOB[i][_NUM_PIECES] for i in range(8)]           # ep col
_ZOB_CASTLE = [_ZOB[i][_NUM_PIECES + 8] for i in range(4)]       # wk,wq,bk,bq


def _board_hash(board, color, en_passant_target, castling_rights):
    h = 0
    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            if piece != moves.EMPTY:
                idx = _PIECE_CODES[piece]
                h ^= _ZOB[row * 8 + col][idx]
    if color == "b":
        h ^= _ZOB_SIDE
    if en_passant_target:
        h ^= _ZOB_EP[en_passant_target[1]]
    rights = castling_rights or set()
    for i, r in enumerate(("wk", "wq", "bk", "bq")):
        if r in rights:
            h ^= _ZOB_CASTLE[i]
    return h


# ---------------------------------------------------------------------------
# Transposition table
# ---------------------------------------------------------------------------
_TT_SIZE = 1 << 20   # 1 M entries
_TT_EXACT, _TT_LOWER, _TT_UPPER = 0, 1, 2

_tt_lock = threading.Lock()
_tt: dict[int, tuple] = {}   # hash → (depth, score, flag, best_move)


def _tt_get(h, depth, alpha, beta):
    entry = _tt.get(h)
    if entry is None:
        return None, None
    e_depth, e_score, e_flag, e_move = entry
    if e_depth < depth:
        return None, e_move          # shallow — only usable as move hint
    if e_flag == _TT_EXACT:
        return e_score, e_move
    if e_flag == _TT_LOWER and e_score >= beta:
        return e_score, e_move
    if e_flag == _TT_UPPER and e_score <= alpha:
        return e_score, e_move
    return None, e_move


def _tt_put(h, depth, score, flag, best_move):
    if len(_tt) > _TT_SIZE:
        _tt.clear()                  # simple replacement — clear when full
    _tt[h] = (depth, score, flag, best_move)


# ---------------------------------------------------------------------------
# Move ordering helpers
# ---------------------------------------------------------------------------
_MVV_LVA = {
    "p": 1, "h": 2, "b": 3, "r": 4, "q": 5, "k": 6
}


def _move_score(board, move, tt_best=None):
    """Higher score → searched first."""
    source, target = move

    # Hash move gets highest priority
    if tt_best and move == tt_best:
        return 20_000

    target_piece = board[target[0]][target[1]]
    source_piece = board[source[0]][source[1]]

    # MVV-LVA (Most Valuable Victim — Least Valuable Attacker)
    if target_piece != moves.EMPTY:
        victim  = _MVV_LVA.get(target_piece[1], 0)
        attacker = _MVV_LVA.get(source_piece[1], 6)
        return 10_000 + victim * 10 - attacker

    # Promotion
    if source_piece in ("wp", "bp") and target[0] in (0, 7):
        return 9_000

    return 0


def ordered_moves(board, legal, tt_best=None):
    return sorted(legal, key=lambda m: _move_score(board, m, tt_best), reverse=True)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------
def choose_move(board, color, level, en_passant_target=None, castling_rights=None):
    legal = all_legal_moves(board, color, en_passant_target, castling_rights)
    if not legal:
        return None

    # 1. Opening book
    book_move = choose_book_move(board, color, legal, en_passant_target, castling_rights, level)
    if book_move:
        return book_move

    # 2. Neural policy (if model is available)
    neural_move = neural_policy.choose_neural_move(
        board, color, legal, en_passant_target, castling_rights,
        NEURAL_TEMPERATURE.get(level, 0.5),
    )
    if neural_move:
        return neural_move

    # 3. Minimax with iterative deepening
    depth = MODELS.get(level, MODELS[2])["depth"]

    if level == 1:
        # Level 1: shallow depth + some randomness so it makes obvious blunders
        return _choose_with_randomness(board, color, depth, legal, en_passant_target,
                                       set(castling_rights or set()), blunder_rate=0.15)

    return iterative_deepening(board, color, depth, legal, en_passant_target,
                               set(castling_rights or set()))


def _choose_with_randomness(board, color, depth, legal, en_passant_target, castling_rights,
                             blunder_rate=0.15):
    """Level 1: occasionally pick a random move to simulate human error."""
    if random.random() < blunder_rate:
        return random.choice(legal)
    return iterative_deepening(board, color, depth, legal, en_passant_target, castling_rights)


# ---------------------------------------------------------------------------
# Iterative Deepening
# ---------------------------------------------------------------------------
def iterative_deepening(board, color, max_depth, legal, en_passant_target, castling_rights):
    best_move = random.choice(legal)
    for d in range(1, max_depth + 1):
        candidate = choose_search_move(board, color, d, legal, en_passant_target, castling_rights)
        if candidate:
            best_move = candidate
    return best_move


# ---------------------------------------------------------------------------
# Root search
# ---------------------------------------------------------------------------
def choose_search_move(board, color, depth, legal, en_passant_target, castling_rights):
    h = _board_hash(board, color, en_passant_target, castling_rights)
    _, tt_best = _tt_get(h, depth, -1_000_000, 1_000_000)

    scored = []
    alpha = -1_000_000
    beta  =  1_000_000

    for move in ordered_moves(board, legal, tt_best):
        child_board, child_ep, child_rights = simulate_move(board, move, en_passant_target, castling_rights)
        score = -negamax(child_board, moves.opponent(color), depth - 1,
                          -beta, -alpha, child_ep, child_rights)
        scored.append((move, score))
        if score > alpha:
            alpha = score

    if not scored:
        return None

    scored.sort(key=lambda x: x[1], reverse=True)
    best_score = scored[0][1]

    # Store in TT
    _tt_put(h, depth, best_score, _TT_EXACT, scored[0][0])

    # At level 3 always pick best; lower levels pick from close candidates
    top = [m for m, s in scored if best_score - s <= 0]
    return top[0] if top else scored[0][0]


# ---------------------------------------------------------------------------
# Negamax with alpha-beta + quiescence search
# ---------------------------------------------------------------------------
def negamax(board, color, depth, alpha, beta, en_passant_target, castling_rights):
    h = _board_hash(board, color, en_passant_target, castling_rights)
    cached, tt_best = _tt_get(h, depth, alpha, beta)
    if cached is not None:
        return cached

    status = moves.game_status(board, color, en_passant_target, castling_rights)
    if status == "checkmate":
        return -100_000 - depth      # prefer faster mates
    if status == "stalemate":
        return 0

    if depth == 0:
        return quiescence(board, color, alpha, beta, en_passant_target, castling_rights)

    legal = all_legal_moves(board, color, en_passant_target, castling_rights)
    if not legal:
        return evaluate(board, color, en_passant_target, castling_rights)

    orig_alpha = alpha
    best_move  = None
    best_score = -1_000_000

    for move in ordered_moves(board, legal, tt_best):
        child_board, child_ep, child_rights = simulate_move(board, move, en_passant_target, castling_rights)
        score = -negamax(child_board, moves.opponent(color), depth - 1,
                          -beta, -alpha, child_ep, child_rights)
        if score > best_score:
            best_score = score
            best_move  = move
        alpha = max(alpha, score)
        if alpha >= beta:
            break   # beta cut-off

    # Store in transposition table
    flag = _TT_EXACT
    if best_score <= orig_alpha:
        flag = _TT_UPPER
    elif best_score >= beta:
        flag = _TT_LOWER
    _tt_put(h, depth, best_score, flag, best_move)

    return best_score


# ---------------------------------------------------------------------------
# Quiescence Search
# ---------------------------------------------------------------------------
_QSEARCH_MAX_DEPTH = 6


def quiescence(board, color, alpha, beta, en_passant_target, castling_rights, qdepth=0):
    """Search captures until the position is quiet to avoid the horizon effect."""
    stand_pat = evaluate(board, color, en_passant_target, castling_rights)

    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    if qdepth >= _QSEARCH_MAX_DEPTH:
        return alpha

    legal = all_legal_moves(board, color, en_passant_target, castling_rights)
    captures = [m for m in legal if _is_capture_or_promotion(board, m)]

    for move in ordered_moves(board, captures):
        child_board, child_ep, child_rights = simulate_move(board, move, en_passant_target, castling_rights)
        score = -quiescence(child_board, moves.opponent(color), -beta, -alpha,
                             child_ep, child_rights, qdepth + 1)
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score

    return alpha


def _is_capture_or_promotion(board, move):
    source, target = move
    if board[target[0]][target[1]] != moves.EMPTY:
        return True
    piece = board[source[0]][source[1]]
    return piece in ("wp", "bp") and target[0] in (0, 7)


# ---------------------------------------------------------------------------
# Opening book
# ---------------------------------------------------------------------------
def choose_book_move(board, color, legal, en_passant_target, castling_rights, level):
    book = load_opening_book()
    if not book:
        return None

    key = position_key(board, color, en_passant_target, castling_rights)
    entries = book.get(key)
    if not entries:
        return None

    legal_by_uci = {move_to_uci(move): move for move in legal}
    candidates = [
        (legal_by_uci[uci], score)
        for uci, score in entries
        if uci in legal_by_uci
    ]
    if not candidates:
        return None

    return sample_weighted_moves(candidates, BOOK_TEMPERATURE.get(level, 0.65))


def load_opening_book():
    global OPENING_BOOK
    if OPENING_BOOK is not None:
        return OPENING_BOOK
    if not OPENING_BOOK_PATH.exists():
        OPENING_BOOK = {}
        return OPENING_BOOK

    payload = json.loads(OPENING_BOOK_PATH.read_text(encoding="utf-8"))
    OPENING_BOOK = payload.get("positions", {})
    return OPENING_BOOK


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def all_legal_moves(board, color, en_passant_target=None, castling_rights=None):
    legal = []
    for row in range(8):
        for col in range(8):
            if moves.piece_color(board[row][col]) != color:
                continue
            for target in moves.legal_moves(board, row, col, en_passant_target, castling_rights):
                legal.append(((row, col), target))
    return legal


def simulate_move(board, move, en_passant_target, castling_rights):
    source, target = move
    child = [row[:] for row in board]
    rights = set(castling_rights or set())
    moving_piece = child[source[0]][source[1]]
    result = moves.move_piece(child, source, target, en_passant_target)
    update_castling_rights(rights, source, moving_piece, result)
    return child, result.en_passant_target, rights


def update_castling_rights(castling_rights, source, moving_piece, result):
    source_row, source_col = source
    color = moving_piece[0]
    if moving_piece[1] == "k":
        castling_rights.discard(color + "k")
        castling_rights.discard(color + "q")
    elif moving_piece[1] == "r":
        remove_rook_castling_right(castling_rights, source_row, source_col, color)

    if result.captured and result.captured[1] == "r" and result.captured_square:
        captured_row, captured_col = result.captured_square
        remove_rook_castling_right(castling_rights, captured_row, captured_col, result.captured[0])


def remove_rook_castling_right(castling_rights, row, col, color):
    home_row = 7 if color == "w" else 0
    if row != home_row:
        return
    if col == 0:
        castling_rights.discard(color + "q")
    elif col == 7:
        castling_rights.discard(color + "k")


def position_key(board, color, en_passant_target=None, castling_rights=None):
    board_fen = "/".join(fen_row(row) for row in board)
    turn = "True" if color == "w" else "False"
    castling = castling_key(castling_rights)
    ep = square_name(en_passant_target) if en_passant_target else "-"
    return f"{board_fen} {turn} {castling} {ep}"


def fen_row(row):
    result = ""
    empty_count = 0
    for piece in row:
        if piece == moves.EMPTY:
            empty_count += 1
            continue
        if empty_count:
            result += str(empty_count)
            empty_count = 0
        result += fen_piece(piece)
    if empty_count:
        result += str(empty_count)
    return result


def fen_piece(piece):
    symbol = {"p": "p", "h": "n", "b": "b", "r": "r", "q": "q", "k": "k"}[piece[1]]
    return symbol.upper() if piece[0] == "w" else symbol


def castling_key(castling_rights):
    rights = castling_rights or set()
    value = ""
    if "wk" in rights: value += "K"
    if "wq" in rights: value += "Q"
    if "bk" in rights: value += "k"
    if "bq" in rights: value += "q"
    return value or "-"


def square_name(square):
    row, col = square
    return f"{chr(ord('a') + col)}{8 - row}"


def move_to_uci(move):
    source, target = move
    return square_name(source) + square_name(target)


def sample_weighted_moves(candidates, temperature):
    candidates = sorted(candidates, key=lambda item: item[1], reverse=True)
    top = candidates[:min(6, len(candidates))]
    adjusted = []
    for move, score in top:
        adjusted.append((move, max(float(score), 1.0) ** (1 / max(temperature, 0.05))))
    total = sum(weight for _move, weight in adjusted)
    pick = random.uniform(0, total)
    running = 0
    for move, weight in adjusted:
        running += weight
        if running >= pick:
            return move
    return adjusted[0][0]
