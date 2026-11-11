"""Tests for flash-safety-audit.

Fast tests:   pytest -m "not slow"
All tests:    pytest

Slow tests record every fixture page in headless Chromium (1024x768, 7 s)
and check the results against the expected-results table in README.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import audit  # noqa: E402
from analyse import Interval, _intervals, analyse_video, measure_flash_rate  # noqa: E402
import make_fixtures  # noqa: E402
import make_videos  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
RECORD_SECONDS = 7
IRIS_DEFAULT = 0.25
WCAG = 0.111

# Expected outcomes. Columns:
#   name, flash rate, default IRIS (0.25), WCAG setting (0.111), WCAG verdict, extra warning
# IRIS outcomes: "pass", "fail", "fail-extended" (extended only), "fail-red" (red flash fail too)
# extra: True / False / None (not checked)
EXPECTED = [
    ("static_white", 0, "pass", "pass", "PASS", False),
    ("full_1hz", 1, "pass", "pass", "PASS", False),
    ("full_2hz", 2, "fail-extended", "fail-extended", "PASS", True),
    ("full_4hz", 4, "fail", "fail", "FAIL", None),
    ("full_5hz", 5, "fail", "fail", "FAIL", None),
    ("full_red_5hz", 5, "fail-red", "fail", "FAIL", None),
    ("box30_5hz", 5, "pass", "pass", "PASS", False),
    ("box39_5hz", 5, "pass", "fail", "FAIL", None),
    ("box45_5hz", 5, "pass", "fail", "FAIL", None),
    ("box49_5hz", 5, "pass", "fail", "FAIL", None),
    ("box60_5hz", 5, "fail", "fail", "FAIL", None),
]

VIDEO_EXPECTED = [  # rate, WCAG verdict, extra warning
    (0, "PASS", False),
    (1, "PASS", False),
    (2, "PASS", True),
    (5, "FAIL", None),
]


def check_iris(a, expected: str) -> None:
    flash_fail = a.luminance_flash_fail_frames + a.red_flash_fail_frames
    extended = a.luminance_extended_fail_frames + a.red_extended_fail_frames
    if expected == "pass":
        assert a.iris_overall in ("Pass", "PassWithWarning"), a.iris_overall
    elif expected == "fail":
        assert a.iris_overall == "Fail" and flash_fail > 0
    elif expected == "fail-extended":
        assert a.iris_overall == "Fail" and flash_fail == 0 and extended > 0
    elif expected == "fail-red":
        assert a.iris_overall == "Fail" and a.red_flash_fail_frames > 0
    else:
        raise ValueError(expected)


def check_wcag(a, verdict: str, extra) -> None:
    assert ("PASS" if a.wcag_pass else "FAIL") == verdict
    if extra is not None:
        assert a.has_extra_warnings == extra


# ---------------------------------------------------------------- fast tests

def test_fixtures_are_up_to_date():
    for name, colour, rate, size in make_fixtures.FIXTURES:
        page = FIXTURES / f"{name}.html"
        assert page.read_text(encoding="utf-8") == make_fixtures.render(name, colour, rate, size)


def test_parse_viewport():
    assert audit.parse_viewport("1024x768") == (1024, 768)
    assert audit.parse_viewport(" 640 X 360 ") == (640, 360)
    with pytest.raises(Exception):
        audit.parse_viewport("big")


def test_intervals_grouping():
    rows = [{"Frame": str(i + 1), "R": "3" if i in (10, 11, 12, 40, 41) else "0"} for i in range(50)]
    assert _intervals(rows, "R", {3}, 25) == [Interval(0.4, 0.52), Interval(1.6, 1.68)]
    assert _intervals(rows, "R", {2}, 25) == []


def test_cli_rejects_bad_threshold(tmp_path):
    assert audit.main(["--video", str(tmp_path / "x.mp4"), "--area-threshold", "2"]) == 2


@pytest.fixture(scope="session")
def videos(tmp_path_factory):
    return make_videos.make_videos(tmp_path_factory.mktemp("videos"))


@pytest.mark.parametrize("rate,verdict,extra", VIDEO_EXPECTED)
def test_video_input(videos, rate, verdict, extra):
    a = analyse_video(videos[rate], WCAG)
    assert a.fps == make_videos.FPS
    check_wcag(a, verdict, extra)
    measured = measure_flash_rate(videos[rate])["flashes_per_s"]
    assert abs(measured - rate) <= 0.2


def test_cli_video_report(videos, tmp_path):
    code = audit.main(["--video", str(videos[5]), "--out", str(tmp_path)])
    assert code == 1
    (report_dir,) = tmp_path.iterdir()
    md = (report_dir / "report.md").read_text(encoding="utf-8")
    assert "not a compliance certificate" in md
    assert "## WCAG 2.3.1 result: FAIL" in md
    assert "## Extra warnings (not WCAG)" in md
    assert (report_dir / "frames.csv").is_file()
    assert (report_dir / "report.json").is_file()


# ---------------------------------------------------------------- slow tests

@pytest.fixture(scope="session")
def recordings(tmp_path_factory):
    """Record each fixture page once, lazily."""
    from record import record_page

    cache: dict[str, object] = {}
    folder = tmp_path_factory.mktemp("recordings")

    def get(name: str):
        if name not in cache:
            cache[name] = record_page(
                (FIXTURES / f"{name}.html").as_uri(),
                folder / f"{name}.mp4",
                viewport=(1024, 768),
                duration=RECORD_SECONDS,
                settle=1.0,
            )
        return cache[name]

    return get


@pytest.mark.slow
@pytest.mark.parametrize("name,rate,default_iris,wcag_iris,verdict,extra", EXPECTED,
                         ids=[e[0] for e in EXPECTED])
def test_fixture_page(recordings, name, rate, default_iris, wcag_iris, verdict, extra):
    rec = recordings(name)

    # Recording quality: frame rate and flash rate within +-0.2 (detects dropped frames).
    assert abs(rec.source_fps - 25) <= 0.2
    assert abs(rec.timestamp_fps - 25) <= 0.2
    assert rec.frames == RECORD_SECONDS * 25
    if rate > 0:
        assert rec.padded_frames == 0, "flashing page must not need padding"
    measured = measure_flash_rate(rec.video_path)["flashes_per_s"]
    assert abs(measured - rate) <= 0.2, f"measured {measured:.2f}/s, expected {rate}/s"

    check_iris(analyse_video(rec.video_path, IRIS_DEFAULT), default_iris)
    a = analyse_video(rec.video_path, WCAG)
    check_iris(a, wcag_iris)
    check_wcag(a, verdict, extra)


@pytest.mark.slow
def test_cli_html_end_to_end(tmp_path):
    code = audit.main(["--html", str(FIXTURES / "box39_5hz.html"),
                       "--duration", "4", "--out", str(tmp_path)])
    assert code == 1
    (report_dir,) = tmp_path.iterdir()
    for f in ("report.md", "report.json", "frames.csv", "recording.mp4", "iris.log"):
        assert (report_dir / f).is_file(), f
