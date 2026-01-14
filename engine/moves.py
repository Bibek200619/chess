from dataclasses import dataclass


EMPTY = "__"

STARTING_BOARD = [
    ["br", "bh", "bb", "bq", "bk", "bb", "bh", "br"],
    ["bp", "bp", "bp", "bp", "bp", "bp", "bp", "bp"],
    [EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY],
    [EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY],
    [EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY],
    [EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY],
    ["wp", "wp", "wp", "wp", "wp", "wp", "wp", "wp"],
    ["wr", "wh", "wb", "wq", "wk", "wb", "wh", "wr"],
]


@dataclass
class MoveResult:
    captured: str | None = None
    captured_square: tuple[int, int] | None = None
    en_passant_target: tuple[int, int] | None = None
    promoted: bool = False
    castled: bool = False


def new_board():
    return [row[:] for row in STARTING_BOARD]


def piece_color(piece):
    return None if piece == EMPTY else piece[0]


def opponent(color):
    return "b" if color == "w" else "w"


def color_name(color):
    return "White" if color == "w" else "Black"


def in_bounds(row, col):
    return 0 <= row < 8 and 0 <= col < 8


def legal_moves(board, row, col, en_passant_target=None, castling_rights=None):
    piece = board[row][col]
    if piece == EMPTY:
        return []

    color = piece[0]
    moves = pseudo_legal_moves(board, row, col, en_passant_target, castling_rights)
    return [
        target
        for target in moves
        if not would_leave_king_in_check(board, (row, col), target, color, en_passant_target)
    ]


def pseudo_legal_moves(board, row, col, en_passant_target=None, castling_rights=None):
    piece = board[row][col]
    if piece == EMPTY:
        return []

    kind = piece[1]
    color = piece[0]

    if kind == "p":
        return pawn_moves(board, row, col, color, en_passant_target)
    if kind == "h":
        return horse_moves(board, row, col, color)
    if kind == "b":
        return sliding_moves(board, row, col, color, [(-1, -1), (-1, 1), (1, -1), (1, 1)])
    if kind == "r":
        return sliding_moves(board, row, col, color, [(-1, 0), (1, 0), (0, -1), (0, 1)])
    if kind == "q":
        return sliding_moves(
            board,
            row,
            col,
            color,
            [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)],
        )
    if kind == "k":
        return king_moves(board, row, col, color, castling_rights)

    return []


def pawn_moves(board, row, col, color, en_passant_target=None):
    moves = []
    direction = -1 if color == "w" else 1
    start_row = 6 if color == "w" else 1
    one_step = row + direction
    two_step = row + (direction * 2)

    if in_bounds(one_step, col) and board[one_step][col] == EMPTY:
        moves.append((one_step, col))
        if row == start_row and in_bounds(two_step, col) and board[two_step][col] == EMPTY:
            moves.append((two_step, col))

    for capture_col in (col - 1, col + 1):
        if not in_bounds(one_step, capture_col):
            continue
        target = board[one_step][capture_col]
        if target != EMPTY and piece_color(target) != color and target[1] != "k":
            moves.append((one_step, capture_col))
        elif en_passant_target == (one_step, capture_col):
            side_piece = board[row][capture_col]
            if side_piece == opponent(color) + "p":
                moves.append((one_step, capture_col))

    return moves


def horse_moves(board, row, col, color):
    moves = []
    for row_delta, col_delta in ((2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)):
        target_row = row + row_delta
        target_col = col + col_delta
        if can_land_on(board, target_row, target_col, color):
            moves.append((target_row, target_col))
    return moves


def king_moves(board, row, col, color, castling_rights=None):
    moves = []
    for row_delta in (-1, 0, 1):
        for col_delta in (-1, 0, 1):
            if row_delta == 0 and col_delta == 0:
                continue
            target_row = row + row_delta
            target_col = col + col_delta
            if can_land_on(board, target_row, target_col, color):
                moves.append((target_row, target_col))
    moves.extend(castling_moves(board, row, col, color, castling_rights))
    return moves


def castling_moves(board, row, col, color, castling_rights=None):
    if not castling_rights:
        return []

    home_row = 7 if color == "w" else 0
    if row != home_row or col != 4 or board[row][col] != color + "k":
        return []
    if is_in_check(board, color):
        return []

    moves = []
    enemy = opponent(color)
    if (
        color + "k" in castling_rights
        and board[home_row][7] == color + "r"
        and board[home_row][5] == EMPTY
        and board[home_row][6] == EMPTY
        and not is_square_attacked(board, (home_row, 5), enemy)
        and not is_square_attacked(board, (home_row, 6), enemy)
    ):
        moves.append((home_row, 6))

    if (
        color + "q" in castling_rights
        and board[home_row][0] == color + "r"
        and board[home_row][1] == EMPTY
        and board[home_row][2] == EMPTY
        and board[home_row][3] == EMPTY
        and not is_square_attacked(board, (home_row, 3), enemy)
        and not is_square_attacked(board, (home_row, 2), enemy)
    ):
        moves.append((home_row, 2))

    return moves


def sliding_moves(board, row, col, color, directions):
    moves = []
    for row_delta, col_delta in directions:
        target_row = row + row_delta
        target_col = col + col_delta
        while in_bounds(target_row, target_col):
            target = board[target_row][target_col]
            if target == EMPTY:
                moves.append((target_row, target_col))
            elif piece_color(target) != color and target[1] != "k":
                moves.append((target_row, target_col))
                break
            else:
                break
            target_row += row_delta
            target_col += col_delta
    return moves


def can_land_on(board, row, col, color):
    if not in_bounds(row, col):
        return False
    target = board[row][col]
    return target == EMPTY or (piece_color(target) != color and target[1] != "k")


def move_piece(board, source, target, en_passant_target=None):
    source_row, source_col = source
    target_row, target_col = target
    piece = board[source_row][source_col]
    captured = board[target_row][target_col]
    captured_square = target if captured != EMPTY else None

    if is_en_passant(board, source, target, en_passant_target):
        captured_square = (source_row, target_col)
        captured = board[captured_square[0]][captured_square[1]]
        board[captured_square[0]][captured_square[1]] = EMPTY

    castled = piece[1] == "k" and abs(target_col - source_col) == 2
    if castled:
        rook_source_col = 7 if target_col > source_col else 0
        rook_target_col = 5 if target_col > source_col else 3
        board[source_row][rook_target_col] = board[source_row][rook_source_col]
        board[source_row][rook_source_col] = EMPTY

    promoted_piece = promote_if_needed(piece, target_row)
    board[target_row][target_col] = promoted_piece
    board[source_row][source_col] = EMPTY

    new_en_passant_target = None
    if piece[1] == "p" and abs(target_row - source_row) == 2:
        new_en_passant_target = ((source_row + target_row) // 2, source_col)

    return MoveResult(
        captured=captured if captured != EMPTY else None,
        captured_square=captured_square,
        en_passant_target=new_en_passant_target,
        promoted=promoted_piece != piece,
        castled=castled,
    )


def is_en_passant(board, source, target, en_passant_target):
    source_row, source_col = source
    target_row, target_col = target
    piece = board[source_row][source_col]
    return (
        piece[1] == "p"
        and en_passant_target == target
        and source_col != target_col
        and board[target_row][target_col] == EMPTY
    )


def promote_if_needed(piece, row):
    if piece == "wp" and row == 0:
        return "wq"
    if piece == "bp" and row == 7:
        return "bq"
    return piece


def is_in_check(board, color):
    king_square = find_king(board, color)
    if king_square is None:
        return True
    return is_square_attacked(board, king_square, opponent(color))


def find_king(board, color):
    king = color + "k"
    for row in range(8):
        for col in range(8):
            if board[row][col] == king:
                return row, col
    return None


def is_square_attacked(board, square, attacker_color):
    row, col = square
    pawn_direction = -1 if attacker_color == "w" else 1
    for attack_col in (col - 1, col + 1):
        pawn_row = row - pawn_direction
        if in_bounds(pawn_row, attack_col) and board[pawn_row][attack_col] == attacker_color + "p":
            return True

    for row_delta, col_delta in ((2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)):
        if in_bounds(row + row_delta, col + col_delta) and board[row + row_delta][col + col_delta] == attacker_color + "h":
            return True

    if ray_attacks(board, square, attacker_color, [(-1, -1), (-1, 1), (1, -1), (1, 1)], {"b", "q"}):
        return True
    if ray_attacks(board, square, attacker_color, [(-1, 0), (1, 0), (0, -1), (0, 1)], {"r", "q"}):
        return True

    for row_delta in (-1, 0, 1):
        for col_delta in (-1, 0, 1):
            if row_delta == 0 and col_delta == 0:
                continue
            target_row = row + row_delta
            target_col = col + col_delta
            if in_bounds(target_row, target_col) and board[target_row][target_col] == attacker_color + "k":
                return True

    return False


def ray_attacks(board, square, attacker_color, directions, attacking_kinds):
    row, col = square
    for row_delta, col_delta in directions:
        target_row = row + row_delta
        target_col = col + col_delta
        while in_bounds(target_row, target_col):
            piece = board[target_row][target_col]
            if piece != EMPTY:
                if piece[0] == attacker_color and piece[1] in attacking_kinds:
                    return True
                break
            target_row += row_delta
            target_col += col_delta
    return False


def would_leave_king_in_check(board, source, target, color, en_passant_target=None):
    test_board = [row[:] for row in board]
    move_piece(test_board, source, target, en_passant_target)
    return is_in_check(test_board, color)


def has_legal_moves(board, color, en_passant_target=None, castling_rights=None):
    for row in range(8):
        for col in range(8):
            if piece_color(board[row][col]) == color and legal_moves(board, row, col, en_passant_target, castling_rights):
                return True
    return False


def game_status(board, color_to_move, en_passant_target=None, castling_rights=None):
    in_check = is_in_check(board, color_to_move)
    can_move = has_legal_moves(board, color_to_move, en_passant_target, castling_rights)
    if in_check and not can_move:
        return "checkmate"
    if not in_check and not can_move:
        return "stalemate"
    if in_check:
        return "check"
    return "playing"
