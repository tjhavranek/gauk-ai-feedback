# Agentic use (optional, experimental)

Everything in this folder is optional. The chatbot prompt and the local check
described in the main README are enough for most students. This folder is for
those who already use an agentic tool and want it to run the whole review.

## What an agent adds

An agent can read your files directly, run the formal check itself, and check
every quote in the review against your text before you see it. It works under
the same rules and the same instructions as the chatbot prompt, so the review
has the same content.

- [`RUNBOOK.md`](RUNBOOK.md) is the procedure. Claude Code, in the Claude
  desktop app or on the command line, follows it through the project skill in
  `.claude/skills/gauk-feedback/`; Codex, in the ChatGPT desktop app or on the
  command line, and other agents are pointed to it by `AGENTS.md`.
- [`mad-research/`](mad-research/) explains how to run mad-research, an audit
  by Claude and Codex, with a GA UK rubric.
- [`paper-workshop/`](paper-workshop/) explains how to run the first act of
  paper-workshop, a workshop of Claude reviewers, on a proposal.

## Status

Experimental. The runbook has been exercised on the invented applications in
`tests/`, not on real ones. The mad-research and paper-workshop routes have not
been run end to end on a GA UK application at all. Both tools were built for
research papers, and they will read a proposal much as they would read a paper.

Nor is there evidence that heavier is better. In a pre-registered study, the
authors of 44 published economics meta-analyses ranked three AI reports on
their own paper. They preferred a single pass by one model to a multi-agent
debate protocol, by 0.66 rank points (95% CI 0.32 to 1.00). The study concerned
papers, not grant proposals, and it has not yet been peer-reviewed, but it is a
reason to start with the single pass and use the heavier tools as a
cross-check.

Havránek, T. and Z. Iršová (2026). "Does Multi-Agent Debate Improve AI Feedback
on Research Papers?" arXiv:2607.14713, <https://arxiv.org/abs/2607.14713>.

## Privacy

An agent sends your text to the company behind its model, and mad-research in
its default mode sends it to two (Anthropic and OpenAI). Agree this with your
project leader first: the declaration of honour limits who may see the project
text.
