# Changelog

## v0.5.4 - 2026-09-21

From the vice-rector for doctoral study, who tried the tool on a real
application:

- The chatbot step names the university's Copilot first, with the university's
  own reason for it, and the other chatbots after. The prompt is long, so the
  step also says what to do if a chatbot will not take all of it: attach it as
  a file, or use another one.
- The page and both READMEs say to run the check at least a few days before
  the faculty deadline, so that there is time to revise.

## v0.5.5 - 2026-09-21

- A short anonymous feedback questionnaire, linked at the end of the chatbot
  steps and from the footer. It needs no sign-in and asks nothing that
  identifies the respondent. Two of its questions ask which chatbot was used
  and whether it took the whole prompt at the first try, which is the one
  thing about the Copilot recommendation that could not be established in
  advance.

## v0.5.3 - 2026-09-20

- The page and the READMEs point to Microsoft Copilot through
  office365.cuni.cz with a university CAS account, which Charles University
  says has commercial data protection, with a button beside the other
  chatbots. Pasting other people's personal data still needs their consent,
  and the consent step says so.

## v0.5.2 - 2026-09-19

From testers' reports on real proposals:

- The prompts say that the annotation is the web-form field: an abstract or
  opening paragraph of the proposal is not assessed in its place, and an
  annotation that was not pasted goes under "Not checked".
- A draft presented as a GA UK application is reviewed as one even if it does
  not follow the structure; the refusal covers material that is, or is said to
  be, for another scheme.
- The file check recognises the headings "Material resources" and
  "Presentation of results" (or "Results and their presentation").
- The page gives the reason for the leader's consent next to the checkbox
  instead of behind a click.

## v0.5.1 - 2026-09-17

- The agentic route points to the desktop apps, where no terminal is needed:
  Claude Code in the Code tab of the Claude desktop app, and Codex in the
  ChatGPT desktop app (the Codex app became part of it in July 2026). The steps
  on the page and in the README now have the student copy the application into
  a folder inside the tool.
- The runbook says what to do when Python is missing: say so, install it only
  with the user's agreement, and otherwise point to the web page.
- The link to meta-analysis.cz reads "More tools, data and code", on the page
  and in the READMEs.

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
