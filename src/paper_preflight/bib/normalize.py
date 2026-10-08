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


def deaccent(text: str) -> str:
    """Strip diacritics and fold special letters, keeping the case ("Étienne" is "Etienne")."""
    text = unicodedata.normalize("NFKD", text.translate(_SPECIAL_LETTERS))
    return unicodedata.normalize("NFKC", "".join(c for c in text if not unicodedata.combining(c)))


def fold(text: str) -> str:
    """Lower-case, strip diacritics and fold special letters; CJK characters pass through."""
    return deaccent(text).casefold()


def title_key(title: str) -> str:
    """A comparison key for titles: folded words joined by single spaces.

    Digits are kept ("16x16" ≠ "32x32") and CJK text is not dropped, unlike ASCII-only keys.
    Hyphens and punctuation are treated as separators. The solar mass reads alike however a
    registry writes it ("1 M sub sun" in ADS, "1 M(solar)" in Crossref, 10.1086/172827).
    """
    key = " ".join(_WORD_RE.findall(fold(title.replace("_", " "))))
    return _SOLAR.sub(r"\1 sun", key) if " sun" in key or " solar" in key else key


_SOLAR = re.compile(r"\b([mlr]) (?:sub )?(?:sun|solar)\b")


def word_count(title: str) -> int:
    key = title_key(title)
    if not key:
        return 0
    words = key.split()
    # CJK text has no spaces: count characters of CJK runs as words.
    return sum(len(w) if any("一" <= c <= "鿿" for c in w) else 1 for w in words)
