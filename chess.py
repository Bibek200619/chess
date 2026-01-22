import turtle
import time

# ============================================================
#   TURTLE CHESS - VERSION A (FULL RULES, NO AI)
#   PART 1 / 3  —  BOARD ENGINE + UTILITIES
# ============================================================

# --------- Screen Setup ---------
screen = turtle.Screen()
screen.title("Full Chess in Turtle - Version A")
screen.setup(width=800, height=800)
screen.tracer(0)

pen = turtle.Turtle()
pen.hideturtle()
pen.penup()
pen.speed(0)

SQ = 80  # square size

# --------- Board Representation ---------
# "--" = empty, otherwise "wp", "wn", "bk", etc.
board = [
    ["br","bn","bb","bq","bk","bb","bn","br"],
    ["bp","bp","bp","bp","bp","bp","bp","bp"],
    ["--","--","--","--","--","--","--","--"],
    ["--","--","--","--","--","--","--","--"],
    ["--","--","--","--","--","--","--","--"],
    ["--","--","--","--","--","--","--","--"],
    ["wp","wp","wp","wp","wp","wp","wp","wp"],
    ["wr","wn","wb","wq","wk","wb","wn","wr"]
]

turn = "w"       # whose turn
selected = None  # selected square
legal_moves = [] # legal moves for selected piece

# Used to track castling rights
castle_rights = {
    "w_king_moved": False,
    "w_rrook_moved": False,
    "w_lrook_moved": False,
    "b_king_moved": False,
    "b_rrook_moved": False,
    "b_lrook_moved": False
}

# En-passant tracking
ep_square = None  # stores a tuple like (r, c)

# ============================================================
#   DRAWING FUNCTIONS
# ============================================================

def draw_square(x, y, color):
    pen.goto(x, y)
    pen.color("black", color)
    pen.begin_fill()
    for _ in range(4):
        pen.forward(SQ)
        pen.right(90)
    pen.end_fill()

def draw_board():
    colors = ["#EEEED2", "#769656"]
    for r in range(8):
        for c in range(8):
            x = -320 + c * SQ
            y = 320 - r * SQ
            draw_square(x, y, colors[(r + c) % 2])

def draw_pieces():
    pen.color("black")
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p != "--":
                x = -320 + c * SQ + 20
                y = 320 - r * SQ - 60
                pen.goto(x, y)
                pen.write(p, font=("Arial", 30, "bold"))

def highlight_square(r, c, color="yellow"):
    x = -320 + c * SQ
    y = 320 - r * SQ
    pen.goto(x, y)
    pen.color(color)
    pen.width(4)
    pen.pendown()
    for _ in range(4):
        pen.forward(SQ)
        pen.right(90)
    pen.penup()
    pen.width(1)

def refresh():
    pen.clear()
    draw_board()
    draw_pieces()

    # highlight legal moves
    for (r, c) in legal_moves:
        highlight_square(r, c, "blue")

    # highlight selected square
    if selected:
        highlight_square(selected[0], selected[1], "red")

    screen.update()

# ============================================================
#   HELPER / UTILITY FUNCTIONS
# ============================================================

def inside(r, c):
    """Check inside board."""
    return 0 <= r < 8 and 0 <= c < 8

def clone(b):
    return [row.copy() for row in b]

def find_king(color, b):
    """Return (r, c) of king for given color."""
    for r in range(8):
        for c in range(8):
            if b[r][c] == color + "k":
                return r, c
    return None

# ============================================================
#   ATTACK DETECTION (USED FOR CHECK & LEGAL MOVE FILTERING)
# ============================================================

def square_attacked(r, c, color, b):
    enemy = "b" if color == "w" else "w"

    # Knight attack
    knight_steps = [(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)]
    for dr, dc in knight_steps:
        nr, nc = r + dr, c + dc
        if inside(nr, nc) and b[nr][nc] == enemy + "n":
            return True

    # Pawn attack
    step = -1 if color == "w" else 1
    for dc in [-1, 1]:
        nr, nc = r + step, c + dc
        if inside(nr, nc) and b[nr][nc] == enemy + "p":
            return True

    # Rook / Queen attack
    for dr, dc in [(1,0),(-1,0),(0,1),(0,-1)]:
        nr, nc = r + dr, c + dc
        while inside(nr, nc):
            piece = b[nr][nc]
            if piece != "--":
                if piece[0] == enemy and piece[1] in ("r", "q"):
                    return True
                break
            nr += dr
            nc += dc

    # Bishop / Queen attack
    for dr, dc in [(1,1),(1,-1),(-1,1),(-1,-1)]:
        nr, nc = r + dr, c + dc
        while inside(nr, nc):
            piece = b[nr][nc]
            if piece != "--":
                if piece[0] == enemy and piece[1] in ("b", "q"):
                    return True
                break
            nr += dr
            nc += dc

    # King attack
    for dr, dc in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
        nr, nc = r + dr, c + dc
        if inside(nr, nc) and b[nr][nc] == enemy + "k":
            return True

    return False
# ============================================================
#   MOVE GENERATION (for each piece)
# ============================================================

def generate_moves_for_piece(r, c, b, color):
    piece = b[r][c]
    if piece == "--" or piece[0] != color:
        return []

    kind = piece[1]
    moves = []

    # ---------- Pawn ----------
    if kind == "p":
        step = -1 if color == "w" else 1

        # forward move
        if inside(r + step, c) and b[r + step][c] == "--":
            moves.append((r + step, c))

            # double move
            start_row = 6 if color == "w" else 1
            if r == start_row and b[r + 2*step][c] == "--":
                moves.append((r + 2*step, c))

        # capture left/right
        for dc in (-1, 1):
            nr, nc = r + step, c + dc
            if inside(nr, nc) and b[nr][nc] != "--" and b[nr][nc][0] != color:
                moves.append((nr, nc))

        # en-passant
        global ep_square
        if ep_square:
            er, ec = ep_square
            if r == er and abs(c - ec) == 1:
                moves.append((r + step, ec))

    # ---------- Knight ----------
    elif kind == "n":
        for dr, dc in [(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)]:
            nr, nc = r + dr, c + dc
            if inside(nr, nc):
                if b[nr][nc] == "--" or b[nr][nc][0] != color:
                    moves.append((nr, nc))

    # ---------- King ----------
    elif kind == "k":
        steps = [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]
        for dr, dc in steps:
            nr, nc = r + dr, c + dc
            if inside(nr, nc):
                if b[nr][nc] == "--" or b[nr][nc][0] != color:
                    moves.append((nr, nc))

        # castling
        moves.extend(generate_castling(r, c, b, color))

    # ---------- Rook / Bishop / Queen ----------
    elif kind in ("r", "b", "q"):

        directions = []
        if kind == "r":
            directions = [(1,0),(-1,0),(0,1),(0,-1)]
        if kind == "b":
            directions = [(1,1),(1,-1),(-1,1),(-1,-1)]
        if kind == "q":
            directions = [
                (1,0),(-1,0),(0,1),(0,-1),
                (1,1),(1,-1),(-1,1),(-1,-1)
            ]

        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            while inside(nr, nc):
                if b[nr][nc] == "--":
                    moves.append((nr, nc))
                else:
                    if b[nr][nc][0] != color:
                        moves.append((nr, nc))
                    break
                nr += dr
                nc += dc

    return moves


# ============================================================
#   CASTLING LOGIC
# ============================================================

def generate_castling(r, c, b, color):
    """Return available castling moves for king."""
    moves = []

    if color == "w":
        king_moved = castle_rights["w_king_moved"]
        rrook_moved = castle_rights["w_rrook_moved"]
        lrook_moved = castle_rights["w_lrook_moved"]
    else:
        king_moved = castle_rights["b_king_moved"]
        rrook_moved = castle_rights["b_rrook_moved"]
        lrook_moved = castle_rights["b_lrook_moved"]

    # king must not have moved
    if king_moved:
        return moves

    row = 7 if color == "w" else 0

    # ----- King-side castle -----
    if not rrook_moved:
        if b[row][5] == "--" and b[row][6] == "--":
            if (not square_attacked(row, 4, color, b) and
                not square_attacked(row, 5, color, b) and
                not square_attacked(row, 6, color, b)):
                moves.append((row, 6))

    # ----- Queen-side castle -----
    if not lrook_moved:
        if b[row][1] == "--" and b[row][2] == "--" and b[row][3] == "--":
            if (not square_attacked(row, 2, color, b) and
                not square_attacked(row, 3, color, b) and
                not square_attacked(row, 4, color, b)):
                moves.append((row, 2))

    return moves


# ============================================================
#   MOVE FILTERING (ILLEGAL MOVES)
# ============================================================

def generate_legal_moves(r, c, b, color):
    """Generate all moves and filter out illegal ones (king safety)."""
    raw_moves = generate_moves_for_piece(r, c, b, color)
    legal = []

    for (mr, mc) in raw_moves:
        temp = clone(b)

        # store piece
        moving_piece = temp[r][c]

        # en-passant handling
        global ep_square
        if moving_piece[1] == "p" and ep_square:
            er, ec = ep_square
            if mr == er + (-1 if color == "w" else 1) and mc == ec:
                temp[er][ec] = "--"  # capture pawn

        # make move
        temp[mr][mc] = temp[r][c]
        temp[r][c] = "--"

        # castling rook moves
        if moving_piece[1] == "k":
            if (mc - c == 2):  # king-side
                temp[r][5] = temp[r][7]
                temp[r][7] = "--"
            if (mc - c == -2):  # queen-side
                temp[r][3] = temp[r][0]
                temp[r][0] = "--"

        kr, kc = find_king(color, temp)
        if not square_attacked(kr, kc, color, temp):
            legal.append((mr, mc))

    return legal


# ============================================================
#   ENUMERATE ALL MOVES (CHECKMATE DETECTION)
# ============================================================

def any_legal_moves(color, b):
    for r in range(8):
        for c in range(8):
            if b[r][c] != "--" and b[r][c][0] == color:
                if generate_legal_moves(r, c, b, color):
                    return True
    return False


# ============================================================
#   MOUSE HANDLING + MOVE EXECUTION
# ============================================================

def get_square_from_xy(x, y):
    c = int((x + 320) // SQ)
    r = int((320 - y) // SQ)
    if inside(r, c):
        return (r, c)
    return None

def execute_move(sr, sc, tr, tc):
    """Executes a move on the real board and updates rights."""
    global ep_square

    piece = board[sr][sc]
    color = piece[0]
    kind = piece[1]

    # Clear en-passant first
    ep_square = None

    # Pawn double step = new EP square
    if kind == "p" and abs(sr - tr) == 2:
        ep_square = ((sr + tr)//2, sc)

    # En-passant capture
    if kind == "p" and sc != tc and board[tr][tc] == "--":
        dr = 1 if color == "w" else -1
        board[tr + dr][tc] = "--"

    # Execute move
    board[tr][tc] = board[sr][sc]
    board[sr][sc] = "--"

    # Pawn promotion
    if kind == "p" and (tr == 0 or tr == 7):
        board[tr][tc] = color + "q"  # promote to queen

    # Castling rook moves
    if kind == "k":
        if tc - sc == 2:  # king-side
            board[tr][5] = board[tr][7]
            board[tr][7] = "--"
        elif tc - sc == -2:  # queen-side
            board[tr][3] = board[tr][0]
            board[tr][0] = "--"

    update_castling_rights(sr, sc, piece)


def update_castling_rights(r, c, piece):
    color = piece[0]
    kind = piece[1]

    if color == "w":
        if kind == "k":
            castle_rights["w_king_moved"] = True
        if kind == "r":
            if c == 0 and r == 7:
                castle_rights["w_lrook_moved"] = True
            if c == 7 and r == 7:
                castle_rights["w_rrook_moved"] = True

    else:
        if kind == "k":
            castle_rights["b_king_moved"] = True
        if kind == "r":
            if c == 0 and r == 0:
                castle_rights["b_lrook_moved"] = True
            if c == 7 and r == 0:
                castle_rights["b_rrook_moved"] = True

# ============================================================
#   CLICK HANDLER + TURN MANAGEMENT
# ============================================================

def click_handler(x, y):
    global selected, legal_moves, turn

    sq = get_square_from_xy(x, y)
    if not sq:
        return

    r, c = sq

    # --- Selecting first square ---
    if selected is None:
        if board[r][c] != "--" and board[r][c][0] == turn:
            selected = (r, c)
            legal_moves = generate_legal_moves(r, c, board, turn)
            refresh()
        return

    # --- Selecting destination ---
    sr, sc = selected

    if (r, c) in legal_moves:
        # Execute the move
        execute_move(sr, sc, r, c)

        # Switch turn
        turn = "b" if turn == "w" else "w"

        # Check for checkmate
        if checkmate_check(turn):
            refresh()
            time.sleep(1)
            screen.textinput("Game Over", f"Checkmate! {turn.upper()} loses. Restart program to play again.")
            turtle.bye()
            return

    # Deselect piece after attempting the move
    selected = None
    legal_moves = []
    refresh()


# ============================================================
#   CHECKMATE & CHECK DETECTION
# ============================================================

def is_in_check(color, b):
    kr, kc = find_king(color, b)
    return square_attacked(kr, kc, color, b)

def checkmate_check(color):
    # If king not in check → no checkmate possible
    if not is_in_check(color, board):
        return False

    # If king in check AND no legal moves → checkmate
    if not any_legal_moves(color, board):
        return True

    return False


# ============================================================
#   MAIN LOOP INITIALIZATION
# ============================================================

def start_game():
    refresh()
    screen.onclick(click_handler)
    turtle.mainloop()


# ============================================================
#   START PROGRAM
# ============================================================

start_game()
