"""Generate the HTML test fixtures in tests/fixtures/.

Each page has a black background. A centred box (or the whole viewport)
blinks between a colour and black using CSS @keyframes with steps(1, end).
Period = 1 / rate seconds. Box size is given as a percentage of the
viewport width and height, so the flashing area proportion is size**2.

Run:  python tests/make_fixtures.py
"""

from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# name, colour, flashes per second (0 = static), box size in % of viewport
FIXTURES = [
    ("static_white", "#fff", 0, 100),
    ("full_1hz", "#fff", 1, 100),
    ("full_2hz", "#fff", 2, 100),
    ("full_4hz", "#fff", 4, 100),
    ("full_5hz", "#fff", 5, 100),
    ("full_red_5hz", "#f00", 5, 100),
    ("box30_5hz", "#fff", 5, 30),
    ("box39_5hz", "#fff", 5, 39),
    ("box45_5hz", "#fff", 5, 45),
    ("box49_5hz", "#fff", 5, 49),
    ("box60_5hz", "#fff", 5, 60),
]

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{name}</title>
<!-- TEST FIXTURE: may flash. Open only in a headless browser. -->
<style>
  html, body {{ margin: 0; height: 100%; background: #000; overflow: hidden; }}
  #box {{
    position: absolute;
    left: {offset}vw; top: {offset}vh;
    width: {size}vw; height: {size}vh;
    background: {colour};
    {animation}
  }}
  @keyframes blink {{
    0%   {{ background: {colour}; }}
    50%  {{ background: #000; }}
  }}
</style>
</head>
<body><div id="box"></div></body>
</html>
"""


def render(name: str, colour: str, rate: float, size: int) -> str:
    if rate > 0:
        animation = f"animation: blink {1.0 / rate:g}s steps(1, end) infinite;"
    else:
        animation = ""
    return TEMPLATE.format(
        name=name, colour=colour, size=size,
        offset=f"{(100 - size) / 2:g}", animation=animation,
    )


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    for name, colour, rate, size in FIXTURES:
        (FIXTURES_DIR / f"{name}.html").write_text(
            render(name, colour, rate, size), encoding="utf-8"
        )
    print(f"Wrote {len(FIXTURES)} fixtures to {FIXTURES_DIR}")


if __name__ == "__main__":
    main()
