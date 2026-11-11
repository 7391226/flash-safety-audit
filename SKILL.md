---
name: flash-safety-audit
description: Measure a web page, local HTML file, game recording or video for photosensitive epilepsy (seizure) risk and report against WCAG 2.3.1 (Three Flashes or Below Threshold). Use when the user asks to check, audit or test anything that flashes, flickers, strobes, blinks or has fast animation for epilepsy, seizure, photosensitivity, WCAG 2.3.1 or accessibility safety.
---

# Flash safety audit

Records the page in a **headless** browser (or reads a video), runs EA's IRIS
flash detector with the WCAG area threshold (0.111 of the screen), and writes
a Markdown + JSON report. It is a screening, not a certificate.
Run commands from this skill's folder with its own Python,
`.\.venv\Scripts\python.exe` (shown as `python` below). Pass `--out` to put
the report in the user's project.

## 1. Setup (only if `.venv` is missing or imports fail)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

## 2. Pick the input

| Input | Use when |
| --- | --- |
| `--url https://...` | a live web page |
| `--html path\page.html` | a local HTML file |
| `--video path\clip.mp4` | a game capture, trailer or any existing video |

```powershell
python scripts/audit.py --url https://example.com
python scripts/audit.py --html page.html --duration 10
python scripts/audit.py --video clip.mp4
```

Useful options: `--duration` (s, default 10), `--settle` (s, default 1),
`--viewport` (default 1024x768), `--out` (default `reports/`).
Exit code 0 = PASS, 1 = FAIL, 2 = error. Clicks, hover and scrolling are not
supported; if the hazard needs interaction, ask the user for a screen recording
and use `--video`.

## 3. Read the report (`report.md`)

- **WCAG 2.3.1 result** is the only verdict. FAIL if any luminance or red
  "flash failure" frames were found. Quote the time ranges.
- **Extra warnings (not WCAG)** are IRIS broadcast rules (e.g. 2–3 flashes/s
  for several seconds). Mention them separately; never call them a WCAG failure.
- Flicker faster than half the frame rate (~12 Hz for page recordings) is not
  measured. Never describe such content as "passed".
- Always repeat the disclaimer: a pass does not prove the page is safe.

## 4. Fixes to suggest when it fails

- Slow flashing to below 3 per second.
- Make the flashing area smaller (well under 341 x 256 px at 1024 x 768).
- Reduce the brightness contrast between the flash states.
- Avoid saturated red flashes.
- Honour `@media (prefers-reduced-motion: reduce)` and add a pause/stop control.

## 5. Safety rule

Never open test pages, audited pages or recordings in a visible browser, and
never show them or embed them for the user. Run them only headless through
`scripts/audit.py`. Share the report, not the footage.
