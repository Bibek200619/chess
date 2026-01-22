import turtle


screen = turtle.Screen()
screen.title("Chess Board")
screen.setup(600, 600)

pen = turtle.Turtle()
pen.speed(0)
pen.hideturtle()

SQUARE = 60  # size of each square


def draw_square(x, y, color):
    pen.penup()
    pen.goto(x, y)
    pen.pendown()
    pen.color("black", color)
    pen.begin_fill()
    for _ in range(4):
        pen.forward(SQUARE)
        pen.right(90)
    pen.end_fill()


def draw_chessboard():
    colors = ["#EEEED2", "#769656"]  # light, dark
    start_x = -240
    start_y = 240

    for row in range(8):
        for col in range(8):
            x = start_x + col * SQUARE
            y = start_y - row * SQUARE
            color = colors[(row + col) % 2]
            draw_square(x, y, color)


# Draw the board
draw_chessboard()

turtle.done()
