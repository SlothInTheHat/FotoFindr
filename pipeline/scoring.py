"""
Step 5 — Low-value photo scoring using heuristics only (no ML required).

Returns:
  importance_score: float 0.0–1.0  (lower = more likely junk)
  flags: list[str]                  (reasons for low score)
"""

import io
import hashlib
import numpy as np
from PIL import Image

# In-memory duplicate tracking (per process lifetime — good enough for demo)
_seen_hashes: set[str] = set()


def score_photo(image_bytes: bytes) -> tuple[float, list[str]]:
    flags: list[str] = []
    penalty = 0.0

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    arr = np.array(img)

    # --- Duplicate detection ---
    phash = hashlib.md5(image_bytes).hexdigest()
    if phash in _seen_hashes:
        flags.append("duplicate")
        penalty += 0.6
    else:
        _seen_hashes.add(phash)

    # --- Screenshot detection (very wide or very tall aspect ratio + common screen resolutions) ---
    ratio = w / h if h else 1
    if ratio > 2.5 or ratio < 0.4:
        flags.append("screenshot")
        penalty += 0.3
    if (w, h) in {(1080, 1920), (1170, 2532), (1284, 2778), (390, 844)}:
        flags.append("screenshot")
        penalty += 0.2

    # --- Blurriness (Laplacian variance) ---
    gray = np.mean(arr, axis=2).astype(np.float32)
    laplacian = _laplacian_variance(gray)
    if laplacian < 50:
        flags.append("blurry")
        penalty += 0.4

    # --- Low brightness ---
    brightness = arr.mean()
    if brightness < 20:
        flags.append("dark")
        penalty += 0.3

    # --- Nearly monochrome (low color variance) ---
    color_std = arr.std(axis=(0, 1)).mean()
    if color_std < 10:
        flags.append("monochrome")
        penalty += 0.2

    score = max(0.0, 1.0 - penalty)
    return round(score, 3), list(set(flags))


def _laplacian_variance(gray: np.ndarray) -> float:
    """Simple discrete Laplacian for blur detection (numpy-only)."""
    lap = (
        gray[1:-1, 1:-1] * -4
        + gray[0:-2, 1:-1]
        + gray[2:,   1:-1]
        + gray[1:-1, 0:-2]
        + gray[1:-1, 2:]
    )
    return float(lap.var())
