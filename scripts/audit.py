"""flash-safety-audit: screen a web page or video for WCAG 2.3.1 flash risk.

Usage (PowerShell):
    python scripts/audit.py --url https://example.com
    python scripts/audit.py --html page.html
    python scripts/audit.py --video clip.mp4

Exit code: 0 = WCAG 2.3.1 PASS, 1 = FAIL, 2 = error.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyse import DEFAULT_AREA_THRESHOLD, analyse_video  # noqa: E402
from report import DISCLAIMER, write_reports  # noqa: E402


def parse_viewport(text: str) -> tuple[int, int]:
    m = re.fullmatch(r"\s*(\d+)\s*[xX]\s*(\d+)\s*", text)
    if not m:
        raise argparse.ArgumentTypeError("use WIDTHxHEIGHT, e.g. 1024x768")
    return int(m.group(1)), int(m.group(2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="audit.py",
        description="Screen a web page or video for photosensitive epilepsy "
                    "risk (WCAG 2.3.1, Three Flashes or Below Threshold).",
        epilog=DISCLAIMER,
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="web address to record (http/https)")
    src.add_argument("--html", type=Path, help="local HTML file to record")
    src.add_argument("--video", type=Path, help="video file to analyse directly")
    p.add_argument("--viewport", type=parse_viewport, default=(1024, 768),
                   help="browser viewport, default 1024x768 (matches the WCAG pixel definition)")
    p.add_argument("--duration", type=float, default=10.0,
                   help="seconds to record (default 10)")
    p.add_argument("--settle", type=float, default=1.0,
                   help="seconds to wait after load before recording (default 1)")
    p.add_argument("--out", type=Path, default=Path("reports"),
                   help="folder for reports (default reports/)")
    p.add_argument("--area-threshold", type=float, default=DEFAULT_AREA_THRESHOLD,
                   help="flash area proportion (default 0.111 = WCAG 341x256 on 1024x768)")
    return p


def _slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-.")
    return (s or "audit")[:60]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not 0 < args.area_threshold <= 1:
        print("error: --area-threshold must be between 0 and 1", file=sys.stderr)
        return 2
    if args.duration <= 0 or args.settle < 0:
        print("error: --duration must be > 0 and --settle >= 0", file=sys.stderr)
        return 2

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        if args.video:
            video = args.video.resolve()
            if not video.is_file():
                raise FileNotFoundError(f"video not found: {video}")
            source, name = str(video), video.stem
            out_dir = args.out / f"{_slug(name)}-{stamp}"
            out_dir.mkdir(parents=True, exist_ok=True)
            recording, viewport = None, None
        else:
            if args.html:
                html = args.html.resolve()
                if not html.is_file():
                    raise FileNotFoundError(f"HTML file not found: {html}")
                url, name, source = html.as_uri(), html.stem, str(html)
            else:
                parsed = urlparse(args.url)
                if parsed.scheme not in ("http", "https"):
                    raise ValueError("--url must start with http:// or https://")
                url, name, source = args.url, parsed.netloc + parsed.path, args.url
            out_dir = args.out / f"{_slug(name)}-{stamp}"
            out_dir.mkdir(parents=True, exist_ok=True)

            from record import record_page  # imported late: Playwright is only needed here

            print(f"Recording {url} headless for {args.duration:g} s ...")
            rec = record_page(url, out_dir / "recording.mp4", args.viewport,
                              args.duration, args.settle)
            video, recording, viewport = rec.video_path, rec.to_dict(), args.viewport

        print("Analysing with IRIS ...")
        analysis = analyse_video(video, args.area_threshold,
                                 csv_out=out_dir / "frames.csv",
                                 log_out=out_dir / "iris.log")
        md, _ = write_reports(out_dir, source, analysis, viewport, recording)
    except Exception as exc:  # report any failure as a clean CLI error
        print(f"error: {exc}", file=sys.stderr)
        return 2

    verdict = "PASS" if analysis.wcag_pass else "FAIL"
    extra = " (extra non-WCAG warnings present)" if analysis.has_extra_warnings else ""
    print(f"WCAG 2.3.1: {verdict}{extra}")
    print(f"Report: {md}")
    print(DISCLAIMER)
    return 0 if analysis.wcag_pass else 1


if __name__ == "__main__":
    sys.exit(main())
