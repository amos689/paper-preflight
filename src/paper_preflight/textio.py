"""Reading text files with honest encoding detection.

LaTeX and BibTeX files in the wild come as UTF-8 (with or without BOM), GB18030/GBK (common in
Chinese theses), or Latin-1. We never guess silently: the detected encoding is returned so that
it can be reported, and Latin-1 is only used as a last resort because it accepts any byte.
"""

from __future__ import annotations

import codecs
from dataclasses import dataclass
from pathlib import Path

_FALLBACK_ENCODINGS = ("utf-8", "gb18030", "latin-1")


@dataclass(frozen=True)
class TextFile:
    path: Path
    text: str
    encoding: str
    had_bom: bool
    newline: str  # "\n", "\r\n" or "\r" (the first line ending seen; "\n" if none)


def decode_bytes(data: bytes) -> tuple[str, str, bool]:
    """Decode bytes, returning (text, encoding, had_bom)."""
    if data.startswith(codecs.BOM_UTF8):
        return data[len(codecs.BOM_UTF8) :].decode("utf-8"), "utf-8", True
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16"), "utf-16", True
    for encoding in _FALLBACK_ENCODINGS:
        try:
            return data.decode(encoding), encoding, False
        except UnicodeDecodeError:
            continue
    raise AssertionError("latin-1 decodes any byte sequence")  # pragma: no cover


def detect_newline(text: str) -> str:
    index = text.find("\n")
    if index == -1:
        return "\r" if "\r" in text else "\n"
    return "\r\n" if index > 0 and text[index - 1] == "\r" else "\n"


def read_text(path: Path) -> TextFile:
    """Read a text file, keeping its original line endings (offsets must match the file)."""
    text, encoding, had_bom = decode_bytes(path.read_bytes())
    return TextFile(
        path=path, text=text, encoding=encoding, had_bom=had_bom, newline=detect_newline(text)
    )


class LineIndex:
    """Map character offsets to 1-based (line, column) positions.

    Columns count Unicode code points, which is what we declare in SARIF output
    (``columnKind: unicodeCodePoints``). ``\\r\\n`` counts as a single line break.
    """

    def __init__(self, text: str) -> None:
        starts = [0]
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch == "\r":
                if i + 1 < n and text[i + 1] == "\n":
                    i += 1
                starts.append(i + 1)
            elif ch == "\n":
                starts.append(i + 1)
            i += 1
        self._starts = starts

    def position(self, offset: int) -> tuple[int, int]:
        """Return the 1-based (line, column) of a character offset."""
        lo, hi = 0, len(self._starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self._starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1, offset - self._starts[lo] + 1
