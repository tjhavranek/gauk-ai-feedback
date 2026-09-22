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
    found, amb = gc.assign_slots({n: Path(n) for n in ("navrh_projektu.pdf",
                                                       "zivotopis_navrhovatele.pdf")})
    check("'navrhovatel' in a CV's name does not make it a proposal",
          found.get("proposal") == Path("navrh_projektu.pdf")
          and found.get("cv_pi") == Path("zivotopis_navrhovatele.pdf") and not amb,
          f"{found} {amb}")
    found, amb = gc.assign_slots({n: Path(n) for n in ("projekt.pdf",
                                                       "proposal_bibliography.pdf")})
    check("a bibliography named like the proposal is never taken for it",
          "proposal" not in found, str(found))
    found, amb = gc.assign_slots({n: Path(n) for n in ("navrh.docx", "navrh.pdf")})
    check("a PDF and its Word draft are one attachment, and the PDF is used",
          found.get("proposal") == Path("navrh.pdf") and not amb, str(found))

    print("\nsection headings worded differently")
    _, crit, _ = gc.load_rules()
    text = ("1. Current state of knowledge\nx\n2. Material resources for the project\nx\n"
            "3. Objectives\nx\n4. Methods\nx\n5. Timeline\n2027\n6. Risks\nx\n"
            "7. Research team\nx\n8. Presentation of results\nx")
    _, heads = gc.section_lines(text, crit)
    check("'Material resources' and 'Presentation of results' are recognised",
          {2, 8} <= set(heads), str(heads))
    _, heads = gc.section_lines("1. State of the art\nx\nMaterials and methods\ny\n"
                                "Outcomes were measured weekly.\n", crit)
    check("'Materials and methods' and a body sentence are not taken for headings",
          set(heads) == {1}, str(heads))
    text = ("1. Současný stav poznání\nx\n2. Materiální zajištění\nx\n3. Cíle\nx\n"
            "4. Způsob řešení\nPostup:\n1. Schedule interviews with teachers\n"
            "5. Plán prací\n2027\n6. Identifikace rizik\nx\n7. Řešitelský kolektiv\nx\n"
            "8. Očekávané výsledky\nx")
    lines, heads = gc.section_lines(text, crit)
    check("a numbered list item inside another section is not taken for a heading",
          5 not in heads or not lines[heads[5]].startswith("1."), str(heads))

    # body sentences must not move a heading and so change what is reported
    _, crit, rnd = gc.load_rules()

    def proposal_findings(body: str, duration: str = "1") -> set[str]:
        rep = gc.Report("t", 24, "2026-09-19", False, "2026-09-19")
        gc._proposal_rules(Path("navrh.docx"), {"text": body, "format": "docx"},
                           {"duration_years": duration}, rnd, crit, rep)
        return {f.rule for f in rep.findings}

    sections = ["1. Current state of knowledge", "2. Material provision", "3. Objectives",
                "4. Method of work", "5. Timetable", "6. Identification of risks",
                "7. Characteristics of the team", "8. Expected results and their presentation"]

    def proposal(extra: dict[int, str]) -> str:
        return "\n".join(f"{h}\n{extra.get(k, 'Text of the section.')}"
                         for k, h in enumerate(sections, 1))

    got = proposal_findings(proposal({4: "Scheduled interviews were tested in a pilot in 2026.",
                                      5: "January to December 2027: data and analysis."}))
    check("a body sentence starting with 'Scheduled' does not become the timetable",
          not got & {"R17_TIMETABLE_YEARS", "R13B_SECTION_ORDER"}, str(got))
    got = proposal_findings(proposal({5: "2027: data.\nExpected outcomes will be presented "
                                         "at two conferences.\n2028: writing."}))
    check("a body sentence starting with 'Expected outcomes' does not end the timetable",
          "R17_TIMETABLE_YEARS" in got and "R13B_SECTION_ORDER" not in got, str(got))
    body = proposal({6: "1. Equipment failure. Probability low; a second device is available."})
    body = body.replace("2. Material provision", "2. Laboratory access")
    got = proposal_findings(body)
    check("a numbered risk item is not promoted to a missing section's heading",
          "R13B_SECTION_ORDER" not in got, str(got))

    print("\nprojects in the CVs against the other-projects field")
    cv = {"cv_supervisor": "Projekty:\nŘešitel projektu GA ČR 25-01234S (2025–2027)\n"
                           "Člen výzkumné skupiny Cooperatio",
          "cv_pi": "Účast na konferenci, stipendium, bez projektů."}
    for label, texts, form, expect in (
            ("a funder in the leader's CV that the field leaves out is asked about",
             cv, {"other_projects": "Žádné další projekty."}, {"GA ČR", "Cooperatio"}),
            ("a funder the field names is not asked about, in any spelling",
             cv, {"other_projects": "Vedoucí: GAČR 25-01234S, blízké téma; skupina COOPERATIO."},
             set()),
            ("a project the field gives under its English name is not asked about",
             {"cv_pi": "Principal investigator, GA UK 123456 (2026-2027)"},
             {"other_projects": "Charles University Grant Agency 123456, a related topic"},
             set()),
            ("a funder's own programme counts as that funder",
             {"cv_supervisor": "PI, GA CR EXPRO 23-12345X (2023-2027)"},
             {"other_projects": "GA CR 23-12345X, unrelated"}, set()),
            ("a funder's English name in a CV is recognised",
             {"cv_supervisor": "Member of a Charles University Grant Agency project (2026-2028)"},
             {"other_projects": "None."}, {"GA UK"}),
            ("a review or panel role is not a project",
             {"cv_supervisor": "Reviewer for the Czech Science Foundation\n"
                               "ERC evaluation panel member"},
             {"other_projects": "None."}, set()),
            ("a project that ended before the year of applying is not asked about",
             {"cv_pi": "GA UK 654321, hlavní řešitel (2021–2023)"},
             {"other_projects": "Žádné."}, set()),
            ("nothing is said when the form has no such field", cv, {}, set()),
            ("words that merely contain a funder's letters are not a funder",
             {"cv_supervisor": "Uncertain gauges; primusová; Mercedes; expropriation."},
             {"other_projects": "-"}, set())):
        rep = gc.Report("t", 24, "2026-09-16", False, "2026-09-16")
        gc.other_projects_rule(form, texts, rep, year=2026)
        got = {name for f in rep.findings for name, _ in gc.FUNDERS if name in f.measured}
        check(label, got == expect and all(f.kind == gc.ADVISORY for f in rep.findings),
              str([f.measured for f in rep.findings]))

    with tempfile.TemporaryDirectory() as tmp:
        index, criteria, rnd = gc.load_rules()
        for label, width, height, rotation, expect_finding in (
                ("portrait A4", 595.28, 841.89, 0, False),
                ("landscape A4", 841.89, 595.28, 0, False),
                ("rotated A4", 841.89, 595.28, 90, False),
                ("portrait Letter", 612, 792, 0, True),
                ("landscape Letter", 792, 612, 0, True)):
            with gc.pypdf.PdfWriter() as pdf:
                pdf.add_blank_page(width=width, height=height).rotate(rotation)
                pdf.write(Path(tmp) / "proposal.pdf")
            rep = gc.check_one(Path(tmp), None, None, index, criteria, rnd)
            check(f"page size: {label}",
                  ("R03B_PAGE_SIZE" in rules_of(rep)) == expect_finding,
                  str([(f.rule, f.measured) for f in rep.findings]))
        try:
            import fitz
        except ImportError:
            fitz = None
        if fitz is not None and gc.pdfplumber is not None:
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((72, 100), "Eleven point text on a rotated page. " * 3, fontsize=11)
            page.set_rotation(90)
            doc.save(str(Path(tmp) / "rotated.pdf"))
            doc.close()
            typ = gc.typography(Path(tmp) / "rotated.pdf")
            check("a rotated page gives no false font-size reading",
                  "error" in typ or abs(typ["modal_pt"] - 11) < 0.6, str(typ))
            doc = fitz.open()
            doc.new_page().insert_text((72, 100), "Locked against editing only.", fontsize=11)
            doc.save(str(Path(tmp) / "locked.pdf"), encryption=fitz.PDF_ENCRYPT_AES_128,
                     owner_pw="owner", user_pw="", permissions=fitz.PDF_PERM_PRINT)
            doc.close()
            facts = gc.pdf_facts(Path(tmp) / "locked.pdf")
            check("a PDF locked only against editing is still read",
                  "error" not in facts and facts.get("pages") == 1, str(facts.get("error")))
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
        yml = Path(tmp) / "form.yml"
        yml.write_text("budget_wages: 20000\nbudget_stipends: 120.000\n"
                       "budget_total_year1: 161000\nai_used: yes\n", encoding="utf-8")
        form = gc.read_form(yml, None)
        check("form.yml values stay text: 120.000 and yes survive unquoted",
              form.get("budget_stipends") == "120.000" and form.get("ai_used") == "yes",
              str(form))
        index, criteria, rnd = gc.load_rules()
        rep = gc.Report("t", 24, "x", False, "x")
        gc._budget_rules(form, rnd, rep)
        check("so a Czech thousands separator gives no false stipend-share breach",
              not rep.findings and any("stipends" in m for m in rep.measured),
              str([(f.rule, f.measured) for f in rep.findings]))
        rep = gc.Report("t", 24, "x", False, "x")
        gc._budget_rules({"budget_wages": "20", "budget_stipends": "120000"}, rnd, rep)
        check("an amount that looks like thousands is UNKNOWN, not a breach",
              not rep.findings and any("in thousands" in n for n in rep.not_checked),
              str(rep.not_checked))
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
    check("an altered second line of a quote is caught",
          verdicts('- **Quote:** "Fiktivní projekt se zabývá\n  úplně jiným problémem"\n'
                   '- **Type:** statement') == ["not_found"])
    check("„…\" quotes closed with a straight mark, two to a line, are both checked",
          verdicts('- **Citace:** „Fiktivní projekt se zabývá" / „slouží pouze k testování '
                   'kontrolního skriptu."') == ["exact", "exact"])
    check("a Czech quote does not swallow the next fields or their quoted terms",
          verdicts("- **Citace:** „Fiktivní projekt se zabývá modelovým problémem“\n"
                   "- **Typ:** tvrzení\n"
                   "- **Náprava:** doplňte „Metody odhadu panelových dat“") == ["exact"])
    bare_review = ("## Findings\n\n### 1. First\n- **Quote:** \"Fiktivní projekt se "
                   "zabývá\"\n\n### 2. Second\n- **Type:** omission\n\n## For your supervisor\n")
    check("a finding without a quote is reported",
          vq.findings_without_quote(bare_review) == ["2. Second"],
          str(vq.findings_without_quote(bare_review)))
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
        _, _, rnd = gc.load_rules()
        flat = " ".join(txt.split())
        check(f"prompt_{lang}: carries every reminder, printed under the closing heading",
              all(" ".join(it[lang].split()) in flat for it in rnd["reminders"]["items"])
              and ("REMINDERS BEFORE SUBMITTING" in txt or "PŘIPOMÍNKY PŘED PODÁNÍM" in txt))
        check(f"prompt_{lang}: no stale citation of a repealed measure",
              "11/2023" not in txt and "42/2025" not in txt.split("repeals")[0])
        # The prompt names its own end marker, so that a chatbot can tell the
        # student when a paste arrived cut short. A build that splits on the
        # first marker instead of the last would ship a prompt of a few
        # hundred characters that still looks well formed.
        check(f"prompt_{lang}: the whole prompt was built, not cut at the first end marker",
              len(txt) > 30000, f"{len(txt)} characters")
        check(f"prompt_{lang}: the last line of the prompt is the end marker it names",
              txt.rstrip().rstrip("`").rstrip().endswith("=== PROMPT END ==="))
        # The prompt describes its end marker rather than quoting it: a quoted
        # marker would sit inside every truncated prefix, so a chatbot could
        # find it and conclude the prompt arrived whole.
        body = (ROOT / "src" / f"prompt_body_{lang}.md").read_text(encoding="utf-8")
        prompt_only = txt.replace("\r\n", "\n").split("```text\n", 1)[1].rsplit("\n```", 1)[0]
        check(f"prompt_{lang}: the end marker is written once, at the end, and never quoted",
              sum(1 for ln in body.split("\n") if ln.strip() == "=== PROMPT END ===") == 1
              and prompt_only.count("=== PROMPT END ===") == 1)

    import build as _bld
    src_en = (ROOT / "src" / "prompt_body_en.md").read_text(encoding="utf-8")
    for break_it, why in (
            (lambda s: s.replace("\n=== PROMPT END ===", "", 1), "no end marker"),
            (lambda s: s.replace("=== PROMPT BEGIN ===",
                                 "=== PROMPT BEGIN ===\n=== PROMPT BEGIN ===", 1),
             "two begin markers")):
        try:
            _bld.extract_prompt(break_it(src_en))
            refused = False
        except SystemExit:
            refused = True
        check(f"build: a prompt source with {why} is refused, not patched up", refused)

    print("\nthe web page")
    import json
    import build as bld
    with tempfile.TemporaryDirectory() as tmp:
        site = Path(tmp) / "site"
        bld.build_site(site, vendor=False)
        data = json.loads((site / "data.js").read_text(encoding="utf-8")
                          .split("=", 1)[1].strip().rstrip(";"))
        for lang in ("en", "cs"):
            dist_txt = (ROOT / "dist" / f"prompt_{lang}.md").read_text(encoding="utf-8")
            fenced = dist_txt.replace("\r\n", "\n").split("```text\n", 1)[1].rsplit("\n```", 1)[0]
            check(f"web: the {lang} prompt is exactly the one in dist/",
                  data["prompt"][lang] == fenced,
                  f"web {len(data['prompt'][lang])} chars, dist {len(fenced)}")
        rp = gc.load_rules()[2]["running_projects"]
        for part, short in (("continuation", "cont"), ("final", "final")):
            for lang in ("en", "cs"):
                txt = bld.report_text(*gc.load_rules(), lang, part)
                check(f"report_{short}_{lang}: carries every rule line for its mode",
                      all(" ".join(it[lang].split()) in " ".join(txt.split())
                          for it in rp[part]["items"]))
                check(f"report_{short}_{lang}: the page copies exactly that prompt",
                      data["reportPrompt"][short][lang] == txt)
                other = "final" if part == "continuation" else "continuation"
                only = [it for it in rp[other]["items"]
                        if it["id"] not in {x["id"] for x in rp[part]["items"]}]
                check(f"report_{short}_{lang}: and not the other mode's rules",
                      not any(" ".join(it[lang].split()) in " ".join(txt.split())
                              for it in only if it["id"] in ("final_deferral", "cont_team")))
        check("every running-project line cites a published source",
              all(it.get("basis") for part in ("continuation", "final")
                  for it in rp[part]["items"]))
        check("web: the page shows the same reminders as the prompt",
              all(data["reminders"][lang] == [it[lang] for it in gc.load_rules()[2]
                                              ["reminders"]["items"]]
                  for lang in ("en", "cs")))
        check("web: the browser runs the repository's own checker",
              (site / "py/checker/gauk_check.py").read_bytes()
              == (ROOT / "checker/gauk_check.py").read_bytes())
        check("web: the browser gets the repository's own rules",
              all((site / "py/rules" / n).read_bytes() == (ROOT / "rules" / n).read_bytes()
                  for n in ("INDEX.yml", "criteria.yml", "round24.yml")))
    strings = json.loads((ROOT / "web/strings.json").read_text(encoding="utf-8"))
    probs = bld.site_problems(strings)
    check("web: every text on the page exists in Czech and English", not probs, str(probs))
    untranslated = [s for s in gc.NOT_CHECKED_ALWAYS if s not in strings["cs"].get("nc", {})]
    check("web: every fixed NOT CHECKED line has a Czech translation", not untranslated,
          str(untranslated[:2]))
    page = (ROOT / "web/index.html").read_text(encoding="utf-8")
    check("web: the page loads nothing from another site",
          "connect-src 'self'" in page and 'src="http' not in page
          and "fonts.googleapis" not in page)

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
