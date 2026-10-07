"""Render the README's logo and static badges as SVG files in docs/assets/.

    uv run --with pillow python docs/assets/make_brand.py

Text widths are measured with the real fonts (Verdana for badges, Arial Bold for the wordmark,
Microsoft YaHei or another CJK font for Chinese), so the shapes fit the text. Live badges (CI,
PyPI, Glama) are not made here; the README links them from their services.
"""

# ruff: noqa: E501  (the SVG templates are clearer as one line per element)

from __future__ import annotations

from html import escape
from pathlib import Path

from PIL import ImageFont

HERE = Path(__file__).resolve().parent
BRAND = HERE / "brand"
BADGES = HERE / "badges"

FONT_DIRS = [Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype"), Path("/Library/Fonts")]


def _font(names: list[str], size: int) -> ImageFont.FreeTypeFont:
    for folder in FONT_DIRS:
        for name in names:
            hits = list(folder.rglob(name)) if folder.exists() else []
            if hits:
                return ImageFont.truetype(str(hits[0]), size)
    raise SystemExit(f"none of {names} found; pass a system with these fonts")


VERDANA = _font(["verdana.ttf", "DejaVuSans.ttf"], 11)
CJK = _font(["msyh.ttc", "NotoSansCJK-Regular.ttc", "PingFang.ttc"], 11)
ARIAL_BOLD = _font(["arialbd.ttf", "DejaVuSans-Bold.ttf"], 72)


def text_width(text: str) -> float:
    """Badge text width: CJK characters measured with the CJK font, the rest with Verdana."""
    width = 0.0
    for ch in text:
        font = CJK if ord(ch) > 0x2E80 else VERDANA
        width += font.getlength(ch)
    return width


# ---------------------------------------------------------------- logo

NAVY = "#17324d"
NAVY_DARK_MODE = "#24496f"
PAPER = "#f6f9fc"
FOLD = "#9ec5ef"
LINE = "#c3d3e6"
BRACKET = "#2f6fb0"
CHECK = "#2da44e"


def mark(x: int, y: int, background: str) -> str:
    """The mark: a sheet of references with a green check, in a 128-pixel rounded square."""

    def at(dx: float, dy: float) -> str:
        return f"{x + dx:g} {y + dy:g}"

    rows = []
    for i, length in enumerate((34, 26, 38, 22)):
        top = 34 + i * 15
        rows.append(
            f'<rect x="{x + 36}" y="{y + top}" width="7" height="7" rx="1.5" fill="{BRACKET}"/>'
            f'<rect x="{x + 48}" y="{y + top}" width="{length}" height="7" rx="3.5" fill="{LINE}"/>'
        )
    return "\n  ".join(
        [
            f'<rect x="{x}" y="{y}" width="128" height="128" rx="32" fill="{background}"/>',
            f'<path d="M{at(34, 18)}H{x + 72}L{at(96, 42)}V{y + 102}'
            f"A8 8 0 0 1 {at(88, 110)}H{x + 34}A8 8 0 0 1 {at(26, 102)}V{y + 26}"
            f'A8 8 0 0 1 {at(34, 18)}Z" fill="{PAPER}"/>',
            f'<path d="M{at(72, 18)}V{y + 36}A6 6 0 0 0 {at(78, 42)}H{x + 96}Z" fill="{FOLD}"/>',
            *rows,
            f'<circle cx="{x + 94}" cy="{y + 96}" r="22" fill="{CHECK}" stroke="{background}" '
            'stroke-width="6"/>',
            f'<path d="M{x + 84} {y + 96.5}L{x + 91.5} {y + 104}L{x + 104.5} {y + 89}" fill="none" '
            'stroke="#ffffff" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round"/>',
        ]
    )


def logo(dark: bool) -> str:
    first, second = "paper-", "preflight"
    tracking = -2
    width_first = ARIAL_BOLD.getlength(first) + tracking * len(first)
    width_second = ARIAL_BOLD.getlength(second) + tracking * len(second)
    text_x = 174
    width = int(text_x + width_first + width_second + 24)
    ink, accent = ("#e6edf3", "#79b8ff") if dark else ("#1b2a3a", "#2f6fb0")
    background = NAVY_DARK_MODE if dark else NAVY
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="160" viewBox="0 0 {width} 160" role="img" aria-labelledby="title desc">
  <title id="title">paper-preflight</title>
  <desc id="desc">A sheet of references with a green check mark, beside the paper-preflight wordmark.</desc>
  {mark(16, 16, background)}
  <text x="{text_x}" y="106" fill="{ink}" font-family="Arial, Helvetica, sans-serif" font-size="72" font-weight="700" letter-spacing="{tracking}">{first}<tspan fill="{accent}">{second}</tspan></text>
</svg>
"""


def mark_only() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160" role="img" aria-label="paper-preflight">
  <title>paper-preflight</title>
  {mark(16, 16, NAVY)}
</svg>
"""


# ---------------------------------------------------------------- badges

LABEL = "#3b4a5a"
FAMILY = "Verdana, Geneva, DejaVu Sans, Microsoft YaHei, PingFang SC, Noto Sans CJK SC, sans-serif"


def badge(label: str, value: str, color: str) -> str:
    pad = 8
    left = round(text_width(label) + 2 * pad)
    right = round(text_width(value) + 2 * pad)
    total = left + right
    title = escape(f"{label}: {value}")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="22" viewBox="0 0 {total} 22" role="img" aria-label="{title}">
  <title>{title}</title>
  <clipPath id="r"><rect width="{total}" height="22" rx="3"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{total}" height="22" fill="{LABEL}"/>
    <rect x="{left}" width="{right}" height="22" fill="{color}"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="{FAMILY}" font-size="11">
    <text x="{left / 2:g}" y="15">{escape(label)}</text>
    <text x="{left + right / 2:g}" y="15">{escape(value)}</text>
  </g>
</svg>
"""


BLUE, GREEN, TEAL, PURPLE, SLATE = "#2f6fb0", "#2da44e", "#2e7d78", "#6f52c8", "#4f6d8a"

# name: (English label, English value, Chinese label, Chinese value, colour)
BADGE_SET = {
    "license": ("license", "MIT", "许可证", "MIT", GREEN),
    "python": ("Python", "3.11–3.14", "Python", "3.11–3.14", "#346c97"),
    "input": ("input", "LaTeX · BibTeX · PDF", "输入", "LaTeX · BibTeX · PDF", BLUE),
    "sources": ("checked against", "6 scholarly databases", "核对来源", "6 个学术数据库", TEAL),
    "verdicts": ("verdicts", "no LLM", "判定", "不用大模型", PURPLE),
    "mcp": ("MCP", "read-only", "MCP", "只读", PURPLE),
    "platforms": ("platforms", "Windows / Linux / macOS", "平台", "Windows / Linux / macOS", SLATE),
    "languages": ("languages", "EN / 简体中文", "语言", "EN / 简体中文", SLATE),
}


def main() -> None:
    BRAND.mkdir(parents=True, exist_ok=True)
    BADGES.mkdir(parents=True, exist_ok=True)
    (BRAND / "paper-preflight-logo.svg").write_text(logo(dark=False), encoding="utf-8")
    (BRAND / "paper-preflight-logo-dark.svg").write_text(logo(dark=True), encoding="utf-8")
    (BRAND / "paper-preflight-mark.svg").write_text(mark_only(), encoding="utf-8")
    for name, (en_label, en_value, zh_label, zh_value, color) in BADGE_SET.items():
        (BADGES / f"{name}.en.svg").write_text(badge(en_label, en_value, color), encoding="utf-8")
        (BADGES / f"{name}.zh-CN.svg").write_text(
            badge(zh_label, zh_value, color), encoding="utf-8"
        )
    print(f"wrote 3 logo files and {2 * len(BADGE_SET)} badges")


if __name__ == "__main__":
    main()
