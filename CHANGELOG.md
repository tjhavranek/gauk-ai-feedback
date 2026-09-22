# Changelog

## v0.7.0 - 2026-09-22

A switch at the top of the page: a new application, a continuation request
with its annual report, or a final report. This replaces the static list of
v0.6.0, which told students what to look for instead of looking for them.

- On either report setting the page copies a prompt that reviews the report:
  whether the comment on the spending ties each sum to what it bought and
  explains every transfer both ways, whether each result the report mentions
  is attached, what a deferred assessment requires, what a finished project is
  assessed on, and whether any cost is one GA UK does not fund. It says what
  it cannot see, every time, so that silence is not taken for a pass.
- It never says whether the year's work justifies continuing, whether the
  project should count as fulfilled, or what mark it would get. That belongs
  to the rapporteur and the boards, and it refuses if asked.
- The report prompts are about 10,500 characters against the application's
  42,800, because they carry no application rules, and each has its own
  downloadable file for a chat that will not take a long paste.
- The new-application route is untouched: on the default setting the page is
  what it was, and the file check and the agentic route stay with it. Choosing
  a report hides what belongs only to an application rather than dressing it
  up as something it can do.
- Both report prompts are generated from the same source and the same rules,
  with tests that each carries its own mode's rules and that the page copies
  exactly the published prompt.

## v0.6.0 - 2026-09-22

A funded project files two more things, and neither is a new application.

- A section on the page, "Already running a project", with a short list for a
  continuation request with its annual report, and one for a final report:
  what the comment on the spending has to say, what is attached rather than
  described, the affiliation and dedication every output carries, what a
  deferred assessment requires, and what a finished project is assessed on.
  Both lists are generated from `rules/round24.yml` like the reminders, so the
  page cannot drift from them, and every line rests on the published
  "Řeším projekt" page.
- The review and the file check are unchanged and still cover new
  applications only. The prompt goes on refusing a continuation request or a
  report, and now says where the list is. Nothing on the page reads a report.
- The notice shown once the round-24 rules expire says that it is the
  application rules that have run out: final reports are due in April, after
  that date, and the list does not depend on the round's calendar.

## v0.5.7 - 2026-09-22

- A planned patent counts as a finished project's output, which the reminders
  already said and the outputs trigger did not. A patent-only plan is no
  longer short of an output, and the demand for journals or publishers now
  applies only where publications are planned.
- Two published documents disagree about a patent on its own: the criteria for
  assessing a finished project accept a publication accepted for print or a
  patent, while the FAQ says a project counts as fulfilled only if at least
  one publication comes out of it. A plan with a patent and no publication now
  draws a low-severity question pointing at both, and sends the applicant to
  the faculty or the office, rather than the tool picking a side.

## v0.5.6 - 2026-09-21

The prompt is about 42,000 characters and some chats will not take a paste
that long. A prompt cut short still looks well formed, and a review written
from the first few thousand characters has none of the fixed sections and no
worth, so the student had no way to tell.

- The prompt now opens by checking that it arrived whole, and refuses to
  review anything if it did not, telling the student to send it as a file or
  use another chatbot instead. It describes its end marker rather than
  quoting it, because a quoted marker would sit inside every cut-short copy.
  It stays silent when the prompt is whole, treats the application that
  follows as expected rather than as a missing end, and says it cannot
  confirm, rather than asserting a cut, when the prompt came as an
  attachment it cannot fully see. Checked against a model on truncated and
  whole prompts, in Czech and English, and with the prompt and the
  application pasted in one message.
- The chatbot step names what a cut-short paste looks like from the student's
  side: the paste stops short, the chatbot says the text is too long, or the
  review lacks the parts listed in step 5.
- The build refuses a prompt source that does not have exactly one begin
  marker line and one end marker line, in that order, instead of quietly
  supplying one. A quoted marker had already made one build produce a
  585-character prompt that still looked well formed. Tests cover both, and
  the web page's copy of the prompt is now compared with the published one
  for equality rather than containment.

## v0.5.5 - 2026-09-21

- A short anonymous feedback questionnaire, linked at the end of the chatbot
  steps and from the footer. It needs no sign-in and asks nothing that
  identifies the respondent. Two of its questions ask which chatbot was used
  and whether it took the whole prompt at the first try, which is the one
  thing about the Copilot recommendation that was not tested in advance.
- The chatbot step says what a prompt cut short looks like, so that a review
  missing its fixed parts is recognised as a truncated prompt rather than
  read as a review.

## v0.5.4 - 2026-09-21

From the vice-rector for doctoral study, who tried the tool:

- The chatbot step names the university's Copilot first, with the university's
  own reason for it, and the other chatbots after. The prompt is long, so the
  step also says what to do if a chatbot will not take all of it: attach it as
  a file, or use another one.
- The page and both READMEs say to run the check at least a few days before
  the faculty deadline, so that there is time to revise.

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
