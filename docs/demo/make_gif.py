"""Render docs/demo/demo.gif: a real run of paper-preflight on the demo paper, typed and printed.

    uv run --with pillow python docs/demo/make_gif.py [--font PATH] [--symbol-font PATH]

The text is the real report: the check runs against the live sources (or the local cache) and
is printed by the same renderer as the CLI, recorded instead of shown. Only the timing is staged.
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from rich.console import Console
from rich.segment import Segment
from rich.style import Style

from paper_preflight.check import VerifyOptions, run_check
from paper_preflight.report.text import render_text

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "demo.gif"
COMMAND = "paper-preflight check examples/demo-paper"
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
WAITING = "Verifying references against Crossref, dblp, arXiv, DataCite and OpenAlex…"
COLUMNS = 92
FONT_SIZE = 15
LINE = 21
PAD = 18
BAR = 30

# GitHub's dark terminal colours
BACKGROUND = (13, 17, 23)
BAR_COLOUR = (33, 38, 45)
FOREGROUND = (201, 209, 217)
DIM = (125, 133, 144)
PROMPT = (126, 231, 135)
COLOURS = {
    "red": (255, 123, 114),
    "yellow": (227, 179, 65),
    "cyan": (86, 212, 221),
    "green": (126, 231, 135),
}
DOTS = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]

FONTS = [
    "C:/Windows/Fonts/consola.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
]
BOLD_FONTS = [
    "C:/Windows/Fonts/consolab.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/System/Library/Fonts/Menlo.ttc",
]
SYMBOL_FONTS = [
    "C:/Windows/Fonts/seguisym.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Apple Symbols.ttf",
]

Span = tuple[str, tuple[int, int, int], bool]  # text, colour, bold


def first(paths: list[str]) -> str:
    for path in paths:
        if Path(path).exists():
            return path
    sys.exit(f"no font found among {paths}; pass one with --font")


def colour(style: Style | None) -> tuple[tuple[int, int, int], bool]:
    if style is None:
        return FOREGROUND, False
    bold = bool(style.bold)
    if style.dim:
        return DIM, bold
    name = style.color.name if style.color else ""
    return COLOURS.get(name, FOREGROUND), bold


def report_lines() -> list[list[Span]]:
    """The demo paper's report as the CLI prints it, line by line, with each span's colour."""
    result = run_check(ROOT / "examples" / "demo-paper", verify=VerifyOptions())
    console = Console(
        file=io.StringIO(), width=COLUMNS, record=True, force_terminal=True,
        color_system="truecolor",
    )  # fmt: skip
    render_text(result, console, "en", True)
    lines: list[list[Span]] = []
    for line in Segment.split_lines(console._record_buffer):
        spans: list[Span] = []
        for segment in line:
            if segment.text:
                fill, bold = colour(segment.style)
                spans.append((segment.text, fill, bold))
        lines.append(spans)
    while lines and not lines[-1]:
        lines.pop()
    return lines


class Screen:
    def __init__(self, rows: int, font: str, bold: str, symbols: str) -> None:
        self.regular = ImageFont.truetype(font, FONT_SIZE)
        self.bold = ImageFont.truetype(bold, FONT_SIZE)
        self.symbols = ImageFont.truetype(symbols, FONT_SIZE)
        self.cell = self.regular.getlength("M")
        self.size = (int(2 * PAD + COLUMNS * self.cell), BAR + 2 * PAD + rows * LINE)

    def frame(self, lines: list[list[Span]]) -> Image.Image:
        image = Image.new("RGB", self.size, BACKGROUND)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, self.size[0], BAR), fill=BAR_COLOUR)
        for i, dot in enumerate(DOTS):
            x = PAD + i * 20
            draw.ellipse((x, BAR / 2 - 6, x + 12, BAR / 2 + 6), fill=dot)
        for row, spans in enumerate(lines):
            x, y = float(PAD), BAR + PAD + row * LINE
            for text, fill, bold in spans:
                for char in text:
                    font = (
                        self.symbols if char in SPINNER else (self.bold if bold else self.regular)
                    )
                    draw.text((x, y), char, font=font, fill=fill)
                    x += self.cell
        return image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--font", default=None)
    parser.add_argument("--bold-font", default=None)
    parser.add_argument("--symbol-font", default=None)
    args = parser.parse_args()

    report = report_lines()
    screen = Screen(
        len(report) + 2,
        args.font or first(FONTS),
        args.bold_font or first(BOLD_FONTS),
        args.symbol_font or first(SYMBOL_FONTS),
    )
    prompt: list[Span] = [("$ ", PROMPT, True)]
    frames: list[tuple[Image.Image, int]] = [(screen.frame([prompt]), 800)]
    for end in range(2, len(COMMAND) + 2, 2):  # two characters a frame
        frames.append((screen.frame([[*prompt, (COMMAND[:end], FOREGROUND, False)]]), 70))
    typed = [*prompt, (COMMAND, FOREGROUND, False)]
    frames[-1] = (frames[-1][0], 500)
    for tick in range(14):
        waiting: list[Span] = [(SPINNER[tick % len(SPINNER)] + " ", COLOURS["green"], False)]
        frames.append((screen.frame([typed, [*waiting, (WAITING, DIM, False)]]), 90))
    shown = [typed]
    for line in report:
        shown.append(line)
        # a finding arrives whole: its message (and the message's wrapped lines) with its heading
        starts = not line or line[0][0].rstrip() in {"error", "warning", "info"}
        if starts or len(shown) == 2:
            frames.append((screen.frame(shown), 280))
        else:
            frames[-1] = (screen.frame(shown), 280)
    frames[-1] = (frames[-1][0], 9000)

    images = [
        image.quantize(colors=255, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
        for image, _ in frames
    ]
    images[0].save(
        OUT,
        save_all=True,
        append_images=images[1:],
        duration=[ms for _, ms in frames],
        loop=0,
        optimize=True,
    )
    print(f"{OUT.relative_to(ROOT)}: {len(frames)} frames, {OUT.stat().st_size // 1024} KiB")


if __name__ == "__main__":
    main()
