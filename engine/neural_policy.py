"""
neural_policy.py — Deep CNN with residual blocks for chess move prediction.

Architecture (AlphaZero-inspired):
  • Input: 8×8×17 tensor
      - 12 planes for pieces (one-hot per piece type per color)
      - 1 plane for side to move (all 1s or all 0s)
      - 4 planes for castling rights
  • Body: Conv2D stem + N residual blocks (BatchNorm + ReLU)
  • Policy head: Conv2D → Flatten → Dense(4096) — predicts move logits
  • Value head: Conv2D → Flatten → Dense(256) → Dense(1, tanh) — predicts win prob

This is dramatically more powerful than the previous flat MLP because:
  1. CNN layers capture spatial patterns on the 8×8 board
  2. Residual connections allow much deeper networks without vanishing gradients
  3. The value head provides position evaluation (replaces pure minimax eval)
  4. BatchNorm stabilises training
"""

import math
import random
from pathlib import Path

from engine import moves

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "data" / "neural_policy.keras"

# ---------------------------------------------------------------------------
# Board encoding constants (kept for training script compatibility)
# ---------------------------------------------------------------------------
PIECE_PLANES = {
    "wp": 0, "wh": 1, "wb": 2, "wr": 3, "wq": 4, "wk": 5,
    "bp": 6, "bh": 7, "bb": 8, "br": 9, "bq": 10, "bk": 11,
}

# Legacy flat-feature size (kept for training script that may still use it)
INPUT_SIZE = (8 * 8 * 12) + 1 + 4 + 8
OUTPUT_SIZE = 64 * 64   # from-square × to-square

# CNN input shape: 8 × 8 × 17
CNN_INPUT_SHAPE = (8, 8, 17)

# ---------------------------------------------------------------------------
# Model cache
# ---------------------------------------------------------------------------
_MODEL = None
_MODEL_ATTEMPTED = False


def load_model():
    global _MODEL, _MODEL_ATTEMPTED
    if _MODEL_ATTEMPTED:
        return _MODEL
    _MODEL_ATTEMPTED = True

    if not MODEL_PATH.exists():
        return None

    try:
        import tensorflow as tf
    except ImportError:
        return None

    try:
        _MODEL = tf.keras.models.load_model(MODEL_PATH)
        print(f"[neural_policy] Loaded model from {MODEL_PATH}")
    except Exception as exc:
        print(f"[neural_policy] Failed to load model: {exc}")
        _MODEL = None

    return _MODEL


# ---------------------------------------------------------------------------
# Position encoding — 8×8×17 tensor
# ---------------------------------------------------------------------------
def encode_position_cnn(board, color, en_passant_target=None, castling_rights=None):
    """
    Returns a (8, 8, 17) float32 list-of-lists representation.
    Planes 0-11:  piece planes (see PIECE_PLANES)
    Plane  12:    side to move (all 1s = white, all 0s = black)
    Planes 13-16: castling rights (wk, wq, bk, bq)
    """
    import numpy as np
    tensor = np.zeros(CNN_INPUT_SHAPE, dtype=np.float32)

    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            if piece != moves.EMPTY:
                plane = PIECE_PLANES[piece]
                tensor[row, col, plane] = 1.0

    side_value = 1.0 if color == "w" else 0.0
    tensor[:, :, 12] = side_value

    rights = castling_rights or set()
    for i, right in enumerate(("wk", "wq", "bk", "bq")):
        if right in rights:
            tensor[:, :, 13 + i] = 1.0

    # En passant — mark the target square column in a special way
    if en_passant_target:
        ep_row, ep_col = en_passant_target
        # We encode it into the side-to-move plane won't conflict;
        # instead overwrite nothing — ep is implicitly captured by board state.
        pass

    return tensor


# Legacy flat encoding (kept for backward compat with old training script)
def encode_position(board, color, en_passant_target=None, castling_rights=None):
    features = [0.0] * INPUT_SIZE
    offset = 0
    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            if piece == moves.EMPTY:
                continue
            plane = PIECE_PLANES[piece]
            features[offset + (plane * 64) + (row * 8) + col] = 1.0
    offset += 8 * 8 * 12
    features[offset] = 1.0 if color == "w" else 0.0
    offset += 1
    rights = castling_rights or set()
    for index, right in enumerate(("wk", "wq", "bk", "bq")):
        features[offset + index] = 1.0 if right in rights else 0.0
    offset += 4
    if en_passant_target:
        features[offset + en_passant_target[1]] = 1.0
    return features


# ---------------------------------------------------------------------------
# Move index helpers
# ---------------------------------------------------------------------------
def move_index(move):
    source, target = move
    source_index = (source[0] * 8) + source[1]
    target_index = (target[0] * 8) + target[1]
    return (source_index * 64) + target_index


# ---------------------------------------------------------------------------
# Neural move selection
# ---------------------------------------------------------------------------
def choose_neural_move(board, color, legal, en_passant_target=None,
                        castling_rights=None, temperature=0.35):
    model = load_model()
    if model is None:
        return None

    try:
        import numpy as np
        tensor = encode_position_cnn(board, color, en_passant_target, castling_rights)
        batch = np.expand_dims(tensor, 0)  # shape (1, 8, 8, 17)

        outputs = model.predict(batch, verbose=0)

        # Model may have 1 or 2 outputs (policy, or policy + value)
        if isinstance(outputs, (list, tuple)):
            policy_logits = outputs[0][0]   # shape (4096,)
        else:
            policy_logits = outputs[0]      # shape (4096,)

        scored = []
        for move in legal:
            idx = move_index(move)
            scored.append((move, float(policy_logits[idx])))

        if not scored:
            return None
        return sample_scored_moves(scored, temperature)

    except Exception as exc:
        print(f"[neural_policy] Prediction error: {exc}")
        return None


# ---------------------------------------------------------------------------
# Softmax sampling
# ---------------------------------------------------------------------------
def sample_scored_moves(scored, temperature):
    scored = sorted(scored, key=lambda item: item[1], reverse=True)
    top = scored[:min(8, len(scored))]
    best_score = max(score for _move, score in top)
    adjusted = []
    for move, score in top:
        weight = math.exp((score - best_score) / max(temperature, 0.05))
        adjusted.append((move, weight))
    total = sum(weight for _move, weight in adjusted)
    if total <= 0:
        return top[0][0]
    pick = random.uniform(0, total)
    running = 0
    for move, weight in adjusted:
        running += weight
        if running >= pick:
            return move
    return adjusted[0][0]


# ---------------------------------------------------------------------------
# Model builder — called from training script
# ---------------------------------------------------------------------------
def build_cnn_model(tf, num_res_blocks=10, filters=128):
    """
    Build an AlphaZero-style CNN model.

    Args:
        tf: TensorFlow module
        num_res_blocks: number of residual blocks in the body
        filters: number of convolutional filters

    Returns:
        Compiled Keras model with dual policy+value heads
    """
    inputs = tf.keras.Input(shape=CNN_INPUT_SHAPE, name="board_input")

    # Stem
    x = tf.keras.layers.Conv2D(filters, 3, padding="same", use_bias=False, name="stem_conv")(inputs)
    x = tf.keras.layers.BatchNormalization(name="stem_bn")(x)
    x = tf.keras.layers.ReLU(name="stem_relu")(x)

    # Residual tower
    for i in range(num_res_blocks):
        residual = x
        x = tf.keras.layers.Conv2D(filters, 3, padding="same", use_bias=False,
                                    name=f"res{i}_conv1")(x)
        x = tf.keras.layers.BatchNormalization(name=f"res{i}_bn1")(x)
        x = tf.keras.layers.ReLU(name=f"res{i}_relu1")(x)
        x = tf.keras.layers.Conv2D(filters, 3, padding="same", use_bias=False,
                                    name=f"res{i}_conv2")(x)
        x = tf.keras.layers.BatchNormalization(name=f"res{i}_bn2")(x)
        x = tf.keras.layers.Add(name=f"res{i}_add")([x, residual])
        x = tf.keras.layers.ReLU(name=f"res{i}_relu2")(x)

    # Policy head
    p = tf.keras.layers.Conv2D(2, 1, padding="same", use_bias=False, name="policy_conv")(x)
    p = tf.keras.layers.BatchNormalization(name="policy_bn")(p)
    p = tf.keras.layers.ReLU(name="policy_relu")(p)
    p = tf.keras.layers.Flatten(name="policy_flatten")(p)
    policy_out = tf.keras.layers.Dense(OUTPUT_SIZE, activation="softmax", name="policy")(p)

    # Value head
    v = tf.keras.layers.Conv2D(1, 1, padding="same", use_bias=False, name="value_conv")(x)
    v = tf.keras.layers.BatchNormalization(name="value_bn")(v)
    v = tf.keras.layers.ReLU(name="value_relu")(v)
    v = tf.keras.layers.Flatten(name="value_flatten")(v)
    v = tf.keras.layers.Dense(256, activation="relu", name="value_dense")(v)
    value_out = tf.keras.layers.Dense(1, activation="tanh", name="value")(v)

    model = tf.keras.Model(inputs=inputs, outputs=[policy_out, value_out])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss={"policy": "sparse_categorical_crossentropy", "value": "mse"},
        loss_weights={"policy": 1.0, "value": 1.0},
        metrics={"policy": "accuracy"},
    )
    return model
