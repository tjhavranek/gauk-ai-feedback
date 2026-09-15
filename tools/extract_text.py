#!/usr/bin/env python3
"""Write the text of an application folder to one file.

Useful for an agentic tool that works better from plain text than from PDFs,
and as the source for tools/verify_quotes.py. Each attachment appears under a
header line with its file name, with a marker at the start of every PDF page so
that a finding can give its page. The web-form fields follow if the folder has
a form file, or if one is given with --form.

    python tools/extract_text.py my_application/ --out application_text.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "checker"))

import gauk_check as gc  # noqa: E402


def extract(folder: Path, form: Path | None = None) -> str:
    parts = []
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() not in gc.ATTACHMENT_SUFFIXES:
            continue
        facts = gc.attachment_facts(f)
        if "error" in facts or "text_error" in facts:
            body = f"[{facts.get('error') or facts['text_error']}]"
        elif facts.get("page_texts"):
            body = "\n".join(f"--- page {i} ---\n{t.strip() or '[no text on this page]'}"
                             for i, t in enumerate(facts["page_texts"], start=1))
        else:
            body = facts.get("text", "").strip()
        parts.append(f"=== {f.name} ===\n{body}\n")
    form = form or gc.form_file(folder)
    if form:
        try:
            fields = gc.read_form(form, None)
        except gc.FormError as exc:
            fields = {}
            parts.append(f"=== {form.name} ===\n[{exc}]\n")
        if fields:
            parts.append(f"=== {form.name} ===")
            parts += [f"--- {k} ---\n{v.strip()}\n" for k, v in fields.items()]
    return "\n".join(parts)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--form", type=Path, default=None,
                    help="a form file kept outside the application folder")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    if not args.folder.is_dir():
        print(f"not a folder: {args.folder}", file=sys.stderr)
        return 1
    text = extract(args.folder, args.form)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out} ({len(text)} characters)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
