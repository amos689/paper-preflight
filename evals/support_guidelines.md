# Citation-support annotation guidelines

Each item pairs one **claim** from a paper with the **cited work** it is attached to. The
question is narrow: *does the cited work's own text support what this sentence uses it for?*
Not whether the claim is true, not whether a better citation exists.

## What you get

- `claim`: the part of the sentence the citation is attached to (the whole sentence, or its
  clause when one sentence cites several works in different clauses). `[cited work]` stands for
  the citation itself when the sentence uses it as a noun ("We follow [cited work]").
- `sentence` and `previous_sentence`: context. Judge the claim, read in its context.
- `evidence_level`: `full_text` (the work's own text: its LaTeX source, an open-access copy or
  Europe PMC), `abstract` (only the abstract was available) or `none`.
- `passages`: the abstract (passage 0, when known) and the passages ranked closest to the claim,
  by number. They are a sample of the text.
- `full_text_file`: every passage, numbered `[n]`. **Search it** (for the claim's key terms,
  names and numbers) before deciding that something is absent.

## Labels

**supported**: the work's text states the claim's content as the sentence uses it, or plainly
entails it. Typical cases:

- a finding or number attributed to the work appears in it (rounding as written: "about 90%"
  is supported by "89.7%"; "95%" is not supported by "93%");
- the sentence names the work as the source of a method, model, dataset, benchmark, tool or
  definition, and the work introduces or describes it ("we use the X dataset [a]", "X [a] is a
  transformer for Y");
- a background statement cites the work as one example of a line of research ("X has been
  studied [a, b]"), and the work is about X.

**partially_supported**: the claim makes several points and the work supports some but not the
others (not found, or contradicted). Name the sub-claims and which are supported.

**not_supported**: only with `full_text`. After searching the full text, the work does not
say what the claim attributes to it, or says something different (another number, the
opposite finding, another method). Typical cases: a number that the work does not report; a
result attributed to the wrong paper; a claim about a topic the work does not touch.

**cannot_determine**:

- the evidence is `none`, or the text is garbled, truncated or not the work itself (a paywall
  page, a different paper);
- the evidence is `abstract` only and the abstract does not settle the claim (an abstract
  cannot show that something is absent from a paper);
- the claim is too vague to check against any text ("see [a] for details", "[a] and others"),
  or depends on information outside the work (it is about the citing paper's own results).

When in doubt between two labels, choose the more cautious: `cannot_determine` over
`not_supported`, `partially_supported` over `supported`.

## Evidence

For `supported` and `partially_supported`, give the passage number and a quote: **an exact
copy** of one or two sentences from that passage (no paraphrase, no ellipsis inside a sentence).
For `not_supported`, say what you searched for and, if the work says something different,
quote that.

## Output

One JSON object per item:

```json
{"id": "...", "label": "supported", "passage": 3, "quote": "...", "subclaims": [],
 "searched": "", "rationale": "one or two sentences"}
```

`subclaims` (only for `partially_supported`): `[{"text": "...", "supported": true}, ...]`.
`searched` (only for `not_supported`): the terms you looked for in the full text.

These labels are made by AI annotators working independently, then adjudicated; the gold set
says so wherever it is used.
