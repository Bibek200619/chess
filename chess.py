import turtle

screen = turtle.Screen()
screen.title("Chess Game")
screen.setup(600, 600)
screen.tracer(0)

pen = turtle.Turtle()
pen.hideturtle()
pen.penup()

board = [["br","bh","bb","bq","bk","bb","bh","br"],
         ["bp","bp","bp","bp","bp","bp","bp","bp"],
         ["__","__","__","__","__","__","__","__"],
         ["__","__","__","__","__","__","__","__"],
         ["__","__","__","__","__","__","__","__"],
         ["__","__","__","__","__","__","__","__"],
         ["wp","wp","wp","wp","wp","wp","wp","wp"],
         ["wr","wh","wb","wq","wk","wb","wh","wr"],
         ]

white_piece = ["wp","wr","wh","wb","wq","wk","wb","wh","wr"]
black_piece = ["br","bh","bb","bq","bk","bb","bh","br","bp"]

left = -240
right = 240

turns = [white_piece, black_piece]
selected = None
count = 0

def main():
    chess_board()
    pieces_location()
    screen.onclick(move_piece)
    screen.listen()


def small_square(x,y,colour):
    pen.penup()
    pen.goto(x,y)
    pen.pendown()
    pen.color(colour)
    pen.pencolor("Black")
    pen.begin_fill()
    for _ in range(4):
        pen.forward(60)
        pen.right(90)
    pen.end_fill()

def chess_board():
    colours = ["black", "white"]

    for raw in range(8):
        for col in range(8):
            x = left + 60 * col
            y = right - 60 * raw
            colour = colours[(raw + col) % 2]
            small_square(x,y,colour)

def pieces_location():
    initial_x = -215
    initial_y = 205
    for raw in range(8):
        for col in range(8):
            x = initial_x + 60 * col
            y = initial_y - 60 * raw
            put_piece(x, y, raw, col)

def put_piece(x,y,raw,col):
    pen.penup()
    pen.goto(x,y)
    pen.pendown()
    if board[raw][col] != "__" :
        pen.color("#99FFEA") if board[raw][col] in white_piece else pen.color("#8E15AB")
        pen.write((board[raw][col]),font=("Arial",12,"bold"))


def move_piece(x , y ):
    global selected, count
    turn = turns[0 if count % 2 == 0 else 1]

    square = xy_location(x,y)
    if square == None:
        return
    else:
        raw, col = square
        highlight_next_move(board[raw][col], raw, col,turn)


    if selected is None:
        if board[raw][col] != "__" and board[raw][col] in turn:
            selected = (raw,col)
        return

    source_raw , source_col = selected

    if board[raw][col] in turn and board[source_raw][source_col] in turn:
        return


    board[raw][col] = board[source_raw][source_col]
    board[source_raw][source_col]  = "__"
    selected = None
    refresh()
    count = count + 1


def refresh():
    pen.clear()
    chess_board()
    pieces_location()
    screen.update()
    print_board(board)

def xy_location(x,y):
    raw = int((240 - y) // 60)
    col = int((240 + x) // 60)
    if 0 <= raw < 8 and 0 <= col < 8:
        return raw,col
    return None

def print_board(board):
    for raw in range(8):
        for col in range(8):
            print(board[raw][col],end=" ")
        print()

def highlight_next_move(piece,raw,col,turn):
    if piece in turn:
        green_it(piece,raw,col)

def green_it(piece,raw,col):
    if piece in ["bp","wp"]:
        if (piece == "wp" and raw == 6) or (piece == "bp" and raw == 1) :
            next_raw = raw + 2 if piece == "bp" else raw - 2

            not_moved = True
        else:
            next_raw = raw + 1 if piece == "bp" else raw - 1
            not_moved = False

        if next_raw < 0 or next_raw >= 8:
            return
        
        x = -240 + (col * 60)
        y = 240 - (next_raw * 60)
        pawn_highlights(x, y, not_moved,piece)

    elif piece in ["bw","wr"] :
        pass

def pawn_highlights(x, y, not_moved,nm):
    if not_moved:
        paint_highlights(x, y+60 if nm == "bp" else y-60 )
        paint_highlights(x, y)
    else:
        paint_highlights(x,y)

def paint_highlights(x,y):
    pen.penup()
    pen.goto(x, y)
    pen.pendown()
    pen.color("green")
    pen.begin_fill()
    for _ in range(4):
        pen.forward(60)
        pen.right(90)
    pen.end_fill()

if __name__ == "__main__":
    main()

turtle.done()