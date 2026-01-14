import json
import mimetypes
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HOST = "127.0.0.1"
PORT = 8000
ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import ai as chess_ai
from engine import moves


class GameState:
    def __init__(self):
        self.lock = threading.RLock()
        self.reset()

    def reset(self):
        with getattr(self, "lock", threading.RLock()):
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
            self.last_move = None
            self.version = getattr(self, "version", 0) + 1
            return self.snapshot()

    def snapshot(self):
        model_info = chess_ai.MODELS.get(self.ai_level, {})
        return {
            "board": self.board,
            "turn": self.turn,
            "turnName": moves.color_name(self.turn),
            "selected": as_list(self.selected),
            "legalTargets": [list(target) for target in self.legal_targets],
            "whiteCaptures": self.white_captures,
            "blackCaptures": self.black_captures,
            "message": self.message,
            "winner": self.winner,
            "gameOverMessage": self.game_over_message,
            "playMode": self.play_mode,
            "aiLevel": self.ai_level,
            "aiLevelName": model_info.get("name", ""),
            "aiDepth": model_info.get("depth", 2),
            "aiThinking": self.ai_thinking,
            "premoveEnabled": self.premove_enabled,
            "premoveSelected": as_list(self.premove_selected),
            "premoveTarget": as_list(self.premove_target),
            "lastMove": [list(square) for square in self.last_move] if self.last_move else None,
            "checkSquare": as_list(self.check_square()),
            "models": chess_ai.MODELS,
            "version": self.version,
            "engineVersion": "2.0-CNN",
        }

    def check_square(self):
        if moves.is_in_check(self.board, self.turn):
            return moves.find_king(self.board, self.turn)
        return None

    def click(self, row, col):
        should_start_ai = False
        with self.lock:
            if self.winner:
                return self.snapshot()

            square = (row, col)
            if not moves.in_bounds(row, col):
                self.clear_selection()
                return self.snapshot()

            if self.is_ai_turn():
                self.handle_premove_click(square)
                return self.snapshot()

            piece = self.board[row][col]
            if self.selected and square in self.legal_targets:
                source = self.selected
                self.make_move(source, square)
                self.selected = None
                self.legal_targets = []
                self.update_game_state()
                should_start_ai = self.is_ai_turn()
            elif piece != moves.EMPTY and moves.piece_color(piece) == self.turn:
                self.select_piece(row, col)
            else:
                self.message = "Choose a highlighted square" if self.selected else f"{moves.color_name(self.turn)} to move"

            state = self.snapshot()

        if should_start_ai:
            return self.start_ai_turn()
        return state

    def select_piece(self, row, col):
        self.selected = (row, col)
        self.legal_targets = moves.legal_moves(self.board, row, col, self.en_passant_target, self.castling_rights)
        piece = self.board[row][col]
        name = piece_name(piece)
        self.message = f"{name} selected"
        if not self.legal_targets:
            self.message = "That move will not save your king" if moves.is_in_check(self.board, self.turn) else f"{name} has no legal moves"

    def clear_selection(self):
        self.selected = None
        self.legal_targets = []
        self.message = f"{moves.color_name(self.turn)} to move"

    def make_move(self, source, target):
        moving_piece = self.board[source[0]][source[1]]
        result = moves.move_piece(self.board, source, target, self.en_passant_target)
        self.update_castling_rights(source, moving_piece, result)
        self.en_passant_target = result.en_passant_target
        self.message = self.move_message(moving_piece, result, target)
        self.turn = moves.opponent(self.turn)
        self.last_move = (source, target)
        self.version += 1
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
            return f"Captured {piece_name(result.captured).lower()}"
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
        with self.lock:
            if not self.is_ai_turn() or self.ai_thinking:
                return self.snapshot()
            self.ai_thinking = True
            self.message = f"{chess_ai.MODELS[self.ai_level]['name']} is thinking"
            snapshot = {
                "board": [row[:] for row in self.board],
                "turn": self.turn,
                "en_passant_target": self.en_passant_target,
                "castling_rights": set(self.castling_rights),
                "level": self.ai_level,
                "version": self.version,
            }

        threading.Thread(target=self.run_ai_move, args=(snapshot,), daemon=True).start()
        return self.snapshot()

    def run_ai_move(self, snapshot):
        move = chess_ai.choose_move(
            snapshot["board"],
            snapshot["turn"],
            snapshot["level"],
            snapshot["en_passant_target"],
            snapshot["castling_rights"],
        )

        should_start_next_ai = False
        with self.lock:
            if snapshot["version"] != self.version or not self.is_ai_turn():
                self.ai_thinking = False
                return

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
                should_start_next_ai = self.is_ai_turn()

        if should_start_next_ai:
            self.start_ai_turn()

    def handle_premove_click(self, square):
        if not self.premove_enabled or not self.ai_thinking:
            self.message = "Engine is thinking"
            return

        row, col = square
        piece = self.board[row][col]
        human_color = moves.opponent(self.ai_color)

        if self.premove_selected is None:
            if moves.piece_color(piece) == human_color:
                self.premove_selected = square
                self.premove_target = None
                self.message = "Choose premove target"
            else:
                self.message = "Select your piece for premove"
            return

        if moves.piece_color(piece) == human_color:
            self.premove_selected = square
            self.premove_target = None
            self.message = "Choose premove target"
        else:
            self.premove_target = square
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

    def set_mode(self, mode):
        should_start_ai = False
        with self.lock:
            self.play_mode = "friend" if mode == "friend" else "ai"
            self.selected = None
            self.legal_targets = []
            self.premove_selected = None
            self.premove_target = None
            self.ai_thinking = False
            if self.play_mode == "friend":
                self.message = "Friend mode: both sides are human"
            else:
                self.message = "AI mode: you play White"
                should_start_ai = self.is_ai_turn()
            state = self.snapshot()

        if should_start_ai:
            return self.start_ai_turn()
        return state

    def set_level(self, level):
        with self.lock:
            self.ai_level = level if level in chess_ai.MODELS else 1
            model = chess_ai.MODELS[self.ai_level]
            self.message = f"Selected {model['name']} ({model['params']})"
            return self.snapshot()

    def set_premove(self, enabled):
        with self.lock:
            self.premove_enabled = bool(enabled)
            self.premove_selected = None
            self.premove_target = None
            self.message = f"Premove {'on' if self.premove_enabled else 'off'}"
            return self.snapshot()

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


def as_list(square):
    return list(square) if square else None


def piece_name(piece):
    names = {"k": "King", "q": "Queen", "r": "Rook", "b": "Bishop", "h": "Knight", "p": "Pawn"}
    return names[piece[1]]


GAME = GameState()


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_file(WEB_DIR / "index.html")
            return
        if self.path == "/api/state":
            self.send_json(GAME.snapshot())
            return
        if self.path == "/api/engine-info":
            from engine import neural_policy
            model_loaded = neural_policy._MODEL_ATTEMPTED and neural_policy._MODEL is not None
            self.send_json({
                "version": "2.0-CNN",
                "architecture": "CNN + Residual Blocks (AlphaZero-style)",
                "features": [
                    "Quiescence search (no horizon effect)",
                    "Zobrist transposition table (1M entries)",
                    "Iterative deepening",
                    "Piece-square tables (PST)",
                    "King safety evaluation",
                    "Pawn structure (doubled/isolated/passed)",
                    "Bishop pair bonus",
                    "Rook on open file bonus",
                    "MVV-LVA move ordering",
                ],
                "models": chess_ai.MODELS,
                "neuralModelLoaded": model_loaded,
            })
            return
        if self.path.startswith("/static/"):
            self.send_file(WEB_DIR / self.path.removeprefix("/static/"))
            return
        self.send_error(404)

    def do_POST(self):
        body = self.read_json()
        if self.path == "/api/reset":
            self.send_json(GAME.reset())
        elif self.path == "/api/click":
            self.send_json(GAME.click(int(body.get("row", -1)), int(body.get("col", -1))))
        elif self.path == "/api/mode":
            self.send_json(GAME.set_mode(body.get("mode", "ai")))
        elif self.path == "/api/level":
            self.send_json(GAME.set_level(int(body.get("level", 1))))
        elif self.path == "/api/premove":
            self.send_json(GAME.set_premove(bool(body.get("enabled"))))
        else:
            self.send_error(404)

    def read_json(self):
        length = int(self.headers.get("content-length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_json(self, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path):
        if not path.exists() or not path.is_file():
            self.send_error(404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def main():
    threading.Thread(target=chess_ai.load_opening_book, daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Chess web app running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
