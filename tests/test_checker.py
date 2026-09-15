#!/usr/bin/env python3
"""Regression tests for the checker, the build and the quote verifier.

The tests that matter most come first. A finding raised against an application
that is formally correct, or against something on the not-a-defect list, sends
a student after a problem that does not exist. So the clean and the
accepted-variant fixtures must produce nothing at all, and that is asserted
before anything else.

    python tests/make_fixtures.py
    python tests/test_checker.py

Exits 0 if everything holds, 1 otherwise. No test framework is needed.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "checker"))
sys.path.insert(0, str(ROOT / "tools"))

import gauk_check as gc  # noqa: E402
import verify_quotes as vq  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        failures.append(name)


def report_for(app: str):
    index, criteria, rnd = gc.load_rules()
    d = FIXTURES / app
    return gc.check_one(d, gc.form_file(d), None, index, criteria, rnd)


def rules_of(rep, kind=None) -> set[str]:
    return {f.rule for f in rep.findings if kind is None or f.kind == kind}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not FIXTURES.exists():
        print("fixtures missing; run: python tests/make_fixtures.py", file=sys.stderr)
        return 1

    print("no finding against a formally correct application, or against "
          "anything on the not-a-defect list")
    for app in ("F001_clean_cs", "F003_clean_en", "F008_accepted_variants"):
        rep = report_for(app)
        check(f"{app}: no findings at all", not rep.findings,
              f"got {[(f.rule, f.measured) for f in rep.findings]}")

    rep = report_for("F001_clean_cs")
    check("F001: measured values are listed even without findings",
          any("pages (limit 5)" in m for m in rep.measured)
          and any("stipends" in m for m in rep.measured), str(rep.measured))
    rep = report_for("F003_clean_en")
    check("F003: the form.yml was read", "budget_total_year1" in rep.inputs_seen["form_fields"],
          str(rep.inputs_seen))
    rep = report_for("F008_accepted_variants")
    check("F008: the Word draft of the proposal was read",
          "navrh_projektu.docx" in rep.inputs_seen["attachments"]
          and rep.doc_language == "cs", str(rep.inputs_seen))
    check("F008: and the student is told to convert it to PDF",
          any("convert it" in n for n in rep.not_checked), str(rep.not_checked))

    print("\ndefects are caught")
    rep = report_for("F002_defective_cs")
    for rule in ("R03_PAGE_LIMIT", "R06_ANNUAL_CEILING", "R06B_WAGE_CAP",
                 "R06C_STIPEND_SHARE"):
        check(f"F002: {rule} fires", rule in rules_of(rep, gc.BLOCKING))
    check("F002: ineligible costs are advisory, never blocking",
          not any(f.rule.startswith("R10_") and f.kind == gc.BLOCKING
                  for f in rep.findings))
    check("F002: a conference with no active participation is flagged",
          "R10_INELIGIBLE_PASSIVE_ATTENDANCE" in rules_of(rep))

    rep = report_for("F004_missing_sections_cs")
    missing = [f for f in rep.findings if f.rule == "R13_SECTION_HEADING"]
    check("F004: missing sections are reported", len(missing) == 1)
    check("F004: naming the three absent sections",
          bool(missing) and all(s in missing[0].measured for s in ("5.", "6.", "8.")),
          missing[0].measured if missing else "")
    check("F004: a missing section is advisory, not a breach",
          bool(missing) and missing[0].kind == gc.ADVISORY)

    for app, what in (("F005_cs_form_en_proposal", "Czech form, English proposal"),
                      ("F007_en_form_cs_proposal", "English form, Czech proposal")):
        rep = report_for(app)
        check(f"{app}: {what} is one advisory, in either direction",
              [(f.rule, f.kind) for f in rep.findings]
              == [("R11_PROPOSAL_LANGUAGE", gc.ADVISORY)],
              str([(f.rule, f.kind) for f in rep.findings]))

    rep = report_for("F009_stale_timetable")
    tt = [f for f in rep.findings if f.rule == "R17_TIMETABLE_YEARS"]
    check("F009: the timetable's years are flagged", len(tt) == 1, str(rules_of(rep)))
    check("F009: naming the academic year, 2026 and 2028",
          bool(tt) and all(s in tt[0].measured for s in ("academic", "2026", "2028")),
          tt[0].measured if tt else "")
    check("F009: and only as an advisory", bool(tt) and tt[0].kind == gc.ADVISORY)

    rep = report_for("F010_long_publication_list")
    pl = [f for f in rep.findings if f.rule == "R16_PUBLICATION_LIST"]
    check("F010: a twelve-item publication list is flagged",
          len(pl) == 1 and "12" in pl[0].measured, str(rules_of(rep)))

    print("\nan unreadable file yields UNKNOWN and never a breach")
    rep = report_for("F006_no_text_layer")
    check("F006: nothing blocking", not rules_of(rep, gc.BLOCKING),
          f"got {sorted(rules_of(rep, gc.BLOCKING))}")
    check("F006: R00_UNREADABLE is UNKNOWN", "R00_UNREADABLE" in rules_of(rep, gc.UNKNOWN))
    check("F006: its page count is still measured",
          any(m.startswith("navrh_projektu.pdf: 4 pages") for m in rep.measured),
          str(rep.measured))

    print("\ninput a student might really give")
    for raw, want in (("160000", 160000), ("160 000", 160000), ("160.000", 160000),
                      ("160 000 Kč", 160000), ("160000.0", 160000),
                      ("160 000,00", 160000), ("?", None), ("cca 160 000", None),
                      ("160-170 000", None), ("1.5", None)):
        check(f"amount {raw!r} reads as {want}", gc.parse_amount(raw) == want,
              str(gc.parse_amount(raw)))
    files = {n: Path(n) for n in ("proposal_references.pdf", "research_proposal.pdf",
                                  "literatura.pdf")}
    found, amb = gc.assign_slots(files)
    check("a file whose name fits two attachments is not used for either",
          found.get("proposal") == Path("research_proposal.pdf")
          and found.get("references") == Path("literatura.pdf"), str(found))
    found, amb = gc.assign_slots({n: Path(n) for n in ("navrh_v1.pdf", "navrh_v2.pdf")})
    check("two candidate proposals are reported as ambiguous, not guessed",
          "proposal" not in found and len(amb.get("proposal", [])) == 2, str(amb))
    found, amb = gc.assign_slots({n: Path(n) for n in ("navrh.docx", "navrh.pdf")})
    check("a PDF and its Word draft are one attachment, and the PDF is used",
          found.get("proposal") == Path("navrh.pdf") and not amb, str(found))

    with tempfile.TemporaryDirectory() as tmp:
        docx = Path(tmp) / "draft.docx"
        with zipfile.ZipFile(docx, "w") as z:
            z.writestr("word/document.xml", (
                '<w:document xmlns:w="w"><w:body><w:p><w:r><w:t>Kept text.</w:t></w:r>'
                '<w:del w:id="1"><w:r><w:delText>struck out</w:delText></w:r></w:del>'
                '<w:r><w:instrText> PAGE </w:instrText></w:r></w:p></w:body></w:document>'))
        text = gc.docx_text(docx)
        check("Word: deleted tracked changes and field codes are not read",
              "Kept text." in text and "struck" not in text and "PAGE" not in text, text)
        bad = Path(tmp) / "form.yml"
        bad.write_text("annotation: a: b: c\n  - broken", encoding="utf-8")
        try:
            gc.read_form(bad, None)
            raised = False
        except gc.FormError:
            raised = True
        check("a broken form.yml raises FormError, not a traceback", raised)
        csvf = Path(tmp) / "form.csv"
        csvf.write_text("annotation;keywords\nshort row\n", encoding="utf-8")
        check("a CSV row with a missing cell does not become the text 'None'",
              gc.read_form(csvf, None) == {"annotation": "short row"},
              str(gc.read_form(csvf, None)))

    print("\nno finding cites a repealed measure")
    stale = []
    for d in sorted(p for p in FIXTURES.iterdir() if p.is_dir()):
        for f in report_for(d.name).findings:
            if "11/2023" in f.source or "42/2025" in f.source:
                stale.append((d.name, f.rule))
    check("every finding cites a current published document", not stale, str(stale))

    print("\ntext normalisation")
    check("non-breaking spaces fold to ordinary ones",
          gc.fold("Current state of knowledge") == "current state of knowledge")
    check("diacritics fold away", gc.fold("Způsob řešení") == "zpusob reseni")
    check("soft hyphens and zero-width characters are dropped",
          gc.fold("Cíle­projektu​") == "cileprojektu")
    check("character counting normalises to NFC",
          gc.count_chars("řelí") == gc.count_chars("řelí"))
    check("the form version is read from the form file, not guessed",
          gc.form_language({"form_language": "Čeština"}) == "cs"
          and gc.form_language({"form_language": "EN"}) == "en"
          and gc.form_language({}) is None)

    print("\nthe quote verifier")
    source = gc.attachment_facts(FIXTURES / "F001_clean_cs" / "navrh_projektu.pdf")["text"]

    def verdicts(review, src=source):
        return [s for _, s in vq.verify_detail(review, src)]

    check("a real quote is found despite line breaks",
          verdicts('- **Quote:** "Fiktivní projekt se zabývá modelovým problémem"')
          == ["exact"])
    check("an invented quote is caught",
          verdicts("- **Citace:** „Tento projekt jistě změní celý obor“") == ["not_found"])
    check("a quote found only without diacritics is accepted but marked",
          verdicts('- **Quote:** "Fiktivni projekt se zabyva modelovym problemem"')
          == ["diacritics"])
    check("every quote on a line is checked, not just the longest",
          verdicts('- **Quote:** "Fiktivní projekt se zabývá" and "slouží pouze k '
                   'nicotnému účelu"') == ["exact", "not_found"])
    check("a quote running over two lines is joined and checked",
          verdicts('- **Quote:** "Fiktivní projekt se zabývá\n  modelovým problémem"')
          == ["exact"])
    two = "The first sentence says one thing. The second sentence says another."
    check("the pieces of an ellipsed quote must come in order",
          verdicts('- **Quote:** "The second sentence ... The first sentence"', two)
          == ["not_found"]
          and verdicts('- **Quote:** "The first sentence ... says another"', two)
          == ["exact"])
    check("no piece of an ellipsed quote is dropped, however short",
          verdicts('- **Quote:** "Fiktivní projekt se ... ne zabývá modelovým problémem"')
          == ["not_found"])
    check("a quote too short to identify a place is refused",
          verdicts('- **Quote:** "projekt"') == ["too_short"])
    check("but a short quote that is a whole field or line is accepted",
          verdicts('- **Quote:** "Žádné."', "--- other_projects ---\nŽádné.\n")
          == ["exact"])
    check("quotes in the Contribution section are checked too",
          verdicts('## Contribution\nThe text says "slouží pouze k testování '
                   'kontrolního skriptu" and "přinese revoluci v oboru".')
          == ["exact", "not_found"])

    print("\nevery report carries the list of what was not checked")
    for app in ("F001_clean_cs", "F002_defective_cs"):
        block = gc.render_block(report_for(app))
        check(f"{app}: NOT CHECKED block present", "NOT CHECKED" in block)
        check(f"{app}: eligibility named in it", "standard period of study" in block)
        check(f"{app}: marked unofficial", "unofficial" in block)
        check(f"{app}: explains that an advisory needs confirming",
              "a person must confirm it" in block)
    check("a clean report does not claim the application is in order",
          "not a statement that the application is complete"
          in gc.render_block(report_for("F001_clean_cs")))

    print("\nthe generated artefacts match the rules")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "build.py"), "--check"],
                       capture_output=True, text=True)
    check("dist/ is up to date with rules/ and src/", r.returncode == 0, r.stderr.strip())
    for lang, head, contrib in (("en", "DOES NOT TREAT AS A DEFECT", "## Contribution"),
                                ("cs", "ZA VADU NEPOVAŽUJE", "## Přínos projektu")):
        p = ROOT / "dist" / f"prompt_{lang}.md"
        txt = p.read_text(encoding="utf-8") if p.exists() else ""
        check(f"prompt_{lang}: carries the not-a-defect list", head in txt)
        check(f"prompt_{lang}: has the contribution trigger and block",
              "N-CONTRIBUTION" in txt and contrib in txt)
        check(f"prompt_{lang}: says it is unofficial",
              "UNOFFICIAL" in txt or "NEOFICIÁLNÍ" in txt)
        check(f"prompt_{lang}: no stale citation of a repealed measure",
              "11/2023" not in txt and "42/2025" not in txt.split("repeals")[0])

    print("\nno personal path or address in a published file")
    # built from pieces so that this file does not trip its own scan
    markers = ["C:" + "\\Users", "/Us" + "ers/", "/ho" + "me/", "@gm" + "ail", "Drop" + "box"]
    leaks = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in (".md", ".yml", ".yaml", ".py",
                                                        ".txt", ".cff", ".json", ".cfg"):
            continue
        if any(part in ("fixtures", "out", ".git") for part in p.relative_to(ROOT).parts):
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        leaks += [(str(p.relative_to(ROOT)), m) for m in markers if m in text]
    check("no personal path or email address in any published file", not leaks,
          str(leaks[:10]))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
