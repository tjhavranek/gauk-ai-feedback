#!/usr/bin/env python3
"""Check that every quote in a review appears in the application.

A review is only as good as its evidence, and a language model can misquote or
invent a sentence. This script reads a review written to the output schema of
dist/prompt_en.md or dist/prompt_cs.md and checks two kinds of quote: every
quoted passage on a "Quote:" or "Citace:" line, including one that runs over
several lines, and every quoted sentence in the Contribution section. It also
checks that every finding carries a quote.

Matching ignores case, line breaks, page markers and the kind of spaces a PDF
happens to use. A quote shortened with an ellipsis must be found piece by
piece, in order, close together. A quote that is found only once diacritics
are ignored, which happens with PDFs whose text layer lost them, is accepted
but listed. A changed word is never accepted, and neither is a quote too short
to identify a place in the text, unless it is a whole line of the source, such
as a form field that reads "None."

    python tools/verify_quotes.py review.md my_application/
    python tools/verify_quotes.py review.md application_text.txt

Exit status 0 when every quote is found and every finding has one. 1
otherwise, and also when the review contains no quotes at all, which a review
in the output schema never does; pass --allow-no-quotes if that is really the
case.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "checker"))

import gauk_check as gc  # noqa: E402

MIN_CHARS = 12      # a shorter quote cannot identify a place in the text
WINDOW = 1500       # the pieces of an ellipsed quote must lie this close together

# Opening mark -> the marks that may close it. English “…”, Czech „…“ (or „…”),
# straight "…" and both directions of guillemets.
PAIRS = {"“": "”", "„": "“”", '"': '"',
         "»": "«", "«": "»"}
LABEL = re.compile(r"^\s*[-*]?\s*\*{0,2}\s*(quote|citace)\s*\*{0,2}\s*:\s*\*{0,2}\s*(.*)$",
                   re.IGNORECASE)
FIELD = re.compile(r"^\s*[-*]\s*\*\*")          # the next "- **Label:**" line
ELLIPSIS = re.compile(r"\[\.\.\.\]|\[…\]|\.\.\.|…")
MARKER_LINE = re.compile(r"^(=== .* ===|--- page \d+ ---|--- [a-z0-9_]+ ---)$", re.M)
CONTRIBUTION_HEAD = re.compile(r"^#+\s*(contribution|přínos projektu)\b", re.IGNORECASE)
FINDINGS_HEAD = re.compile(r"^##\s*(findings|nálezy)\b", re.IGNORECASE)
PUNCT = " .,;:!?'\"“”„«»()"


def segments(s: str) -> tuple[list[str], str | None]:
    """The quoted passages in s, each opening mark paired with its own closing
    mark, and the text after an opening mark that is never closed (or None)."""
    out, i = [], 0
    while i < len(s):
        closers = PAIRS.get(s[i])
        if closers:
            ends = [j for j in (s.find(c, i + 1) for c in closers) if j > i]
            if not ends:
                return out, s[i + 1:]
            j = min(ends)
            out.append(s[i + 1:j])
            i = j + 1
        else:
            i += 1
    return out, None


def _ends_block(line: str) -> bool:
    return not line.strip() or line.lstrip().startswith("#") or bool(
        FIELD.match(line) or LABEL.match(line))


def quotes_in(review: str) -> list[str]:
    """Every quoted passage on a Quote:/Citace: line, joined across line breaks
    up to the next field of the finding, and every quoted passage of three
    words or more in the Contribution section."""
    out: list[str] = []
    lines = review.splitlines()
    in_contribution = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("#"):
            in_contribution = bool(CONTRIBUTION_HEAD.match(line.strip()))
            i += 1
            continue
        m = LABEL.match(line)
        if m:
            rest = m.group(2)
            segs, tail = segments(rest)
            while tail is not None and i + 1 < len(lines) and not _ends_block(lines[i + 1]):
                i += 1
                rest += " " + lines[i].strip()
                segs, tail = segments(rest)
            if tail is not None:
                segs.append(tail)       # an unclosed quote is still checked
            if not segs and rest.strip(PUNCT):
                segs = [rest.strip(PUNCT)]
            out += [s for s in segs if s.strip(PUNCT)]
        elif in_contribution:
            out += [s for s in segments(line)[0] if len(s.split()) >= 3]
        i += 1
    return out


def findings_without_quote(review: str) -> list[str]:
    """The titles of findings (### headings under Findings / Nálezy) that
    carry no Quote:/Citace: line."""
    missing, in_findings, title, has = [], False, None, False
    for line in review.splitlines() + ["## end"]:
        s = line.strip()
        if s.startswith("#"):
            if title is not None and not has:
                missing.append(title)
            title, has = None, False
            if s.startswith("## ") or s.startswith("# "):
                in_findings = bool(FINDINGS_HEAD.match(s))
            elif in_findings and s.startswith("### "):
                title = s[4:]
        elif title is not None and LABEL.match(line):
            has = True
    return missing


def _exact(t: str) -> str:
    t = unicodedata.normalize("NFKC", t).lower().translate(gc.ZERO_WIDTH)
    return re.sub(r"\s+", " ", t)


def _pieces(quote: str, norm) -> list[str]:
    """The parts of a quote between ellipses, each normalised. A part with no
    letter or digit carries no evidence and is dropped; nothing else is."""
    parts = [norm(p).strip(PUNCT) for p in ELLIPSIS.split(quote)]
    return [p for p in parts if re.search(r"\w", p)]


def _in_order(pieces: list[str], src: str) -> bool:
    i = src.find(pieces[0])
    while i >= 0:
        pos, ok = i + len(pieces[0]), True
        for p in pieces[1:]:
            j = src.find(p, pos)
            if j < 0 or j - pos > WINDOW:
                ok = False
                break
            pos = j + len(p)
        if ok:
            return True
        i = src.find(pieces[0], i + 1)
    return False


def classify(quote: str, src_exact: str, src_folded: str,
             whole_lines: frozenset = frozenset()) -> str:
    """'exact', 'diacritics', 'too_short' or 'not_found'. A short quote is
    accepted only when it is a whole line of the source, such as a form field
    that reads "None.", because only then does it point to one place."""
    pieces = _pieces(quote, _exact)
    if not pieces:
        return "too_short"
    if sum(len(p) for p in pieces) < MIN_CHARS:
        whole = _exact(quote).strip(PUNCT)
        return "exact" if whole and whole in whole_lines else "too_short"
    if _in_order(pieces, src_exact):
        return "exact"
    if _in_order(_pieces(quote, gc.fold), src_folded):
        return "diacritics"
    return "not_found"


def load_source(path: Path) -> str:
    if path.is_dir():
        texts = []
        for f in sorted(path.iterdir()):
            if f.suffix.lower() in gc.ATTACHMENT_SUFFIXES:
                texts.append(gc.attachment_facts(f).get("text", ""))
            elif f.name.startswith("form.") and f.suffix.lower() in gc.FORM_SUFFIXES:
                try:
                    texts += list(gc.read_form(f, None).values())
                except gc.FormError:
                    pass
        return "\n".join(texts)
    return path.read_text(encoding="utf-8")


def verify_detail(review_text: str, source_text: str) -> list[tuple[str, str]]:
    src = MARKER_LINE.sub(" ", source_text)
    src_exact, src_folded = _exact(src), gc.fold(src)
    whole_lines = frozenset(_exact(ln).strip(PUNCT) for ln in source_text.splitlines()
                            if ln.strip())
    return [(q, classify(q, src_exact, src_folded, whole_lines))
            for q in quotes_in(review_text)]


def verify(review_text: str, source_text: str) -> tuple[list[str], list[str]]:
    """Return (found, not_found)."""
    detail = verify_detail(review_text, source_text)
    return ([q for q, s in detail if s in ("exact", "diacritics")],
            [q for q, s in detail if s in ("too_short", "not_found")])


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("review", type=Path)
    ap.add_argument("source", type=Path, help="the application folder or its text file")
    ap.add_argument("--allow-no-quotes", action="store_true")
    args = ap.parse_args()
    review = args.review.read_text(encoding="utf-8")
    detail = verify_detail(review, load_source(args.source))
    bad = [(q, s) for q, s in detail if s in ("too_short", "not_found")]
    loose = [q for q, s in detail if s == "diacritics"]
    bare = findings_without_quote(review)
    print(f"{len(detail) - len(bad)} quotes found in the application, {len(bad)} not found")
    for q, s in bad:
        label = "too short to verify" if s == "too_short" else "NOT FOUND"
        print(f"  {label}: {q[:160]}")
    for q in loose:
        print(f"  found only when diacritics are ignored: {q[:160]}")
    for t in bare:
        print(f"  finding with no quote: {t[:160]}")
    if not detail:
        print("  no quotes in the review")
        return 0 if args.allow_no_quotes else 1
    return 1 if bad or bare else 0


if __name__ == "__main__":
    raise SystemExit(main())
