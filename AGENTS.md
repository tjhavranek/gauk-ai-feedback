# Notes for coding agents

This repository is an unofficial pre-submission review for applications to the
Charles University Grant Agency (GA UK).

## If a user asks you to review a GA UK application

Follow [`agentic/RUNBOOK.md`](agentic/RUNBOOK.md) step by step. Never write
proposal text for the user, never estimate the chance of funding, never modify
the user's files, and stop if the user is evaluating someone else's
application.

## If you are changing this repository

- `rules/` is canonical and `dist/` is generated. Edit `rules/` or `src/`, then
  run `python tools/build.py`.
- Every rule cites a published source defined in `rules/criteria.yml`.
- Before committing, run `python tests/make_fixtures.py` and
  `python tests/test_checker.py`. Both must pass.
- Never commit text from a real application. The fixtures are invented.
