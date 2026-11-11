"""Write the audit result as Markdown and JSON."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from analyse import Analysis

DISCLAIMER = (
    "This is a preliminary screening, not a compliance certificate. "
    "A passing result does not prove that the page is safe."
)


def write_reports(
    out_dir: Path,
    source: str,
    analysis: Analysis,
    viewport: tuple[int, int] | None,
    recording: dict | None,
) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    notes = _notes(analysis, viewport, recording)

    data = {
        "disclaimer": DISCLAIMER,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "viewport": list(viewport) if viewport else None,
        "wcag_2_3_1": {
            "result": "PASS" if analysis.wcag_pass else "FAIL",
            "area_threshold": analysis.area_threshold,
            "luminance_flash_fail_frames": analysis.luminance_flash_fail_frames,
            "red_flash_fail_frames": analysis.red_flash_fail_frames,
            "luminance_fail_intervals": [i.label() for i in analysis.luminance_fail_intervals],
            "red_fail_intervals": [i.label() for i in analysis.red_fail_intervals],
        },
        "extra_warnings_non_wcag": {
            "luminance_extended_fail_frames": analysis.luminance_extended_fail_frames,
            "red_extended_fail_frames": analysis.red_extended_fail_frames,
            "luminance_warning_frames": analysis.luminance_warning_frames,
            "red_warning_frames": analysis.red_warning_frames,
            "extended_fail_intervals": [i.label() for i in analysis.extended_intervals],
            "iris_overall_result": analysis.iris_overall,
        },
        "analysis": analysis.to_dict(),
        "recording": recording,
        "notes": notes,
    }
    json_path = out_dir / "report.json"
    json_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    md_path = out_dir / "report.md"
    md_path.write_text(_markdown(source, analysis, viewport, recording, notes), encoding="utf-8")
    return md_path, json_path


def _notes(a: Analysis, viewport: tuple[int, int] | None, recording: dict | None) -> list[str]:
    notes = [
        f"Flicker faster than about {a.max_measurable_hz:g} flashes per second "
        f"(half of the {a.fps:g} fps frame rate) cannot be measured reliably. "
        "Such content was not verified; a PASS does not cover it.",
        "IRIS adds up the flashing area over the whole frame. WCAG looks at any "
        "single 341 x 256 px region. For small flashes spread across the screen "
        "this result can be stricter than WCAG.",
        "Time ranges show the frames IRIS flagged. Each flag looks back over the "
        "previous 1 second, so the flashing may start up to 1 s earlier.",
    ]
    if recording and recording.get("padded_frames"):
        notes.append(
            f"The browser sent no new frames for the last {recording['padded_frames']} "
            "frame(s), which means the screen did not change. The last frame was "
            "repeated to fill the recording."
        )
    if viewport and tuple(viewport) != (1024, 768):
        notes.insert(0, (
            f"Viewport was {viewport[0]} x {viewport[1]}, not 1024 x 768. The area "
            f"threshold was kept at {a.area_threshold:g} of the viewport. "
            "It was assumed that the viewport fills a typical screen."
        ))
    if viewport is None:
        notes.insert(0, (
            f"Area threshold {a.area_threshold:g} of the video frame. It was "
            "assumed that the video fills a typical screen."
        ))
    return notes


def _intervals_text(intervals) -> str:
    return ", ".join(i.label() for i in intervals) if intervals else "—"


def _markdown(source, a: Analysis, viewport, recording, notes) -> str:
    verdict = "PASS" if a.wcag_pass else "FAIL"
    lines = [
        "# Flash safety audit",
        "",
        f"> **Warning:** {DISCLAIMER}",
        "",
        f"- **Source:** `{source}`",
    ]
    if viewport:
        lines.append(f"- **Viewport:** {viewport[0]} x {viewport[1]}")
    lines += [
        f"- **Analysed:** {a.frames} frames at {a.fps:g} fps ({a.duration_s:g} s)",
        "",
        f"## WCAG 2.3.1 result: {verdict}",
        "",
        f"Area threshold: {a.area_threshold:g} of the screen "
        "(WCAG: 341 x 256 px on 1024 x 768 ≈ 0.111). "
        "More than 3 flashes in any 1 second over this area is a failure.",
        "",
        "| Flash type | Failed frames | Time ranges |",
        "| --- | --- | --- |",
        f"| Luminance (general flash) | {a.luminance_flash_fail_frames} | "
        f"{_intervals_text(a.luminance_fail_intervals)} |",
        f"| Red flash | {a.red_flash_fail_frames} | {_intervals_text(a.red_fail_intervals)} |",
        "",
        "## Extra warnings (not WCAG)",
        "",
        "These come from broadcast guidelines used by IRIS (for example 2–3 flashes "
        "per second sustained for several seconds). They do **not** change the "
        "WCAG 2.3.1 result above.",
        "",
        "| Type | Luminance frames | Red frames |",
        "| --- | --- | --- |",
        f"| Extended failure | {a.luminance_extended_fail_frames} | {a.red_extended_fail_frames} |",
        f"| Warning | {a.luminance_warning_frames} | {a.red_warning_frames} |",
        "",
        f"Extended failure time ranges: {_intervals_text(a.extended_intervals)}",
        "",
        f"IRIS overall result (with this area threshold): `{a.iris_overall}`",
        "",
        "## Limits and assumptions",
        "",
    ]
    lines += [f"- {n}" for n in notes]
    lines += ["", "## Files", ""]
    if recording:
        lines.append(f"- Recording: `{Path(recording['video_path']).name}`")
    if a.frame_csv:
        lines.append(f"- Frame data: `{a.frame_csv.name}`")
    lines += ["- Machine-readable report: `report.json`", ""]
    return "\n".join(lines)
