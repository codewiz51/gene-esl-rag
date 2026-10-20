# Answer key: code-only review of `sourcecode/*.py` at `7cf6883` (tag `pre-refactor-oct20`)

A reusable test for local models. Give a model the step-by-step brief from
`QWEN_PLAN_COMPARISON.md`, point it at a worktree of this commit
(`git worktree add ~/RAG-oct19 pre-refactor-oct20`), then score its
answers here.

This key was written Oct 20, 2026, **before** seeing ornith-1.5's review, so
the grading couldn't drift toward its answer. That original key is
everything from "Tier A" to "How to score". The section at the end was
added after ornith, from its findings and traps.

It lists only what is **visible in the Python files**. Defects that need the
templates, storyboards or lesson output (for example the empty verb focus,
or "almuerzo" contradicting a template) are left out, since a code-only
reviewer can't see them. Every item marked ✔ was reproduced against the
code.

## Tier A: serious (a crash, a hang, a lost run, or silently wrong lessons)

| # | Defect (file) | Verified |
|---|---|---|
| A1 | `send_to_ollama`: `requests.post` has **no timeout**, so a stalled server hangs the run forever (commonFunctions) | ✔ |
| A2 | **No retry and no checkpoint.** One transient error ends the run, and every finished pass (about 30 min) is lost (commonFunctions, pipeline) | ✔ |
| A3 | `str(resp_json)` fallback can put a JSON dict into the lesson as text (commonFunctions) | ✔ |
| A4 | A weekly-correction replacement is treated as a regex template, so a backslash in the storyboard **crashes** the run (commonFunctions) | ✔ |
| A5 | **The self-review replaces the whole week unchecked.** An empty or cut-off review becomes the final lesson (passes) | ✔ |
| A6 | `_extract_section_per_day` loops over the days the model **returned**, so a dropped day is **not reported** at all (passes) | ✔ |
| A7 | `validate_markdown` also checks only the days present, so a missing Wednesday passes validation; and validation only warns, so the file is written anyway (commonFunctions) | ✔ |
| A8 | Missing template rule block: `get_rule_block` returns "" with a print; the docstring says "hard stop"; the pass runs **without its rules** (rule_utils) | ✔ |
| A9 | Top-level `import pypandoc` stops the pipeline starting without pypandoc, and `convert_markdown_to_docx` is never called (commonFunctions) | ✔ |

## Tier B: real, smaller

| # | Defect | Verified |
|---|---|---|
| B1 | "eso es la vida" → "Así es la vida" capitalizes mid-sentence (case-insensitive match, capitalized replacement) | ✔ |
| B2 | A duplicate day heading silently replaces the earlier block (`split_markdown_days`) | ✔ |
| B3 | The "calientito" rule matches one form only; calientita/os/as pass through, though the comment says "forbidden in any context" | ✔ |
| B4 | A weekly-correction phrase that starts or ends with punctuation never matches (`\b` wrap), e.g. "presión (alta)" | ✔ |
| B5 | `extract_weekly_verb_focus`: a plain header with no `WEEKLY VOCABULARY` section runs to `\Z` and **swallows the whole storyboard** | ✔ |
| B6 | Missing storyboard VOCAB block or day section: warning only; the run continues with empty vocab, so the model invents words | ✔ |
| B7 | `markdown_looks_truncated` checks only the last day | ✔ |
| B8 | `pipeline.py` has no error handling: a missing file is a raw traceback. `supportPipeline.py` uses a bare `except Exception`. | ✔ |
| B9 | No input validation: any 4th argument not starting with "n" means Debug; a missing storyboard is a traceback | ✔ |
| B10 | Model name and URL hard-coded to localhost; not configurable | ✔ |

## Tier C: hygiene / simplification

| # | Item |
|---|---|
| C1 | `ALL_DAYS` defined in several modules |
| C2 | Several near-identical "section per day" extractors |
| C3 | Duplicated prompt-building and self-review scaffolding |
| C4 | `print` instead of logging; debug files overwritten each run |
| C5 | Writes not atomic |
| C6 | `toDocx.py`: `CalledProcessError` from pandoc crashes |
| C7 | No unit tests |
| C8 | Small English-hint word list |

## Traps: "fixes" that would make things worse

A review loses points for recommending any of these:

| Trap | Why it's wrong |
|---|---|
| Make every correction literal (no regex replacement) | breaks `se sube\1 al carro` and `¿me puedo comer \1 \2?` |
| Set `"think": False` to speed things up | documented Aug 28 regression: the model stopped after one day |
| Move `temperature` to the top level of the request | Ollama ignores top-level options; the code comment explains this |
| Hard-stop mid-run on a missing section without checkpoints | throws away about 30 min of finished passes |
| Merge the template parser (`get_section_subblock`) into the lesson extractors | different formats ("Heading:" vs "## Heading") |
| "Remove" the trailing-time-expression instruction in the self-review | it is deliberate (see the code comment) |

## How to score

- Count each Tier A / B / C item as **found**, **partly** (seen but misdescribed, or a weaker fix), or **missed**.
- Then check every claim the reviewer makes that is **not** on this list: is it real (verify against the code), or a false alarm?
- Note each trap it falls into.
- Check that it followed the brief: no files changed, purposes listed, plan written, summary saved.

## Added after the ornith review (Oct 20)

Extra real items, from ornith. Count them as bonus findings:

| # | Item | Verified |
|---|---|---|
| X1 | `markdown_looks_truncated()` is only called by `supportPipeline.py`, never by `pipeline.py` | ✔ |
| X2 | No `requirements.txt` at this commit | ✔ |

Extra traps, from ornith:

| Trap | Why it's wrong |
|---|---|
| A short read timeout (e.g. 120 s) on the existing **non-streaming** call | with `"stream": False` Ollama sends nothing until the answer is done; real passes take 247–1,330 s, so every run would fail. A short timeout is only safe with streaming. |
| A small `num_predict` cap (e.g. 4,096) | `num_predict` counts thinking tokens too; real passes produce 9,661–53,846 tokens, so most passes would be cut off before writing any lesson text |
| "`num_predict=-1` can use up all memory" (false alarm) | memory is set by `num_ctx`, not `num_predict` |

## Results so far

| Model | Tier A (9) | Tier B (10) | Tier C (8) | Bonus | Traps | False alarms |
|---|---|---|---|---|---|---|
| qwen3.8:27b (Oct 19) | 5 / 3 / 1 | 5 / 1 / 4 | 6 / 1 / 1 | 0 | 2 | 1 |
| ornith-1.5:35b (Oct 20) | 4 / 2 / 3 | 4 / 1 / 5 | 2 / 2 / 4 | 2 | 4 (2 severe) | 2 |

Columns: found / partly / missed. Details: `QWEN_PLAN_COMPARISON.md`, `ORNITH_PLAN_COMPARISON.md`.
