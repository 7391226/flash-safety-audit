"""Generate synthetic test videos with OpenCV.

640 x 360, 30 fps, 6 seconds, full-screen white/black.
Flash rates: 0 (static white), 1, 2 and 5 flashes per second.

Run:  python tests/make_videos.py [output_folder]
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

WIDTH, HEIGHT, FPS, SECONDS = 640, 360, 30, 6
RATES = [0, 1, 2, 5]


def video_name(rate: int) -> str:
    return f"full_{rate}hz.mp4"


def make_video(path: Path, rate: float) -> Path:
    white = np.full((HEIGHT, WIDTH, 3), 255, np.uint8)
    black = np.zeros_like(white)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot write {path}")
    try:
        for i in range(FPS * SECONDS):
            t = i / FPS
            on = rate == 0 or int(t * rate * 2) % 2 == 0  # white half of each period
            writer.write(white if on else black)
    finally:
        writer.release()
    return path


def make_videos(out_dir: Path) -> dict[int, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return {r: make_video(out_dir / video_name(r), r) for r in RATES}


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "videos"
    for rate, p in make_videos(target).items():
        print(f"{rate} Hz -> {p}")
