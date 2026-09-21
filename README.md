# gauk-ai-feedback

*Tomáš Havránek, Charles University · more tools, data and code at
[meta-analysis.cz](https://meta-analysis.cz)*

An unofficial pre-submission review for applications to the Charles University
Grant Agency (GA UK, Grantová agentura Univerzity Karlovy). It reads a draft
the way an opponent will and tells the student what to fix before the faculty
deadline. Formal problems come first: a missing section, a page limit, a
budget over its caps, a timetable that follows the academic year. Then the
substance, above all whether the application says what the project will add
and whether the methods and the time requested can deliver it.

> **Unofficial.** This is not a GA UK or Charles University tool, and neither
> has reviewed or endorsed it. Its rules are transcribed from the published
> documents of the 24th round and may contain mistakes; where those documents
> or your faculty say something different, they are right. It cannot tell you
> whether you will be funded, and it never writes any part of your
> application. Read [DISCLOSURE.md](DISCLOSURE.md) before using it.

Česky: [README.cs.md](README.cs.md).

**The easiest way is the web page:
[tjhavranek.github.io/gauk-ai-feedback](https://tjhavranek.github.io/gauk-ai-feedback/)**,
in Czech and English, with nothing to install. It copies the prompt for you and
can check your attachments in your own browser without uploading them.

## Quick start

1. Ask your project leader whether you may paste the draft into a chatbot
   (see [Before you paste anything](#before-you-paste-anything)).
2. Open the prompt in [English](dist/prompt_en.md) or [Czech](dist/prompt_cs.md)
   and click the copy icon in the top right corner of the grey box.
3. Paste it into a new chat, then paste your draft after it. Start with
   Microsoft Copilot via [office365.cuni.cz](https://office365.cuni.cz/),
   signed in with your university CAS account: Charles University says that
   version has commercial data protection. ChatGPT, Claude and Gemini take the
   same prompt. If a chatbot will not take all of it, attach the prompt as a
   file instead. Pasting other people's personal data, such as the leader's
   CV, still needs their explicit consent.

Do this at least a few days before your faculty's deadline, so there is time
to revise. That is all most students need; the rest of this page explains the
review, the local formal check and the agentic route.

## Three ways to use it

You need nothing but a chatbot for the first. The second is for students who
are comfortable with a command line; the third also works in the Claude and
ChatGPT desktop apps, without one.

1. With any chatbot: paste one prompt, then your draft. This is the main route
   and the one to start with.
2. The local formal check: a Python script that runs on your computer, sends
   nothing anywhere, and reports what can be counted: pages, the first-year
   budget totals, sections, the years in the timetable, the length of the
   leader's publication list.
3. With an agentic tool, optional and experimental: Claude Code, Codex or a
   similar agent runs the check, reads your files, writes the review and then
   verifies every quote in it against your text.

## Before you paste anything

A chatbot sends whatever you paste to the company that runs it. The
declaration of honour says the project text may not be given to anyone outside
the team without the project leader's consent, so ask your leader, usually your
supervisor, first. Leave out what should not travel: unpublished data, and the
leader's CV unless they agree. Check whether your faculty has rules on AI
tools; the university's guidance is at <https://ai.cuni.cz/AI-81.html>. An
account with training switched off lowers the risk, but it does not make
sharing permitted. The local check sends nothing anywhere.

## 1. With a chatbot

1. Open [`dist/prompt_en.md`](dist/prompt_en.md) (English) or
   [`dist/prompt_cs.md`](dist/prompt_cs.md) (Czech) and copy everything from
   `=== PROMPT BEGIN ===` to `=== PROMPT END ===`.
2. Start a new chat and paste the prompt. After it, paste your draft: the
   web-form fields and the text of the project proposal, and the CVs if you
   want them read too. Say which section you apply in (A, B or C), for how many
   years, and which version of the form you use. If the draft is long, send it
   in several messages and say when it is complete.
3. If you can, also paste the self-report block,
   [`dist/self_report_en.md`](dist/self_report_en.md) or
   [`dist/self_report_cs.md`](dist/self_report_cs.md), filled in with the
   numbers from the application's own character counters and your files. A
   chatbot cannot count characters or pages reliably, so the prompt forbids it
   to guess; without the block, those lines come back as NOT MEASURED.
4. Read the review. It always has the same parts: a short summary, the formal
   check, a list of what it could not check, a paragraph on the contribution,
   at most ten findings with a verbatim quote and a concrete fix each, and a
   paragraph you can forward to your supervisor.

Revise and run it again once or twice. Further runs on the same draft tend to
repeat themselves, and by then your supervisor is the better reader.

## 2. The local formal check

Install Python 3.10 or newer. On macOS the command is `python3`; on Windows,
`py` works if `python` is not found. Then, in this folder:

    python -m pip install -r requirements.txt

Put your application into a folder of its own. The file names only need to
contain a recognisable word: `navrh` or `proposal` for the project proposal,
`cv_resitel` or `cv_pi` and `cv_vedouci` or `cv_supervisor` for the CVs,
`literatura` or `references` for the list of references. Each name should fit
one attachment only; the script does not guess between two candidates. A Word
draft of the proposal is read as well. Copy [`templates/form.yml`](templates/form.yml) into
the folder and fill in the web-form fields you have. Then run:

    python checker/gauk_check.py one my_application/

The result is `check.md` in the folder. Paste it after the prompt in step 1,
and the chatbot will take its numbers as given.

Every finding is marked BLOCKING, ADVISORY or UNKNOWN. BLOCKING is a clear
breach of a written rule, such as six pages where five are allowed. ADVISORY is
measured but open to a reasonable explanation, such as a word in the budget
that suggests an ineligible cost, or a proposal that seems to be in a
different language from the form. UNKNOWN means the script could not tell, for
example from a scanned PDF. The report also lists the values it measured
without finding a problem. There is no "all clear". A report with no findings
still ends with the rules the script cannot see: whether you are within the
standard period of study, how many projects you are already on, whether your
leader has recommended the application, and your faculty's own deadline.

The script does not check character counts yet, and of the budget it checks
only the first-year totals you enter in `form.yml`: the annual ceiling, the
wage cap and the stipend share. Read the character counts off the counters in
the application, and check the other caps against the budget rules in the
prompt.

## 3. With an agentic tool (optional, experimental)

Download this repository as a ZIP (or clone it), copy your application files
into a folder inside it, for example `my_application`, open the repository
folder in Claude Code and ask it to check your application, for example "check
my GA UK application in the folder my_application". No terminal is needed: Claude Code is the Code
tab of the [Claude desktop app](https://claude.com/download), with a paid plan,
and Codex is part of the [ChatGPT desktop app](https://chatgpt.com/download).
The agent runs the Python scripts itself; if Python is missing, it says so and
asks before installing it.
The project skill in `.claude/skills/gauk-feedback/` makes it follow
[`agentic/RUNBOOK.md`](agentic/RUNBOOK.md): run the formal check, read your
files, write the review under the same rules as the chatbot prompt, and verify
every quote against your text with `tools/verify_quotes.py` before showing it
to you. Codex and other agents that read `AGENTS.md` follow the same
runbook. The agent never changes your files.

For a second opinion, [`agentic/`](agentic/) describes how to run two heavier
tools on a proposal: [mad-research](https://github.com/tjhavranek/mad-research),
an audit by Claude and Codex, and
[paper-workshop](https://github.com/tjhavranek/paper-workshop), a workshop of
Claude reviewers. Both were built for research papers, neither has been tried
on a GA UK application, and there is no evidence that they give better advice
than the single pass. Use them only if you already know them, and never let
paper-workshop rewrite your application.

## What the review will not do

It will not estimate your chance of funding, give a score or a grade, or
compare you with other applicants. It has not seen the other applications, and
a number of that kind mostly discourages people who should apply.

It will not write or rewrite your text, even if you ask. You sign a declaration
that you prepared the application independently. The review says what is
missing and where it belongs; you write it.

It is not for evaluators. Opponents, rapporteurs, board members and faculty
officers should not use it on applications they assess: assessment is
confidential, and a chatbot would send someone else's application to a third
party. Faculty and GA UK staff are welcome to point students to it before the
faculty deadline.

## The AI declaration

The application asks whether you used AI in preparing it and, if you did, how
and to what extent. Using this review counts, so note which tool and model you
used. The applicant guide states that the answer is not a criterion for
assessing the project. A template for describing AI use is at
<https://ai.cuni.cz/AI-81.html>.

## Limits

It covers new applications in the 24th round (the call opens on 1 October
2026; projects start in 2027) and nothing else: not continuation requests, not
final reports. Faculty-specific rules and deadlines are not covered, and the
faculty deadline is the one that binds you. The rules expire on 1 February
2027, after which the checker refuses to run until they are updated.

It has been tested on invented applications only; see
[`docs/VALIDATION.md`](docs/VALIDATION.md). Language models miss problems that
a specialist in your field would see, and they can be wrong with confidence.
Push back on a finding you disagree with, and take the scientific questions to
your supervisor.

## How it is built

The rules live in one place, [`rules/`](rules/), each with its published
source. The prompts in `dist/` are generated from them and from the texts in
`src/`, and a test fails when a generated file no longer matches its sources.

    rules/          the rules, in YAML, with their sources
    src/            the hand-written prompt texts, with slots for the rules
    dist/           the generated prompts and rubric; do not edit
    checker/        the local formal check
    tools/          build, text extraction, quote verification
    templates/      form.yml for your web-form fields
    agentic/        the agentic runbook and the optional integrations
    tests/          invented applications and the test suite

To rebuild and test, install `requirements-dev.txt` and run
`python tools/build.py`, `python tests/make_fixtures.py` and
`python tests/test_checker.py`.

## Problems and corrections

If a rule is wrong or has changed, please open an issue naming the rule and
the published source. Do not paste any part of a real application into an
issue. For anything else, there is a short anonymous
[feedback questionnaire](https://forms.cloud.microsoft/e/t38pQfuAmm) linked from the page.

## Author and licence

Written by Tomáš Havránek ([meta-analysis.cz](https://meta-analysis.cz)),
Charles University, who is a member of the GA UK Grant Council; [DISCLOSURE.md](DISCLOSURE.md) sets out what follows from that.
The design follows [erc-ai-feedback](https://github.com/tjhavranek/erc-ai-feedback),
a similar review for ERC Starting and Consolidator Grant proposals. MIT
licence.
