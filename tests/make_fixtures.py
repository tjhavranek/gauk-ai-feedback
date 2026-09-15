#!/usr/bin/env python3
"""Build the synthetic fixture applications the checker is tested against.

The fixtures are generated rather than committed as binaries so that a reviewer
can see exactly what each one carries. Every application here is invented.
None of it is a real GA UK submission, and the science in it is deliberately
thin: these files exist to exercise page counts, budget arithmetic, timetable
years and the list of things the tool does not report, not to be read.

    python tests/make_fixtures.py
"""

from __future__ import annotations

import csv
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import yaml

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF is required to build fixtures:  "
             "python -m pip install -r requirements-dev.txt")

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "fixtures"

A4 = fitz.paper_rect("a4")

# The PDF base-14 fonts use WinAnsi encoding, which has no ř, č, š, ž, ě or ů.
# A fixture written with them extracts as mojibake, which would test the
# checker against a defect the fixture invented rather than against Czech.
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]
FONT_FILE = next((f for f in FONT_CANDIDATES if Path(f).exists()), None)
if FONT_FILE is None:
    sys.exit("no Unicode TrueType font found; install DejaVu Sans or Arial")

SECTIONS_CS = [
    "1. Současný stav poznání",
    "2. Materiální zajištění projektu",
    "3. Cíle řešení projektu",
    "4. Způsob řešení",
    "5. Časový harmonogram",
    "6. Identifikace rizik",
    "7. Charakteristika řešitelského kolektivu",
    "8. Očekávané výsledky projektu včetně jejich prezentace",
]
SECTIONS_EN = [
    "1. Current state of knowledge",
    "2. Material provision for the project",
    "3. Objectives of the project",
    "4. Method of work",
    "5. Timetable",
    "6. Identification of risks",
    "7. Characteristics of the team",
    "8. Expected results and their presentation",
]

FILLER = (
    "Tato část je vyplněna zástupným textem, aby měl soubor realistickou délku. "
    "Fiktivní projekt se zabývá modelovým problémem, který slouží pouze k "
    "testování kontrolního skriptu. "
)
NO_OTHER_CS = "Navrhovatel ani vedoucí se nepodílejí na žádném dalším projektu."

FILLER_EN = (
    "This part is filled with placeholder text so that the file has a realistic "
    "length. The invented project addresses a model problem and exists only to "
    "exercise the checking script. "
)


def write_pdf(path: Path, headings, body, pages=3, size=11, page_rect=A4,
              bodies: dict | None = None):
    """A few headings per page. `bodies` maps a heading to its own text, or to
    a list of literal lines (for numbered lists)."""
    doc = fitz.open()
    per_page = max(1, len(headings) // pages + 1)
    idx = 0
    for _ in range(pages):
        page = doc.new_page(width=page_rect.width, height=page_rect.height)
        page.insert_font(fontname="F0", fontfile=FONT_FILE)
        y = 60
        for h in headings[idx:idx + per_page]:
            page.insert_text((60, y), h, fontsize=size + 1, fontname="F0")
            y += 22
            content = (bodies or {}).get(h, body * 3)
            lines = content if isinstance(content, list) else _wrap(content, 88)[:12]
            for line in lines[:14]:
                page.insert_text((60, y), line, fontsize=size, fontname="F0")
                y += size * 1.25
            y += 12
        idx += per_page
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    doc.close()


def write_docx(path: Path, paragraphs: list[str]):
    """A minimal valid .docx, without python-docx."""
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
          '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>')
    body = "".join(f'<w:p><w:r><w:t xml:space="preserve">{escape(p)}</w:t></w:r></w:p>'
                   for p in paragraphs)
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f'<w:body>{body}</w:body></w:document>')
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)


def _wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def form_csv(path: Path, **fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fields), delimiter=";")
        w.writeheader()
        w.writerow(fields)


def form_yaml(path: Path, **fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(fields, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")


def standard_attachments(d: Path, lang="cs"):
    if lang == "cs":
        write_pdf(d / "cv_resitel.pdf", ["Životopis hlavního řešitele"], FILLER, pages=1)
        write_pdf(d / "cv_vedouci.pdf", ["Životopis vedoucího"], FILLER, pages=2)
        write_pdf(d / "literatura.pdf", ["Odkazy na použitou literaturu"], FILLER, pages=1)
    else:
        write_pdf(d / "cv_pi.pdf", ["CV of the principal investigator"], FILLER_EN, pages=2)
        write_pdf(d / "cv_supervisor.pdf", ["CV of the project leader"], FILLER_EN, pages=2)
        write_pdf(d / "references.pdf", ["References"], FILLER_EN, pages=1)


def clean_cs(base: Path):
    """A Czech application in section A with no formal defects."""
    d = base / "F001_clean_cs"
    write_pdf(d / "navrh_projektu.pdf", SECTIONS_CS, FILLER, pages=4)
    standard_attachments(d)
    form_csv(
        d / "form.csv", form_language="cs", duration_years="1",
        annotation="A" * 900, objectives="B" * 600,
        keywords="metaanalýza; publikační zkreslení; ekonomie",
        team_characteristics="C" * 400,
        budget_justification=(
            "Stipendium hlavního řešitele 80 000 Kč na řešení projektu. "
            "Stipendium spoluřešitele 40 000 Kč. Materiál 20 000 Kč."),
        budget_table="80 000; 40 000; 20 000",
        budget_total_year1="161000", budget_wages="0", budget_stipends="120000",
        other_projects=NO_OTHER_CS,
    )


def defective_cs(base: Path):
    """Six pages, an over-ceiling budget, a stipend share below the floor, and
    ineligible costs named in the justification."""
    d = base / "F002_defective_cs"
    write_pdf(d / "navrh_projektu.pdf", SECTIONS_CS[:5], FILLER, pages=6)
    write_pdf(d / "cv_resitel.pdf", ["Životopis hlavního řešitele"], FILLER, pages=3)
    write_pdf(d / "cv_vedouci.pdf", ["Životopis vedoucího"], FILLER, pages=2)
    write_pdf(d / "literatura.pdf", ["Odkazy na použitou literaturu"], FILLER, pages=1)
    form_csv(
        d / "form.csv", form_language="cs", duration_years="2",
        annotation="A" * 120, objectives="B" * 200, keywords="x",
        team_characteristics="C" * 30,
        budget_justification=(
            "Notebook pro řešitele 45 000 Kč. Účast na konferenci 30 000 Kč. "
            "Kurz statistiky 12 000 Kč. Pohoštění na semináři 5 000 Kč. "
            "Mzda školitele 25 000 Kč."),
        budget_table="45 000; 30 000; 12 000; 5 000; 25 000",
        budget_total_year1="340000", budget_wages="60000", budget_stipends="90000",
        other_projects="-",
    )


def clean_en(base: Path):
    """An English application in section B with no formal defects, whose form
    fields are given in a form.yml, the route an applicant would take."""
    d = base / "F003_clean_en"
    write_pdf(d / "proposal.pdf", SECTIONS_EN, FILLER_EN, pages=4)
    standard_attachments(d, "en")
    form_yaml(
        d / "form.yml", form_language="en", duration_years=2,
        annotation="A" * 1100, objectives="B" * 800,
        keywords="spintronics; altermagnetism; transport",
        team_characteristics="C" * 500,
        budget_justification=(
            "Stipend for the principal investigator 80 000 CZK. "
            "Consumables 35 000 CZK. Open access fee 40 000 CZK."),
        budget_table="80 000; 35 000; 40 000",
        budget_total_year1=178000, budget_wages=0, budget_stipends=80000,
        other_projects="The leader runs GACR 24-12345S on a different topic; there "
                       "is no thematic overlap with this project.",
    )


def missing_sections(base: Path):
    """Sections 5, 6 and 8 absent from the proposal: the defect the substantive
    review is meant to catch and the checker can only hint at."""
    d = base / "F004_missing_sections_cs"
    write_pdf(d / "navrh_projektu.pdf",
              [SECTIONS_CS[i] for i in (0, 1, 2, 3, 6)], FILLER, pages=4)
    standard_attachments(d)
    form_csv(
        d / "form.csv", form_language="cs", duration_years="1",
        annotation="A" * 700, objectives="B" * 400, keywords="rozpočet; stipendia; respondenti",
        team_characteristics="C" * 200,
        budget_justification="Stipendium 80 000 Kč. Materiál 15 000 Kč.",
        budget_table="80 000; 15 000",
        budget_total_year1="109000", budget_wages="0", budget_stipends="95000",
        other_projects=NO_OTHER_CS,
    )


def cs_form_en_proposal(base: Path):
    """The Czech version of the form with an English proposal. The guide says
    one project cannot combine languages, so this is one advisory finding."""
    d = base / "F005_cs_form_en_proposal"
    write_pdf(d / "navrh_projektu.pdf", SECTIONS_EN, FILLER_EN, pages=4)
    standard_attachments(d)
    form_csv(
        d / "form.csv", form_language="cs", duration_years="1",
        annotation="A" * 800, objectives="B" * 500, keywords="metaanalýza; ekonomie; data",
        team_characteristics="C" * 300,
        budget_justification="Stipendium hlavního řešitele 80 000 Kč na řešení "
                             "projektu a materiál 20 000 Kč.",
        budget_table="80 000; 20 000",
        budget_total_year1="115000", budget_wages="0", budget_stipends="80000",
        other_projects=NO_OTHER_CS,
    )


def unreadable(base: Path):
    """A proposal with no text layer, standing in for a scan. Every text rule
    over it must return UNKNOWN and none may return a breach."""
    d = base / "F006_no_text_layer"
    doc = fitz.open()
    for _ in range(4):
        page = doc.new_page(width=A4.width, height=A4.height)
        page.draw_rect(fitz.Rect(60, 60, 500, 700), color=(0.8, 0.8, 0.8))
    d.mkdir(parents=True, exist_ok=True)
    doc.save(str(d / "navrh_projektu.pdf"))
    doc.close()
    standard_attachments(d)
    form_csv(
        d / "form.csv", form_language="cs", duration_years="1",
        annotation="A" * 700, objectives="B" * 400, keywords="metaanalýza; ekonomie; data",
        team_characteristics="C" * 200,
        budget_justification="Stipendium 80 000 Kč.",
        budget_table="80 000", budget_total_year1="92000",
        budget_wages="0", budget_stipends="80000", other_projects=NO_OTHER_CS)


def en_form_cs_proposal(base: Path):
    """The English version of the form with a Czech proposal: one application
    cannot combine languages, and the opponent may be from abroad."""
    d = base / "F007_en_form_cs_proposal"
    write_pdf(d / "navrh_projektu.pdf", SECTIONS_CS, FILLER, pages=4)
    standard_attachments(d, "en")
    form_csv(
        d / "form.csv", form_language="en", duration_years="1",
        annotation="A" * 800, objectives="B" * 500, keywords="metaanalýza; ekonomie; data",
        team_characteristics="C" * 300,
        budget_justification="Stipend for the principal investigator 80 000 CZK.",
        budget_table="80 000", budget_total_year1="92000",
        budget_wages="0", budget_stipends="80000",
        other_projects="Neither the applicant nor the leader takes part in any other project.")


def accepted_variants(base: Path):
    """Variants the published documents allow, all at once, plus a Word draft
    of the proposal. Must produce no finding at all.

    - the proposal is still a Word draft: the guide asks for PDF, so the
      checker reads it and asks for the PDF under NOT CHECKED
    - an ethics committee statement in the ethics slot
    - the leader's CV lists exactly ten publications
    - supervisor pay of 20 000 CZK, above the 10 % recommendation
    - respondents paid as a service; a conference with a poster
    """
    d = base / "F008_accepted_variants"
    paras = []
    for h in SECTIONS_CS:
        paras.append(h)
        if h.startswith("5."):
            paras.append("Leden až prosinec 2027: sběr dat, analýza a příprava "
                         "rukopisu.")
        else:
            paras.append(FILLER * 2)
    write_docx(d / "navrh_projektu.docx", paras)
    write_pdf(d / "cv_resitel.pdf", ["Životopis hlavního řešitele"], FILLER, pages=1)
    write_pdf(d / "cv_vedouci.pdf",
              ["Životopis vedoucího", "Deset nejvýznamnějších publikací"], FILLER,
              pages=1,
              bodies={"Deset nejvýznamnějších publikací": [
                  f"{i}. Novák, J. et al. (2024). Fiktivní článek číslo {i}. "
                  f"Journal of Tests." for i in range(1, 11)]})
    write_pdf(d / "literatura.pdf", ["Odkazy na použitou literaturu"], FILLER, pages=1)
    write_pdf(d / "eticka_komise.pdf", ["Vyjádření etické komise"], FILLER, pages=1)
    form_csv(
        d / "form.csv", form_language="cs", duration_years="1",
        annotation="A" * 900, objectives="B" * 600, keywords="rozpočet; stipendia; respondenti",
        team_characteristics="C" * 400,
        budget_justification=(
            "Stipendium hlavního řešitele 80 000 Kč. Stipendium spoluřešitele "
            "40 000 Kč. Mzda školitele 20 000 Kč. Úhrada respondentům formou "
            "služby 10 000 Kč. Konference: aktivní účast s posterem, cesta a "
            "ubytování 15 000 Kč."),
        budget_table="80 000; 40 000; 20 000; 10 000; 15 000",
        budget_total_year1="189000", budget_wages="20000", budget_stipends="120000",
        other_projects=NO_OTHER_CS,
    )


def stale_timetable(base: Path):
    """A one-year project whose timetable follows the academic year, names
    2026, and runs into 2028."""
    d = base / "F009_stale_timetable"
    write_pdf(d / "navrh_projektu.pdf", SECTIONS_CS, FILLER, pages=4,
              bodies={SECTIONS_CS[4]: (
                  "Harmonogram je rozvržen podle akademického roku 2026/2027. "
                  "Leden až prosinec 2026: rešerše literatury. Rok 2028: "
                  "dokončení a publikace výsledků.")})
    standard_attachments(d)
    form_csv(
        d / "form.csv", form_language="cs", duration_years="1",
        annotation="A" * 800, objectives="B" * 500, keywords="metaanalýza; ekonomie; data",
        team_characteristics="C" * 300,
        budget_justification="Stipendium hlavního řešitele 80 000 Kč.",
        budget_table="80 000", budget_total_year1="92000",
        budget_wages="0", budget_stipends="80000", other_projects=NO_OTHER_CS)


def long_publication_list(base: Path):
    """The leader's CV lists twelve publications; at most ten are allowed."""
    d = base / "F010_long_publication_list"
    write_pdf(d / "navrh_projektu.pdf", SECTIONS_CS, FILLER, pages=4)
    write_pdf(d / "cv_resitel.pdf", ["Životopis hlavního řešitele"], FILLER, pages=1)
    write_pdf(d / "cv_vedouci.pdf",
              ["Životopis vedoucího", "Nejvýznamnější publikace"], FILLER, pages=1,
              bodies={"Nejvýznamnější publikace": [
                  f"{i}. Novák, J. et al. (2023). Fiktivní článek {i}. Journal of Tests."
                  for i in range(1, 13)]})
    write_pdf(d / "literatura.pdf", ["Odkazy na použitou literaturu"], FILLER, pages=1)
    form_csv(
        d / "form.csv", form_language="cs", duration_years="1",
        annotation="A" * 800, objectives="B" * 500, keywords="metaanalýza; ekonomie; data",
        team_characteristics="C" * 300,
        budget_justification="Stipendium hlavního řešitele 80 000 Kč.",
        budget_table="80 000", budget_total_year1="92000",
        budget_wages="0", budget_stipends="80000", other_projects=NO_OTHER_CS)


BUILDERS = (clean_cs, defective_cs, clean_en, missing_sections,
            cs_form_en_proposal, unreadable, en_form_cs_proposal,
            accepted_variants, stale_timetable, long_publication_list)


def main() -> int:
    if OUT.exists():
        for p in sorted(OUT.rglob("*"), reverse=True):
            p.unlink() if p.is_file() else p.rmdir()
    for fn in BUILDERS:
        fn(OUT)
        print(f"  built {fn.__name__}")
    print(f"fixtures in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
