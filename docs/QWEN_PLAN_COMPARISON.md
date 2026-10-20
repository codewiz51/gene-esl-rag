# Qwen's refactor plan vs. the Oct 20 refactor

Qwen (local, `qwen3.8:27b`) wrote `REFACTOR_PLAN.md` on the evening of
Oct 19, 2026 from the 9 Python files in `sourcecode/`. It was never
implemented. Claude did the refactor on Oct 20 without seeing that plan.
This compares the two, item by item, so the next time qwen is used for
code work its blind spots are known in advance.

Each of qwen's claims was **tested against the code**, not just read.

**Context that matters for fairness.** Gene ran qwen one step at a time,
on purpose, with this brief (Oct 19):

> You have access to the directory ~/RAG/sourcecode. List all python
> files in the directory. Do not recurse into sub folders.
> Analyze the python file content for each file. Report the purpose of
> each python script.
> Analyze the source code for weaknesses. Do not change any files.
> Analysis only.
> Prepare a plan for streamlining, correcting and simplifying the python
> code. Produce a markdown file.
> *(then: save a summary of the conversation to ~/AIExperiments)*

So qwen was asked for a **code-only** review of the Python files, and it
did exactly that. It never saw the templates, the storyboards, a lesson
or the git history, and half the pipeline's logic lives in those files.
It was also never asked for the client/server mode, `--resume` or
anything else Gene asked Claude for on Oct 20. Section 2 ("Outside
qwen's brief") is therefore a map of what a code-only review cannot see,
not a list of qwen's failures. Sections 3 and 4 judge what qwen did with
what it was given.

## 1. Scorecard

### Correctness items (qwen's P0)

| ID | Qwen's claim | Claim accurate? | Status after Oct 20 |
|---|---|---|---|
| C1 | "eso es la vida" → "Así es la vida" capitalizes mid-sentence | **Yes.** Test: "Ella dice que eso es la vida." → "…que Así es la vida." | Claude missed it on the first pass. **Fixed later on Oct 20**: the replacement copies the case of the first letter it replaces. |
| C2 | A backslash in a weekly correction crashes the run | **Yes.** Test: `foo → bar\1` crashes with `PatternError`. | Claude missed it on the first pass. **Fixed later on Oct 20**, for weekly corrections only. **Qwen's fix is wrong** (see §3). |
| C3 | No timeout, no retry on the Ollama call | Yes | Fixed: streaming, 120 s inactivity timeout, 2 retries, typed errors |
| C4 | `str(resp_json)` can end up in the lesson | Yes | Fixed: raises an error instead |
| C5 | Top-level `pypandoc` import breaks startup | Yes | Fixed: unused function and import removed |
| C6 | Self-review output not checked | Yes | Fixed, more strictly than proposed: the review is rejected unless every day and section survive and its length is 70–150% of the original |
| C7 | `markdown_looks_truncated` checks only the last day | Yes | Covered: `validate_markdown` now checks every day (exit 3) and each pass retries missing days. The function itself is unchanged. |
| C8 | A missing day heading "merges" the next day into this one | **No.** Test: the day is *dropped* (empty), not merged. | Covered: a storyboard with an empty day now stops before any model call (exit 1). |
| C9 | A duplicate day heading silently overwrites the first | Yes | Claude missed it on the first pass. **Fixed later on Oct 20**: reported, and the longer block is kept. |

### Reliability items (qwen's P1)

| ID | Qwen's claim | Status after Oct 20 |
|---|---|---|
| R1–R4 | Missing sections only warn; make it a hard stop ("strict mode") | Done differently: the pass retries, then the lesson is written and the run exits 3 (see §3) |
| R5 | Missing template rule block should be a hard stop | Fixed: checked before the first model call (exit 1) |
| R6 | Error handling differs between the two pipelines | Fixed: one client, one CLI wrapper |
| R7 | .md/.docx timestamps differ | Moot: the function was removed |
| R8 | `mainSupport.md` can go stale | Partly: `--resume` refuses if it changed; nothing else |

### Simplification items (qwen's P2)

| ID | Qwen's claim | Status after Oct 20 |
|---|---|---|
| S1 | Four versions of "extract a section per day" | **Not done.** Claude added a fifth (`_coverage_gaps`) |
| S2 | `ALL_DAYS` defined in several places | Fixed (`config.py`) |
| S3–S5 | Duplicated prompt-building code in `passes.py` | Not done (deliberately: prompt text was not to change) |
| S6 | Pandoc logic duplicated | Fixed by removal |
| S7 | `extract_day_focus` should warn when it finds nothing | Not done |

### Strengthening items (qwen's P3)

| ID | Qwen's claim | Status after Oct 20 |
|---|---|---|
| Q1–Q2 | Weak hint and validation heuristics | Partly: new checks for STUDENT, DIRECTION and LENGTH. The English-hint list is unchanged. |
| Q3 | Use logging | Done |
| Q4 | Move config out of the code | Done |
| Q5 | Type hints + unit tests | **Unit tests done later on Oct 20**: 84 tests in `sourcecode/tests/`. No type hints. |
| Q6 | `toDocx.py` crashes on a Pandoc error | Not done |

## 2. Outside qwen's brief

Everything below was found on Oct 20, and all of it was outside a code-only review of `sourcecode/*.py`. It shows what that kind of review cannot catch, whoever does it. Ordered by impact:

1. **The weekly verb focus never reached the model.** Since Week 35 the
   storyboard header read "WEEKLY VERB FOCUS (reference only …):", and the
   parser matched only the bare header. Every pass-pipeline run sent an
   empty verb focus. Finding it took reading the storyboards and the git
   history, not just the code.
2. **Contradictions across files.** The template said "almuerzo en bolsa";
   the code rewrote it to "almuerzo en llevar"; the Five-Minute template
   said "almuerzo en llevar"; qwen itself had flagged the phrase as odd in
   lesson output. The bug only shows when code and data are read together.
3. **"calientito" missed its inflected forms.** The rule matched one word,
   so "mantas calientitas" passed through. Visible only in output.
4. **Lesson-quality defects.** These are visible only by running the
   pipeline and reading the result:
   - questions treating the student as Marisol (7 per run);
   - Five-Minute translations in the wrong language (7 of 7 days);
   - Examples copied from the story;
   - "la pila" for a battery;
   - a storyboard rule copied into the story.

   Qwen's plan explicitly put prompt content out of scope, so these were
   never in reach.
5. **No way to prove "behavior-preserving."** The plan promised no change
   in behavior but had no test for it. The Oct 20 work proved it: with
   identical model answers, all 9 prompts and both lesson files were
   byte-identical to the old code, and each later prompt change touched
   only the prompts intended.
6. **Not in its brief:** Macbook/Studio client-server mode, `--resume`,
   `--check`, run folders. Qwen wasn't asked for these, so this isn't a
   failing; but no plan covered resuming a 40-minute run after a failure.

## 3. Where qwen's fixes would have caused damage

- **C2, the literal-replacement fix.** Qwen proposed passing every
  correction's replacement as a literal string. Two of the base
  corrections rely on group references:
  - `se sube\1 al carro`
  - `¿me puedo comer \1 \2?`

  Test with qwen's fix: "¿puedo tener una manzana?" becomes
  "¿me puedo comer \1 \2?" (literal backslashes in the lesson). The
  correct fix is literal replacement **only for weekly corrections**
  from the storyboard.
- **R1–R4, strict mode as a hard stop.** In qwen's plan this raises an
  error mid-run, and the plan has no checkpoints, so one missing section
  in pass 5 would throw away about 30 minutes of finished passes. The
  Oct 20 design instead retries the pass, checkpoints every step, writes
  the lesson and exits 3, so nothing is lost and the gap is listed.
- **S1, one extractor for everything.** This lumps the template parser
  (`get_section_subblock`, which reads "Heading:" lines in the template)
  with the lesson parsers (which read "## Heading" in Markdown). They
  parse different formats; forcing one function onto both adds risk for
  little gain.

## 4. What qwen did well

- It found three real bugs Claude missed: C1, C2 and C9.
- Its priorities were right: correctness, then reliability, then
  simplification, then optional work.
- It kept the layered "3D-printer" architecture instead of flattening it.
  Claude made the same call.
- It wanted unit tests. That was fair criticism of the first Oct 20
  pass; the suite was added the same afternoon.
- Its static reading was thorough and mostly accurate (C8 was the one
  misread).

## 5. How to use qwen for code work next time

1. **Give it the data, not just the code**: a storyboard, both templates,
   and one real lesson output. Its biggest misses came from never seeing
   them.
2. **Ask it to prove each bug** with a two-line test or a sample input.
   C8 would have been corrected that way.
3. **Ask for every caller of a function before accepting a fix to it.** The
   C2 fix failed because it didn't check how `BASE_CORRECTIONS` uses
   group references.
4. **Ask how a proposed hard stop interacts with a 40-minute run**
   (restart cost, partial output). This is a design check qwen did not do.
5. **Require a behavior-preservation test** (prompt-equivalence against a
   fake model) for any "no behavior change" refactor.
6. **Good use of qwen**: a second-opinion static review of a finished
   change, looking for edge cases. That's where it found C1, C2 and C9.
   **Poor use**: unsupervised implementation, or anything that depends on
   reading lesson output.

## 6. Open items from this comparison

C1, C2 (weekly corrections only) and C9 were fixed on Oct 20 with unit
tests. Still open from qwen's list, all low priority:
- S1/S3/S4: duplicated extraction and prompt-building code.
- S7: warn when a day has no focus line.
- Q1/Q2: the English-hint word list and per-day accent check.
- Q6: `toDocx.py` error handling.
- R8: stale `mainSupport.md`.
