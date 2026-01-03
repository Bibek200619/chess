import turtle

pen = turtle.Pen()

left = -240
right = 240

def main():
    chess_board()

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

if __name__ == "__main__":
    main()