"""Whether a cited work's text confirms a claim, with the passage that shows it (S5).

A :class:`Verifier` scores how strongly a passage supports a claim (0..1); a small local model
does it. ``support`` is an evidence finder, not a judge of citations:

* **supported**: a passage scores at least ``support_at``; the quote is that passage's best
  sentence, an exact excerpt of the text;
* **could not confirm**: everything else, with the reason: no text of the work could be had,
  only its abstract was available, or no passage of the accessible text scored high enough.

It never says that a citation is wrong. On the gold set (evals/support_eval.py), a low score
meant a mis-citation less than half of the time: genuine citations often paraphrase loosely or
only point to a dataset or method, and real mis-citations are rare (about 3% of citations), so
a local verifier cannot tell the two apart well enough to accuse anyone.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from paper_preflight.support.evidence import ABSTRACT, Evidence
from paper_preflight.support.retrieve import rank

SUPPORTED, NOT_CONFIRMED = "supported", "not_confirmed"
SUPPORT_AT = 0.4  # HHEM on the gold set: 97% of its confirmations are right (evals/support_eval.py)
PASSAGES = 4  # ranked passages read per claim; more find a few more and are right less often


class Verifier(Protocol):
    def scores(self, claim: str, passages: Sequence[str]) -> list[float]:
        """For each passage, how strongly it supports the claim (0..1)."""
        ...


@dataclass(frozen=True)
class Judgement:
    verdict: str  # SUPPORTED | NOT_CONFIRMED
    reason: str  # SUPPORTING_PASSAGE, NAME_IN_TITLE, NO_TEXT, ABSTRACT_ONLY or NOT_FOUND
    quote: str = ""  # an exact excerpt of the evidence, or the title that names the work
    score: float = 0.0  # the best passage's score
    passage: int = -1  # the best passage's index in the evidence


_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])")


def best_sentence(verifier: Verifier, claim: str, passage: str) -> str:
    """The passage's sentence that supports the claim best: the quote shown to the user."""
    sentences = [s for s in _SENTENCE.split(passage) if s.strip()] or [passage]
    scores = verifier.scores(claim, sentences)
    return sentences[max(range(len(sentences)), key=scores.__getitem__)]


_TITLE_WORD = re.compile(r"[A-Za-z0-9]+(?:[-+.][A-Za-z0-9]+)*")


def name_in_title(name: str, title: str) -> bool:
    """Whether the cited work's title names what the citation is set after ("Adam \\cite{x}").

    An acronym or a name with inner capitals or digits ("BERT", "ImageNet", "GPT-4") counts
    anywhere in the title, as a word. A plain capitalised word ("Adam", "Dropout") counts only as
    the title's own name: "Adam: A Method for ...", "... (Adam)".
    """
    if not name or not title:
        return False
    if sum(c.isupper() for c in name) >= 2 or any(c.isdigit() for c in name):
        words = _TITLE_WORD.findall(title)
        return name in words or f"{name}s" in words  # "GELU" in "... Units (GELUs)"
    text = " ".join(title.split())
    return bool(re.match(re.escape(name) + r"\s*[:–—-]\s", text)) or f"({name})" in text


def judge(
    claim: str,
    evidence: Evidence,
    verifier: Verifier,
    *,
    support_at: float = SUPPORT_AT,
    passages: int = PASSAGES,
    name: str = "",
    title: str = "",
) -> Judgement:
    """A passage that scores ``support_at`` or more confirms the claim. Failing that, a citation
    set right after a name (``name``) is confirmed when the cited work's ``title`` names it."""
    named = name_in_title(name, title)
    if not evidence.passages:
        if named:
            return Judgement(SUPPORTED, "NAME_IN_TITLE", title)
        return Judgement(NOT_CONFIRMED, "NO_TEXT")
    hits = rank(claim, evidence.passages, top=passages)
    texts = [evidence.passages[h.index] for h in hits]
    scores = verifier.scores(claim, texts)
    best = max(range(len(scores)), key=scores.__getitem__)
    score, index = scores[best], hits[best].index
    if score >= support_at:
        quote = best_sentence(verifier, claim, texts[best])
        if quote not in evidence.passages[index]:
            quote = ""  # a quote is an exact excerpt of the evidence, or nothing
        return Judgement(SUPPORTED, "SUPPORTING_PASSAGE", quote, score, index)
    if named:
        return Judgement(SUPPORTED, "NAME_IN_TITLE", title, score)
    reason = "ABSTRACT_ONLY" if evidence.level == ABSTRACT else "NOT_FOUND"
    return Judgement(NOT_CONFIRMED, reason, score=score, passage=index)
