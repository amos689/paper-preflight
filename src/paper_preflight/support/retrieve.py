"""The passages of a cited work most likely to bear on a claim (S3).

Okapi BM25 over the work's passages, with two additions:

* numbers count double: a claim of "93.5% on SST-2" is about the passage that says 93.5, so a
  passage holding every number of the claim is ranked first;
* the abstract (passage 0) is always among the passages returned, since it states the work's
  main findings.

A dense re-ranker can come on top later; this ranking needs no model and no download.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

K1, B = 1.5, 0.75
TOP = 4
# a number ("93.5%", "0.001"), or a word that may hold digits and hyphens ("SST-2", "2D")
_WORD = re.compile(r"\d+(?:[.,]\d+)*%?(?![^\W_])|[^\W_]+(?:[-'][^\W_]+)*")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*%?")
_STOPWORDS = frozenset(
    "a an the of in on for to and or with by from as at is are was were be been being this that "
    "these those it its we our they their which who whom such than then there here can may might "
    "also not no but if into over under between using use used based via et al cited work".split()
)


def tokens(text: str) -> list[str]:
    """Lower-cased words and numbers, without stopwords; "93.5%" stays one token."""
    return [t for t in (m.group(0).lower() for m in _WORD.finditer(text)) if t not in _STOPWORDS]


@dataclass(frozen=True)
class Hit:
    index: int  # the passage's position in the work
    score: float
    numbers: bool  # holds every number of the claim


def rank(claim: str, passages: list[str] | tuple[str, ...], top: int = TOP) -> list[Hit]:
    """The ``top`` passages for the claim, best first (the abstract always included)."""
    if not passages:
        return []
    documents = [tokens(p) for p in passages]
    query = tokens(claim)
    numbers = {t for t in query if _NUMBER.fullmatch(t)}
    average = sum(len(d) for d in documents) / len(documents) or 1.0
    frequency = Counter(term for d in documents for term in set(d))
    hits = []
    for index, document in enumerate(documents):
        counts = Counter(document)
        score = 0.0
        for term in query:
            if term not in counts:
                continue
            idf = math.log(1 + (len(documents) - frequency[term] + 0.5) / (frequency[term] + 0.5))
            tf = (
                counts[term]
                * (K1 + 1)
                / (counts[term] + K1 * (1 - B + B * len(document) / average))
            )
            score += idf * tf * (2.0 if term in numbers else 1.0)
        has_numbers = bool(numbers) and numbers <= counts.keys()
        hits.append(Hit(index, score, has_numbers))
    hits.sort(key=lambda h: (h.numbers, h.score), reverse=True)
    chosen = hits[:top]
    if all(h.index != 0 for h in chosen):
        chosen = [*chosen[: top - 1], next(h for h in hits if h.index == 0)]
    return chosen
