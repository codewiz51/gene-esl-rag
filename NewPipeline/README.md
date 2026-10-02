# Pass-based pipeline

## Status (as of Oct 2, 2026)

Used for production runs on Weeks 35, 37, 38 and 39, for both MAIN and
Five-Minute. Output still goes through a human correction run before it
is used with students (see "Weekly workflow" below). Defects found and
fixed during development are listed under "Fixed so far". Week 39 added
the optional STUDY NOTES / WEEK NOTES storyboard blocks, a per-day verb
focus for the Examples pass, and a hint checker.

**No .docx output.** `pipeline.py` and `supportPipeline.py` write only
Markdown. (The original `generateMain.py` / `generateSupport.py` no
longer write .docx either; `commonFunctions.convert_markdown_to_docx()`
still exists if a corrected lesson ever needs one.)

## Files

- `rule_utils.py` — pulls named `#BEGIN RULES:` / `#BEGIN DICTIONARY:`
  blocks (and named sub-sections of `SECTION_CONTENT`) out of
  `MainLessonTemplate.txt`, so each pass sees only its own rules.
- `storyboard_utils.py` — parses the raw storyboard file: weekly verb
  focus, each day's narrative bullets, each day's `=== VOCAB DAY ===`
  block, plus the optional `WEEK NOTES` block, optional per-day
  `STUDY NOTES` blocks, and each day's focus line (the "Introduce ...",
  "Light review of ..." lines above its Examples).
- `qa_utils.py` — `lint_hints()`: no-model check, run at the end of both
  pipelines. Prints `HINT WARNING` for any Warmup / Grammar / Student
  Questions hint longer than 3 words or made only of common English
  words. Warns only; never edits the lesson.
- `state.py` — `WeekState`: holds each day's finished section text as
  passes fill it in, and assembles the final Markdown in canonical
  section order.
- `passes.py` — the MAIN passes (in dependency order below), plus
  `fiveminute_self_review_pass()` used by `supportPipeline.py`.
- `pipeline.py` — MAIN orchestrator / CLI, same call shape as
  `generateMain.py`. Also writes `mainSupport.md` (fixed filename)
  alongside the timestamped output, so `supportPipeline.py` /
  `generateSupport.py` has a stable name to point at.
- `supportPipeline.py` — Five-Minute orchestrator, same call shape as
  `generateSupport.py`, with one addition: a self-review pass before
  corrections/validation/write. Imports `generateSupport.py`'s
  extraction helpers directly rather than duplicating them.
  `generateSupport.py` itself is untouched.

## Optional storyboard blocks

Both are optional. A storyboard without them runs exactly as before.
Write them as plain facts, not as instructions to the model: the model
treats everything in them as source material.

**WEEK NOTES** - one block, placed above `# MONDAY STORYBOARD`. Use it
for real facts and cast limits that hold for the whole week (clinic
hours and address, who appears on which days, how Marisol gets to work).
Passed to the Story, Warmup/Grammar, Examples and Student Questions
passes, which are told to obey it.

```
# === WEEK NOTES ===
Setting: ... Hours: ...
Cast for this week: Camy, Marisa and Donna appear only on Monday. ...
# === END WEEK NOTES ===
```

**STUDY NOTES** - one block per day that needs exact source material
(for example certification practice-test questions with the correct
answers and explanations). Place it after that day's bullets and before
the next `# DAY STORYBOARD` heading.

```
# === STUDY NOTES SATURDAY ===
Source: ... (book, page)
Question 1 ...
Correct answer: ...
Why the others are wrong: ...
# === END STUDY NOTES SATURDAY ===
```

The Story and Vocabulary passes never see it (it is stripped from the
story requirements). Only the Examples and Student Questions passes
receive it, and only for the day it belongs to: Examples become one
numbered item per question (question, correct answer, why, why each
wrong choice is wrong), the dialogue requirement is waived for that day,
and Student Questions are written about the notes. The day's bullets
should still say what the character is doing (for example "studies
questions 1, 2 and 3"), because the Story pass cannot see the notes.

Check the notes against the source before running; the model is told to
use only what is in them.

## Run it

```bash
cd /Users/gene/Documents/RAG/NewPipeline
time python3 pipeline.py 35 Week35StoryBoard.md MainLessonTemplate.txt Debug ; \
time python3 supportPipeline.py 35 mainSupport.md Week35StoryBoard.md FiveMinuteTemplate.txt promptFive.md Debug ; \
afplay /System/Library/Sounds/Glass.aiff
```

Week 39 and later: after the main lesson is corrected, point the
Five-Minute run at the corrected file instead of `mainSupport.md`, so the
five-minute lesson inherits the fixes:

```bash
time python3 supportPipeline.py 39 39_MAIN_corrected.md Week39StoryBoard.md FiveMinuteTemplate.txt promptFive.md Debug
```

(`mainSupport.md` is written automatically by `pipeline.py` and holds the
uncorrected main lesson.)

Reads the same `weekly_template_dir` / `lesson_dir` as the existing
pipeline (via shared `commonFunctions.py`, imported from `sourcecode/`
- nothing duplicated). Output uses `MAIN_PASSPIPELINE` /
`FIVEMIN_PASSPIPELINE` suffixes so it never collides with or overwrites
`generateMain.py` / `generateSupport.py`'s own output. Typical run time:
~25 min MAIN + ~5-6 min Five-Minute.

## MAIN pass order (each depends only on layers already written)

1. **Vocabulary** — from storyboard `VOCAB` blocks only.
2. **Story** — from Story Requirements + Vocabulary. Sees the whole
   week at once so register can vary day to day.
3. **Warmup + Grammar** — from each day's Story Requirements (so the
   correct verb/tense is taught, not an invented one) + Vocabulary.
   Grammar is written in English here.
4. **Grammar → Spanish translation** — narrow, single-purpose: takes
   the English Grammar explanation and translates only the prose (not
   the Pattern Practice list, not quoted English target phrases) into
   Cuban Spanish. Split out from step 3 deliberately, so "write it" and
   "translate it, but leave X/Y untouched" aren't one overloaded call.
5. **Examples + Translation Practice** — from finished Story +
   Vocabulary + each day's focus line. Enforces language direction
   explicitly (Spanish→English items must be in Spanish, including the
   required professional-register item; English→Spanish items in
   English). Requires at least two Examples items that use the day's
   verb(s), forbids grammar commentary, and uses STUDY NOTES and WEEK
   NOTES when present.
6. **Student Questions** — whole week visible, so it can avoid
   repeating a question across days. Hint rule is repeated in the
   instructions (one Spanish word or a short Spanish phrase, never
   English, never the answer). Uses STUDY NOTES and WEEK NOTES when
   present.
7. **Self-review** — judgment-only pass over the fully assembled week:
   register variety across days, Examples dialogue naturalness, no B1
   vocabulary in Story prose. Explicitly told NOT to flag trailing time
   expressions (deliberately cut from the template - natural in Cuban
   Spanish) and NOT to touch item counts/hints/vocabulary (checked by
   code in `common.validate_markdown()`, not by model judgment).

## Weekly workflow

1. Write `WeekNNStoryBoard.md` in `source_docs/WeeklyTemplates`
   (use WEEK NOTES / STUDY NOTES when the week needs them).
2. `pipeline.py` (MAIN, about 40 minutes on the current model).
3. Read the output, correct it by hand or with Claude, and save it as
   `NN_MAIN_corrected.md` in `source_docs/WeeklyLessons`. Watch the
   terminal for `HINT WARNING` lines.
4. `supportPipeline.py` pointed at the corrected file (see "Run it"),
   then correct that output as `NN_FIVEMIN_corrected.md`.
5. Commit code, templates and storyboards. `source_docs/WeeklyLessons/`
   and `debug_*.txt` are in `.gitignore`, so lesson output is not
   committed.

## Five-Minute flow

Unchanged extraction/generation from `generateSupport.py`, plus:
- **`fiveminute_self_review_pass`** — narrow, single check: every
  Grammar Focus must have a *character* as the grammatical subject
  ("Marisol tells...", not "'have' shows..."). Deliberately does not
  touch Mini Story word counts, comma limits, or connector choice -
  see "Known gaps" below.

## Fixed so far (for context on what "n=1 clean" actually covers)

- Rule-to-pass mapping corrected to match the live template exactly
  (`SENTENCE_STYLE` not `SENTENCE_CONTROL`; `TRAILING_TIME_EXPRESSION`
  and `SPANISH_VOICE` correctly absent, deliberately cut upstream).
- `MARKDOWN_LAYOUT` added to every pass (was missing entirely at
  first) - fixed Examples losing its numbered-list structure and
  Translation Practice using illegal bold headers.
- General output-format guardrails (no HTML, no invented rules, no
  reasoning narration) added to every pass and to both self-review
  passes.
- Warmup/Grammar pass wasn't receiving per-day Story Requirements, so
  it invented its own grammar topic instead of teaching that day's
  actual verb/tense focus - fixed by passing `story_requirements_by_day`
  through.
- Grammar-in-Spanish (an established, tested practice - see Week 34)
  moved out of the generation pass into its own translation pass,
  rather than asking one call to write and translate simultaneously.
- Examples/Translation Practice language-direction bug (an English
  sentence placed in the Spanish→English list, attempting to satisfy
  the required professional-register item) - fixed with an explicit
  instruction; confirmed fixed on the following run.
- `pipeline.py` wasn't writing `mainSupport.md` (the fixed-filename
  copy `generateSupport.py`/`supportPipeline.py` expect) - added.

## Known gaps / next steps

- **No deterministic checker yet** for: Mini Story word-count-per-
  sentence (8-12), comma limit (<=1), the and/but/because connector
  restriction, or Translation Practice language direction. All of
  these are currently enforced only by prompt instruction, which is
  why they slipped at least once each during testing. Candidate: add
  checks to `commonFunctions.validate_markdown()` so both pipelines
  benefit, rather than duplicating logic here.
- **Quality still depends on the storyboard.** Errors that recur across
  runs are usually fixed by a storyboard fact, a WEEK NOTES / STUDY
  NOTES entry, or a `CUBAN_REGISTER` entry in `MainLessonTemplate.txt`,
  not by editing the model output each time.
- **Model-written Spanish needs a read.** Typical misses: English titles
  ("Mr.") inside Spanish sentences, a wrong gender on acronyms (la
  HIPAA), and the answer repeated inside a hint.
- **No per-pass retry/repair loop** - a pass missing a day or section
  currently just warns and moves on, same as `generateMain.py`'s
  existing behavior.
