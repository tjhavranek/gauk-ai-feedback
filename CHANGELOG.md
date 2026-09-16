# Changelog

## v0.5.0 - 2026-09-16

Points that are easy to get wrong when filling in the application, added so
that the review stays about the project rather than turning into a form audit.

- Six reminders, printed at the end of every review and shown under the result
  of the file check: the timetable by calendar year, what the team field in
  the form says about each member, how the budget justification is set out,
  overhead in the outlook for later years, the other-projects field compared
  with both CVs, and what a finished project is assessed on. Each rests on a
  published document.
- The file check asks when a CV names a funder or programme, such as GA ČR,
  that the other-projects field does not name (advisory). The web page has an
  optional box for that field.
- The prompts now also catch a project year that starts after January or ends
  before December, a risk whose remedy is to extend the project, planned
  results with no original publication or no time for a manuscript to be
  accepted, and a budget justification that is hard to follow (one finding for
  all of it). Missing details in the form's team field are a low-severity
  finding. Findings about how the form and the budget are filled in take at
  most three of the ten places.
- The rules state that the outlook for later years includes overhead and that
  each cost belongs to the year of its activity. The round-22 applicant guide
  is cited for the year of study and the department in the team field, which
  the round-24 guide no longer spells out.

## v0.4.1 - 2026-09-16

Fixes from an overnight stress test: 39 invented and broken applications run
through the command line and the web page (identical results on every case
the page accepts), and invented drafts reviewed through the prompts by three
different models.

- The font-size check no longer misreads text on rotated pages as small type.
- PDFs locked only against editing (they open without a password) are read on
  the web page as well as the command line; `pycryptodome` is now a dependency.
- The quote verifier accepts „…" quotes closed with a straight mark, which
  chatbots often type, instead of reporting correct quotes as not found.
- The prompts: the first reply gives the consent reminder and then the review,
  without waiting for confirmation; the formal-check table holds only values
  from the checker or the student's own numbers; a fix never includes
  replacement or example wording, with an example of the difference; a
  personnel cost without a stated role is MEDIUM, not HIGH.

## v0.4.0 - 2026-09-15

- A web page, published with GitHub Pages at
  <https://tjhavranek.github.io/gauk-ai-feedback/>, in Czech and English. It
  offers the three routes: it copies the chatbot prompt once the student
  confirms the project leader's consent, it runs the formal check on the
  student's attachments inside the browser (the unchanged checker under
  Pyodide, served from the same address, with nothing uploaded), and it points
  to the agentic route. The page is generated from `rules/`, `src/` and `web/`
  on every push and is never committed, so it cannot drift from the prompts.
- The page-size check accepts landscape and rotated A4 pages (found by Codex).
- A link to meta-analysis.cz in the READMEs and on the page.

## v0.3.0 - 2026-09-15

First public release.

- Rules for the 24th round (the call opens on 1 October 2026), transcribed from
  the published applicant guide, the practical tips, the FAQ and Rector's
  Measures 30/2026 and 31/2026. Every rule cites its source in
  `rules/criteria.yml`.
- The chatbot prompt in English and Czech, generated from the rules, with a
  contribution trigger and a Contribution section in the review. Severity is
  tied to what the text shows, never to a guess about reviewers.
- The local formal check (`checker/gauk_check.py`) for one application at a
  time: attachments, page limits, file size, section headings, the first-year
  budget totals, amounts in the table against the justification, costs GA UK
  does not fund, the language of the proposal against the form version, the
  years in the timetable, the length of the leader's publication list, and a
  declared but undescribed use of AI. It reads a `form.yml` and Word drafts,
  lists what it measured, and reports UNKNOWN rather than guessing.
- A list of things the review never reports as a formal defect, each allowed
  by a published document.
- An agentic runbook, a Claude Code project skill, `AGENTS.md` for other agents,
  a quote verifier, and notes on using mad-research and paper-workshop.
- Ten invented applications and a test suite that runs on every push.

## Before v0.3.0

Versions 0.1 and 0.2 were unpublished development versions from August and
September 2026.
