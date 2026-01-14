"""
evaluate.py — Advanced static evaluation for the chess engine.

Improvements over the previous version:
  • Piece-square tables (PST) for all piece types, tuned for middlegame/endgame
  • King safety: penalise exposed king, reward pawn shield
  • Pawn structure: doubled, isolated, and passed pawn detection
  • Mobility bonus (number of pseudo-legal moves)
  • Tempo bonus (side to move gets a small bonus)
  • Bishop pair bonus
  • Rook on open/semi-open file bonus
"""

from engine import moves as _moves

# ---------------------------------------------------------------------------
# Piece base values (centipawns)
# ---------------------------------------------------------------------------
PIECE_VALUES = {
    "p": 100,
    "h": 320,
    "b": 330,
    "r": 500,
    "q": 900,
    "k": 0,
}

# ---------------------------------------------------------------------------
# Piece-square tables (white perspective, index [row][col], row 0 = rank 8)
# ---------------------------------------------------------------------------
# Pawns: encourage centre advance and e/d pawns
PST_PAWN = [
    [  0,   0,   0,   0,   0,   0,   0,   0],
    [ 50,  50,  50,  50,  50,  50,  50,  50],
    [ 10,  10,  20,  30,  30,  20,  10,  10],
    [  5,   5,  10,  25,  25,  10,   5,   5],
    [  0,   0,   0,  20,  20,   0,   0,   0],
    [  5,  -5, -10,   0,   0, -10,  -5,   5],
    [  5,  10,  10, -20, -20,  10,  10,   5],
    [  0,   0,   0,   0,   0,   0,   0,   0],
]

# Knights: bad on rim, great in the centre
PST_KNIGHT = [
    [-50, -40, -30, -30, -30, -30, -40, -50],
    [-40, -20,   0,   0,   0,   0, -20, -40],
    [-30,   0,  10,  15,  15,  10,   0, -30],
    [-30,   5,  15,  20,  20,  15,   5, -30],
    [-30,   0,  15,  20,  20,  15,   0, -30],
    [-30,   5,  10,  15,  15,  10,   5, -30],
    [-40, -20,   0,   5,   5,   0, -20, -40],
    [-50, -40, -30, -30, -30, -30, -40, -50],
]

# Bishops: diagonals and open boards
PST_BISHOP = [
    [-20, -10, -10, -10, -10, -10, -10, -20],
    [-10,   0,   0,   0,   0,   0,   0, -10],
    [-10,   0,   5,  10,  10,   5,   0, -10],
    [-10,   5,   5,  10,  10,   5,   5, -10],
    [-10,   0,  10,  10,  10,  10,   0, -10],
    [-10,  10,  10,  10,  10,  10,  10, -10],
    [-10,   5,   0,   0,   0,   0,   5, -10],
    [-20, -10, -10, -10, -10, -10, -10, -20],
]

# Rooks: open files and 7th rank
PST_ROOK = [
    [  0,   0,   0,   0,   0,   0,   0,   0],
    [  5,  10,  10,  10,  10,  10,  10,   5],
    [ -5,   0,   0,   0,   0,   0,   0,  -5],
    [ -5,   0,   0,   0,   0,   0,   0,  -5],
    [ -5,   0,   0,   0,   0,   0,   0,  -5],
    [ -5,   0,   0,   0,   0,   0,   0,  -5],
    [ -5,   0,   0,   0,   0,   0,   0,  -5],
    [  0,   0,   0,   5,   5,   0,   0,   0],
]

# Queens: avoid early development, flexible
PST_QUEEN = [
    [-20, -10, -10,  -5,  -5, -10, -10, -20],
    [-10,   0,   0,   0,   0,   0,   0, -10],
    [-10,   0,   5,   5,   5,   5,   0, -10],
    [ -5,   0,   5,   5,   5,   5,   0,  -5],
    [  0,   0,   5,   5,   5,   5,   0,  -5],
    [-10,   5,   5,   5,   5,   5,   0, -10],
    [-10,   0,   5,   0,   0,   0,   0, -10],
    [-20, -10, -10,  -5,  -5, -10, -10, -20],
]

# King middlegame: hide behind pawns, castle early
PST_KING_MG = [
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-20, -30, -30, -40, -40, -30, -30, -20],
    [-10, -20, -20, -20, -20, -20, -20, -10],
    [ 20,  20,   0,   0,   0,   0,  20,  20],
    [ 20,  30,  10,   0,   0,  10,  30,  20],
]

# King endgame: become active
PST_KING_EG = [
    [-50, -40, -30, -20, -20, -30, -40, -50],
    [-30, -20, -10,   0,   0, -10, -20, -30],
    [-30, -10,  20,  30,  30,  20, -10, -30],
    [-30, -10,  30,  40,  40,  30, -10, -30],
    [-30, -10,  30,  40,  40,  30, -10, -30],
    [-30, -10,  20,  30,  30,  20, -10, -30],
    [-30, -30,   0,   0,   0,   0, -30, -30],
    [-50, -30, -30, -30, -30, -30, -30, -50],
]

PIECE_PST = {
    "p": PST_PAWN,
    "h": PST_KNIGHT,
    "b": PST_BISHOP,
    "r": PST_ROOK,
    "q": PST_QUEEN,
}

# ---------------------------------------------------------------------------
# Endgame detection
# ---------------------------------------------------------------------------
_ENDGAME_MATERIAL_THRESHOLD = 1300  # queens gone or both sides have ≤ 1 minor

def _total_material(board):
    total = 0
    for row in board:
        for piece in row:
            if piece != _moves.EMPTY and piece[1] != "k":
                total += PIECE_VALUES[piece[1]]
    return total


def _is_endgame(board):
    return _total_material(board) < _ENDGAME_MATERIAL_THRESHOLD


# ---------------------------------------------------------------------------
# Pawn structure helpers
# ---------------------------------------------------------------------------
def _pawn_file_sets(board):
    """Return {col: count} maps for white and black pawns."""
    white = {}
    black = {}
    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            if piece == "wp":
                white[col] = white.get(col, 0) + 1
            elif piece == "bp":
                black[col] = black.get(col, 0) + 1
    return white, black


def _pawn_structure_score(board, color, white_files, black_files):
    """Doubled / isolated / passed pawn bonuses & penalties (centipawns)."""
    own_files = white_files if color == "w" else black_files
    opp_files = black_files if color == "w" else white_files
    score = 0

    for col, count in own_files.items():
        # Doubled pawns — penalty
        if count > 1:
            score -= 15 * (count - 1)

        # Isolated pawns — penalty
        neighbours = (col - 1, col + 1)
        if not any(n in own_files for n in neighbours):
            score -= 20

        # Passed pawns — bonus (no enemy pawn in front on same or adjacent files)
        if not any(opp_files.get(n, 0) > 0 for n in (col - 1, col, col + 1)):
            score += 30

    return score


# ---------------------------------------------------------------------------
# King safety
# ---------------------------------------------------------------------------
_PAWN_SHIELD_SQUARES_W = {
    # king col → expected pawn positions (row, col)
    6: [(6, 5), (6, 6), (6, 7), (5, 5), (5, 6), (5, 7)],
    7: [(6, 5), (6, 6), (6, 7)],
    0: [(6, 0), (6, 1), (6, 2)],
    1: [(6, 0), (6, 1), (6, 2)],
}

_PAWN_SHIELD_SQUARES_B = {
    6: [(1, 5), (1, 6), (1, 7), (2, 5), (2, 6), (2, 7)],
    7: [(1, 5), (1, 6), (1, 7)],
    0: [(1, 0), (1, 1), (1, 2)],
    1: [(1, 0), (1, 1), (1, 2)],
}


def _king_safety_score(board, color, endgame):
    """Pawn-shield bonus and open-file near king penalty."""
    if endgame:
        return 0  # king activity valued in endgame via PST

    king_sq = _moves.find_king(board, color)
    if king_sq is None:
        return -500

    king_row, king_col = king_sq
    pawn = color + "p"
    score = 0

    shields = (_PAWN_SHIELD_SQUARES_W if color == "w" else _PAWN_SHIELD_SQUARES_B)
    for sq in shields.get(king_col, []):
        if board[sq[0]][sq[1]] == pawn:
            score += 10

    # Penalise open file near king
    direction = -1 if color == "w" else 1
    for dc in (-1, 0, 1):
        c = king_col + dc
        if not (0 <= c < 8):
            continue
        has_own_pawn = any(
            board[r][c] == pawn for r in range(8)
        )
        if not has_own_pawn:
            score -= 15  # semi-open file near king

    return score


# ---------------------------------------------------------------------------
# Rook bonus
# ---------------------------------------------------------------------------
def _rook_file_bonus(board, color):
    """Bonus for rooks on open or semi-open files."""
    score = 0
    own_pawn = color + "p"
    opp_pawn = _moves.opponent(color) + "p"
    for row in range(8):
        for col in range(8):
            if board[row][col] != color + "r":
                continue
            col_pieces = [board[r][col] for r in range(8)]
            own_pawns = col_pieces.count(own_pawn)
            opp_pawns = col_pieces.count(opp_pawn)
            if own_pawns == 0 and opp_pawns == 0:
                score += 20  # fully open file
            elif own_pawns == 0:
                score += 10  # semi-open (only enemy pawn)
    return score


# ---------------------------------------------------------------------------
# Bishop pair
# ---------------------------------------------------------------------------
def _bishop_pair_bonus(board, color):
    count = sum(
        1
        for row in range(8)
        for col in range(8)
        if board[row][col] == color + "b"
    )
    return 30 if count >= 2 else 0


# ---------------------------------------------------------------------------
# PST lookup
# ---------------------------------------------------------------------------
def _pst_value(piece_kind, row, col, color, endgame):
    if piece_kind == "k":
        table = PST_KING_EG if endgame else PST_KING_MG
    else:
        table = PIECE_PST.get(piece_kind)
        if table is None:
            return 0

    # White reads the table top-to-bottom as rank 8 → rank 1;
    # Black reads the table mirrored (rank 1 → rank 8).
    effective_row = row if color == "w" else (7 - row)
    return table[effective_row][col]


# ---------------------------------------------------------------------------
# Main evaluation function
# ---------------------------------------------------------------------------
def evaluate(board, ai_color, en_passant_target=None, castling_rights=None):
    """
    Returns a score in centipawns from the perspective of `ai_color`.
    Positive = better for AI, negative = better for opponent.
    """
    endgame = _is_endgame(board)
    white_files, black_files = _pawn_file_sets(board)

    score = 0
    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            if piece == _moves.EMPTY:
                continue

            color = piece[0]
            kind = piece[1]
            sign = 1 if color == ai_color else -1

            # Material
            material = PIECE_VALUES[kind]

            # PST
            pst = _pst_value(kind, row, col, color, endgame)

            score += sign * (material + pst)

    # Pawn structure
    for color, sign in ((ai_color, 1), (_moves.opponent(ai_color), -1)):
        score += sign * _pawn_structure_score(board, color, white_files, black_files)
        score += sign * _king_safety_score(board, color, endgame)
        score += sign * _rook_file_bonus(board, color)
        score += sign * _bishop_pair_bonus(board, color)

    # Mobility bonus
    ai_opp = _moves.opponent(ai_color)
    ai_mobility = _count_pseudo_moves(board, ai_color)
    opp_mobility = _count_pseudo_moves(board, ai_opp)
    score += (ai_mobility - opp_mobility) * 3

    # Tempo
    score += 10

    return score


def _count_pseudo_moves(board, color):
    total = 0
    for row in range(8):
        for col in range(8):
            if _moves.piece_color(board[row][col]) == color:
                total += len(_moves.pseudo_legal_moves(board, row, col))
    return total
