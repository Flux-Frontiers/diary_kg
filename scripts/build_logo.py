#!/usr/bin/env python3
"""Draw the DiaryKG logo in Art Techno and write every size the repo uses.

The mark is a pen nib whose breather hole is a die. It writes a line of dated
nodes, with a clock wave under it: someone wrote this, in order, over time.
The palette, drawing helpers and outlined lettering come from the Art Techno
brand build, so the SVGs render the same everywhere.

Usage::

    python scripts/build_logo.py

Needs ``fonttools`` and Pillow, Google Chrome for the PNG renders, and a clone
of https://github.com/Flux-Frontiers/art_techno beside this repo. Set ``CHROME``
to the browser binary if it is not at the default macOS path.

Writes, under ``assets/``:

- ``diarykg_logo.svg`` and ``diarykg_logo.png``: the square mark (1024 px PNG)
- ``logos/diarykg_icon.svg``: the mark reduced for 64 px and below
- ``logos/diarykg_banner.svg`` and ``logos/diarykg_banner.png``
- ``logos/logo_{512,256,128}.png`` from the mark and ``logos/logo_{64,32}.png``
  from the icon
- ``badges/badge_200.png`` from the mark and ``badges/badge_{80,40,20}.png``
  from the icon
"""

import importlib.util
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
AT_BUILD = ROOT.parent / "art_techno" / "docs" / "brand" / "build.py"

_spec = importlib.util.spec_from_file_location("at_build", AT_BUILD)
at = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(at)

f, line, pad, diamond, clipped_rect = at.f, at.line, at.pad, at.diamond, at.clipped_rect
OBSIDIAN, COPPER, GOLD, GREEN, MINT, SILK = (
    at.OBSIDIAN,
    at.COPPER,
    at.GOLD,
    at.GREEN,
    at.MINT,
    at.SILK,
)

NAME = "DIARYKG"
PART = "FLUX-FRONTIERS | DIARY-KG"


def rect(
    x: float, y: float, w: float, h: float, fill: str, stroke: str = "", width: float = 0
) -> str:
    s = f' stroke="{stroke}" stroke-width="{f(width)}"' if stroke else ""
    return f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" fill="{fill}"{s}/>'


def poly(pts: list[tuple[float, float]], fill: str) -> str:
    d = "M" + "L".join(f"{f(x)} {f(y)}" for x, y in pts) + "Z"
    return f'<path d="{d}" fill="{fill}"/>'


def die(x: float, y: float, s: float) -> str:
    """The breather hole: a green die in a dark line with a light core.

    :param x: Center x.
    :param y: Center y.
    :param s: Side length.
    """
    return rect(x - s / 2, y - s / 2, s, s, GREEN, OBSIDIAN, s / 9) + rect(
        x - s / 6, y - s / 6, s / 3, s / 3, SILK
    )


def open_via(x: float, y: float) -> str:
    """The open end of the written line: a gold ring round a dark core."""
    return f'<circle cx="{f(x)}" cy="{f(y)}" r="7.5" fill="{OBSIDIAN}" stroke="{GOLD}" stroke-width="3"/>'


def wave(x0: float, x1: float, y: float, amp: float, period: float, width: float) -> str:
    """A copper clock wave between two diamonds.

    :param x0: Left end.
    :param x1: Right end.
    :param y: Center line.
    :param amp: Half the wave height.
    :param period: Length of one high-low cycle.
    :param width: Stroke width.
    """
    half = period / 2
    n = int((x1 - x0 - 24) // half)
    n -= n % 2
    x = (x0 + x1) / 2 - n * half / 2
    pts = [(x0 + 8, y + amp), (x, y + amp)]
    hi = False
    for _ in range(n):
        yy = y + amp if hi else y - amp
        pts += [(x, yy), (x + half, yy)]
        x += half
        hi = not hi
    pts += [(x, y + amp), (x1 - 8, y + amp)]
    return (
        line(pts, COPPER, width)
        + diamond(x0 + 3, y + amp, 6, COPPER)
        + diamond(x1 - 3, y + amp, 6, COPPER)
    )


def nib() -> str:
    """The nib and its written line on a 512 field, centered on x = 256."""
    out = []
    # The grip: two copper heat-sink fins.
    for y in (40, 54):
        out.append(rect(214, y, 84, 9, COPPER))
    # The nib: shoulders, an engraved inner line, the slit and the die.
    body = [(206, 70), (306, 70), (326, 90), (326, 196), (256, 266), (186, 196), (186, 90)]
    out.append(poly(body, GOLD))
    out.append(line([(206, 104), (206, 188), (256, 238), (306, 188), (306, 104)], OBSIDIAN, 3.5))
    out.append(line([(256, 268), (256, 170)], OBSIDIAN, 4.5))
    out.append(die(256, 150, 34))
    # The written line: time, with an entry at each node.
    ly = 304
    out.append(line([(256, 262), (256, ly)], GOLD, 6))
    out.append(line([(100, ly), (412, ly)], GOLD, 6))
    out.append(open_via(94, ly) + open_via(418, ly))
    for x in (148, 202, 310, 364):
        out.append(pad(x, ly, 12, GOLD) + pad(x, ly, 5.3, GREEN))
    out.append(pad(256, ly, 9, GOLD))
    out.append(wave(132, 380, 344, 7, 31, 3.5))
    return "".join(out)


def nib_small() -> str:
    """The nib reduced for 64 px and below: the nib, its die, the line."""
    body = [(22, 10), (42, 10), (46, 14), (46, 30), (32, 44), (18, 30), (18, 14)]
    out = [poly(body, GOLD)]
    out.append(line([(32, 44.5), (32, 26)], OBSIDIAN, 2))
    out.append(die(32, 21, 10))
    out.append(line([(11, 52), (53, 52)], GOLD, 3) + line([(32, 43), (32, 52)], GOLD, 3))
    out.append(pad(17, 52, 3.4, GOLD) + pad(47, 52, 3.4, GOLD))
    return "".join(out)


def frame(w: float, h: float, inset: float, c: float, heavy: float) -> str:
    """Double frame with 45-degree corners and a green diamond at each corner.

    :param w: Canvas width.
    :param h: Canvas height.
    :param inset: Distance of the heavy line from the canvas edge.
    :param c: Corner cut of the heavy line.
    :param heavy: Stroke width of the heavy line.
    """
    out = [
        f'<path d="{clipped_rect(inset, inset, w - 2 * inset, h - 2 * inset, c)}" fill="none" stroke="{GOLD}" stroke-width="{f(heavy)}"/>',
        f'<path d="{clipped_rect(inset * 1.9, inset * 1.9, w - 3.8 * inset, h - 3.8 * inset, c * 0.75)}" fill="none" stroke="{GOLD}" stroke-width="{f(heavy * 0.4)}" stroke-opacity=".6"/>',
    ]
    d = inset * 1.45 + c * 0.4375
    for cx, cy in ((d, d), (w - d, d), (d, h - d), (w - d, h - d)):
        out.append(diamond(cx, cy, inset * 0.5, GREEN))
    return "".join(out)


def svg(w: int, h: int, title: str, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f"<title>{title}</title>"
        f'<rect width="{w}" height="{h}" fill="{OBSIDIAN}"/>{body}</svg>\n'
    )


def mark(display, mono) -> str:
    """512 square mark: the nib, the name and the part line beneath."""
    body = frame(512, 512, 10, 26, 5) + nib()
    body += display.path(NAME, 256, 430, 40, 0.2, "middle", GOLD)
    body += mono.path(PART, 256, 462, 13.5, 0.3, "middle", MINT)
    return svg(512, 512, "DiaryKG mark, Art Techno", body)


def icon() -> str:
    """64 icon: the reduced nib in one heavy frame, no lettering."""
    body = f'<path d="{clipped_rect(2.5, 2.5, 59, 59, 7.5)}" fill="none" stroke="{GOLD}" stroke-width="3"/>'
    return svg(64, 64, "DiaryKG icon, Art Techno", body + nib_small())


def banner(display, mono) -> str:
    """1280 x 320 banner: the nib left, the name and part line right."""
    s = 0.78
    body = frame(1280, 320, 10, 18, 3)
    body += (
        f'<g transform="translate({f(230 - 256 * s)} {f(160 - 196 * s)}) scale({s})">{nib()}</g>'
    )
    cx, room, gap = 820, 760, 34
    size = min(120, 120 * room / display.width(NAME, 120, 0.2))
    part = min(26, 26 * room / mono.width(PART, 26, 0.3))
    cap = display.cap * size / display.upm
    pcap = mono.cap * part / mono.upm
    base = (320 - (cap + gap + pcap)) / 2 + cap
    body += display.path(NAME, cx, base, size, 0.2, "middle", GOLD)
    body += mono.path(PART, cx, base + gap + pcap, part, 0.3, "middle", MINT)
    return svg(1280, 320, "DiaryKG banner, Art Techno", body)


def render(src: Path, out: Path, w: int, h: int) -> None:
    """Render the SVG ``src`` to ``out`` at ``w`` x ``h`` px with headless Chrome.

    :param src: SVG file; its ``width`` attribute sets the CSS width.
    :param out: PNG to write.
    :param w: Output width in px.
    :param h: Output height in px.
    """
    svg_w = int(src.read_text().split('width="', 1)[1].split('"', 1)[0])
    subprocess.run(
        [
            at.CHROME,
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--window-size={svg_w},{svg_w * h // w}",
            f"--force-device-scale-factor={w / svg_w}",
            f"--screenshot={out}",
            src.as_uri(),
        ],
        check=True,
        capture_output=True,
    )


def resized(master: Path, dest: Path, px: int) -> None:
    Image.open(master).convert("RGB").resize((px, px), Image.LANCZOS).save(dest, optimize=True)


def main() -> None:
    at.fetch_fonts()
    display = at.Face(at.CACHE / "JosefinSans.ttf", weight=600)
    mono = at.Face(at.CACHE / "IBMPlexMono-Medium.ttf")

    assets = ROOT / "assets"
    logos = assets / "logos"
    badges = assets / "badges"

    mark_svg = assets / "diarykg_logo.svg"
    icon_svg = logos / "diarykg_icon.svg"
    banner_svg = logos / "diarykg_banner.svg"
    mark_svg.write_text(mark(display, mono))
    icon_svg.write_text(icon())
    banner_svg.write_text(banner(display, mono))

    mark_png = assets / "diarykg_logo.png"
    render(mark_svg, mark_png, 1024, 1024)
    render(banner_svg, banner_svg.with_suffix(".png"), 2560, 640)
    with tempfile.TemporaryDirectory() as tmp:
        icon_png = Path(tmp) / "icon.png"
        render(icon_svg, icon_png, 1024, 1024)
        for px in (512, 256, 128):
            resized(mark_png, logos / f"logo_{px}.png", px)
        for px in (64, 32):
            resized(icon_png, logos / f"logo_{px}.png", px)
        resized(mark_png, badges / "badge_200.png", 200)
        for px in (80, 40, 20):
            resized(icon_png, badges / f"badge_{px}.png", px)


if __name__ == "__main__":
    main()
