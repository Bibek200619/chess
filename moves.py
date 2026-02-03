import turtle

pen = turtle.Turtle()
pen.hideturtle()
pen.penup()

legal_moves = []

def highlight_next_move(piece,raw,col,turn, board):
    if piece in turn:
        highlight(piece, raw, col, board)

def highlight(piece, raw, col, board):
    pen.clear()
    current_piece = "b" if piece[0] == "b" else "w"

    if piece in ["bp", "wp"]:
        if (piece == "wp" and raw == 6) or (piece == "bp" and raw == 1):
            next_raw = raw + 2 if piece == "bp" else raw - 2

            not_moved = True
        else:
            next_raw = raw + 1 if piece == "bp" else raw - 1
            not_moved = False

        if next_raw < 0 or next_raw >= 8:
            return


        x = -240 + (col * 60)
        y = 240 - (next_raw * 60)
        paint_highlights(x, y-60) if piece == "wp" else paint_highlights(x, y+60)
        pawn_highlights(x, y, not_moved, piece)


    elif piece[1] == 'b' :
        next_moves = bishop_highlights(raw, col, board,current_piece)

        display_highlights( next_moves)

    elif piece[1] == 'r':
        next_moves = rook_highlights(raw, col,board, current_piece)

        display_highlights( next_moves)

    elif piece[1] == 'q':
        next_moves = queen_highlights(raw, col, board,current_piece)

        display_highlights(next_moves)

    elif piece[1] == 'h':
        next_moves = horse_highlights(raw, col,board,current_piece)

        display_highlights( next_moves)

    elif piece[1] == 'k':
        next_moves = king_highlights(raw, col, board,current_piece)

        display_highlights( next_moves)

def display_highlights( next_moves):
    for raw, col in next_moves:
        x = -240 + (col * 60)
        y = 240 - (raw * 60)
        paint_highlights(x, y)
        paint_highlights(x, y)

def king_highlights(initial_raw, initial_col, board,piece):
    next_moves = []
    direction = [(1, 1),
           (1, -1),
           (1, 0),
           (-1, 0),
           (-1, 1),
           (-1, -1),
           (0, -1,),
           (0, 1,),]
    for raw,col in direction:
        raw = initial_raw + raw
        col = initial_col + col
        if 0 <= raw < 8 and 0 <= col < 8:
            current_piece = board[raw][col]
            if board[raw][col] == "__":
                next_moves.append((raw, col))
            elif current_piece[0] != piece[0]:
                next_moves.append((raw, col))
    print(next_moves)
    return next_moves


def horse_highlights(initial_raw, initial_col, board,piece):
    next_moves = []
    direction = [(2, 1),
           (2, -1),
           (-2, 1),
           (-2, -1),
           (1, 2),
           (1, -2),
           (-1, -2),
           (-1, 2),
           ]
    for raw, col in direction:
        print(piece)
        raw = initial_raw + raw
        col = initial_col + col
        if 0 <= raw < 8 and 0 <= col < 8:
            current_piece = board[raw][col]
            if board[raw][col] == "__" :
                next_moves.append((raw, col))
            elif current_piece[0] != piece[0]:
                next_moves.append((raw, col))
    return next_moves


def pawn_highlights(x, y, not_moved, piece):

    if not_moved:
        paint_highlights(x, y )
    else:
        paint_highlights(x, y)
    paint_highlights(x, y-120) if piece == "wp" else paint_highlights(x, y+120)


def queen_highlights(initial_raw, initial_col, board,piece):
    next_moves = []
    sign = {"-": -1, "+": +1}
    for ch1, ch2 in [["-", "+"], ["+", "-"], ["+", "+"], ["-", "-"]]:
        raw = initial_raw
        col = initial_col
        for x in range(0, 8):
            raw = raw + sign[ch1]
            col = col + sign[ch2]
            if 0 <= raw < 8 and 0 <= col < 8:
                current_piece = board[raw][col]
                if board[raw][col] == "__":
                    next_moves.append([raw, col])
                elif current_piece[0] != piece:
                    next_moves.append([raw, col])
                    break
                else:
                    break
            else:
                break
    directions = [
        (-1, 0),  # up
        (1, 0),  # down
        (0, -1),  # left
        (0, 1)  # right
    ]

    for dr, dc in directions:
        raw = initial_raw
        col = initial_col

        for x in range(0, 8):
            raw += dr
            col += dc

            if 0 <= raw < 8 and 0 <= col < 8:
                current_piece = board[raw][col]
                if board[raw][col] == "__":
                    print(piece, current_piece[0])
                    print(current_piece[0] != piece)
                    next_moves.append([raw, col])
                elif current_piece[0] != piece:
                    next_moves.append([raw, col])
                    break
                else:
                    break
            else:
                break
    return next_moves


def rook_highlights(initial_raw, initial_col, board, piece):
    next_moves = []
    directions = [
        (-1, 0),  # up
        (1, 0),   # down
        (0, -1),  # left
        (0, 1)    # right
    ]

    for dr, dc in directions:
        raw = initial_raw
        col = initial_col

        for x in range(0, 8):
            raw += dr
            col += dc

            if 0 <= raw < 8 and 0 <= col < 8:
                current_piece = board[raw][col]
                if board[raw][col] == "__":
                    next_moves.append([raw, col])
                elif current_piece[0] != piece:
                    next_moves.append([raw, col])
                    break
                else:
                    break
            else:
                break

    return next_moves


def bishop_highlights(initial_raw, initial_col, board,piece):
    next_moves = []
    sign = {"-": -1, "+": +1}
    for ch1, ch2 in [["-", "+"], ["+", "-"], ["+", "+"], ["-", "-"]]:
        raw = initial_raw
        col = initial_col
        for x in range(0, 8):
            raw = raw + sign[ch1]
            col = col + sign[ch2]
            if 0 <= raw < 8 and 0 <= col < 8:
                current_piece = board[raw][col]
                if board[raw] [col] == "__" :
                    next_moves.append([raw, col])
                elif current_piece[0] != piece:
                    next_moves.append([raw, col])
                    break
                else:
                    break
            else:
                break
    return next_moves


def paint_highlights(x, y):
    if 180 >= x >= -240 and 240 >= y >= -180:
        legal_moves.append(location_converter(x, y))
        pen.penup()
        pen.goto(x, y)
        pen.pendown()
        pen.pensize(5)
        pen.color("red")
        for _ in range(4):
            pen.forward(60)
            pen.right(90)

def location_converter(x, y):
    raw   = (240 - y) // 60
    col   = (240 + x) // 60
    return [raw, col]

def refresh():
    legal_moves.clear()

def is_valid(raw, col):
    print(raw, col)
    print(legal_moves)
    move = [raw, col]
    if move in legal_moves :
        legal_moves.clear()
        return True
    else:
        legal_moves.clear()
        return False
