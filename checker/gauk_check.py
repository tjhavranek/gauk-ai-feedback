#!/usr/bin/env python3
"""Formal check of a GA UK application. No model, no network.

Unofficial. Not issued, reviewed or endorsed by GA UK or Charles University.

Everything this script reports is countable or matchable: a page count, a file
size, a character count, an arithmetic identity, a year in a timetable. Nothing
here is a judgement about the science, and nothing here leaves the machine it
runs on.

Four things it deliberately will not do.

It has no PASS state. An application with no findings prints "no findings",
not "in order", and every run prints the list of rules the script cannot see.
Someone who reads a clean report and concludes the application is complete has
been misled.

It never reports MISSING when it means UNKNOWN. A field the form file does not
carry, a file it could not read, a heading it could not match, a number it
could not parse: all of these are UNKNOWN. A false "the annotation is missing"
costs a student time they do not have before a faculty deadline.

It never flags anything on the `not_defects` list in rules/round24.yml, which
holds things the published documents allow.

It refuses to run on stale rules. Past the sunset date in rules/INDEX.yml it
exits 3 unless told otherwise, because a confident answer from last year's
rules is worse than no answer.

    python checker/gauk_check.py one my_application/

It checks one application at a time, the applicant's own. An application folder
holds the attachments (PDF, or a .docx draft) and, optionally, a form.yml with
the web-form fields; see templates/form.yml.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import logging
import re
import sys
import unicodedata
import zipfile
from dataclasses import dataclass, asdict, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required:  python -m pip install -r requirements.txt")

try:
    import pypdf
except ImportError:  # pragma: no cover
    pypdf = None

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None

# pypdf and pdfminer log every odd font or broken cross-reference; a student
# needs the findings, not that noise.
for _name in ("pypdf", "pdfminer"):
    logging.getLogger(_name).setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "rules"

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_STALE = 3

# A4 in PDF points, with the tolerance a converter can introduce.
A4_PT = (595.28, 841.89)
A4_TOL = 6.0

ATTACHMENT_SUFFIXES = (".pdf", ".docx", ".doc")
FORM_SUFFIXES = (".yml", ".yaml", ".csv", ".tsv", ".xlsx")

SRC_OR = "Opatření rektora 31/2026 (Zásady činnosti GA UK)"
SRC_INFO = "Informace k podání přihlášky, 24. kolo"
SRC_INFO_PDF = "Informace k .pdf příloze Návrh projektu"
SRC_PRAKT = "Praktické informace k podání návrhu projektu (2027)"


# --------------------------------------------------------------------------
# findings
# --------------------------------------------------------------------------

BLOCKING = "BLOCKING"     # certain, and a breach of a written rule
ADVISORY = "ADVISORY"     # measured but not certain, or a rule that admits judgement
UNKNOWN = "UNKNOWN"       # could not be established; never reported as a breach


@dataclass
class Finding:
    rule: str
    kind: str                 # BLOCKING | ADVISORY | UNKNOWN
    where: str                # file, page, or form field
    measured: str
    expected: str
    confirm: str              # how a human confirms this in seconds
    source: str               # which published GA UK document the rule comes from

    def line(self) -> str:
        return (
            f"{self.rule} [{self.kind}] {self.where}\n"
            f"    measured: {self.measured}\n"
            f"    expected: {self.expected}\n"
            f"    confirm:  {self.confirm}\n"
            f"    source:   {self.source}"
        )


@dataclass
class Report:
    app_id: str
    rules_round: int
    rules_verified_on: str
    rules_official: bool
    generated_on: str
    doc_language: str = "unknown"
    findings: list[Finding] = field(default_factory=list)
    measured: list[str] = field(default_factory=list)   # values that raised no finding
    not_checked: list[str] = field(default_factory=list)
    inputs_seen: dict = field(default_factory=dict)

    def add(self, f: Finding) -> None:
        self.findings.append(f)

    def counts(self) -> dict:
        c = {BLOCKING: 0, ADVISORY: 0, UNKNOWN: 0}
        for f in self.findings:
            c[f.kind] += 1
        return c


# --------------------------------------------------------------------------
# rules
# --------------------------------------------------------------------------

def load_rules() -> tuple[dict, dict, dict]:
    index = yaml.safe_load((RULES / "INDEX.yml").read_text(encoding="utf-8"))
    criteria = yaml.safe_load((RULES / "criteria.yml").read_text(encoding="utf-8"))
    rnd = yaml.safe_load((RULES / index["current_rules_file"]).read_text(encoding="utf-8"))
    return index, criteria, rnd


def staleness_gate(index: dict, allow_stale: bool) -> None:
    today = dt.date.today()
    sunset = index["sunset_on"]
    warn = index["warn_after"]
    if isinstance(sunset, str):
        sunset = dt.date.fromisoformat(sunset)
    if isinstance(warn, str):
        warn = dt.date.fromisoformat(warn)
    if today >= sunset and not allow_stale:
        print(
            f"the rules in rules/ expired on {sunset}. Check for a newer version "
            f"of this tool, or pass --rules-may-be-stale if you accept the risk "
            f"of answering from last round's rules.",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_STALE)
    if today >= warn:
        print(
            f"  these rules were transcribed for round {index['current_round']} "
            f"and are past {warn}; confirm against the current published documents",
            file=sys.stderr,
        )


# --------------------------------------------------------------------------
# reading the inputs
# --------------------------------------------------------------------------

ZERO_WIDTH = dict.fromkeys(map(ord, "­​‌‍﻿"), None)


def fold(text: str) -> str:
    """Normalise text before matching against it.

    Four real cases make this necessary rather than tidy, and each of them
    would otherwise produce a finding against an application that is correct.

    A PDF written with one of the base-14 fonts has no Czech letters in its
    text layer at all and extracts as mojibake. Applicants in a hurry type
    "Zpusob reseni" without diacritics. Headings are capitalised any way at
    all. And Word, LaTeX and most PDF writers put non-breaking or thin spaces
    between words, so a literal match on "Current state of knowledge" fails
    against text that reads "Current\\xa0state\\xa0of\\xa0knowledge".

    So: compatibility-decompose, which folds the space variants and ligatures;
    drop the combining marks, which removes the diacritics; drop the invisible
    characters; and collapse runs of whitespace.
    """
    s = unicodedata.normalize("NFKD", text.lower()).translate(ZERO_WIDTH)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s)


def count_chars(text: str) -> int:
    """GA UK counts characters including spaces. NFC, because a decomposed
    diacritic would otherwise count twice and Czech text is full of them.

    This convention is an assumption until it is checked against the
    application's own counter. Until rules/round24.yml sets calibrated: true,
    the character rules do not fire.
    """
    return len(unicodedata.normalize("NFC", text))


class FormError(Exception):
    """A form file that exists but cannot be read."""


def read_form(path: Path, mapping: dict | None) -> dict:
    """Read the web-form fields. Returns {field_id: text}.

    A form.yml written from templates/form.yml is the simple route for an
    applicant. A CSV or XLSX export is read as well. Fields that are absent
    or empty are left out, and the rules then report them as not checked,
    never as missing. A file that cannot be parsed raises FormError, which the
    caller turns into an UNKNOWN finding rather than a traceback.
    """
    if not path.is_file():
        return {}
    suffix = path.suffix.lower()
    try:
        if suffix in (".yml", ".yaml"):
            # BaseLoader keeps every value as the text the student typed: an
            # unquoted 120.000 stays "120.000" rather than becoming 120.0, and
            # yes stays "yes" rather than becoming True
            data = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader) or {}
            if not isinstance(data, dict):
                raise FormError("the file is not a list of 'field: value' lines")
            return {str(k): str(v) for k, v in data.items()
                    if v is not None and str(v).strip()}
        rows: list[dict] = []
        if suffix in (".csv", ".tsv"):
            raw = path.read_bytes()
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("cp1250")    # a CSV saved by Czech Excel
            delim = "\t" if suffix == ".tsv" else (
                ";" if text.count(";") > text.count(",") else ",")
            rows = list(csv.DictReader(text.splitlines(), delimiter=delim))
        elif suffix in (".xlsx", ".xlsm"):
            try:
                import openpyxl
            except ImportError:
                raise FormError("openpyxl is not installed")
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            it = wb.active.iter_rows(values_only=True)
            header = [str(c or "") for c in next(it, [])]
            for r in it:
                rows.append(dict(zip(header, r)))
    except FormError:
        raise
    except Exception as exc:
        raise FormError(f"{type(exc).__name__}: {exc}") from exc
    if not rows:
        return {}

    # a short CSV row gives None for its missing cells, and an extra cell sits
    # under the key None; neither is a field
    row = {k: ("" if v is None else str(v)) for k, v in rows[0].items() if k is not None}
    if mapping:
        return {canon: row[col] for canon, col in mapping.items()
                if col in row and row[col].strip()}
    out = {}
    for k, v in row.items():
        # digits are kept, because field ids such as budget_total_year1 carry one
        key = re.sub(r"[^a-z0-9_]", "", str(k).lower().replace(" ", "_"))
        if key and v.strip():
            out[key] = v
    return out


def docx_text(path: Path) -> str:
    """Text of a .docx without python-docx: paragraphs become lines.

    The visible text only. Deleted tracked changes, text moved away and field
    codes are dropped, so that a review cannot quote words the student has
    already struck out. Comments live in another part of the file and are never
    read.
    """
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    for tag in ("w:del", "w:moveFrom"):
        xml = re.sub(rf"<{tag}\b[^>]*/>", "", xml)
        xml = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", "", xml, flags=re.S)
    for tag in ("w:delText", "w:instrText"):
        xml = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", "", xml, flags=re.S)
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    xml = re.sub(r"<w:(?:br|cr)\b[^>]*/>", "\n", xml)
    return html.unescape(re.sub(r"<[^>]+>", "", xml))


def pdf_facts(path: Path) -> dict:
    """Page count, page size and text of a PDF. Never raises.

    A PDF that cannot be opened yields {'error': ...}, and every rule over it
    becomes UNKNOWN. A PDF that opens but has no readable text yields
    {'text_error': ...}: its page count and page size are still checked, its
    text is not. Pages with no text in an otherwise readable PDF are listed
    under 'empty_pages', because a rule over the text cannot see them.
    """
    facts: dict = {"bytes": path.stat().st_size, "format": "pdf"}
    if pypdf is None:
        facts["error"] = "pypdf not installed"
        return facts
    try:
        reader = pypdf.PdfReader(str(path))
        facts["pages"] = len(reader.pages)
        box = reader.pages[0].mediabox
        facts["width_pt"] = float(box.width)
        facts["height_pt"] = float(box.height)
        short_side, long_side = sorted((facts["width_pt"], facts["height_pt"]))
        facts["is_a4"] = (
            abs(short_side - A4_PT[0]) <= A4_TOL
            and abs(long_side - A4_PT[1]) <= A4_TOL
        )
    except Exception as exc:  # a corrupt or encrypted file is UNKNOWN, not a breach
        facts["error"] = f"{type(exc).__name__}: {exc}"
        return facts
    page_texts = []
    for p in reader.pages:
        try:
            page_texts.append(p.extract_text() or "")
        except Exception:
            page_texts.append("")
    facts["page_texts"] = page_texts
    facts["text"] = "\n".join(page_texts)
    empty = [i for i, t in enumerate(page_texts, start=1) if not t.strip()]
    if len(empty) == len(page_texts):
        facts["text_error"] = "no text layer (scanned?)"
    elif empty:
        facts["empty_pages"] = empty
    return facts


def attachment_facts(path: Path) -> dict:
    """Facts about one attachment. A .docx draft is read, so that a proposal can
    be checked before it is converted; its page count and font size cannot be
    established without rendering it, so no rule over those runs on it."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return pdf_facts(path)
    facts: dict = {"bytes": path.stat().st_size, "format": suffix.lstrip(".")}
    if suffix == ".docx":
        try:
            facts["text"] = docx_text(path)
            if not facts["text"].strip():
                facts["error"] = "empty Word document"
        except Exception as exc:
            facts["error"] = f"{type(exc).__name__}: {exc}"
    else:
        facts["error"] = "Word 97-2003 (.doc) file; the checker cannot read its text"
    return facts


def typography(path: Path) -> dict:
    """Modal body font size and a line-spacing proxy. Advisory only.

    Word's "spacing 1" is not a fixed leading in the resulting PDF, and fonts
    can be scaled at embed time, so neither number is a certainty. The script
    reports what it measured and lets a human look at the page.
    """
    if pdfplumber is None:
        return {"error": "pdfplumber not installed"}
    try:
        with pdfplumber.open(str(path)) as pdf:
            sizes: dict[float, int] = {}
            tops: list[float] = []
            for page in pdf.pages[:3]:
                for ch in page.chars:
                    s = round(float(ch["size"]), 1)
                    sizes[s] = sizes.get(s, 0) + 1
                tops += sorted({round(float(c["top"]), 1) for c in page.chars})
            if not sizes:
                return {"error": "no characters"}
            modal = max(sizes.items(), key=lambda kv: kv[1])[0]
            small = sum(n for s, n in sizes.items() if s < 10.5)
            deltas = sorted(b - a for a, b in zip(tops, tops[1:]) if 0 < b - a < 4 * modal)
            lead = deltas[len(deltas) // 2] if deltas else None
            return {
                "modal_pt": modal,
                "share_below_10_5pt": round(small / sum(sizes.values()), 3),
                "median_leading_pt": round(lead, 2) if lead else None,
                "leading_ratio": round(lead / modal, 2) if lead else None,
            }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


# Folded, so that a PDF whose text layer lost its diacritics still classifies.
CS_STOPWORDS = {"se", "na", "je", "ze", "do", "pro", "ktere", "teto", "bude",
                "byl", "jsou", "nebo", "podle", "resitel", "projektu"}
EN_STOPWORDS = {"the", "of", "and", "to", "in", "is", "will", "this", "that",
                "for", "with", "are", "from", "which"}


def detect_language(text: str) -> str:
    """'cs', 'en' or 'unknown', from common words in the whole text. A guess:
    quotations and examples in the other language can mislead it, so every rule
    that uses it is advisory, and a text with few common words is 'unknown'."""
    words = re.findall(r"[a-z]+", fold(text))
    if len(words) < 40:
        return "unknown"
    cs = sum(w in CS_STOPWORDS for w in words)
    en = sum(w in EN_STOPWORDS for w in words)
    if cs + en < 20:
        return "unknown"
    ratio = cs / max(cs + en, 1)
    if ratio > 0.7:
        return "cs"
    if ratio < 0.3:
        return "en"
    return "unknown"


def form_language(form: dict) -> str | None:
    """Which version of the web form is used. Only the form file can say this;
    it is not inferred from the text, because the Czech version carries an
    English title and annotation by design."""
    v = fold(str(form.get("form_language", ""))).strip()
    if v in ("cs", "cz", "cze", "ces", "czech", "cesky", "cestina",
             "sk", "slovak", "slovensky", "slovencina"):
        return "cs"
    if v in ("en", "eng", "english", "anglicky", "anglictina"):
        return "en"
    return None


AMOUNT = re.compile(r"\b(\d{1,3}(?:[   ]\d{3})+|\d{4,7})\b")


def amounts_in(text: str) -> set[int]:
    out = set()
    for m in AMOUNT.finditer(text or ""):
        try:
            out.add(int(re.sub(r"[   ]", "", m.group(1))))
        except ValueError:
            pass
    return out


def section_lines(text: str, criteria: dict) -> tuple[list[str], dict[int, int]]:
    """Locate the eight prescribed headings as lines.

    A heading counts when a line, after an optional section number, starts with
    one of the section's heading phrases and is short enough to be a heading.
    Returns the text's lines and {section number: line index}. A section whose
    heading is not found here may still be present under other wording; the
    callers treat absence as "not located", never as "missing".
    """
    lines = text.splitlines()
    folded = [fold(ln).strip() for ln in lines]
    found: dict[int, int] = {}
    for s in criteria["proposal_sections"]["sections"]:
        pats = [fold(m) for m in s["match"]]
        for i, fl in enumerate(folded):
            if not fl or len(fl) > 120:
                continue
            num = re.match(r"^(\d{1,2})\s*[.)]?\s*", fl)
            head = fl[num.end():] if num else fl
            if num and int(num.group(1)) != s["n"]:
                continue
            if any(head.startswith(p) for p in pats):
                found[s["n"]] = i
                break
    return lines, found


# --------------------------------------------------------------------------
# the rules
# --------------------------------------------------------------------------

# Regular expressions over the folded file name. "navrh" must not match the
# word for applicant, navrhovatel, which belongs to the PI's CV.
WANTED = {
    "proposal": (r"navrh(?!ovatel)", "proposal"),
    "cv_pi": ("cv_resitel", "cv_pi", "zivotopis_resitel", "zivotopis_hlavniho",
              "navrhovatel"),
    "cv_supervisor": ("cv_vedouci", "cv_supervisor", "zivotopis_vedouci"),
    "references": ("literatura", "references", "odkazy", "bibliograph"),
}
# A file named for the ethics committee statement is not an extra attachment.
ETHICS_SLOT = ("etick", "etik", "ethic")


def assign_slots(files: dict[str, Path]) -> tuple[dict[str, Path], dict[str, list[str]]]:
    """Which file is which attachment, by name.

    Nothing is guessed. A slot that two different files could fill gets
    neither, and a file whose name fits two slots, such as
    proposal_references.pdf, fills no slot that lacks a clear candidate; both
    cases come back as ambiguous. A PDF and a Word draft with the same name are
    one attachment, and the PDF is used, because it is what gets uploaded.
    """
    def slots_of(name: str) -> list[str]:
        n = fold(name).replace(" ", "_")
        return [k for k, stems in WANTED.items() if any(re.search(s, n) for s in stems)]

    by_slot: dict[str, list[Path]] = {k: [] for k in WANTED}
    multi: list[tuple[Path, list[str]]] = []
    for name, p in files.items():
        s = slots_of(name)
        if len(s) == 1:
            by_slot[s[0]].append(p)
        elif len(s) > 1:
            multi.append((p, s))
    found: dict[str, Path] = {}
    ambiguous: dict[str, list[str]] = {}
    for k, paths in by_slot.items():
        if len({Path(p.name.lower()).stem for p in paths}) == 1:
            paths.sort(key=lambda p: (p.suffix.lower() != ".pdf", p.name.lower()))
            found[k] = paths[0]
        elif paths:
            ambiguous[k] = sorted(p.name for p in paths)
    for p, slots in multi:
        for k in slots:
            if k not in found:
                ambiguous.setdefault(k, []).append(p.name)
    return found, ambiguous


def run_rules(app: Path, form: dict, rnd: dict, criteria: dict, rep: Report) -> None:
    files = {p.name.lower(): p for p in sorted(app.iterdir())
             if p.is_file() and p.suffix.lower() in ATTACHMENT_SUFFIXES}
    rep.inputs_seen["attachments"] = sorted(files)
    rep.inputs_seen["form_fields"] = sorted(form)

    # -- R01 attachment set -------------------------------------------------
    found, ambiguous = assign_slots(files)
    spec = {a["id"]: a for a in rnd["attachments"]["items"]}
    for key in WANTED:
        if key in found:
            continue
        if key in ambiguous:
            measured = ("more than one file could be this attachment: "
                        + ", ".join(ambiguous[key]))
            confirm = ("rename the files so that each name fits one attachment "
                       "only, then run the check again")
        else:
            words = " or ".join(s.split("(")[0] for s in WANTED[key])
            measured = f"no file whose name contains {words}"
            confirm = "list the folder; the file may simply be named differently"
        rep.add(Finding(
            rule="R01_ATTACHMENT_SET", kind=UNKNOWN, where=f"{app.name}/",
            measured=measured,
            expected=f"the attachment '{spec[key]['en_name']}'",
            confirm=confirm, source=SRC_INFO))

    matched = {p.name.lower() for p in found.values()}
    unsure = {n.lower() for names in ambiguous.values() for n in names}
    extra = {n for n in files if n not in matched and n not in unsure
             and not any(t in fold(n) for t in ETHICS_SLOT)}
    # a Word draft of an attachment that also exists as PDF is not extra
    extra = {n for n in extra
             if not any(Path(n).stem == Path(m).stem for m in matched)}
    if extra:
        rep.add(Finding(
            rule="R01B_EXTRA_ATTACHMENT", kind=ADVISORY, where=f"{app.name}/",
            measured=", ".join(sorted(extra)),
            expected="the listed attachments only; charts and preliminary results "
                     "belong inside the project proposal",
            confirm="open the file and see whether it is one of the attachments, "
                    "perhaps under another name",
            source=SRC_INFO))

    # -- R02..R04 file size, pages, page size ------------------------------
    max_mb = rnd["attachments"]["max_file_size_mb"]
    facts_by_key: dict[str, dict] = {}
    for key, path in found.items():
        facts = attachment_facts(path)
        facts_by_key[key] = facts
        limit = spec[key].get("max_pages")

        if facts.get("bytes") and facts["bytes"] > max_mb * 1024 * 1024:
            rep.add(Finding(
                rule="R02_FILE_SIZE", kind=BLOCKING, where=path.name,
                measured=f"{facts['bytes'] / 1024 / 1024:.1f} MB",
                expected=f"at most {max_mb} MB",
                confirm="file properties", source=SRC_INFO))

        if "error" in facts or "text_error" in facts:
            rep.add(Finding(
                rule="R00_UNREADABLE", kind=UNKNOWN, where=path.name,
                measured=facts.get("error") or facts["text_error"],
                expected="a file whose text the checker can read",
                confirm="open the file; if it is a scan or an old .doc, no text "
                        "rule can run on it",
                source=SRC_INFO))
        elif facts.get("empty_pages"):
            rep.not_checked.append(
                f"the text of {path.name}, page(s) {facts['empty_pages']}: there is "
                f"no text layer there (a figure, a blank page or a scan), so no "
                f"rule reads it and the review cannot quote it")
        if "error" in facts:
            continue

        if facts["format"] != "pdf":
            rep.not_checked.append(
                f"{path.name} is a Word file. The guide asks for PDF attachments; "
                f"convert it before uploading"
                + (" and run the check again, since its page count is not checked"
                   if limit else ""))
        elif limit and facts.get("pages", 0) > limit:
            rep.add(Finding(
                rule="R03_PAGE_LIMIT", kind=BLOCKING, where=path.name,
                measured=f"{facts['pages']} pages",
                expected=f"at most {limit}",
                confirm="open the file and go to the last page",
                source=SRC_INFO))
        else:
            rep.measured.append(
                f"{path.name}: {facts['pages']} page{'s' if facts['pages'] != 1 else ''}"
                + (f" (limit {limit})" if limit else "")
                + f", {facts['bytes'] / 1024 / 1024:.1f} MB (limit {max_mb} MB)")

        if key == "proposal" and facts["format"] == "pdf" and facts.get("is_a4") is False:
            rep.add(Finding(
                rule="R03B_PAGE_SIZE", kind=ADVISORY, where=path.name,
                measured=f"{facts['width_pt']:.0f} x {facts['height_pt']:.0f} pt",
                expected="A4 (595 x 842 pt)",
                confirm="page setup in the source document",
                source=SRC_INFO))

        if "text_error" in facts:
            continue
        if key == "proposal":
            _proposal_rules(path, facts, form, rnd, criteria, rep)
        if key == "cv_supervisor":
            _publication_list_rule(path, facts, rnd, rep)

    # -- R05 character counts ----------------------------------------------
    calibrated = rnd["form_fields"]["counting"]["calibrated"]
    for f in rnd["form_fields"]["fields"]:
        fid = f["id"]
        if fid not in form:
            if not f.get("conditional"):
                rep.not_checked.append(
                    f"length of the form field '{f['en']}' (not in the form file)")
            continue
        if not calibrated:
            rep.not_checked.append(
                f"length of '{f['en']}': read it off the character counter in "
                f"the application")
            continue
        n = count_chars(form[fid])
        lo = f["min"] or 0
        if n < lo or n > f["max"]:
            rep.add(Finding(
                rule="R05_FIELD_LENGTH", kind=BLOCKING, where=f"form: {f['en']}",
                measured=f"{n} characters",
                expected=f"{lo}-{f['max']}",
                confirm="the character counter beside the field in the application",
                source=SRC_INFO))

    # -- R18 AI use declared but not described ------------------------------
    used = fold(form.get("ai_used", "")).strip()
    if used in ("yes", "y", "true", "ano", "a") and not form.get("ai_description", "").strip():
        rep.add(Finding(
            rule="R18_AI_DESCRIPTION", kind=ADVISORY, where="form: AI use",
            measured="AI use is declared, but the form file has no description",
            expected="how and to what extent AI was used, in at most 500 characters",
            confirm="the AI field in the application; using this review counts",
            source=SRC_INFO))

    # -- R06 budget arithmetic ---------------------------------------------
    _budget_rules(form, rnd, rep)

    # -- R09 amounts in the table versus amounts in the justification -------
    just = form.get("budget_justification", "")
    table = form.get("budget_table", "")
    if just and table:
        in_text, in_table = amounts_in(just), amounts_in(table)
        only_text = sorted(a for a in in_text - in_table if a >= 1000)
        only_table = sorted(a for a in in_table - in_text if a >= 1000)
        if only_text or only_table:
            rep.add(Finding(
                rule="R09_AMOUNT_MISMATCH", kind=ADVISORY,
                where="form: financial requirements",
                measured=f"only in the justification: {only_text or '-'}; "
                         f"only in the table: {only_table or '-'}",
                expected="the amounts in the table and in the written "
                         "justification agree",
                confirm="read the two side by side; a rounded or aggregated "
                        "figure is a legitimate reason for a difference",
                source=SRC_INFO))
    elif just and not table:
        rep.not_checked.append(
            "whether the budget table matches the written justification "
            "(no table amounts in the form file)")

    # -- R10 ineligible costs, R15 currency ---------------------------------
    _ineligible_rules(form, rnd, rep)

    # -- R11 language of the proposal against the form version --------------
    _language_rule(facts_by_key.get("proposal"), form, rep)


def _proposal_rules(path, facts, form, rnd, criteria, rep) -> None:
    text = facts.get("text", "")
    low = fold(text)
    lines, heads = section_lines(text, criteria)

    # R13 section headings. A section counts as present if its heading line is
    # found, or failing that if one of its phrases occurs anywhere at all; only
    # a section with neither is reported. A heading worded differently is not a
    # missing section, so this stays advisory.
    missing = []
    for s in criteria["proposal_sections"]["sections"]:
        if s["n"] in heads:
            continue
        if not any(fold(m) in low for m in s["match"]):
            missing.append(f"{s['n']}. {s['en_title']}")
    if missing:
        rep.add(Finding(
            rule="R13_SECTION_HEADING", kind=ADVISORY, where=path.name,
            measured="no heading matched for: " + "; ".join(missing),
            expected="all eight prescribed sections, in order; a proposal that "
                     "does not keep the structure may be returned for correction",
            confirm="the heading may simply be worded differently; read the "
                    "proposal and check the content is there",
            source=SRC_INFO_PDF))
    seq = [n for n, _ in sorted(heads.items(), key=lambda kv: kv[1])]
    if len(seq) >= 2 and seq != sorted(seq):
        rep.add(Finding(
            rule="R13B_SECTION_ORDER", kind=ADVISORY, where=path.name,
            measured=f"headings appear in the order {seq}",
            expected="the prescribed order 1-8",
            confirm="skim the headings",
            source=SRC_INFO))

    # R14 CVs where they do not belong
    if re.search(r"h-index|h index|impact factor|IF\s*=|ORCID", text, re.I) and \
            re.search(r"kolektiv|team", low):
        rep.add(Finding(
            rule="R14_CV_IN_PROPOSAL", kind=ADVISORY, where=path.name,
            measured="bibliometric material appears in the proposal text",
            expected="CVs and publication lists go in the attachments, not in "
                     "the team section",
            confirm="look at the team section of the proposal",
            source=SRC_INFO))

    # R17 timetable years
    _timetable_rule(path, lines, heads, form, rnd, rep)

    # R07 font size, PDFs only
    if facts["format"] != "pdf":
        rep.not_checked.append("font size and line spacing of the proposal "
                               "(a Word draft; check them on the PDF)")
        return
    typ = typography(path)
    if "error" not in typ:
        spec = next(a for a in rnd["attachments"]["items"] if a["id"] == "proposal")
        if typ["modal_pt"] and typ["modal_pt"] < spec["font_size_pt"] - 0.6:
            rep.add(Finding(
                rule="R07_FONT_SIZE", kind=ADVISORY, where=path.name,
                measured=f"most body text is {typ['modal_pt']} pt "
                         f"({typ['share_below_10_5pt'] * 100:.0f} % of glyphs "
                         f"below 10.5 pt)",
                expected=f"{spec['font_size_pt']} pt",
                confirm="the measurement is a guide only; embedded fonts can be "
                        "scaled. Look at the source document's style.",
                source=SRC_INFO))
        elif typ["modal_pt"]:
            rep.measured.append(f"{path.name}: most body text is {typ['modal_pt']} pt "
                                f"(rule {spec['font_size_pt']} pt; a guide only)")


def _timetable_rule(path, lines, heads, form, rnd, rep) -> None:
    """R17: the years in section 5 against the funded years.

    The guide asks for the timetable in calendar years, at least one, matching
    the duration entered; for a one-year project in round 24 that is January to
    December 2027.
    """
    if 5 not in heads:
        rep.not_checked.append("the years in the timetable (its heading was not "
                               "located)")
        return
    start = heads[5] + 1
    later = [i for i in heads.values() if i > heads[5]]
    end = min(later) if later else len(lines)
    tt = "\n".join(lines[start:end])
    tt_folded = fold(tt)

    first = rnd["timetable"]["first_funding_year"]
    d = re.fullmatch(r"\s*([123])(?:[.,]0)?\s*", str(form.get("duration_years", "")))
    duration = int(d.group(1)) if d else None

    years = sorted({int(y) for y in re.findall(r"\b(20[2-3]\d)\b", tt)})
    academic = re.findall(r"\b20\d\d\s*/\s*(?:20)?\d\d\b", tt)
    academic += re.findall(r"akademick\w* rok|academic year|semest", tt_folded)
    problems = []
    if academic:
        problems.append("academic-year wording: " + ", ".join(sorted(set(academic))[:3]))
    before = [y for y in years if y < first]
    if before:
        problems.append(f"years before the first funded year {first}: {before}")
    if duration:
        after = [y for y in years if y > first + duration - 1]
        if after:
            problems.append(f"years after the last funded year "
                            f"{first + duration - 1}: {after}")
    else:
        rep.not_checked.append("whether the timetable's years match the duration "
                               "(duration_years is not in the form file)")
    if not years and not academic:
        rep.not_checked.append("the years in the timetable (section 5 names none)")
    elif not problems:
        rep.measured.append(f"years named in the timetable: {years or '-'}")
    if problems:
        rep.add(Finding(
            rule="R17_TIMETABLE_YEARS", kind=ADVISORY, where=f"{path.name}, section 5",
            measured="; ".join(problems),
            expected=f"calendar years from {first}, matching the duration entered; "
                     f"a one-year project runs January to December {first}",
            confirm="read the timetable; a year cited for another reason is fine",
            source=f"{SRC_INFO}; {SRC_OR}, art. 5(1)"))


def _publication_list_rule(path, facts, rnd, rep) -> None:
    """R16: the leader's publication list may hold at most ten items.

    Counts the longest run of numbered items 1, 2, 3, ... after the first line
    mentioning publications. An unnumbered list is not counted and produces no
    finding; ten or fewer items is fine.
    """
    limit = next(a for a in rnd["attachments"]["items"]
                 if a["id"] == "cv_supervisor").get("publications_max")
    lines = facts.get("text", "").splitlines()
    start = next((i for i, ln in enumerate(lines)
                  if re.search(r"publikac|publication", fold(ln))), None)
    if start is None or not limit:
        rep.not_checked.append("the length of the leader's publication list "
                               "(no numbered list located)")
        return
    best = run = 0
    for ln in lines[start + 1:]:
        m = re.match(r"^\s*\[?(\d{1,2})\s*[.)\]]\s*\S", ln)
        if not m:
            continue
        n = int(m.group(1))
        run = n if n == run + 1 else (1 if n == 1 else run)
        best = max(best, run)
    if not best:
        rep.not_checked.append("the length of the leader's publication list "
                               "(the list is not numbered)")
    elif best <= limit:
        rep.measured.append(f"{path.name}: {best} numbered publications (limit {limit})")
    if best > limit:
        rep.add(Finding(
            rule="R16_PUBLICATION_LIST", kind=ADVISORY, where=path.name,
            measured=f"a numbered publication list running to {best} items",
            expected=f"at most {limit} publications from the last five years",
            confirm="count the entries in the leader's CV",
            source=SRC_OR))


def parse_amount(v) -> int | None:
    """A whole amount in CZK from a form field, or None when it cannot be read
    with certainty.

    Accepts 160000, 160 000, 160.000, 160 000 Kč, 160000.0 and 160 000,00.
    Refuses everything else, such as "?", "cca 160 000" or "160-170 000",
    because a misread amount would produce a breach that is not there.
    """
    s = str(v).strip()
    s = re.sub(r"(?i)\s*(kč|czk|,-|\.-)$", "", s)
    s = re.sub(r"[    ]", "", s)
    m = re.fullmatch(r"(\d{1,3}(?:\.\d{3})+|\d+)(?:[.,]0{1,2})?", s)
    return int(m.group(1).replace(".", "")) if m else None


def _budget_rules(form, rnd, rep) -> None:
    b = rnd["budget"]
    unreadable = []

    def num(key):
        v = form.get(key)
        if v in (None, ""):
            return None
        n = parse_amount(v)
        if n is None:
            unreadable.append(f"{key} = {str(v)[:30]!r}")
        elif 0 < n < 1000:
            # the application's own table is in thousands; 120 is probably
            # 120 000 CZK, and guessing would risk a breach that is not there
            unreadable.append(f"{key} = {str(v)[:30]!r} (in thousands? enter whole CZK)")
            return None
        return n

    total = num("budget_total_year1")
    wages = num("budget_wages")
    stipends = num("budget_stipends")
    if unreadable:
        rep.not_checked.append("budget figures that could not be read as a whole "
                               "amount in CZK: " + "; ".join(unreadable))

    if total is None:
        rep.not_checked.append("the requested total against the annual ceiling "
                               "(no readable budget_total_year1 in the form file)")
    elif total <= b["max_per_year"]:
        rep.measured.append(f"budget, first year: {_czk(total)} CZK "
                            f"(limit {_czk(b['max_per_year'])})")
    else:
        rep.add(Finding(
            rule="R06_ANNUAL_CEILING", kind=BLOCKING, where="form: budget",
            measured=f"{total:,} CZK".replace(",", " "),
            expected=f"at most {b['max_per_year']:,} CZK including overhead"
                     .replace(",", " "),
            confirm="the total row of the budget table",
            source=SRC_OR))

    if wages is not None and wages > b["caps"]["wages_and_opc_per_project"]:
        rep.add(Finding(
            rule="R06B_WAGE_CAP", kind=BLOCKING, where="form: budget",
            measured=f"{wages:,} CZK".replace(",", " "),
            expected=f"at most {b['caps']['wages_and_opc_per_project']:,} CZK"
                     .replace(",", " "),
            confirm="the personnel rows of the budget table", source=SRC_OR))

    if wages is not None and stipends is not None and (wages + stipends) > 0:
        share = 100 * stipends / (wages + stipends)
        if share <= b["stipend_share_of_personnel_min_pct"]:
            rep.add(Finding(
                rule="R06C_STIPEND_SHARE", kind=BLOCKING, where="form: budget",
                measured=f"stipends are {share:.1f} % of personnel costs",
                expected=f"strictly more than "
                         f"{b['stipend_share_of_personnel_min_pct']} %",
                confirm="stipends divided by (stipends + wages)", source=SRC_OR))
        else:
            rep.measured.append(f"stipends: {share:.1f} % of personnel costs "
                                f"(must exceed {b['stipend_share_of_personnel_min_pct']} %)")
    else:
        rep.not_checked.append("the stipend share of personnel costs "
                               "(no readable budget_wages and budget_stipends)")
    rep.not_checked.append(
        "the other budget caps (stipends per project and for the principal "
        "investigator, the supervisor's share, 100 000 CZK per person), the "
        "years after the first, and whether the table's rows add up to its "
        "total: the form file carries only the first-year totals")
    # Deliberately absent: the supervisor's pay against 10 % of the PI's
    # stipend (a recommendation, not a limit) and overhead against an exact
    # 15 % (the application computes it). See not_defects.


def _czk(n: int) -> str:
    return f"{n:,}".replace(",", " ")


# Each trigger is a set of regular expressions over folded text. They flag a
# word, not an intention, which is why every one of them is advisory.
INELIGIBLE_TRIGGERS = {
    "training": [r"\bkurz(?!\s+(eur|usd|dolar|men|koruny|cnb))", r"(?<!of )\bcourses?\b",
                 r"\bskolne\b", r"\btuition\b", r"\bskoleni\b", r"\btraining\b"],
    "computers_unjustified": [r"\bnotebook", r"\blaptop", r"\bpocitac",
                              r"\bcomputer", r"\bmonitor\b", r"\btablet"],
    "catering": [r"\bpohosteni", r"\bobcerstveni", r"\bcatering", r"\breprezentac"],
}
CONFERENCE = [r"\bkonferenc", r"\bconference", r"\bworkshop", r"\bletni skol",
              r"\bzimni skol", r"\bsummer school", r"\bwinter school"]
ACTIVE = [r"\baktivni", r"\bactive", r"\bprispev", r"\bposter", r"\bprednas",
          r"\bpresentation", r"\btalk\b", r"\breferat", r"\bpresent"]
RESPONDENT = [r"\brespondent", r"\bproband", r"\bparticipant", r"\bucastnik"]
REWARD = [r"\bodmen", r"\bdar(ek|ky|ku)\b", r"\bgift", r"\bvoucher", r"\breward"]
FOREIGN_CURRENCY = re.compile(r"\b(EUR|USD|GBP|CHF)\b|[€$£]")


def _hits(patterns, text) -> list[str]:
    out = []
    for p in patterns:
        m = re.search(p, text)
        if m:
            out.append(m.group(0).strip())
    return out


def _ineligible_rules(form, rnd, rep) -> None:
    just = form.get("budget_justification", "")
    if not just:
        rep.not_checked.append("costs GA UK does not fund (no budget "
                               "justification in the form file)")
        return
    low = fold(just)
    names = {i["id"]: i["en"] for i in rnd["ineligible_costs"]["items"]}

    flagged: dict[str, list[str]] = {}
    for rule_id, pats in INELIGIBLE_TRIGGERS.items():
        h = _hits(pats, low)
        if h:
            flagged[rule_id] = h
    conf = _hits(CONFERENCE, low)
    if conf and not _hits(ACTIVE, low):
        flagged["passive_attendance"] = conf
    resp, rew = _hits(RESPONDENT, low), _hits(REWARD, low)
    if resp and rew:
        flagged["respondent_rewards"] = resp + rew

    for rule_id, words in flagged.items():
        rep.add(Finding(
            rule=f"R10_INELIGIBLE_{rule_id.upper()}", kind=ADVISORY,
            where="form: financial requirements",
            measured="the justification mentions: " + ", ".join(words),
            expected=f"GA UK does not fund: {names.get(rule_id, rule_id)}",
            confirm="read the sentence. A conference with declared active "
                    "participation is eligible, a computer with a stated reason "
                    "may be, and respondents paid as a service are fine. This "
                    "flags the word, not the intent.",
            source=SRC_INFO))

    if FOREIGN_CURRENCY.search(just):
        rep.add(Finding(
            rule="R15_FOREIGN_CURRENCY", kind=ADVISORY,
            where="form: financial requirements",
            measured="amounts given in a foreign currency",
            expected="amounts in Czech crowns",
            confirm="look for EUR, USD or a currency sign in the justification",
            source=SRC_INFO))


def _language_rule(proposal_facts, form, rep) -> None:
    """R11: one application, one language. The guide says a project is
    submitted in Czech (Slovak) or English and that languages cannot be
    combined within one project; in the Czech version the title and annotation
    are given in both. The proposal's language is inferred from common words,
    which is a guess, so a mismatch is advisory in either direction."""
    plang = "unknown"
    readable = proposal_facts and proposal_facts.get("text") and not (
        "error" in proposal_facts or "text_error" in proposal_facts)
    if readable:
        plang = detect_language(proposal_facts["text"])
    rep.doc_language = plang
    fl = form_language(form)
    if fl is None:
        rep.not_checked.append("whether the proposal is in the language of the "
                               "form version (form_language is not in the form file)")
        return
    if plang == "unknown":
        rep.not_checked.append("the language of the proposal (not determined)")
        return
    name = {"cs": "Czech", "en": "English"}
    if fl != plang:
        rep.add(Finding(
            rule="R11_PROPOSAL_LANGUAGE", kind=ADVISORY, where="project proposal",
            measured=f"the {name[fl]} version of the form with a proposal that "
                     f"reads as {name[plang]}",
            expected="one language per application: the guide says languages "
                     "cannot be combined within one project",
            confirm="open the proposal. The language is inferred from common "
                    "words and can be wrong, for example in a text full of "
                    "quotations",
            source=SRC_INFO))
    else:
        rep.measured.append(f"language of the proposal: {name[plang]}, as the form")


NOT_CHECKED_ALWAYS = [
    "whether the applicant has another application as principal investigator "
    "in this round, or already runs a project as principal investigator",
    "whether the applicant is already on three projects (a project in its final "
    "year does not count)",
    "whether the applicant is within the standard period of study, and whether "
    "their studies have been interrupted",
    "whether the applicant plans to finish their studies during the project, or "
    "before the contract is signed",
    "whether an ethics committee statement is needed: now also for human "
    "biological material and sensitive personal data; if unsure, ask your faculty",
    "whether everyone named in the team characteristics appears in the team table",
    "whether every project of the applicant and the leader appears under "
    "'other projects'",
    "whether the section and group chosen fit the project",
    "whether the leader has recommended the application in the system",
    "the faculty's own, earlier deadline and any faculty-specific rules",
    "everything about the scientific content: this script reads no meaning",
]


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------

def render_block(rep: Report) -> str:
    """The block an applicant pastes into a chat session together with the
    draft. The prompt takes the measured values as given and keeps each
    finding's kind: a model cannot count, so it must not re-count, but an
    advisory finding stays a question for the applicant, not a breach."""
    out = [
        "FORMAL FINDINGS from the gauk-ai-feedback checker (unofficial)",
        "BLOCKING: a measured breach of a written rule. ADVISORY: measured, but "
        "a person must confirm it. UNKNOWN: the checker could not tell. The "
        "values describe the files and form fields the checker read; if one of "
        "those was wrong or out of date, so is the finding.",
        f"application: {rep.app_id}",
        f"rules: GA UK round {rep.rules_round}, transcribed {rep.rules_verified_on}"
        + ("" if rep.rules_official else " (unofficial; not reviewed by GA UK)"),
        f"language of the proposal: {rep.doc_language}",
        "",
    ]
    if not rep.findings:
        out.append("No findings. This is not a statement that the application "
                   "is complete; see the list below.")
    for f in rep.findings:
        out.append(f.line())
        out.append("")
    if rep.measured:
        out.append("MEASURED, NO FINDING:")
        out += [f"  - {m}" for m in rep.measured]
        out.append("")
    out.append("NOT CHECKED: this script cannot see any of the following:")
    for n in rep.not_checked + NOT_CHECKED_ALWAYS:
        out.append(f"  - {n}")
    return "\n".join(out)


def check_one(app: Path, form_path: Path | None, mapping: dict | None,
              index, criteria, rnd) -> Report:
    rep = Report(
        app_id=app.name,
        rules_round=rnd["round"],
        rules_verified_on=str(rnd["verified_on"]),
        rules_official=str(rnd.get("official_review", "none")).lower() not in ("none", ""),
        generated_on=dt.date.today().isoformat(),
    )
    try:
        form = read_form(form_path, mapping) if form_path else {}
    except FormError as exc:
        form = {}
        rep.add(Finding(
            rule="R00_FORM_UNREADABLE", kind=UNKNOWN, where=form_path.name,
            measured=str(exc)[:200],
            expected="a form file in the format of templates/form.yml",
            confirm="open the file; in form.yml, check the indentation and "
                    "that text with a colon in it is in quotes",
            source="templates/form.yml"))
    if not form:
        rep.not_checked.append(
            "every rule about the web-form fields: no form file was found "
            "(copy templates/form.yml into the folder to enable them)")
    run_rules(app, form, rnd, criteria, rep)
    return rep


def write_report(rep: Report, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = asdict(rep)
    payload["counts"] = rep.counts()
    payload["not_checked"] = rep.not_checked + NOT_CHECKED_ALWAYS
    (out_dir / "check.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "check.md").write_text(render_block(rep) + "\n", encoding="utf-8")


def form_file(app: Path) -> Path | None:
    return next((p for p in sorted(app.glob("form.*"))
                 if p.suffix.lower() in FORM_SUFFIXES), None)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    one = sub.add_parser("one", help="check a single application folder")
    one.add_argument("app", type=Path)
    one.add_argument("--form", type=Path, default=None)
    one.add_argument("--form-map", type=Path, default=None)
    one.add_argument("--out", type=Path, default=None,
                     help="where to write check.md and check.json "
                          "(default: the application folder)")
    one.add_argument("--rules-may-be-stale", action="store_true")

    args = ap.parse_args()
    index, criteria, rnd = load_rules()
    staleness_gate(index, args.rules_may_be_stale)

    mapping = None
    if args.form_map and args.form_map.is_file():
        mapping = yaml.safe_load(args.form_map.read_text(encoding="utf-8"))

    if not args.app.is_dir():
        print(f"not a folder: {args.app}", file=sys.stderr)
        return EXIT_USAGE
    if args.form and not args.form.is_file():
        print(f"no such form file: {args.form}", file=sys.stderr)
        return EXIT_USAGE
    rep = check_one(args.app, args.form or form_file(args.app), mapping,
                    index, criteria, rnd)
    write_report(rep, args.out or args.app)
    print(render_block(rep))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
