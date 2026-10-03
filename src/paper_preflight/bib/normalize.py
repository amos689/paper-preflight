"""Text normalisation shared by duplicate detection and (later) source matching."""

from __future__ import annotations

import re
import unicodedata

# Letters that NFKD does not decompose into ASCII base letters.
_SPECIAL_LETTERS = str.maketrans(
    {"ß": "ss", "ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "æ": "ae", "Æ": "AE",
     "œ": "oe", "Œ": "OE", "þ": "th", "ı": "i"}
)  # fmt: skip
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def fold(text: str) -> str:
    """Lower-case, strip diacritics and fold special letters; CJK characters pass through."""
    text = unicodedata.normalize("NFKD", text.translate(_SPECIAL_LETTERS))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return unicodedata.normalize("NFKC", text).casefold()


def title_key(title: str) -> str:
    """A comparison key for titles: folded words joined by single spaces.

    Digits are kept ("16x16" ≠ "32x32") and CJK text is not dropped, unlike ASCII-only keys.
    Hyphens and punctuation are treated as separators.
    """
    return " ".join(_WORD_RE.findall(fold(title.replace("_", " "))))


def word_count(title: str) -> int:
    key = title_key(title)
    if not key:
        return 0
    words = key.split()
    # CJK text has no spaces: count characters of CJK runs as words.
    return sum(len(w) if any("一" <= c <= "鿿" for c in w) else 1 for w in words)
