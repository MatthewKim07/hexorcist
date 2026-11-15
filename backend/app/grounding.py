"""Spec grounding: an assertion may only enforce a requirement the spec actually states.

The model writes each assertion with "spec_quote", the sentence it enforces. This module checks, with plain
string matching and no model, that the quote really occurs in the spec text. An assertion whose quote is
missing or cannot be found is dropped, so a check cannot rest on a sentence the model made up.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

# A quote needs at least this many words to name a sentence at all ("D9" or "the fan" proves nothing).
MIN_QUOTE_WORDS = 3
# Models copy a sentence imperfectly (a dropped "and" or unit). Accept a quote when this share of its words sit,
# in order, in runs of at least two words that the spec contains. A made-up sentence matches a few stray words at most.
MIN_MATCH_SHARE = 0.9
MIN_RUN_WORDS = 2

_WORD = re.compile(r"[a-z]+|\d+(?:\.\d+)?|[<>=%°]")
_SIMPLE = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2212": "-", "\u2014": "-", "\u00a0": " "})


def words(text: str) -> list[str]:
    """Lower-case words and numbers, without markdown, punctuation or spacing, so layout never decides a match."""
    return _WORD.findall(text.translate(_SIMPLE).lower())


def find_quote(quote: str, spec_text: str) -> tuple[bool, str]:
    """(found, reason). The reason names why a quote was refused."""
    q = words(quote or "")
    if not q:
        return False, "it has no spec_quote"
    if len(q) < MIN_QUOTE_WORDS:
        return False, f"its spec_quote {quote.strip()!r} is too short to identify a sentence of the spec"
    s = words(spec_text)
    invented = sorted({w for w in q if w[0].isdigit() and w not in set(s)})
    if invented:
        return False, f"its spec_quote contains {', '.join(invented)}, which the spec does not"
    padded = " " + " ".join(s) + " "
    if " " + " ".join(q) + " " in padded:
        return True, ""
    blocks = SequenceMatcher(None, s, q, autojunk=False).get_matching_blocks()
    if sum(b.size for b in blocks if b.size >= MIN_RUN_WORDS) / len(q) >= MIN_MATCH_SHARE:
        return True, ""
    return False, f"its spec_quote {quote.strip()[:120]!r} was not found in the spec"
