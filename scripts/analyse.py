"""Run IRIS on a video with a WCAG 2.3.1 area threshold and interpret it.

WCAG 2.3.1 "general flash threshold": a flash is a problem if the
combined flashing area is larger than 341 x 256 px on a 1024 x 768
screen, i.e. 341*256 / (1024*768) ~= 0.111 of the screen. IRIS uses
0.25 by default, which lets real WCAG failures through.

IRIS frame results (iris_pse_detection.result.FlashResult):
  3 FlashFail       more than 6 transitions (3 flashes) in 1 s   -> WCAG fail
  2 ExtendedFail    2-3 flashes/s sustained for ~4 s in 5 s       -> not WCAG
  1 PassWithWarning 4+ transitions in 1 s                          -> not WCAG
"""

from __future__ import annotations

import contextlib
import csv
import io
import shutil
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

import cv2
from iris_pse_detection import Configuration, VideoAnalyser
from iris_pse_detection.result import FlashResult

WCAG_AREA_PROPORTION = (341 * 256) / (1024 * 768)  # 0.1110...
DEFAULT_AREA_THRESHOLD = 0.111


@dataclass
class Interval:
    start_s: float
    end_s: float

    def label(self) -> str:
        return f"{self.start_s:.1f}–{self.end_s:.1f} s"


@dataclass
class Analysis:
    area_threshold: float
    fps: float
    frames: int
    duration_s: float
    # WCAG 2.3.1
    luminance_flash_fail_frames: int
    red_flash_fail_frames: int
    luminance_fail_intervals: list[Interval] = field(default_factory=list)
    red_fail_intervals: list[Interval] = field(default_factory=list)
    # Non-WCAG (broadcast-style) extras
    luminance_extended_fail_frames: int = 0
    red_extended_fail_frames: int = 0
    luminance_warning_frames: int = 0
    red_warning_frames: int = 0
    extended_intervals: list[Interval] = field(default_factory=list)
    iris_overall: str = ""
    frame_csv: Path | None = None

    @property
    def wcag_pass(self) -> bool:
        return self.luminance_flash_fail_frames == 0 and self.red_flash_fail_frames == 0

    @property
    def has_extra_warnings(self) -> bool:
        return (
            self.luminance_extended_fail_frames + self.red_extended_fail_frames
            + self.luminance_warning_frames + self.red_warning_frames
        ) > 0

    @property
    def max_measurable_hz(self) -> float:
        """Flicker faster than half the frame rate cannot be counted reliably."""
        return self.fps / 2

    def to_dict(self) -> dict:
        d = asdict(self)
        d["frame_csv"] = str(self.frame_csv) if self.frame_csv else None
        d["wcag_pass"] = self.wcag_pass
        d["has_extra_warnings"] = self.has_extra_warnings
        d["max_measurable_hz"] = self.max_measurable_hz
        return d


def analyse_video(
    video: Path,
    area_threshold: float = DEFAULT_AREA_THRESHOLD,
    csv_out: Path | None = None,
    log_out: Path | None = None,
) -> Analysis:
    """Analyse `video` with IRIS. Optionally keep the frame CSV and IRIS log."""
    video = Path(video)
    if not video.is_file():
        raise FileNotFoundError(video)

    fps, frame_count = _probe(video)

    work = Path(tempfile.mkdtemp(prefix="fsa-iris-"))
    try:
        config = Configuration(area_proportion=area_threshold)
        config.results_path = str(work) + "/"
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            result = VideoAnalyser(config).analyse_video(str(video), output_json=False)
            # IRIS writes <results_path>/<video name>/framedata.csv
        if log_out is not None:
            Path(log_out).write_text(log.getvalue(), encoding="utf-8")

        produced = work / video.name / "framedata.csv"
        rows = _read_frames(produced)
        if csv_out is not None:
            Path(csv_out).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(produced, csv_out)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    iris_fps = int(fps)  # IRIS truncates the frame rate to an integer
    lum = result.total_luminance_incidents
    red = result.total_red_incidents
    return Analysis(
        area_threshold=area_threshold,
        fps=iris_fps,
        frames=len(rows),
        duration_s=round(len(rows) / iris_fps, 3) if iris_fps else 0.0,
        luminance_flash_fail_frames=lum.flash_fail_frames,
        red_flash_fail_frames=red.flash_fail_frames,
        luminance_fail_intervals=_intervals(rows, "LuminanceFrameResult", {FlashResult.FlashFail}, iris_fps),
        red_fail_intervals=_intervals(rows, "RedFrameResult", {FlashResult.FlashFail}, iris_fps),
        luminance_extended_fail_frames=lum.extended_fail_frames,
        red_extended_fail_frames=red.extended_fail_frames,
        luminance_warning_frames=lum.pass_with_warning_frames,
        red_warning_frames=red.pass_with_warning_frames,
        extended_intervals=_intervals(
            rows, ("LuminanceFrameResult", "RedFrameResult"),
            {FlashResult.ExtendedFail}, iris_fps,
        ),
        iris_overall=result.overall_result.name,
        frame_csv=Path(csv_out) if csv_out else None,
    )


def measure_flash_rate(video: Path) -> dict:
    """Diagnostic: flash rate from the spacing of dark->bright edges.

    Only meaningful for simple, regular test content (one blinking element).
    The rate is fps / (average frames between edges), so partial periods at
    the start and end of the video do not bias it.
    """
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open {video}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    means: list[float] = []
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            means.append(float(frame.mean()))
    finally:
        cap.release()
    if not means or not fps:
        return {"frames": len(means), "fps": fps, "flashes_per_s": 0.0}
    lo, hi = min(means), max(means)
    edges: list[int] = []
    if hi - lo > 10:  # ignore compression noise on static content
        mid = (lo + hi) / 2
        edges = [i for i in range(1, len(means)) if means[i - 1] < mid <= means[i]]
    rate = 0.0
    if len(edges) >= 2:
        rate = fps * (len(edges) - 1) / (edges[-1] - edges[0])
    return {"frames": len(means), "fps": fps, "edges": len(edges), "flashes_per_s": rate}


def _probe(video: Path) -> tuple[float, int]:
    cap = cv2.VideoCapture(str(video))
    try:
        if not cap.isOpened():
            raise RuntimeError(
                f"OpenCV cannot open {video}. Convert it to .mp4 (H.264) and try again."
            )
        fps = cap.get(cv2.CAP_PROP_FPS)
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        cap.release()
    if fps < 1:
        raise RuntimeError(f"{video} reports no frame rate; re-encode it with a constant frame rate.")
    if count <= 0:
        raise RuntimeError(f"{video} reports no frame count; re-encode it (e.g. to .mp4).")
    return fps, count


def _read_frames(csv_path: Path) -> list[dict]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _intervals(rows, columns, codes, fps, max_gap_frames: int = 1) -> list[Interval]:
    """Group flagged frames into time ranges (seconds from video start)."""
    if isinstance(columns, str):
        columns = (columns,)
    codes = {int(c) for c in codes}
    flagged = [
        int(r["Frame"]) - 1  # IRIS frame numbers start at 1
        for r in rows
        if any(int(r[c]) in codes for c in columns)
    ]
    if not flagged or not fps:
        return []
    out: list[Interval] = []
    start = prev = flagged[0]
    for f in flagged[1:]:
        if f - prev > max_gap_frames + 1:
            out.append(Interval(start / fps, (prev + 1) / fps))
            start = f
        prev = f
    out.append(Interval(start / fps, (prev + 1) / fps))
    return [Interval(round(i.start_s, 2), round(i.end_s, 2)) for i in out]
