import pyglet

pyglet.options["dpi_scaling"] = "stretch"

from pyglet import shapes

import chess_ai
import moves


SQUARE_SIZE = 82
BOARD_SIZE = SQUARE_SIZE * 8
PANEL_WIDTH = 360
WINDOW_WIDTH = BOARD_SIZE + PANEL_WIDTH
WINDOW_HEIGHT = BOARD_SIZE

LIGHT_SQUARE = (239, 215, 177)
DARK_SQUARE = (174, 132, 96)
BOARD_FRAME = (64, 48, 36)
BOARD_EDGE = (215, 187, 145)
COORD_TEXT = (246, 232, 205, 235)
SELECTED_COLOR = (247, 205, 83)
MOVE_COLOR = (97, 193, 129)
CAPTURE_COLOR = (224, 76, 72)
CHECK_COLOR = (237, 143, 64)
PREMOVE_COLOR = (117, 127, 238)
PANEL_COLOR = (24, 22, 20)
PANEL_ACCENT = (190, 149, 105)
TEXT_COLOR = (250, 244, 232, 255)
MUTED_TEXT = (191, 177, 154, 255)
BUTTON_COLOR = (53, 45, 38)
BUTTON_ACTIVE = (111, 82, 58)
BUTTON_OUTLINE = (132, 105, 76)
WHITE_PIECE = (255, 250, 242, 255)
BLACK_PIECE = (7, 7, 8, 255)
PIECE_SHADOW = (42, 31, 24, 135)

PIECE_SYMBOLS = {
    "wk": "♔",
    "wq": "♕",
    "wr": "♖",
    "wb": "♗",
    "wh": "♘",
    "wp": "♙",
    "bk": "♚",
    "bq": "♛",
    "br": "♜",
    "bb": "♝",
    "bh": "♞",
    "bp": "♟",
}

PIECE_NAMES = {
    "k": "King",
    "q": "Queen",
    "r": "Rook",
    "b": "Bishop",
    "h": "Knight",
    "p": "Pawn",
}


class ChessApp(pyglet.window.Window):
    def __init__(self):
        super().__init__(WINDOW_WIDTH, WINDOW_HEIGHT, "Chess", resizable=False)
        self.set_size(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.set_minimum_size(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.set_maximum_size(WINDOW_WIDTH, WINDOW_HEIGHT)
        pyglet.gl.glClearColor(*(component / 255 for component in PANEL_COLOR), 1)

        self.board = moves.new_board()
        self.turn = "w"
        self.selected = None
        self.legal_targets = []
        self.white_captures = []
        self.black_captures = []
        self.en_passant_target = None
        self.castling_rights = {"wk", "wq", "bk", "bq"}
        self.message = "White to move"
        self.winner = None
        self.game_over_message = None
        self.play_mode = "ai"
        self.ai_color = "b"
        self.ai_level = 1
        self.ai_thinking = False
        self.premove_enabled = False
        self.premove_selected = None
        self.premove_target = None
        self.buttons = []
        self.origin_x = 0
        self.origin_y = 0
        self.panel_x = BOARD_SIZE

    def on_draw(self):
        self.clear()
        self.buttons = []
        self.update_layout()
        self.draw_background()
        self.draw_board()
        self.draw_highlights()
        self.draw_pieces()
        self.draw_panel()
        self.draw_game_over()

    def update_layout(self):
        content_width = BOARD_SIZE + PANEL_WIDTH
        self.origin_x = max(0, int((self.width - content_width) / 2))
        self.origin_y = max(0, int((self.height - BOARD_SIZE) / 2))
        self.panel_x = self.origin_x + BOARD_SIZE

    def draw_background(self):
        shapes.Rectangle(0, 0, self.width, self.height, color=(18, 16, 14)).draw()
        shapes.Rectangle(
            self.origin_x - 12,
            self.origin_y - 12,
            BOARD_SIZE + PANEL_WIDTH + 24,
            BOARD_SIZE + 24,
            color=(12, 11, 10),
        ).draw()

    def draw_board(self):
        shapes.Rectangle(self.origin_x, self.origin_y, BOARD_SIZE, BOARD_SIZE, color=BOARD_FRAME).draw()
        for row in range(8):
            for col in range(8):
                color = LIGHT_SQUARE if (row + col) % 2 == 0 else DARK_SQUARE
                self.draw_square(row, col, color)
        shapes.BorderedRectangle(
            self.origin_x,
            self.origin_y,
            BOARD_SIZE,
            BOARD_SIZE,
            border=3,
            color=(0, 0, 0, 0),
            border_color=BOARD_EDGE,
        ).draw()
        self.draw_coordinates()

    def draw_coordinates(self):
        for col, file_name in enumerate("abcdefgh"):
            x = self.origin_x + col * SQUARE_SIZE + 8
            self.label(file_name, x, self.origin_y + 8, 12, COORD_TEXT, bold=True)

        for row in range(8):
            rank = str(8 - row)
            x = self.origin_x + BOARD_SIZE - 10
            y = self.origin_y + BOARD_SIZE - (row * SQUARE_SIZE) - 18
            self.label(rank, x, y, 13, COORD_TEXT, bold=True, anchor_x="right")

    def draw_highlights(self):
        king_square = moves.find_king(self.board, self.turn)
        if king_square and moves.is_in_check(self.board, self.turn):
            self.draw_square(king_square[0], king_square[1], CHECK_COLOR, inset=7)

        if self.selected:
            self.draw_square(self.selected[0], self.selected[1], SELECTED_COLOR, inset=5)

        for row, col in self.legal_targets:
            color = CAPTURE_COLOR if self.is_capture_target(row, col) else MOVE_COLOR
            self.draw_square(row, col, color, inset=13)

        if self.premove_selected:
            self.draw_square(self.premove_selected[0], self.premove_selected[1], PREMOVE_COLOR, inset=18)
        if self.premove_target:
            self.draw_square(self.premove_target[0], self.premove_target[1], PREMOVE_COLOR, inset=24)

    def draw_square(self, row, col, color, inset=0):
        x = self.origin_x + col * SQUARE_SIZE + inset
        y = self.origin_y + BOARD_SIZE - ((row + 1) * SQUARE_SIZE) + inset
        size = SQUARE_SIZE - (inset * 2)
        shapes.Rectangle(x, y, size, size, color=color).draw()

    def draw_pieces(self):
        for row in range(8):
            for col in range(8):
                piece = self.board[row][col]
                if piece == moves.EMPTY:
                    continue
                x = self.origin_x + col * SQUARE_SIZE + SQUARE_SIZE // 2
                y = self.origin_y + BOARD_SIZE - (row * SQUARE_SIZE) - SQUARE_SIZE // 2
                self.draw_piece(piece, x, y)

    def draw_piece(self, piece, x, y):
        symbol = PIECE_SYMBOLS[piece]
        color = WHITE_PIECE if piece[0] == "w" else BLACK_PIECE
        outline = BLACK_PIECE if piece[0] == "w" else WHITE_PIECE
        for offset_x, offset_y in ((2, -2), (2, 2), (-2, -2), (-2, 2)):
            self.label(symbol, x + offset_x, y - 3 + offset_y, 54, outline, anchor_x="center", anchor_y="center")
        self.label(symbol, x + 3, y - 6, 54, PIECE_SHADOW, anchor_x="center", anchor_y="center")
        self.label(symbol, x, y - 3, 54, color, anchor_x="center", anchor_y="center")

    def draw_panel(self):
        shapes.Rectangle(self.panel_x, self.origin_y, PANEL_WIDTH, BOARD_SIZE, color=PANEL_COLOR).draw()
        shapes.Rectangle(self.panel_x, self.origin_y, 5, BOARD_SIZE, color=PANEL_ACCENT).draw()
        self.panel_text("Chess Engine", 28, 626, 28, bold=True)
        self.panel_text(self.message, 28, 588, 14, color=MUTED_TEXT)

        turn_label = moves.color_name(self.turn)
        if self.winner == "draw":
            turn_label = "Draw"
        elif self.winner:
            turn_label = f"{moves.color_name(self.winner)} wins"

        self.panel_text("Turn", 28, 532, 12, bold=True, color=MUTED_TEXT)
        self.panel_text(turn_label, 28, 498, 24, bold=True)

        self.panel_text("Play Mode", 28, 452, 12, bold=True, color=MUTED_TEXT)
        self.panel_button("Friend", 28, 406, 132, 38, lambda: self.set_play_mode("friend"), self.play_mode == "friend")
        self.panel_button("AI", 178, 406, 142, 38, lambda: self.set_play_mode("ai"), self.play_mode == "ai")

        model = chess_ai.MODELS[self.ai_level]
        self.panel_text("Engine", 28, 356, 12, bold=True, color=MUTED_TEXT)
        self.panel_text(f"{model['name']} ({model['params']})", 28, 326, 15)
        self.panel_text(f"Premove: {'On' if self.premove_enabled else 'Off'}", 28, 300, 13, color=MUTED_TEXT)

        self.panel_button("1M Easy", 28, 250, 92, 36, lambda: self.set_ai_level(1), self.ai_level == 1)
        self.panel_button("50M Med", 132, 250, 92, 36, lambda: self.set_ai_level(2), self.ai_level == 2)
        self.panel_button("100M", 236, 250, 84, 36, lambda: self.set_ai_level(3), self.ai_level == 3)
        self.panel_button("Premove", 28, 202, 142, 38, self.toggle_premove, self.premove_enabled)
        self.panel_button("Reset", 184, 202, 66, 38, self.reset)
        self.panel_button("Quit", 260, 202, 60, 38, self.close)

        self.panel_text("White captures", 28, 144, 12, bold=True, color=MUTED_TEXT)
        self.panel_text(self.capture_text(self.white_captures), 28, 116, 18)
        self.panel_text("Black captures", 28, 74, 12, bold=True, color=MUTED_TEXT)
        self.panel_text(self.capture_text(self.black_captures), 28, 46, 18)

    def draw_game_over(self):
        if not self.game_over_message:
            return

        width = 390
        height = 170
        x = (BOARD_SIZE - width) / 2
        y = self.origin_y + (BOARD_SIZE - height) / 2
        x = self.origin_x + x
        shapes.Rectangle(x, y, width, height, color=(17, 23, 25)).draw()
        shapes.BorderedRectangle(
            x + 8,
            y + 8,
            width - 16,
            height - 16,
            border=4,
            color=(17, 23, 25),
            border_color=SELECTED_COLOR,
        ).draw()
        self.label(self.game_over_message, self.origin_x + BOARD_SIZE / 2, y + 98, 28, TEXT_COLOR, bold=True, anchor_x="center")
        self.label("Press R to play again", self.origin_x + BOARD_SIZE / 2, y + 58, 16, MUTED_TEXT, anchor_x="center")

    def panel_text(self, text, x, y, size, bold=False, color=TEXT_COLOR):
        self.label(text, self.panel_x + x, self.origin_y + y, size, color, bold=bold)

    def panel_button(self, text, x, y, width, height, command, active=False):
        absolute_x = self.panel_x + x
        absolute_y = self.origin_y + y
        color = BUTTON_ACTIVE if active else BUTTON_COLOR
        shapes.BorderedRectangle(
            absolute_x,
            absolute_y,
            width,
            height,
            border=1,
            color=color,
            border_color=BUTTON_OUTLINE,
        ).draw()
        self.label(text, absolute_x + width / 2, absolute_y + height / 2 - 1, 12, TEXT_COLOR, bold=True, anchor_x="center", anchor_y="center")
        self.buttons.append((absolute_x, absolute_y, width, height, command))

    def label(self, text, x, y, size, color, bold=False, anchor_x="left", anchor_y="baseline"):
        pyglet.text.Label(
            text,
            font_name="Arial",
            font_size=size,
            weight="bold" if bold else "normal",
            x=x,
            y=y,
            color=color,
            anchor_x=anchor_x,
            anchor_y=anchor_y,
        ).draw()

    def capture_text(self, captures):
        if not captures:
            return "None"
        return " ".join(PIECE_SYMBOLS[piece] for piece in captures)

    def is_capture_target(self, row, col):
        if self.board[row][col] != moves.EMPTY:
            return True
        if not self.selected:
            return False
        source_row, source_col = self.selected
        piece = self.board[source_row][source_col]
        return piece[1] == "p" and self.en_passant_target == (row, col) and source_col != col

    def on_mouse_press(self, x, y, _button, _modifiers):
        for button_x, button_y, width, height, command in self.buttons:
            if button_x <= x <= button_x + width and button_y <= y <= button_y + height:
                command()
                return

        square = self.square_at(x, y)
        if square is None or self.winner:
            return

        if self.is_ai_turn():
            self.handle_premove_click(square)
            return

        row, col = square
        piece = self.board[row][col]

        if self.selected and (row, col) in self.legal_targets:
            self.apply_move((row, col))
            return

        if piece != moves.EMPTY and moves.piece_color(piece) == self.turn:
            self.select_piece(row, col)
            return

        self.message = "Choose a highlighted square" if self.selected else f"{moves.color_name(self.turn)} to move"

    def on_key_press(self, symbol, _modifiers):
        key = pyglet.window.key
        if symbol == key.R:
            self.reset()
        elif symbol == key.Q:
            self.close()
        elif symbol == key.P:
            self.toggle_premove()
        elif symbol == key._1:
            self.set_ai_level(1)
        elif symbol == key._2:
            self.set_ai_level(2)
        elif symbol == key._3:
            self.set_ai_level(3)

    def select_piece(self, row, col):
        self.selected = (row, col)
        self.legal_targets = moves.legal_moves(self.board, row, col, self.en_passant_target, self.castling_rights)
        piece = self.board[row][col]
        name = PIECE_NAMES[piece[1]]
        self.message = f"{name} selected"
        if not self.legal_targets:
            self.message = "That move will not save your king" if moves.is_in_check(self.board, self.turn) else f"{name} has no legal moves"

    def apply_move(self, target):
        source = self.selected
        self.make_move(source, target)
        self.selected = None
        self.legal_targets = []
        self.update_game_state()
        self.start_ai_turn()

    def make_move(self, source, target):
        moving_piece = self.board[source[0]][source[1]]
        result = moves.move_piece(self.board, source, target, self.en_passant_target)
        self.update_castling_rights(source, moving_piece, result)
        self.en_passant_target = result.en_passant_target
        self.message = self.move_message(moving_piece, result, target)
        self.turn = moves.opponent(self.turn)
        return result

    def move_message(self, moving_piece, result, target):
        next_player = moves.color_name(moves.opponent(moving_piece[0]))
        if result.castled:
            return "Castled"
        if result.captured:
            if moving_piece[0] == "w":
                self.white_captures.append(result.captured)
            else:
                self.black_captures.append(result.captured)
            if result.captured_square != target:
                return "En passant"
            return f"Captured {PIECE_NAMES[result.captured[1]].lower()}"
        if result.promoted:
            return "Pawn promoted to queen"
        return f"{next_player} to move"

    def update_game_state(self):
        status = moves.game_status(self.board, self.turn, self.en_passant_target, self.castling_rights)
        if status == "checkmate":
            self.winner = moves.opponent(self.turn)
            self.message = f"Checkmate. {moves.color_name(self.winner)} won"
            self.game_over_message = f"{moves.color_name(self.winner)} won!"
        elif status == "stalemate":
            self.winner = "draw"
            self.message = "Stalemate"
            self.game_over_message = "Draw by stalemate"
        elif status == "check":
            self.message = f"{moves.color_name(self.turn)} is in check"

    def is_ai_turn(self):
        return self.play_mode == "ai" and self.turn == self.ai_color and not self.winner

    def start_ai_turn(self):
        if not self.is_ai_turn():
            return
        self.ai_thinking = True
        model = chess_ai.MODELS[self.ai_level]
        self.message = f"{model['name']} is thinking"
        pyglet.clock.schedule_once(lambda _dt: self.perform_ai_move(), 0.45)

    def perform_ai_move(self):
        if not self.is_ai_turn():
            self.ai_thinking = False
            return

        move = chess_ai.choose_move(
            self.board,
            self.ai_color,
            self.ai_level,
            self.en_passant_target,
            self.castling_rights,
        )
        if move is None:
            self.ai_thinking = False
            self.update_game_state()
            return

        source, target = move
        self.make_move(source, target)
        self.ai_thinking = False
        self.selected = None
        self.legal_targets = []
        self.update_game_state()

        if not self.winner and self.premove_target:
            self.play_premove_if_legal()

    def handle_premove_click(self, square):
        if not self.premove_enabled or not self.ai_thinking:
            self.message = "Engine is thinking"
            return

        row, col = square
        piece = self.board[row][col]
        human_color = moves.opponent(self.ai_color)

        if self.premove_selected is None:
            if moves.piece_color(piece) == human_color:
                self.premove_selected = (row, col)
                self.premove_target = None
                self.message = "Choose premove target"
            else:
                self.message = "Select your piece for premove"
            return

        if moves.piece_color(piece) == human_color:
            self.premove_selected = (row, col)
            self.premove_target = None
            self.message = "Choose premove target"
        else:
            self.premove_target = (row, col)
            self.message = "Premove ready"

    def play_premove_if_legal(self):
        source = self.premove_selected
        target = self.premove_target
        self.premove_selected = None
        self.premove_target = None

        if not source or not target or self.turn == self.ai_color:
            return
        if moves.piece_color(self.board[source[0]][source[1]]) != self.turn:
            self.message = "Premove cancelled"
            return

        legal = moves.legal_moves(self.board, source[0], source[1], self.en_passant_target, self.castling_rights)
        if target not in legal:
            self.message = "Premove cancelled"
            return

        self.make_move(source, target)
        self.update_game_state()
        if not self.winner:
            self.start_ai_turn()

    def set_ai_level(self, level):
        self.ai_level = level
        model = chess_ai.MODELS[level]
        self.message = f"Selected {model['name']} ({model['params']})"

    def set_play_mode(self, mode):
        self.play_mode = mode
        self.selected = None
        self.legal_targets = []
        self.premove_selected = None
        self.premove_target = None
        self.ai_thinking = False
        if mode == "friend":
            self.message = "Friend mode: both sides are human"
        else:
            self.message = "AI mode: you play White"
            self.start_ai_turn()

    def toggle_premove(self):
        self.premove_enabled = not self.premove_enabled
        self.premove_selected = None
        self.premove_target = None
        self.message = f"Premove {'on' if self.premove_enabled else 'off'}"

    def reset(self):
        self.board = moves.new_board()
        self.turn = "w"
        self.selected = None
        self.legal_targets = []
        self.white_captures = []
        self.black_captures = []
        self.en_passant_target = None
        self.castling_rights = {"wk", "wq", "bk", "bq"}
        self.message = "White to move"
        self.winner = None
        self.game_over_message = None
        self.ai_thinking = False
        self.premove_selected = None
        self.premove_target = None

    def update_castling_rights(self, source, moving_piece, result):
        source_row, source_col = source
        color = moving_piece[0]
        if moving_piece[1] == "k":
            self.castling_rights.discard(color + "k")
            self.castling_rights.discard(color + "q")
        elif moving_piece[1] == "r":
            self.remove_rook_castling_right(source_row, source_col, color)

        if result.captured and result.captured[1] == "r" and result.captured_square:
            captured_row, captured_col = result.captured_square
            self.remove_rook_castling_right(captured_row, captured_col, result.captured[0])

    def remove_rook_castling_right(self, row, col, color):
        home_row = 7 if color == "w" else 0
        if row != home_row:
            return
        if col == 0:
            self.castling_rights.discard(color + "q")
        elif col == 7:
            self.castling_rights.discard(color + "k")

    def square_at(self, x, y):
        board_x = x - self.origin_x
        board_y = y - self.origin_y
        if board_x < 0 or board_x >= BOARD_SIZE or board_y < 0 or board_y >= BOARD_SIZE:
            return None
        return int((BOARD_SIZE - board_y) // SQUARE_SIZE), int(board_x // SQUARE_SIZE)


if __name__ == "__main__":
    ChessApp()
    pyglet.app.run()
