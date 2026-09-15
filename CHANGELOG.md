# Changelog

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
