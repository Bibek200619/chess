import turtle

pen = turtle.Pen()
turtle.tracer(0)
pen.hideturtle()

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

def main():
    chess_board()
    pieces_location()
    turtle.done()


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

if __name__ == "__main__":
    main()