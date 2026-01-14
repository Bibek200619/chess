import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import kagglehub

PROJECT_DIR = Path(__file__).resolve().parent
ORIGINAL_PATH = sys.path[:]
sys.path = [path for path in sys.path if Path(path or ".").resolve() != PROJECT_DIR]
import chess
import chess.pgn
sys.path = ORIGINAL_PATH


DATASET = "saitamachiha/chess-dataset-for-chess-engine"
DEFAULT_OUTPUT = Path("data/opening_book.json")


def main():
    parser = argparse.ArgumentParser(description="Train a compact opening book from the Kaggle chess dataset.")
    parser.add_argument("--dataset-path", type=Path, help="Existing dataset folder. Downloads from Kaggle if omitted.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-games", type=int, default=50_000)
    parser.add_argument("--max-plies", type=int, default=24)
    parser.add_argument("--top-moves", type=int, default=5)
    args = parser.parse_args()

    dataset_path = args.dataset_path or Path(kagglehub.dataset_download(DATASET))
    pgn_files = sorted(dataset_path.rglob("*.pgn"))
    if not pgn_files:
        raise SystemExit(f"No PGN files found in {dataset_path}")

    book, games = build_book(pgn_files, args.max_games, args.max_plies)
    payload = {
        "source": DATASET,
        "games_read": games,
        "max_plies": args.max_plies,
        "positions": {
            key: counter.most_common(args.top_moves)
            for key, counter in book.items()
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(payload['positions'])} positions from {games} games to {args.output}")


def build_book(pgn_files, max_games, max_plies):
    book = defaultdict(Counter)
    games = 0

    for pgn_file in pgn_files:
        with pgn_file.open(encoding="utf-8", errors="ignore") as handle:
            while games < max_games:
                game = chess.pgn.read_game(handle)
                if game is None:
                    break

                board = game.board()
                result = game.headers.get("Result", "*")
                for ply, move in enumerate(game.mainline_moves()):
                    if ply >= max_plies:
                        break

                    key = position_key(board)
                    weight = move_weight(result, board.turn)
                    book[key][move.uci()] += weight
                    board.push(move)

                games += 1
                if games >= max_games:
                    break

        if games >= max_games:
            break

    return book, games


def position_key(board):
    ep = chess.square_name(board.ep_square) if board.ep_square is not None else "-"
    return f"{board.board_fen()} {board.turn} {board.castling_xfen()} {ep}"


def move_weight(result, turn):
    if result == "1/2-1/2":
        return 2
    if result == "1-0":
        return 3 if turn == chess.WHITE else 1
    if result == "0-1":
        return 3 if turn == chess.BLACK else 1
    return 1


if __name__ == "__main__":
    main()
