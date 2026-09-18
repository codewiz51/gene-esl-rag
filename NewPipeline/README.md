# Pass-based pipeline

## Status (as of Sep 18, 2026)

Two consecutive clean runs against Week 35's storyboard, for both MAIN
and Five-Minute. All defects found and fixed during development are
listed under "Fixed so far" below. **Still n=1 on the storyboard** -
only Week 35 has been tested. Treat as a working second pipeline
alongside the original, not yet as a trusted replacement, until it's
been run against at least one or two other weeks' storyboards.

## Files

- `rule_utils.py` — pulls named `#BEGIN RULES:` / `#BEGIN DICTIONARY:`
  blocks (and named sub-sections of `SECTION_CONTENT`) out of
  `MainLessonTemplate.txt`, so each pass sees only its own rules.
- `storyboard_utils.py` — parses the raw storyboard file's weekly verb
  focus, each day's narrative bullets, and each day's `=== VOCAB DAY ===`
  block.
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

## Run it

```bash
cd /Users/gene/Documents/RAG/NewPipeline
time python3 pipeline.py 35 Week35StoryBoard.md MainLessonTemplate.txt Debug ; \
time python3 supportPipeline.py 35 mainSupport.md Week35StoryBoard.md FiveMinuteTemplate.txt promptFive.md Debug ; \
afplay /System/Library/Sounds/Glass.aiff
```

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
   Vocabulary. Enforces language direction explicitly (Spanish→English
   items must be in Spanish, including the required professional-
   register item; English→Spanish items in English).
6. **Student Questions** — whole week visible, so it can avoid
   repeating a question across days.
7. **Self-review** — judgment-only pass over the fully assembled week:
   register variety across days, Examples dialogue naturalness, no B1
   vocabulary in Story prose. Explicitly told NOT to flag trailing time
   expressions (deliberately cut from the template - natural in Cuban
   Spanish) and NOT to touch item counts/hints/vocabulary (checked by
   code in `common.validate_markdown()`, not by model judgment).

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
- **Only tested against Week 35.** Different storyboards (different
  verb focus, different vocab density, non-clinic days) may expose
  new gaps the same way each Week 35 run did.
- **No per-pass retry/repair loop** - a pass missing a day or section
  currently just warns and moves on, same as `generateMain.py`'s
  existing behavior.
