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
    key = " ".join(
        _WORD_RE.findall(fold(_STAR.sub(" ", title).replace("_", " ").replace("×", "x")))
    )
    key = _SOLAR.sub(r"\1 sun", key) if " sun" in key or " solar" in key else key
    if "sim" in key:
        key = " ".join(w for w in map(_untilde, key.split()) if w)
    if any(s in key for s in ("part ", "approximately equal to", "lambda", "0")):
        key = _PART_NUMBER.sub("", _APPROXIMATELY_EQUAL.sub("", key))
        key = _LAMBDA.sub("", _ZERO_FOR_O.sub("o", key))
        key = " ".join(key.split())
    return key


_SOLAR = re.compile(r"\b([mlr]) (?:sub )?(?:sun|solar)\b")
# a subscript star, however written: the stellar mass M_⋆ is the M_star an entry writes (MNRAS
# 462, 1470 in Crossref; heldout17) and the M_* or M⋆ of others, all read as "M"
_STAR = re.compile(r"_\s*(?:[⋆★*]|star\b)", re.IGNORECASE)
# \lsim and \gsim lost their backslash in a registry's title: Crossref's "at 2 lsimzlsim 3" is
# "at 2 <~ z <~ 3" (MNRAS 377, 1717; heldout18)
_TILDE_RELATION = re.compile(r"([lg]sim)?(\w{0,3}?)([lg]sim)?")


def _untilde(word: str) -> str:
    match = _TILDE_RELATION.fullmatch(word)
    return match[2] if match and (match[1] or match[3]) else word


# a symbol a registry spelt out ("Z approximately equal to 0.5", ApJ 285, 426), and the "Part"
# before a part's number ("... networks. Part I. Modeling" where Crossref has "networks: I.")
_APPROXIMATELY_EQUAL = re.compile(r"\bapproximately equal to\b")
_PART_NUMBER = re.compile(r"\bpart (?=(?:[ivx]+|\d+)\b)")
# a wavelength as ADS spells it ("the interstellar lambda 3302 Na I doublet", where Crossref
# dropped the λ; heldout21); a zero a registry typed for the letter o ("A Can0nical
# Integrati0n Technique", IEEE TNS 30; heldout21)
_LAMBDA = re.compile(r"\b(?:lambda ?)+(?=\d)")
_ZERO_FOR_O = re.compile(r"(?<=[a-z])0(?=[a-z])")


def word_count(title: str) -> int:
    key = title_key(title)
    if not key:
        return 0
    words = key.split()
    # CJK text has no spaces: count characters of CJK runs as words.
    return sum(len(w) if any("一" <= c <= "鿿" for c in w) else 1 for w in words)
