"""Record a web page in a headless Chromium with Playwright.

The page is always opened headless. Never change this: test pages and
audited pages may contain hazardous flashing content.

Playwright writes a 25 fps .webm file when the browser context closes.
We record into a fresh, empty temporary folder (file names are random),
then trim the load/settle part away and re-encode the measured part to
an .mp4 file with a constant frame rate, which IRIS reads reliably.
"""

from __future__ import annotations

import shutil
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import cv2
from playwright.sync_api import sync_playwright

PLAYWRIGHT_FPS = 25.0


@dataclass
class Recording:
    video_path: Path          # trimmed .mp4 that is analysed
    fps: float                # frame rate of the trimmed video
    frames: int               # frames in the trimmed video
    duration_s: float         # frames / fps
    source_fps: float         # frame rate reported by the raw .webm
    timestamp_fps: float      # frame rate measured from per-frame timestamps
    skipped_frames: int       # frames trimmed from the start (load + settle)
    padded_frames: int        # last frame repeated at the end (see below)
    viewport: tuple[int, int]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["video_path"] = str(self.video_path)
        return d


def record_page(
    url: str,
    out_path: Path,
    viewport: tuple[int, int] = (1024, 768),
    duration: float = 10.0,
    settle: float = 1.0,
) -> Recording:
    """Record `url` for `duration` seconds after waiting `settle` seconds.

    `out_path` is the .mp4 file to create.
    """
    width, height = viewport
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_dir = Path(tempfile.mkdtemp(prefix="fsa-rec-"))
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)  # never headed
            try:
                t_context = time.monotonic()
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    record_video_dir=str(tmp_dir),
                    record_video_size={"width": width, "height": height},
                )
                page = context.new_page()
                page.goto(url, wait_until="load")
                page.wait_for_timeout(int(settle * 1000))
                t_start = time.monotonic()
                page.wait_for_timeout(int(duration * 1000))
                # The video is only written to disk when the context closes.
                context.close()
            finally:
                browser.close()

        videos = sorted(tmp_dir.glob("*.webm"))
        if not videos:
            raise RuntimeError("Playwright did not produce a video file.")

        skip = max(0, round((t_start - t_context) * PLAYWRIGHT_FPS))
        keep = round(duration * PLAYWRIGHT_FPS)
        return _trim_to_mp4(videos[0], out_path, skip, keep, viewport)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _trim_to_mp4(
    src: Path, dst: Path, skip: int, keep: int, viewport: tuple[int, int]
) -> Recording:
    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise RuntimeError(
            f"OpenCV cannot read {src.name}. Install an OpenCV build with "
            "WebM (VP8) support, e.g. `pip install opencv-python`."
        )
    source_fps = cap.get(cv2.CAP_PROP_FPS) or PLAYWRIGHT_FPS
    fps = PLAYWRIGHT_FPS

    writer = None
    timestamps: list[float] = []
    index = written = padded = 0
    last = None
    try:
        while written < keep:
            ok, frame = cap.read()
            if not ok:
                # Chromium sends no new frames while nothing on screen changes,
                # so the video can end early on a still page. Repeat the last
                # frame to reach the requested duration and record how many.
                if last is None or writer is None:
                    break
                writer.write(last)
                written += 1
                padded += 1
                continue
            last = frame
            ts = cap.get(cv2.CAP_PROP_POS_MSEC)
            if index >= skip:
                if writer is None:
                    h, w = frame.shape[:2]
                    writer = cv2.VideoWriter(
                        str(dst), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h)
                    )
                    if not writer.isOpened():
                        raise RuntimeError(f"Cannot write video to {dst}")
                writer.write(frame)
                timestamps.append(ts)
                written += 1
            index += 1
    finally:
        cap.release()
        if writer is not None:
            writer.release()

    if written == 0:
        raise RuntimeError("The recording is empty after trimming.")

    if len(timestamps) > 1 and timestamps[-1] > timestamps[0]:
        timestamp_fps = (len(timestamps) - 1) * 1000.0 / (timestamps[-1] - timestamps[0])
    else:
        timestamp_fps = source_fps

    return Recording(
        video_path=dst,
        fps=fps,
        frames=written,
        duration_s=written / fps,
        source_fps=round(source_fps, 3),
        timestamp_fps=round(timestamp_fps, 3),
        skipped_frames=skip,
        padded_frames=padded,
        viewport=viewport,
    )
