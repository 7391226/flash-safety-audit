# flash-safety-audit

> **Warning:** This is a preliminary screening, not a compliance certificate.
> A passing result does not prove that the page is safe.

*[Türkçe](README.tr.md)*

An [Agent Skill](https://docs.claude.com/en/docs/claude-code/skills) and
command-line tool that screens a web page or a video for **photosensitive
epilepsy** risk and reports the result against **WCAG 2.3.1 – Three Flashes or
Below Threshold**.

It records the page in a headless Chromium (Playwright for Python), analyses
the frames with [IRIS](https://github.com/electronicarts/IRIS) through its
Python port [`iris-pse-detection`](https://pypi.org/project/iris-pse-detection/),
and writes a Markdown and JSON report.

## Why this exists

IRIS is a good flash detector, but its default flash area threshold is 0.25
(25 % of the screen). WCAG 2.3.1 uses a combined area of 341 × 256 px on a
1024 × 768 screen:

    341 × 256 / (1024 × 768) ≈ 0.111

With the default setting, pages that flash 5 times per second over 15 %, 20 %
or 24 % of the screen **pass**. With 0.111 they correctly **fail**. This tool
sets the WCAG threshold and keeps IRIS's extra broadcast rules apart from the
WCAG verdict.

## Installation (Windows, PowerShell)

Requires Python 3.10 or newer (tested with 3.13).

```powershell
git clone <repository-url> flash-safety-audit
cd flash-safety-audit
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
```

To use it as a Claude Code skill, copy or clone the folder into
`%USERPROFILE%\.claude\skills\flash-safety-audit` (personal) or
`<project>\.claude\skills\flash-safety-audit` (one project). Claude then uses
it when you ask, for example, "check this page for epilepsy risk".

ffmpeg is **not** required: the OpenCV wheel reads Playwright's `.webm`
recordings directly (verified on Windows 11). If your OpenCV build cannot read
a video, convert it to H.264 `.mp4` first, for example with
`ffmpeg -i input.webm output.mp4`.

## Usage

```powershell
python scripts/audit.py --url https://example.com
python scripts/audit.py --html page.html
python scripts/audit.py --video game_capture.mp4
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--viewport` | `1024x768` | Browser size. Matches the WCAG pixel definition. |
| `--duration` | `10` | Seconds to record. |
| `--settle` | `1` | Seconds to wait after page load before recording. |
| `--out` | `reports/` | Folder for the report folders. |
| `--area-threshold` | `0.111` | Flash area proportion. Change only on purpose. |

Exit code: `0` WCAG pass, `1` WCAG fail, `2` error.

Each run creates `reports/<name>-<time>/` with:

- `report.md` – the human-readable report
- `report.json` – the same data for tools
- `frames.csv` – IRIS data for every frame
- `recording.mp4` – the recorded page (not created for `--video`)
- `iris.log` – IRIS console output

## Reading the report

The report has two separate sections.

**WCAG 2.3.1 result – PASS / FAIL.** Number of luminance and red "flash
failure" frames found with the 0.111 area threshold (more than 3 flashes in
any one second). Any value above zero is a FAIL. Time ranges are given in
seconds from the start of the recording.

**Extra warnings (not WCAG).** IRIS "extended failure" and "warning" frames.
These come from broadcast guidelines, for example 2–3 flashes per second
sustained for about 4 seconds. They do not change the WCAG verdict. A
full-screen page flashing twice per second is a WCAG pass but shows an
extended failure here.

## Limits

- **Fast flicker is not measured.** Page recordings run at 25 frames per
  second, so flicker faster than about 12 per second (half the frame rate) can
  be counted wrongly. A PASS does not cover such content.
- **Area model.** IRIS adds up the flashing area over the whole frame; WCAG
  looks at any single 341 × 256 px region. For small flashes spread over the
  screen, the result can be stricter than WCAG.
- **Other viewports.** With a viewport other than 1024 × 768 the threshold
  stays 0.111 of the viewport; the report states the assumption that the
  viewport fills a typical screen.
- **No interaction.** Clicks, hover, scrolling and keyboard input are not
  supported in this version. Record such content yourself and use `--video`.
- **Still pages.** Chromium sends no new frames while nothing changes. The
  last frame is repeated to fill the recording, and the report says so.
- **Video frame rate.** IRIS truncates the frame rate to an integer (29.97 →
  29), which slightly shifts timing for such videos.
- Pattern (stripe) detection is not used.

## Tests

```powershell
python -m pytest -m "not slow"   # fast: synthetic videos, about 15 s
python -m pytest                 # all: also records 11 pages, about 5 min
```

`tests/make_fixtures.py` writes the HTML pages in `tests/fixtures/`.
`tests/make_videos.py` creates synthetic 640 × 360, 30 fps, 6 s videos.
The slow tests also check that each recording has 25 fps and the expected
flash rate (± 0.2), to catch dropped frames.

Expected and measured results on Windows 11:

| Page | IRIS default (0.25) | WCAG setting (0.111) | WCAG 2.3.1 | Extra warning |
| --- | --- | --- | --- | --- |
| Still white | Pass | Pass | PASS | No |
| Full screen, 1/s | Pass | Pass | PASS | No |
| Full screen, 2/s | Fail (extended) | Fail (extended) | PASS | Yes |
| Full screen, 4/s | Fail | Fail | FAIL | — |
| Full screen, 5/s | Fail | Fail | FAIL | — |
| Full screen red (#f00), 5/s | Fail (red too) | Fail | FAIL | — |
| 30 % × 30 % (9 % of area), 5/s | Pass | Pass | PASS | No |
| 39 % × 39 % (15 %), 5/s | Pass | Fail | FAIL | — |
| 45 % × 45 % (20 %), 5/s | Pass | Fail | FAIL | — |
| 49 % × 49 % (24 %), 5/s | Pass | Fail | FAIL | — |
| 60 % × 60 % (36 %), 5/s | Fail | Fail | FAIL | — |

The test pages flash. **Never open them in a visible browser.** The README
deliberately contains no flashing images or videos.

## Licence and credits

MIT – see [LICENSE](LICENSE) and [NOTICE](NOTICE).

- [IRIS](https://github.com/electronicarts/IRIS) by Electronic Arts Inc.,
  BSD-3-Clause.
- [iris-pse-detection](https://pypi.org/project/iris-pse-detection/), the
  Python port of IRIS, MIT.
