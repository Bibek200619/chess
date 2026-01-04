import turtle

screen = turtle.Screen()
screen.title("Chess Game")
screen.setup(600, 600)
screen.tracer(0)

pen = turtle.Turtle()
pen.hideturtle()
pen.penup()


def highlight_next_move(piece,raw,col,turn):
    if piece in turn:
        highlight(piece, raw, col)

def highlight(piece, raw, col):
    pen.clear()
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



    elif piece in ["bb","wb"] :
        next_moves = bishop_highlights(raw, col)

        for raw, col in next_moves:
            x = -240 + (col * 60)
            y = 240 - (raw * 60)
            paint_highlights(x, y)
        paint_highlights(x, y)


    elif piece in ["wr","br"]:
        next_moves = rook_highlights(raw, col)

        for raw, col in next_moves:
            x = -240 + (col * 60)
            y = 240 - (raw * 60)
            paint_highlights(x, y)
        paint_highlights(x, y)

    elif piece in ["wq","bq"]:
        next_moves = queen_highlights(raw, col)
        for raw, col in next_moves:
            x = -240 + (col * 60)
            y = 240 - (raw * 60)
            paint_highlights(x, y)

    elif piece in ["wh", "bh"]:
        x = -240 + (col * 60)
        y = 240 - (raw * 60)
        paint_highlights(x - 60, y + 120) if piece == "wh" else paint_highlights(x + 60 , y - 120)
        paint_highlights(x + 60, y + 120) if piece == "wh" else paint_highlights(x - 60, y - 120)
        paint_highlights(x - 60, y - 120) if piece == "wh" else paint_highlights(x + 60 , y + 120)
        paint_highlights(x + 60, y - 120) if piece == "wh" else paint_highlights(x - 60, y + 120)
        paint_highlights(x - 120, y + 60) if piece == "wh" else paint_highlights(x + 120, y - 60)
        paint_highlights(x - 120, y - 60) if piece == "wh" else paint_highlights(x + 120, y + 60)
        paint_highlights(x + 120, y - 60) if piece == "wh" else paint_highlights(x - 120, y + 60)
        paint_highlights(x + 120, y + 60) if piece == "wh" else paint_highlights(x - 120, y - 60)
        paint_highlights(x,y)

    elif piece in ["wk", "bk"]:
        x = -240 + (col * 60)
        y = 240 - (raw * 60)
        paint_highlights(x + 60, y + 60) if piece == "wk" else paint_highlights(x - 60, y - 60)
        paint_highlights(x - 60, y - 60) if piece == "wk" else paint_highlights(x + 60, y + 60)
        paint_highlights(x - 60, y + 60) if piece == "wk" else paint_highlights(x + 60, y - 60)
        paint_highlights(x + 60, y - 60) if piece == "wk" else paint_highlights(x - 60, y + 60)
        paint_highlights(x + 60, y ) if piece == "wk" else paint_highlights(x - 60, y )
        paint_highlights(x - 60, y ) if piece == "wk" else paint_highlights(x + 60, y )
        paint_highlights(x , y + 60) if piece == "wk" else paint_highlights(x , y - 60)
        paint_highlights(x , y - 60) if piece == "wk" else paint_highlights(x , y + 60)
        paint_highlights(x,y)



def horse_highlights(initial_raw, initial_col):
    next_moves = []
    sign_raw = {"-" : -2, "+" : +2}
    sign_col = {"-" : -1, "+" : -1}
    for ch1, ch2 in [["-", "+"], ["+", "-"], ["+", "+"], ["-", "-"]]:
        raw = initial_raw
        col = initial_col
        for _ in range(4):
            raw += sign_raw[ch1]
            col += sign_col[ch2]


def pawn_highlights(x, y, not_moved, piece):

    if not_moved:
        paint_highlights(x, y )
    else:
        paint_highlights(x, y)
    paint_highlights(x, y-120) if piece == "wp" else paint_highlights(x, y+120)


def queen_highlights(initial_raw, initial_col):
    next_moves = bishop_highlights(initial_raw, initial_col)
    for move in range(0, 8):
        next_moves.append([move, initial_col])
        next_moves.append([initial_raw, move])
    next_moves.remove([initial_raw, initial_col])
    next_moves.remove([initial_raw, initial_col])
    return next_moves


def rook_highlights( initial_raw, initial_col):
    next_moves = []
    for move in range(0, 8):
        next_moves.append([move, initial_col])
        next_moves.append([initial_raw, move])
    next_moves.remove([initial_raw, initial_col])
    next_moves.remove([initial_raw, initial_col])
    return next_moves

def bishop_highlights(initial_raw, initial_col):
    next_moves = []
    sign = {"-": -1, "+": +1}
    for ch1, ch2 in [["-", "+"], ["+", "-"], ["+", "+"], ["-", "-"]]:
        raw = initial_raw
        col = initial_col
        for x in range(0, 8):
            raw = raw + sign[ch1]
            col = col + sign[ch2]
            if 0 <= raw < 8 and 0 <= col < 8:
                next_moves.append([raw, col])
            else:
                break
    return next_moves


def paint_highlights(x, y):
    print(x, y)
    print(180 >= x >= -240 and 240 >= y >= -180)
    if 180 >= x >= -240 and 240 >= y >= -180:
        pen.penup()
        pen.goto(x, y)
        pen.pendown()
        pen.pensize(5)
        pen.color("red")
        for _ in range(4):
            pen.forward(60)
            pen.right(90)
