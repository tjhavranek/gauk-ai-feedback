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
    for f in rnd["form_fields"]["fields"]:
        want_both(f, f"round.form_fields.{f['id']}")

    if not rnd["form_fields"]["counting"]["calibrated"]:
        problems.append(
            "NOTE character counting is not calibrated against the GA UK "
            "application; rule R05 stays disabled"
        )
    return problems


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    if "=== PROMPT BEGIN ===" not in body:
        raise SystemExit("source file has no === PROMPT BEGIN === marker")
    inner = body.split("=== PROMPT BEGIN ===", 1)[1].split("=== PROMPT END ===", 1)[0]
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
        "Unofficial. Copy everything from `=== PROMPT BEGIN ===` to "
        "`=== PROMPT END ===` into a new chat, then paste your draft after it. "
        "See the README for how to use it and what it will not do.\n\n"
    ),
    "cs": (
        "# Kontrola přihlášky GA UK před podáním: zadání pro chatbota\n\n"
        "Neoficiální. Zkopírujte vše od `=== PROMPT BEGIN ===` po "
        "`=== PROMPT END ===` do nového chatu a za to vložte svůj návrh. "
        "Jak ji používat a co nedělá, popisuje README.\n\n"
    ),
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
        "build": sha(Path(__file__)),
    }

    written = []
    for lang in LANGS:
        srcfile = SRC / f"prompt_body_{lang}.md"
        prompt = extract_prompt(srcfile.read_text(encoding="utf-8"))
        spliced = splice(prompt, index, criteria, rnd, lang)
        out = target / f"prompt_{lang}.md"
        out.write_text(header(lang, hashes) + PROMPT_INTRO[lang]
                       + "```text\n" + spliced + "\n```\n", encoding="utf-8")
        written.append(out.name)

        rub = target / f"rubric_locked_{lang}.md"
        blocks = [fn(index, criteria, rnd, lang) for fn in RUBRIC_BLOCKS]
        rub.write_text(
            header(lang, hashes) + "\n\n".join(f"```text\n{b}\n```" for b in blocks) + "\n",
            encoding="utf-8",
        )
        written.append(rub.name)

        sr = target / f"self_report_{lang}.md"
        sr.write_text(
            header(lang, hashes)
            + "```text\n" + r_self_report(index, criteria, rnd, lang) + "\n```\n",
            encoding="utf-8",
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
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def check() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="gauk-build-"))
    try:
        build(tmp)
        stale = []
        for f in sorted(tmp.iterdir()):
            live = DIST / f.name
            if not live.exists() or live.read_bytes() != f.read_bytes():
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
    args = ap.parse_args()

    if args.diff:
        return diff_rounds(*args.diff)
    if args.check:
        return check()

    m = build(DIST)
    print(f"wrote {len(m['files'])} files to dist/ for round {m['round']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
