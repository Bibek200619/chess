"""
train_neural_policy.py — Train the AlphaZero-style CNN chess policy network.

Key differences from the previous flat-MLP trainer:
  • Input: 8×8×17 CNN tensor instead of flat 773-dim vector
  • Architecture: CNN stem + residual blocks + dual policy + value heads
  • Training target: policy from PGN master games + outcome value (win/draw/loss)
  • Data augmentation: board reflection (left-right symmetry)
  • Larger dataset capacity and more epochs for a stronger model

Usage:
  # Quick test (small model, few games)
  python train_neural_policy.py --profile mini --max-games 1000 --epochs 3

  # Level 2 model (medium, ~30 min on M-series Mac)
  python train_neural_policy.py --profile level2 --max-games 50000 --epochs 10

  # Level 3 model (strongest, needs GPU)
  python train_neural_policy.py --profile level3 --max-games 200000 --epochs 20
"""

import argparse
import sys
from pathlib import Path

# Isolate project chess module from python-chess package
PROJECT_DIR = Path(__file__).resolve().parent
ORIGINAL_PATH = sys.path[:]
sys.path = [path for path in sys.path if Path(path or ".").resolve() != PROJECT_DIR]
import chess
import chess.pgn
sys.path = ORIGINAL_PATH

# Ensure the project root is on the path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import neural_policy


DATASET = "saitamachiha/chess-dataset-for-chess-engine"
DEFAULT_OUTPUT = ROOT / "data" / "neural_policy.keras"

PROFILES = {
    # (num_res_blocks, filters, max_games, epochs, batch_size)
    "mini":   (2,  32,  2_000,  3,  128),
    "level1": (4,  64,  20_000, 5,  256),
    "level2": (8,  128, 80_000, 10, 512),
    "level3": (15, 256, 200_000, 20, 512),
}


def main():
    parser = argparse.ArgumentParser(
        description="Train an AlphaZero-style CNN chess policy+value network from PGN games."
    )
    parser.add_argument("--dataset-path", type=Path,
                        help="Existing Kaggle dataset folder. Downloads if omitted.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--profile", choices=PROFILES.keys(), default="level1")
    parser.add_argument("--max-games", type=int, default=None,
                        help="Override max games from profile.")
    parser.add_argument("--max-plies", type=int, default=60,
                        help="Max half-moves per game to sample.")
    parser.add_argument("--max-samples", type=int, default=500_000)
    parser.add_argument("--epochs", type=int, default=None,
                        help="Override epochs from profile.")
    parser.add_argument("--batch-size", type=int, default=None,
                        help="Override batch size from profile.")
    parser.add_argument("--augment", action="store_true", default=True,
                        help="Apply board reflection augmentation (doubles dataset).")
    args = parser.parse_args()

    try:
        import numpy as np
        import tensorflow as tf
    except ImportError as exc:
        raise SystemExit(
            "TensorFlow training dependencies are missing.\n"
            "Install: pip install tensorflow numpy kagglehub chess"
        ) from exc

    num_res_blocks, filters, default_games, default_epochs, default_batch = PROFILES[args.profile]
    max_games   = args.max_games   or default_games
    epochs      = args.epochs      or default_epochs
    batch_size  = args.batch_size  or default_batch

    print(f"\n=== Chess CNN Training ({args.profile}) ===")
    print(f"Residual blocks: {num_res_blocks}, Filters: {filters}")
    print(f"Max games: {max_games}, Epochs: {epochs}, Batch: {batch_size}")

    dataset_path = args.dataset_path or download_dataset()
    pgn_files = sorted(dataset_path.rglob("*.pgn"))
    if not pgn_files:
        raise SystemExit(f"No PGN files found in {dataset_path}")

    print(f"\nCollecting samples from {len(pgn_files)} PGN file(s)...")
    boards_np, policies_np, values_np, games = collect_samples(
        pgn_files, max_games, args.max_plies, args.max_samples, np, args.augment
    )

    if len(policies_np) == 0:
        raise SystemExit("No training samples were collected.")

    print(f"\nCollected {len(policies_np)} samples from {games} games.")
    print(f"Board tensor shape: {boards_np.shape}")

    print("\nBuilding CNN model...")
    model = neural_policy.build_cnn_model(tf, num_res_blocks=num_res_blocks, filters=filters)
    model.summary()

    print("\nTraining...")
    history = model.fit(
        boards_np,
        {"policy": policies_np, "value": values_np},
        epochs=epochs,
        batch_size=batch_size,
        validation_split=0.05,
        shuffle=True,
        callbacks=[
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor="val_policy_accuracy", patience=2, factor=0.5, mode="max", verbose=1
            ),
            tf.keras.callbacks.EarlyStopping(
                monitor="val_policy_accuracy", patience=5, restore_best_weights=True, mode="max", verbose=1
            ),
        ],
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    model.save(args.output)

    final_acc = history.history.get("policy_accuracy", [0])[-1]
    print(f"\n=== Training Complete ===")
    print(f"Policy accuracy: {final_acc:.4f}")
    print(f"Samples: {len(policies_np)} from {games} games")
    print(f"Model saved to: {args.output}")


def download_dataset():
    import kagglehub
    return Path(kagglehub.dataset_download(DATASET))


def collect_samples(pgn_files, max_games, max_plies, max_samples, np, augment):
    """
    Parse PGN files and collect (board_tensor, policy_move_index, game_outcome) triples.
    """
    boards  = []
    policies = []
    values   = []
    games    = 0

    for pgn_file in pgn_files:
        with pgn_file.open(encoding="utf-8", errors="ignore") as handle:
            while games < max_games and len(policies) < max_samples:
                game = chess.pgn.read_game(handle)
                if game is None:
                    break

                outcome = parse_outcome(game)
                board   = game.board()

                for ply, move in enumerate(game.mainline_moves()):
                    if ply >= max_plies or len(policies) >= max_samples:
                        break

                    tensor = encode_python_chess_board(board, np)
                    midx   = move_index_from_python_chess(move)
                    # Value from the perspective of the side to move
                    val    = outcome if board.turn == chess.WHITE else -outcome

                    boards.append(tensor)
                    policies.append(midx)
                    values.append(val)

                    if augment:
                        # Horizontal flip (left-right symmetry)
                        flipped_tensor = np.flip(tensor, axis=1).copy()
                        flipped_move   = flip_move_index(midx)
                        boards.append(flipped_tensor)
                        policies.append(flipped_move)
                        values.append(val)

                    board.push(move)

                games += 1

        if games >= max_games or len(policies) >= max_samples:
            break

    import numpy as np_mod
    boards_np   = np_mod.asarray(boards,   dtype=np_mod.float32)
    policies_np = np_mod.asarray(policies, dtype=np_mod.int32)
    values_np   = np_mod.asarray(values,   dtype=np_mod.float32)
    return boards_np, policies_np, values_np, games


def parse_outcome(game):
    """Return +1 (white wins), -1 (black wins), 0 (draw)."""
    result = game.headers.get("Result", "*")
    if result == "1-0":
        return 1.0
    if result == "0-1":
        return -1.0
    return 0.0


def encode_python_chess_board(board, np):
    """Encode a python-chess Board as an (8, 8, 17) float32 numpy array."""
    from engine.neural_policy import PIECE_PLANES, CNN_INPUT_SHAPE
    tensor = np.zeros(CNN_INPUT_SHAPE, dtype=np.float32)

    for square, piece in board.piece_map().items():
        row = 7 - chess.square_rank(square)
        col = chess.square_file(square)
        key = piece_key(piece)
        plane = PIECE_PLANES[key]
        tensor[row, col, plane] = 1.0

    side_value = 1.0 if board.turn == chess.WHITE else 0.0
    tensor[:, :, 12] = side_value

    tensor[:, :, 13] = 1.0 if board.has_kingside_castling_rights(chess.WHITE)  else 0.0
    tensor[:, :, 14] = 1.0 if board.has_queenside_castling_rights(chess.WHITE) else 0.0
    tensor[:, :, 15] = 1.0 if board.has_kingside_castling_rights(chess.BLACK)  else 0.0
    tensor[:, :, 16] = 1.0 if board.has_queenside_castling_rights(chess.BLACK) else 0.0

    return tensor


def piece_key(piece):
    color = "w" if piece.color == chess.WHITE else "b"
    kind = {
        chess.PAWN: "p", chess.KNIGHT: "h", chess.BISHOP: "b",
        chess.ROOK: "r", chess.QUEEN: "q", chess.KING: "k",
    }[piece.piece_type]
    return color + kind


def move_index_from_python_chess(move):
    """Convert python-chess Move to our from×to index (0-4095)."""
    source_row = 7 - chess.square_rank(move.from_square)
    source_col = chess.square_file(move.from_square)
    target_row = 7 - chess.square_rank(move.to_square)
    target_col = chess.square_file(move.to_square)
    source = (source_row * 8) + source_col
    target = (target_row * 8) + target_col
    return (source * 64) + target


def flip_move_index(idx):
    """Flip a move index horizontally (left-right reflection)."""
    from_sq = idx // 64
    to_sq   = idx  % 64
    from_row, from_col = divmod(from_sq, 8)
    to_row,   to_col   = divmod(to_sq,   8)
    # Mirror column: col → 7-col
    new_from = from_row * 8 + (7 - from_col)
    new_to   = to_row   * 8 + (7 - to_col)
    return new_from * 64 + new_to


if __name__ == "__main__":
    main()
