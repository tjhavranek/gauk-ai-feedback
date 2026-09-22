#!/usr/bin/env python3
"""Generate dist/ from rules/ and src/.

The rules live in YAML exactly once. Every artefact a human reads is generated
from them and stamped with the hash of its sources, so that a rule can be
changed in one place and a drifted copy shows up as a failing check rather than
as a wrong answer six months later.

    python tools/build.py            regenerate dist/
    python tools/build.py --check    regenerate to a temp dir and compare;
                                     exit 2 if dist/ is out of date
    python tools/build.py --diff 24 25
                                     print the rule delta between two rounds

Requires PyYAML. Nothing else.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required:  python -m pip install -r requirements.txt")

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "rules"
SRC = ROOT / "src"
DIST = ROOT / "dist"
WEB = ROOT / "web"
CACHE = ROOT / ".cache"

# The web page runs the checker under Pyodide. Every runtime file it serves is
# listed here with its SHA-256, and a file that does not match is refused, so
# the page never ships code nobody checked and never loads anything from
# another site. Update the version and the hashes together.
PYODIDE_VERSION = "314.0.7"
_CDN = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
VENDOR = {
    "pyodide/pyodide.mjs": (
        _CDN + "pyodide.mjs",
        "6f1d60f7bf529beb300f0f47983c921d3982363640ba20af0e38efdddbc66109"),
    "pyodide/pyodide.asm.mjs": (
        _CDN + "pyodide.asm.mjs",
        "f7cdc8ece80678ceb712f8e65ebe6d3a83203a180c399865f49612a051693635"),
    "pyodide/pyodide.asm.wasm": (
        _CDN + "pyodide.asm.wasm",
        "cc36e3cab04fdfc9a63ff13eb52eae2b911bf46c025cc7b281f394bd3de1d5e6"),
    "pyodide/python_stdlib.zip": (
        _CDN + "python_stdlib.zip",
        "fa1957e5777068fc4f7437f96d860ae2fbe9c19732ba06c84e004ec16dd7dd7a"),
    "pyodide/pyodide-lock.json": (
        _CDN + "pyodide-lock.json",
        "5dc2fc119108bc148c7457dc86e7675b5c87e1cafd420b9c34c1eaef7b36c010"),
    "pyodide/pyyaml-6.0.3-cp314-cp314-pyemscripten_2026_0_wasm32.whl": (
        _CDN + "pyyaml-6.0.3-cp314-cp314-pyemscripten_2026_0_wasm32.whl",
        "a05d2a48c13ed72a8c60c73b30b753a25c3a591bb66c15428b7e95e69a9e806f"),
    "pyodide/pycryptodome-3.23.0-cp37-abi3-pyemscripten_2026_0_wasm32.whl": (
        _CDN + "pycryptodome-3.23.0-cp37-abi3-pyemscripten_2026_0_wasm32.whl",
        "67b86abb0de02dceebf422d10fc6e0e3754aea08626d1957e6fe69b75cbf644d"),
    "py/pypdf-6.18.1-py3-none-any.whl": (
        "https://files.pythonhosted.org/packages/58/13/"
        "645df3995075112cb3cce15e8797c205f0f88fb50acc11012b84b071bc22/"
        "pypdf-6.18.1-py3-none-any.whl",
        "ee93a2665670ecf57ee81d197a4ca548f3dc15f9cefc56e59b8140866aaa3de5"),
}
WEB_FILES = ("index.html", "app.css", "app.js", "worker.js")

LANGS = ("en", "cs")

# Labels that appear in generated blocks. Kept here, not in the YAML, because
# they are wording rather than rules.
L = {
    "en": {
        "criteria_head": "THE OFFICIAL CRITERIA",
        "checklist_head": "WHAT THE OPPONENT IS ASKED",
        "sections_head": "THE PRESCRIBED STRUCTURE OF THE PROJECT PROPOSAL",
        "fields_head": "WEB-FORM FIELDS AND THEIR LIMITS",
        "attach_head": "ATTACHMENTS",
        "budget_head": "BUDGET RULES",
        "inelig_head": "COSTS GA UK DOES NOT FUND",
        "timetable_head": "THE TIMETABLE RULE",
        "notdefects_head": "WHAT THIS REVIEW DOES NOT TREAT AS A DEFECT",
        "notdefects_intro": (
            "Do not report any of the following as a formal defect or a breach: "
            "the published documents allow each of them. Where one bears on the "
            "substance, as a budget too small for the planned work would, raise "
            "it as a point of substance."
        ),
        "team_head": "THE TEAM",
        "reminders_head": "REMINDERS BEFORE SUBMITTING",
        "report_rules_head": "WHAT THE PUBLISHED RULES REQUIRE",
        "report_cont_what": (
            "You are reviewing a CONTINUATION REQUEST together with the ANNUAL "
            "REPORT for the year that is ending. The two are submitted as one "
            "thing: the money asked for the next year, and the report on the "
            "year behind, whose parts are the year's work, the outlook, what "
            "was spent, a comment on the spending, and the results."),
        "report_final_what": (
            "You are reviewing a FINAL REPORT, the one a project files when it "
            "ends. A project that ended early files one too, and a project "
            "whose assessment was deferred files a supplemented report a year "
            "later."),
        "report_deadline": "Deadline",
        "language_head": "LANGUAGE OF THE APPLICATION",
        "up_to": "up to {n}",
        "if_applicable": "only if it applies",
        "annot_langs": ("in English", "in Czech; Czech version of the form only"),
        "not_uploaded": "not uploaded with the application",
        "window": "covering the last {n} years",
        "recommended_ids": "recommended identifiers",
        "per_person_wages": "of that, wages and other personnel costs",
        "notchecked_head": "RULES THIS REVIEW CANNOT SEE",
        "source": "Source",
        "chars": "characters",
        "pages": "pages",
        "pivotal": "GA UK calls this the pivotal chapter of the application.",
        "counting": (
            "Character counts include spaces. You do not count them yourself; "
            "see the formal findings block."
        ),
        "max_per_year": "max per year, including overhead",
        "duration": "duration",
        "years": "years",
        "overhead": ("overhead: at most {pct} % of direct costs; the application "
                     "computes it and rounds it"),
        "wages": "wages and other personnel costs, per project",
        "of_that_supervisor": "of that, for the supervisor",
        "stipends": "stipends, per project",
        "of_that_pi": "of that, for the principal investigator",
        "per_person": "any one person, per calendar year, in total",
        "stipend_share": "stipends must exceed {pct} % of personnel costs",
        "max_pages": "max {n} {pages}",
        "typeset": "{size}, {pt} pt, spacing {sp}",
        "conditional": "conditional",
        "per_file": "max {mb} MB per file",
        "required_contents": "must contain",
        "recommended": "recommended contents",
    },
    "cs": {
        "criteria_head": "OFICIÁLNÍ HLEDISKA POSUZOVÁNÍ",
        "checklist_head": "NA CO SE PTÁ OPONENT",
        "sections_head": "PŘEDEPSANÁ STRUKTURA PŘÍLOHY NÁVRH PROJEKTU",
        "fields_head": "POLE WEBOVÉHO FORMULÁŘE A JEJICH LIMITY",
        "attach_head": "PŘÍLOHY",
        "budget_head": "PRAVIDLA ROZPOČTU",
        "inelig_head": "NÁKLADY, KTERÉ GA UK NEHRADÍ",
        "timetable_head": "PRAVIDLO PRO HARMONOGRAM",
        "notdefects_head": "CO TATO KONTROLA ZA VADU NEPOVAŽUJE",
        "notdefects_intro": (
            "Nic z následujícího neuvádějte jako formální vadu ani porušení "
            "pravidel: zveřejněné dokumenty to vše připouštějí. Pokud se něco "
            "z toho týká obsahu, například rozpočet příliš malý na plánovanou "
            "práci, uveďte to jako věcnou připomínku."
        ),
        "team_head": "ŘEŠITELSKÝ KOLEKTIV",
        "reminders_head": "PŘIPOMÍNKY PŘED PODÁNÍM",
        "report_rules_head": "CO ŽÁDAJÍ ZVEŘEJNĚNÁ PRAVIDLA",
        "report_cont_what": (
            "Kontrolujete ŽÁDOST O POKRAČOVÁNÍ spolu s VÝROČNÍ ZPRÁVOU za "
            "končící rok. Podávají se jako jeden celek: peníze na další rok a "
            "zpráva za rok uplynulý, jejíž částmi jsou zpráva o řešení, "
            "výhled, přehled vyčerpaných financí, komentář k nim a seznam "
            "dosažených výsledků."),
        "report_final_what": (
            "Kontrolujete ZÁVĚREČNOU ZPRÁVU, kterou projekt podává na konci "
            "řešení. Podává ji i projekt, který skončil předčasně, a projekt "
            "s odloženým hodnocením podává po roce doplněnou závěrečnou "
            "zprávu."),
        "report_deadline": "Termín",
        "language_head": "JAZYK PŘIHLÁŠKY",
        "up_to": "nejvýše {n}",
        "if_applicable": "jen pokud se vás týká",
        "annot_langs": ("česky; jen v české verzi formuláře", "anglicky"),
        "not_uploaded": "nevkládá se do aplikace",
        "window": "za posledních {n} let",
        "recommended_ids": "doporučené identifikátory",
        "per_person_wages": "z toho mzdové prostředky a ostatní osobní náklady",
        "notchecked_head": "PRAVIDLA, KTERÁ TATO KONTROLA NEVIDÍ",
        "source": "Zdroj",
        "chars": "znaků",
        "pages": "stran",
        "pivotal": "GA UK označuje tuto kapitolu za stěžejní.",
        "counting": (
            "Počty znaků jsou včetně mezer. Sami je nepočítáte; viz blok "
            "formální kontroly."
        ),
        "max_per_year": "nejvýše na rok, včetně doplňkových nákladů",
        "duration": "doba řešení",
        "years": "roky",
        "overhead": ("doplňkové náklady: nejvýše {pct} % přímých nákladů; aplikace "
                     "je dopočítá a zaokrouhlí"),
        "wages": "mzdové prostředky a ostatní osobní náklady na projekt",
        "of_that_supervisor": "z toho pro školitele",
        "stipends": "stipendia na projekt",
        "of_that_pi": "z toho pro hlavního řešitele",
        "per_person": "jedné osobě za kalendářní rok celkem",
        "stipend_share": "stipendia musí činit více než {pct} % osobních nákladů",
        "max_pages": "nejvýše {n} {pages}",
        "typeset": "formát {size}, velikost písma {pt}, řádkování {sp}",
        "conditional": "podmíněně",
        "per_file": "nejvýše {mb} MB na soubor",
        "required_contents": "musí obsahovat",
        "recommended": "doporučený obsah",
    },
}


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------

def load_rules() -> tuple[dict, dict, dict]:
    index = yaml.safe_load((RULES / "INDEX.yml").read_text(encoding="utf-8"))
    criteria = yaml.safe_load((RULES / "criteria.yml").read_text(encoding="utf-8"))
    rnd = yaml.safe_load(
        (RULES / index["current_rules_file"]).read_text(encoding="utf-8")
    )
    return index, criteria, rnd


def validate(criteria: dict, rnd: dict) -> list[str]:
    """Both languages must exist wherever a node carries text, and every source
    a block cites must be defined.

    A criterion that exists in only one language is the failure this catches:
    it would silently ship an English prompt with a rule the Czech one lacks.
    """
    problems: list[str] = []

    def want_both(node: dict, path: str, keys=("cs", "en")) -> None:
        for k in keys:
            if k not in node and f"{k}_unofficial" not in node and f"{k}_title" not in node:
                problems.append(f"{path}: missing '{k}'")

    for c in criteria["evaluation"]["criteria"]:
        want_both(c, f"criteria.evaluation.{c['id']}")
    for it in criteria["opponent_checklist"]["items"]:
        want_both(it, f"criteria.opponent_checklist.{it['id']}")
    for s in criteria["proposal_sections"]["sections"]:
        want_both(s, f"criteria.proposal_sections.{s['id']}")
        for k in ("cs_title", "en_title", "match"):
            if k not in s:
                problems.append(f"criteria.proposal_sections.{s['id']}: missing '{k}'")

    ids = {s["id"] for s in criteria["sources"]}
    for block in ("evaluation", "dean_statement", "opponent_checklist",
                  "proposal_sections", "process"):
        if criteria[block]["source"] not in ids:
            problems.append(f"criteria.{block}: unknown source "
                            f"'{criteria[block]['source']}'")
    for sid in rnd.get("sources", []):
        if sid not in ids:
            problems.append(f"round: unknown source '{sid}'")

    for it in rnd.get("not_defects", {}).get("items", []):
        want_both(it, f"round.not_defects.{it.get('id')}")
        if it.get("basis") not in ids:
            problems.append(f"round.not_defects.{it.get('id')}: basis "
                            f"'{it.get('basis')}' is not a defined source")
    want_both(rnd.get("timetable", {}), "round.timetable")
    for key in ("note", "caveat"):
        want_both(rnd["team"][key], f"round.team.{key}")
    want_both(rnd["language"]["note"], "round.language.note")
    for it in rnd.get("reminders", {}).get("items", []):
        want_both(it, f"round.reminders.{it.get('id')}")
        for sid in re.findall(r"[A-Z][A-Z0-9]*_[A-Z0-9_]+", it.get("basis", "")):
            if sid not in ids:
                problems.append(f"round.reminders.{it.get('id')}: basis "
                                f"'{sid}' is not a defined source")
    for part in ("continuation", "final"):
        blk = rnd.get("running_projects", {}).get(part, {})
        want_both(blk.get("deadline_note", {}), f"round.running.{part}.deadline")
        for it in blk.get("items", []):
            want_both(it, f"round.running.{part}.{it.get('id')}")
            for sid in re.findall(r"[A-Z][A-Z0-9]*_[A-Z0-9_]+", it.get("basis", "")):
                if sid not in ids:
                    problems.append(f"round.running.{part}.{it.get('id')}: basis "
                                    f"'{sid}' is not a defined source")
    for f in rnd["form_fields"]["fields"]:
        want_both(f, f"round.form_fields.{f['id']}")

    if not rnd["form_fields"]["counting"]["calibrated"]:
        problems.append(
            "NOTE character counting is not calibrated against the GA UK "
            "application; rule R05 stays disabled"
        )
    return problems


def _lf(data: bytes) -> bytes:
    """Git on Windows may check text files out with CRLF endings and on Linux
    with LF. Hashes and comparisons use LF, so that both give the same answer."""
    return data.replace(b"\r\n", b"\n")


def sha(path: Path) -> str:
    return hashlib.sha256(_lf(path.read_bytes())).hexdigest()


# --------------------------------------------------------------------------
# renderers, one per {{include:...}} slot
# --------------------------------------------------------------------------

def _t(node: dict, lang: str) -> str:
    for key in (lang, f"{lang}_unofficial", f"{lang}_title", f"{lang}_note"):
        if isinstance(node.get(key), str):
            return node[key].strip()
    return ""


def _bullets(items: list[str], indent: str = "  ", width: int = 66) -> list[str]:
    out = []
    for text in items:
        wrapped = _wrap(text, width)
        out.append(f"{indent}- {wrapped[0]}")
        out += [f"{indent}  {w}" for w in wrapped[1:]]
    return out


def r_stamp(index, criteria, rnd, lang) -> str:
    notice = index["precedence_notice"][lang]
    if lang == "en":
        lines = [
            f"RULES VERSION: GA UK round {rnd['round']}, transcribed "
            f"{rnd['verified_on']} from the published round-{rnd['round']} documents.",
            "UNOFFICIAL: this review is not issued, reviewed or endorsed by GA UK "
            "or Charles University.",
            notice,
            f"These rules stop being usable on {index['sunset_on']}; after that "
            f"date, check the current published documents before relying on "
            f"anything below.",
        ]
    else:
        lines = [
            f"VERZE PRAVIDEL: GA UK, {rnd['round']}. kolo, přepsáno "
            f"{rnd['verified_on']} ze zveřejněných dokumentů {rnd['round']}. kola.",
            "NEOFICIÁLNÍ: tuto kontrolu nevydala, neprověřila ani neschválila "
            "GA UK ani Univerzita Karlova.",
            notice,
            f"Tato pravidla přestávají platit {index['sunset_on']}; po tomto datu "
            f"ověřte aktuální zveřejněné dokumenty, než se na cokoli níže spolehnete.",
        ]
    return "\n".join(lines)


def r_evaluation(index, criteria, rnd, lang) -> str:
    ev = criteria["evaluation"]
    src = next(s for s in criteria["sources"] if s["id"] == ev["source"])
    out = [L[lang]["criteria_head"], ""]
    out.append(_t(ev["preamble"], lang))
    out.append("")
    for c in ev["criteria"]:
        out.append(f"  ({c['id']})  {_t(c, lang)}")
    out.append("")
    out.append(f"{L[lang]['source']}: {_t(src, lang)}, {ev['locator']}")
    return "\n".join(out)


def r_checklist(index, criteria, rnd, lang) -> str:
    cl = criteria["opponent_checklist"]
    src = next(s for s in criteria["sources"] if s["id"] == cl["source"])
    out = [L[lang]["checklist_head"], ""]
    for it in cl["items"]:
        maps = f"  [{it['maps_to']}]" if it.get("maps_to") else ""
        out.append(f"  - {_t(it, lang)}{maps}")
    out.append("")
    out.append(f"{L[lang]['source']}: {_t(src, lang)}, {cl['locator']}")
    return "\n".join(out)


def r_sections(index, criteria, rnd, lang) -> str:
    ps = criteria["proposal_sections"]
    src = next(s for s in criteria["sources"] if s["id"] == ps["source"])
    out = [L[lang]["sections_head"], "", _t(ps["intro"], lang), ""]
    for s in ps["sections"]:
        out.append(f"  {s['n']}. {s[f'{lang}_title']}")
        for line in _wrap(_t(s, lang), 68):
            out.append(f"       {line}")
        if s.get("pivotal"):
            out.append(f"       >>> {L[lang]['pivotal']}")
        out.append("")
    out.append(f"{L[lang]['source']}: {_t(src, lang)}")
    return "\n".join(out)


def r_form_fields(index, criteria, rnd, lang) -> str:
    ff = rnd["form_fields"]
    out = [L[lang]["fields_head"], "", L[lang]["counting"], ""]
    for f in ff["fields"]:
        name = f[lang] if lang in f else f["en"]
        line = f"  {name}: {_range(f, lang)} {L[lang]['chars']}"
        if f.get("conditional"):
            line += f"  ({_t(f['conditional'], lang)})"
        out.append(line)
        if f.get("note"):
            for w in _wrap(_t(f["note"], lang), 66):
                out.append(f"      {w}")
    return "\n".join(out)


def r_attachments(index, criteria, rnd, lang) -> str:
    at = rnd["attachments"]
    lab = L[lang]
    out = [lab["attach_head"], ""]
    for a in at["items"]:
        req = {"conditional": f"  ({lab['conditional']})",
               False: f"  ({lab['not_uploaded']})"}.get(a["required"], "")
        line = f"  {a[f'{lang}_name']}{req}"
        if a.get("types"):
            line += f" [{', '.join(a['types'])}]"
        if a.get("max_pages"):
            line += ", " + lab["max_pages"].format(
                n=a["max_pages"], pages=_pages(a["max_pages"], lang))
        if a.get("font_size_pt"):
            line += ", " + lab["typeset"].format(
                size=a.get("page_size", "A4"), pt=a["font_size_pt"], sp=a["line_spacing"])
        if a.get("window_years"):
            line += ", " + lab["window"].format(n=a["window_years"])
        out.append(line)
        if a.get("recommended"):
            out.append(f"      {lab['recommended_ids']}: {', '.join(a['recommended'])}")
        for key in ("condition", "note"):
            if a.get(key):
                for w in _wrap(_t(a[key], lang), 66):
                    out.append(f"      {w}")
        for key, label in (("must_contain", lab["required_contents"]),
                           ("should_contain", lab["recommended"])):
            items = a.get(key, {}).get(lang, [])
            if items:
                out.append(f"      {label}:")
                out += _bullets(items, indent="        ", width=62)
    out += ["", "  " + lab["per_file"].format(mb=at["max_file_size_mb"]), ""]
    out += _wrap(_t(at["note"], lang), 70)
    return "\n".join(out)


def r_budget(index, criteria, rnd, lang) -> str:
    b = rnd["budget"]
    c = b["caps"]
    cur = b["currency"]
    lab = L[lang]
    out = [lab["budget_head"], ""]
    out.append(f"  {lab['max_per_year']}: {_n(b['max_per_year'])} {cur}")
    yrs = "/".join(str(d) for d in b["duration_years"])
    out.append(f"  {lab['duration']}: {yrs} {lab['years']}")
    for w in _wrap(_t(b["duration_note"], lang), 66):
        out.append(f"      {w}")
    out.append("  " + lab["overhead"].format(pct=b["overhead_pct"]))
    out.append("")
    out.append(f"  {lab['wages']}: {_n(c['wages_and_opc_per_project'])}")
    out.append(f"    {lab['of_that_supervisor']}: {_n(c['wages_and_opc_per_supervisor'])}")
    out.append(f"  {lab['stipends']}: {_n(c['stipends_per_project'])}")
    out.append(f"    {lab['of_that_pi']}: {_n(c['stipends_per_pi'])}")
    out.append(f"  {lab['per_person']}: {_n(c['per_person_combined'])}")
    out.append(f"    {lab['per_person_wages']}: {_n(c['per_person_wages_and_opc'])}")
    out.append("")
    out.append("  " + lab["stipend_share"].format(
        pct=b["stipend_share_of_personnel_min_pct"]))
    for w in _wrap(_t(b["stipend_share_note"], lang), 66):
        out.append(f"      {w}")
    out.append("")
    for w in _wrap(_t(b["table_must_match_text_note"], lang), 66):
        out.append(f"  {w}")
    if b.get("notes"):
        out.append("")
        out += _bullets([_t(n, lang) for n in b["notes"]])
    return "\n".join(out)


def r_ineligible(index, criteria, rnd, lang) -> str:
    ic = rnd["ineligible_costs"]
    out = [L[lang]["inelig_head"], ""]
    out += _wrap(_t(ic["note"], lang), 70)
    out.append("")
    out += _bullets([_t(it, lang) for it in ic["items"]])
    return "\n".join(out)


def r_timetable(index, criteria, rnd, lang) -> str:
    t = rnd["timetable"]
    out = [L[lang]["timetable_head"], ""]
    out += ["  " + w for w in _wrap(_t(t, lang), 68)]
    out.append("")
    out += ["  " + w for w in _wrap(_t(t["example"], lang), 68)]
    return "\n".join(out)


def r_not_defects(index, criteria, rnd, lang) -> str:
    lab = L[lang]
    out = [lab["notdefects_head"], ""]
    out += _wrap(lab["notdefects_intro"], 70)
    out.append("")
    out += _bullets([_t(it, lang) for it in rnd["not_defects"]["items"]])
    return "\n".join(out)


def r_team(index, criteria, rnd, lang) -> str:
    t = rnd["team"]
    out = [L[lang]["team_head"], ""]
    out += ["  " + w for w in _wrap(_t(t["note"], lang), 68)]
    out.append("")
    out += ["  " + w for w in _wrap(_t(t["caveat"], lang), 68)]
    return "\n".join(out)


def r_reminders(index, criteria, rnd, lang) -> str:
    out = [L[lang]["reminders_head"], ""]
    out += _bullets([_t(it, lang) for it in rnd["reminders"]["items"]])
    return "\n".join(out)


def r_report_what(index, criteria, rnd, lang, part) -> str:
    blk = rnd["running_projects"][part]
    key = "report_cont_what" if part == "continuation" else "report_final_what"
    out = _wrap(L[lang][key], 74)
    out += [""] + _wrap(L[lang]["report_deadline"] + ": "
                        + _t(blk["deadline_note"], lang), 74)
    return "\n".join(out)


def r_report_rules(index, criteria, rnd, lang, part) -> str:
    out = [L[lang]["report_rules_head"], ""]
    out += _bullets([_t(it, lang) for it in
                     rnd["running_projects"][part]["items"]])
    return "\n".join(out)


def r_language(index, criteria, rnd, lang) -> str:
    out = [L[lang]["language_head"], ""]
    out += ["  " + w for w in _wrap(_t(rnd["language"]["note"], lang), 68)]
    return "\n".join(out)


def r_not_checked(index, criteria, rnd, lang) -> str:
    el = rnd["eligibility"]
    out = [L[lang]["notchecked_head"], ""]
    out += _bullets([_t(r, lang) for r in el["rules"]])
    extra = {
        "en": [
            "whether an ethics committee statement is needed (now also for "
            "human biological material and sensitive personal data); if unsure, "
            "ask your faculty",
            "whether everyone named in the team characteristics appears in the "
            "team table",
            "whether every project of the applicant and the leader appears "
            "under 'other projects'",
            "whether the leader has recommended the application in the system",
            "the faculty's own, earlier deadline and any faculty-specific rules",
        ],
        "cs": [
            "zda je potřeba vyjádření etické komise (nově i u lidského "
            "biologického materiálu a citlivých osobních údajů); máte-li "
            "pochybnosti, obraťte se na fakultu",
            "zda jsou všichni, kdo jsou jmenováni v charakteristice kolektivu, "
            "uvedeni v tabulce řešitelského kolektivu",
            "zda jsou v dalších projektech uvedeny všechny projekty navrhovatele "
            "a vedoucího",
            "zda vedoucí projekt v aplikaci doporučil",
            "vlastní, dřívější termín fakulty a případná fakultní pravidla",
        ],
    }
    out += _bullets(extra[lang])
    return "\n".join(out)


def r_self_report(index, criteria, rnd, lang) -> str:
    """The block an applicant fills in by hand when they have no checker output.

    It exists because a chat model cannot count and must not pretend to. The
    applicant reads the numbers off the application's own character counters
    and the file properties of their attachments, which takes about two minutes
    and is the only way those numbers are reliable.
    """
    head = {
        "en": (
            "FORMAL FINDINGS (self-reported)\n"
            "Fill this in from the application's own character counters and\n"
            "from the properties of your files. Leave a line as ? if you do not\n"
            "know; the review will report it as NOT MEASURED, which is better\n"
            "than a guess."
        ),
        "cs": (
            "FORMÁLNÍ KONTROLA (vlastní hlášení)\n"
            "Vyplňte podle počitadel znaků v přihlášce a podle vlastností\n"
            "vašich souborů. Řádek, který neznáte, nechte jako ?; kontrola jej\n"
            "uvede jako NEZMĚŘENO, což je lepší než odhad."
        ),
    }[lang]
    out = [head, ""]
    lab = L[lang]
    for f in rnd["form_fields"]["fields"]:
        name = f[lang] if lang in f else f["en"]
        cond = f", {lab['if_applicable']}" if f.get("conditional") else ""
        names = ([f"{name} ({t})" for t in lab["annot_langs"]]
                 if f.get("bilingual_in_cs_version") else [name])
        for n in names:
            out.append(f"{n}: ? {lab['chars']}   (limit {_range(f, lang)}{cond})")
    out.append("")
    for a in rnd["attachments"]["items"]:
        if a["required"] is False or not a.get("max_pages"):
            continue
        out.append(f"{a[f'{lang}_name']}: ? {L[lang]['pages']}   (max {a['max_pages']})")
    prop = next(a for a in rnd["attachments"]["items"] if a["id"] == "proposal")
    sup = next(a for a in rnd["attachments"]["items"] if a["id"] == "cv_supervisor")
    mb = rnd["attachments"]["max_file_size_mb"]
    extra = {
        "en": [
            f"Project proposal font size: ? pt   (rule: {prop['font_size_pt']})",
            f"Project proposal line spacing: ?   (rule: {prop['line_spacing']})",
            f"Publications listed in the leader's CV: ?   (max {sup['publications_max']})",
            f"Largest attachment: ? MB   (max {mb})",
            "Attachments present: ?",
            "Version of the form (Czech or English): ?",
            "Language of the project proposal: ?",
            "Project duration as entered: ? years",
            "AI used in preparing the application (yes or no): ?",
        ],
        "cs": [
            f"Velikost písma návrhu projektu: ?   (pravidlo: {prop['font_size_pt']})",
            f"Řádkování návrhu projektu: ?   (pravidlo: {prop['line_spacing']})",
            f"Počet publikací v životopise vedoucího: ?   (nejvýše {sup['publications_max']})",
            f"Největší příloha: ? MB   (nejvýše {mb})",
            "Vložené přílohy: ?",
            "Verze formuláře (česká, nebo anglická): ?",
            "Jazyk návrhu projektu: ?",
            "Doba řešení uvedená v přihlášce: ? roky",
            "Použití AI při přípravě přihlášky (ano, nebo ne): ?",
        ],
    }[lang]
    out += ["", *extra]
    return "\n".join(out)


RENDERERS = {
    "stamp": r_stamp,
    "criteria.evaluation": r_evaluation,
    "criteria.opponent_checklist": r_checklist,
    "criteria.proposal_sections": r_sections,
    "round24.form_fields": r_form_fields,
    "round24.attachments": r_attachments,
    "round24.budget": r_budget,
    "round24.ineligible_costs": r_ineligible,
    "round24.timetable": r_timetable,
    "round24.not_defects": r_not_defects,
    "round24.team": r_team,
    "round24.language": r_language,
    "round24.eligibility_not_checked": r_not_checked,
    "round24.reminders": r_reminders,
}

RUBRIC_BLOCKS = (
    r_stamp, r_evaluation, r_checklist, r_sections, r_form_fields,
    r_attachments, r_budget, r_ineligible, r_timetable, r_team, r_language,
    r_not_defects, r_not_checked,
)


def _range(f: dict, lang: str) -> str:
    if f.get("min") is None:
        return L[lang]["up_to"].format(n=f["max"])
    return f"{f['min']}-{f['max']}"


def _pages(n: int, lang: str) -> str:
    """Czech needs the right case after a numeral: 1 strana, 2 strany, 5 stran."""
    if lang != "cs":
        return "page" if n == 1 else "pages"
    if n == 1:
        return "strana"
    return "strany" if 2 <= n <= 4 else "stran"


def _n(value: int) -> str:
    """Czech and English both group thousands with a space, not a comma."""
    return f"{value:,}".replace(",", " ")


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines or [""]


# --------------------------------------------------------------------------
# splicing
# --------------------------------------------------------------------------

def splice(body: str, index, criteria, rnd, lang: str) -> str:
    out = body
    for slot, fn in RENDERERS.items():
        token = "{{include:" + slot + "}}"
        if token in out:
            out = out.replace(token, fn(index, criteria, rnd, lang))
    if "{{include:" in out:
        bad = out.split("{{include:")[1].split("}}")[0]
        raise SystemExit(f"unknown include slot: {{{{include:{bad}}}}}")
    return out


def extract_prompt(body: str) -> str:
    """The prompt, between its two marker lines.

    A marker counts only as a line of its own. The prompt tells the chatbot
    that it ends with the end marker, so that a paste which arrived cut short
    is recognised rather than reviewed; a build that accepted a marker
    mentioned mid-sentence, or synthesised a missing one, would ship a short
    prompt that still looked well formed.
    """
    lines = body.split("\n")
    begins = [i for i, ln in enumerate(lines) if ln.strip() == "=== PROMPT BEGIN ==="]
    ends = [i for i, ln in enumerate(lines) if ln.strip() == "=== PROMPT END ==="]
    for name, found in (("BEGIN", begins), ("END", ends)):
        if len(found) != 1:
            raise SystemExit(f"source file has {len(found)} === PROMPT {name} === "
                             "marker lines, expected exactly one")
    if begins[0] > ends[0]:
        raise SystemExit("=== PROMPT END === comes before === PROMPT BEGIN ===")
    inner = "\n".join(lines[begins[0] + 1:ends[0]])
    return "=== PROMPT BEGIN ===\n" + inner.strip("\n") + "\n\n=== PROMPT END ==="


def header(lang: str, hashes: dict[str, str]) -> str:
    src = " ".join(f"{k}:{v[:12]}" for k, v in sorted(hashes.items()))
    if lang == "en":
        return (
            "<!-- GENERATED by tools/build.py. DO NOT EDIT THIS FILE.\n"
            "     Edit rules/round24.yml, rules/criteria.yml or "
            "src/prompt_body_en.md and rebuild.\n"
            f"     sources {src} -->\n\n"
        )
    return (
        "<!-- VYGENEROVÁNO tools/build.py. TENTO SOUBOR NEUPRAVUJTE.\n"
        "     Upravte rules/round24.yml, rules/criteria.yml nebo "
        "src/prompt_body_cs.md a spusťte build znovu.\n"
        f"     zdroje {src} -->\n\n"
    )


PROMPT_INTRO = {
    "en": (
        "# GA UK pre-submission review: the prompt\n\n"
        "Unofficial. On GitHub, click the copy icon in the top right corner of "
        "the grey box below; it copies everything from `=== PROMPT BEGIN ===` "
        "to `=== PROMPT END ===`. Paste it into a new chat, then paste your "
        "draft after it. The [README](../README.md) explains how to use it and "
        "what it will not do.\n\n"
    ),
    "cs": (
        "# Kontrola přihlášky GA UK před podáním: zadání pro chatbota\n\n"
        "Neoficiální. Na GitHubu klikněte na ikonu kopírování vpravo nahoře v "
        "šedém rámečku níže; zkopíruje vše od `=== PROMPT BEGIN ===` po "
        "`=== PROMPT END ===`. Vložte to do nového chatu a za to vložte svůj "
        "návrh. Jak kontrolu používat a co nedělá, popisuje "
        "[README.cs.md](../README.cs.md).\n\n"
    ),
}


REPORT_INTRO = {
    "en": (
        "Unofficial. Copy everything from `=== PROMPT BEGIN ===` to "
        "`=== PROMPT END ===`, paste it into a new chat, then paste your "
        "report after it. This prompt reviews a report on a funded project; a "
        "new application has its own.\n\n"),
    "cs": (
        "Neoficiální. Zkopírujte vše od `=== PROMPT BEGIN ===` po "
        "`=== PROMPT END ===`, vložte do nového chatu a za to vložte svou "
        "zprávu. Toto zadání kontroluje zprávu o financovaném projektu; "
        "přihláška nového projektu má vlastní.\n\n"),
}


def build(target: Path) -> dict:
    index, criteria, rnd = load_rules()
    problems = validate(criteria, rnd)
    hard = [p for p in problems if not p.startswith("NOTE")]
    for p in problems:
        print(("  " if p.startswith("NOTE") else "  ERROR ") + p, file=sys.stderr)
    if hard:
        raise SystemExit("build refused: fix the errors above")

    target.mkdir(parents=True, exist_ok=True)
    hashes = {
        "INDEX": sha(RULES / "INDEX.yml"),
        "criteria": sha(RULES / "criteria.yml"),
        "round": sha(RULES / index["current_rules_file"]),
        "body_en": sha(SRC / "prompt_body_en.md"),
        "body_cs": sha(SRC / "prompt_body_cs.md"),
        "report_en": sha(SRC / "prompt_report_en.md"),
        "report_cs": sha(SRC / "prompt_report_cs.md"),
        "build": sha(Path(__file__)),
    }

    written = []
    for lang in LANGS:
        srcfile = SRC / f"prompt_body_{lang}.md"
        prompt = extract_prompt(srcfile.read_text(encoding="utf-8"))
        spliced = splice(prompt, index, criteria, rnd, lang)
        out = target / f"prompt_{lang}.md"
        out.write_text(header(lang, hashes) + PROMPT_INTRO[lang]
                       + "```text\n" + spliced + "\n```\n", encoding="utf-8", newline="\n")
        written.append(out.name)

        rub = target / f"rubric_locked_{lang}.md"
        blocks = [fn(index, criteria, rnd, lang) for fn in RUBRIC_BLOCKS]
        rub.write_text(
            header(lang, hashes) + "\n\n".join(f"```text\n{b}\n```" for b in blocks) + "\n",
            encoding="utf-8", newline="\n",
        )
        written.append(rub.name)

        body = extract_prompt((SRC / f"prompt_report_{lang}.md")
                              .read_text(encoding="utf-8"))
        for part, short in (("continuation", "cont"), ("final", "final")):
            text = body
            for slot, fn in (("report.what", r_report_what),
                             ("report.rules", r_report_rules)):
                text = text.replace("{{include:" + slot + "}}",
                                    fn(index, criteria, rnd, lang, part))
            text = splice(text, index, criteria, rnd, lang)
            rep = target / f"report_{short}_{lang}.md"
            rep.write_text(header(lang, hashes) + REPORT_INTRO[lang]
                           + "```text\n" + text + "\n```\n",
                           encoding="utf-8", newline="\n")
            written.append(rep.name)

        sr = target / f"self_report_{lang}.md"
        sr.write_text(
            header(lang, hashes)
            + "```text\n" + r_self_report(index, criteria, rnd, lang) + "\n```\n",
            encoding="utf-8", newline="\n",
        )
        written.append(sr.name)

    manifest = {
        "round": rnd["round"],
        "rules_verified_on": str(rnd["verified_on"]),
        "official_review": rnd.get("official_review"),
        "warn_after": str(index["warn_after"]),
        "sunset_on": str(index["sunset_on"]),
        "source_sha256": hashes,
        "files": sorted(written),
        "notes": [p for p in problems if p.startswith("NOTE")],
    }
    (target / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    return manifest


# --------------------------------------------------------------------------
# the web page
# --------------------------------------------------------------------------

def prompt_text(index, criteria, rnd, lang: str) -> str:
    """The prompt from === PROMPT BEGIN === to === PROMPT END ===, exactly as
    in dist/prompt_<lang>.md."""
    body = extract_prompt((SRC / f"prompt_body_{lang}.md").read_text(encoding="utf-8"))
    return splice(body, index, criteria, rnd, lang)


def report_text(index, criteria, rnd, lang: str, part: str) -> str:
    """The report prompt for one mode, exactly as in dist/."""
    text = extract_prompt((SRC / f"prompt_report_{lang}.md")
                          .read_text(encoding="utf-8"))
    for slot, fn in (("report.what", r_report_what),
                     ("report.rules", r_report_rules)):
        text = text.replace("{{include:" + slot + "}}",
                            fn(index, criteria, rnd, lang, part))
    return splice(text, index, criteria, rnd, lang)


def site_problems(strings: dict) -> list[str]:
    """Every text the page shows must exist in both languages."""
    problems = []
    cs, en = set(strings["cs"]), set(strings["en"])
    problems += [f"'{k}' only in Czech" for k in sorted(cs - en)]
    problems += [f"'{k}' only in English" for k in sorted(en - cs)]
    html = (WEB / "index.html").read_text(encoding="utf-8")
    js = (WEB / "app.js").read_text(encoding="utf-8")
    used = set(re.findall(r'data-t(?:-html)?="([a-z0-9_]+)"', html))
    used |= set(re.findall(r'\bt\("([a-z0-9_]+)"\s*[,)]', js))
    # keys app.js builds at run time
    used |= {f"k_{k}" for k in ("BLOCKING", "ADVISORY", "UNKNOWN")}
    used |= {f"slot_{s}" for s in re.findall(r'\["([a-z_]+)", "[a-z_]+"\]', js)}
    used.add("rule_R10")
    problems += [f"'{k}' used by the page but not defined" for k in sorted(used - cs)]
    return problems


def _fetch_verified(rel: str) -> bytes:
    url, want = VENDOR[rel]
    cached = CACHE / f"pyodide-{PYODIDE_VERSION}" / Path(rel).name
    if cached.exists():
        data = cached.read_bytes()
    else:
        import urllib.request
        with urllib.request.urlopen(url, timeout=120) as r:
            data = r.read()
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
    got = hashlib.sha256(data).hexdigest()
    if got != want:
        raise SystemExit(f"{rel}: SHA-256 {got} does not match the pinned {want}")
    return data


def build_site(target: Path, vendor: bool = False) -> None:
    """Write the web page to `target`. With vendor=True, also the Pyodide
    runtime and the pypdf wheel, each checked against its pinned hash."""
    index, criteria, rnd = load_rules()
    hard = [p for p in validate(criteria, rnd) if not p.startswith("NOTE")]
    strings = json.loads((WEB / "strings.json").read_text(encoding="utf-8"))
    hard += [f"web/strings.json: {p}" for p in site_problems(strings)]
    if hard:
        raise SystemExit("site build refused:\n  " + "\n  ".join(hard))

    if target.exists():
        shutil.rmtree(target)
    (target / "py" / "checker").mkdir(parents=True)
    (target / "py" / "rules").mkdir(parents=True)
    for name in WEB_FILES:
        shutil.copyfile(WEB / name, target / name)
    (target / ".nojekyll").write_text("", encoding="utf-8")
    shutil.copyfile(ROOT / "checker" / "gauk_check.py", target / "py" / "checker" / "gauk_check.py")
    rule_files = ["INDEX.yml", "criteria.yml", index["current_rules_file"]]
    for n in rule_files:
        shutil.copyfile(RULES / n, target / "py" / "rules" / n)

    prompts = {lang: prompt_text(index, criteria, rnd, lang) for lang in LANGS}
    reports = {short: {lang: report_text(index, criteria, rnd, lang, part)
                       for lang in LANGS}
               for part, short in (("continuation", "cont"), ("final", "final"))}
    for lang in LANGS:
        (target / f"prompt_{lang}.txt").write_text(prompts[lang] + "\n",
                                                   encoding="utf-8", newline="\n")
        # the attach-as-a-file route has to work in every mode
        for short in reports:
            (target / f"report_{short}_{lang}.txt").write_text(
                reports[short][lang] + "\n", encoding="utf-8", newline="\n")
    data = {
        "strings": strings,
        "prompt": prompts,
        "promptFile": {lang: f"prompt_{lang}.txt" for lang in LANGS},
        "reportFile": {short: {lang: f"report_{short}_{lang}.txt"
                               for lang in LANGS}
                       for short in ("cont", "final")},
        # One prompt per mode of the switch. The report prompts are far
        # shorter than the application one: they carry no application rules.
        "reportPrompt": reports,
        "selfReport": {lang: r_self_report(index, criteria, rnd, lang) for lang in LANGS},
        "meta": {"round": rnd["round"], "verified": str(rnd["verified_on"]),
                 "sunset": str(index["sunset_on"])},
        "fieldNames": {f["en"]: f["cs"] for f in rnd["form_fields"]["fields"]},
        "attachNames": {a["en_name"]: a["cs_name"] for a in rnd["attachments"]["items"]},
        "reminders": {lang: [_t(it, lang) for it in rnd["reminders"]["items"]]
                      for lang in LANGS},
        "pyodide": {
            "index": "pyodide/",
            # pycryptodome lets pypdf open AES-encrypted PDFs, including ones
            # locked only against editing. pypdf picks its crypto library when
            # it is imported, so it has to be there from the start.
            "packages": ["pyyaml", "pycryptodome"],
            "wheels": sorted(k for k in VENDOR if k.startswith("py/")),
            "files": [{"url": "py/checker/gauk_check.py", "path": "/work/checker/gauk_check.py"}]
                     + [{"url": f"py/rules/{n}", "path": f"/work/rules/{n}"} for n in rule_files],
        },
    }
    (target / "data.js").write_text(
        "window.GAUK = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n",
        encoding="utf-8", newline="\n")

    if vendor:
        for rel in VENDOR:
            out = target / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(_fetch_verified(rel))


def check() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="gauk-build-"))
    try:
        build(tmp)
        stale = []
        for f in sorted(tmp.iterdir()):
            live = DIST / f.name
            if not live.exists() or _lf(live.read_bytes()) != _lf(f.read_bytes()):
                stale.append(f.name)
        stale += [f"{f.name} (not generated by the build)"
                  for f in sorted(DIST.iterdir()) if not (tmp / f.name).exists()]
        if stale:
            print("dist/ is out of date: " + ", ".join(stale), file=sys.stderr)
            print("run: python tools/build.py", file=sys.stderr)
            return 2
        print("dist/ matches rules/ and src/")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def diff_rounds(a: int, b: int) -> int:
    fa, fb = RULES / f"round{a}.yml", RULES / f"round{b}.yml"
    for f in (fa, fb):
        if not f.exists():
            print(f"missing {f}", file=sys.stderr)
            return 1
    da = yaml.safe_load(fa.read_text(encoding="utf-8"))
    db = yaml.safe_load(fb.read_text(encoding="utf-8"))

    def flat(d, p=""):
        for k, v in (d or {}).items():
            key = f"{p}.{k}" if p else str(k)
            if isinstance(v, dict):
                yield from flat(v, key)
            else:
                yield key, v

    ma, mb = dict(flat(da)), dict(flat(db))
    for k in sorted(set(ma) | set(mb)):
        if ma.get(k) != mb.get(k):
            print(f"{k}\n  {a}: {ma.get(k)!r}\n  {b}: {mb.get(k)!r}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--diff", nargs=2, type=int, metavar=("OLD", "NEW"))
    ap.add_argument("--site", type=Path, metavar="DIR",
                    help="write the web page to DIR (not committed; see .github/workflows/pages.yml)")
    ap.add_argument("--vendor", action="store_true",
                    help="with --site: also add the pinned, hash-checked Pyodide runtime and pypdf")
    args = ap.parse_args()

    if args.diff:
        return diff_rounds(*args.diff)
    if args.site:
        build_site(args.site, args.vendor)
        print(f"wrote the web page to {args.site}" + (" with Pyodide" if args.vendor else ""))
        return 0
    if args.check:
        return check()

    m = build(DIST)
    print(f"wrote {len(m['files'])} files to dist/ for round {m['round']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
