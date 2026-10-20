# ornith-1.5:35b code review vs. qwen (same brief, same code)

On Oct 20, 2026 Gene gave `ornith-1.5:35b` (Ollama, non-MLX build, run through
AnythingLLM) the same step-by-step brief qwen had on Oct 19:
1. list the Python files;
2. give each one's purpose;
3. find weaknesses (analysis only);
4. write a refactor plan;
5. save a summary.

It reviewed the same code: a worktree of tag `pre-refactor-oct20` (`7cf6883`)
at `~/RAG-oct19/sourcecode`.

It was scored against `CODE_REVIEW_ANSWER_KEY_7cf6883.md`, which was written
**before** ornith's output was seen. Every claim below was checked against
the code or against the Week 41 run data.

## 1. Head-to-head

| | qwen (Oct 19) | ornith-1.5:35b (Oct 20) |
|---|---|---|
| Tier A, serious (9) | 5 found, 3 partly, 1 missed | **4 found, 2 partly, 3 missed** |
| Tier B, smaller (10) | 5 found, 1 partly, 4 missed | **4 found, 1 partly, 5 missed** |
| Tier C, hygiene (8) | 6 found, 1 partly, 1 missed | **2 found, 2 partly, 4 missed** |
| Real bugs beyond the answer key | 0 | **2** (see §3) |
| Traps (fixes that would do damage) | 2 | **4, two of them severe** (§4) |
| False alarms | 1 | **2** |
| Followed the brief | yes | yes; no source files changed |
| Time for the whole session | not recorded | about 4 minutes |

**Verdict:**
- ornith is **faster and writes a cleaner, more readable review**.
- qwen's review was **more accurate and more complete**.
- ornith's plan is **more dangerous**: its first-priority fix would break every real pipeline run (§4).
- Neither found the subtle code-level bugs: inflected "calientito", punctuation in weekly phrases, the verb-focus parser swallowing the storyboard, dropped days going unreported.

## 2. Item by item

### Tier A: serious

| # | Answer key | ornith | Note |
|---|---|---|---|
| A1 | No timeout on the Ollama call | **found** | but its fix is a trap (§4) |
| A2 | No retry, no checkpoint: one error loses ~30 min of passes | missed | proposes a clean error message, no retry, no checkpoints |
| A3 | `str(resp_json)` can end up in the lesson | missed | |
| A4 | Backslash in a weekly correction crashes the run | **found** (generic: "a bad backreference like `\g`") | didn't tie it to storyboard corrections; fix is a soft trap (§4) |
| A5 | Self-review replaces the week unchecked | **found**, clearly | the plan has no specific fix, only the general missing-section handling |
| A6 | A dropped day is not reported at all | missed | says the extractor "warns ... writes an empty string", which is true for a missing section but not for a missing day |
| A7 | Validation only checks days present; file written anyway | partly | "exit code 0 on broken output" ✔; missing-day hole ✘ |
| A8 | Missing template rule block runs the pass without rules | **found** | |
| A9 | Top-level `pypandoc` import; `convert_markdown_to_docx` never called | partly | saw the import problem only inside the helper, missed that the helper is dead code, and **recommends making it the only implementation** |

### Tier B: smaller

| # | Answer key | ornith |
|---|---|---|
| B1 | "Así es la vida" capitalized mid-sentence | missed |
| B2 | Duplicate day heading overwrites | missed |
| B3 | "calientito" matches one form only | missed |
| B4 | Weekly phrase with punctuation never matches | missed |
| B5 | Plain verb-focus header swallows the whole storyboard | missed |
| B6 | Missing VOCAB block or day: warning only | partly (generic "regex brittleness") |
| B7 | Truncation check looks at the last day only | **found**, plus the extra in §3 |
| B8 | `pipeline.py` has no error handling | **found** |
| B9 | No input validation (missing file = traceback) | **found** |
| B10 | Hard-coded config | **found** |

### Tier C: hygiene

| # | Answer key | ornith |
|---|---|---|
| C1 | `ALL_DAYS` duplicated | **found** |
| C2 | Duplicated extractors | partly |
| C3 | Duplicated prompt scaffolding | missed |
| C4 | `print` instead of logging; debug files overwritten | partly (logging ✔) |
| C5 | Writes not atomic | missed |
| C6 | `toDocx.py` crashes on a Pandoc error | missed (raised path traversal instead) |
| C7 | No unit tests | **found** |
| C8 | Small English-hint word list | missed |

## 3. Real findings beyond the answer key (credit to ornith)

1. **`markdown_looks_truncated()` is never called by `pipeline.py`**, only
   by `supportPipeline.py`. Confirmed.
2. **No `requirements.txt`** at that commit. Confirmed; one was added on
   Oct 20.

It also spotted that a Five-Minute answer that keeps the headings but
contains garbage passes validation. That's fair, and it overlaps A5/A7.

## 4. Traps: fixes that would do damage

1. **Severe: `timeout=(30, 120)` on the existing call.** The old
   `send_to_ollama` uses `"stream": False`, so Ollama sends nothing until
   the whole answer is done. A 120-second read timeout would fail every
   pass that takes longer than 2 minutes. In the three Week 41 runs:
   - story: 755–1,330 s;
   - examples: 339–539 s;
   - self-review: 247–306 s.

   Every run would fail on the story pass. The Oct 20 refactor switched
   to **streaming**, where the read timeout means "no new data for N
   seconds"; that change is what makes a short timeout safe.
2. **Severe: `num_predict=4096`.** In Ollama, `num_predict` counts all
   generated tokens, and the thinking trace is included. Real response
   sizes in the same runs:
   - story: 31,237–53,846;
   - examples: 13,525–21,285;
   - self-review: 9,661–12,235;
   - Five-Minute: 18,030–21,060.

   A 4,096 cap would cut most passes off mid-thinking, before any lesson
   text is written. Ornith calls this its "biggest single risk" and puts
   it first.
3. **Soft: "strip/escape backreferences in `right` values".** Marked
   "optionally", but if applied to all corrections it breaks
   `se sube\1 al carro` and `¿me puedo comer \1 \2?`. This is the same
   trap qwen fell into.
4. **Hard stop without checkpoints.** "Abort the run" on missing sections
   with no way to resume throws away the finished passes. Its principle
   says "fail loudly, but recoverably", but the plan has no recovery
   mechanism. Same trap as qwen.

Lesser concerns:
- "Drop the pypandoc → subprocess fallback" removes robustness.
- "Wrap each `re.sub` in try/except" would skip a broken correction silently.

## 5. False alarms

- **"`num_predict=-1` … can consume all of the unified memory."** Memory
  is set by `num_ctx` (the context window and its cache), not by
  `num_predict`; generation stops when the context is full.
- **"Corrections applied after self-review can clobber it — order-of-operations risk."**
  Running the corrections last is deliberate: it fixes whatever the
  review produced.
- Minor misreads: it calls the system "English-to-Spanish" (it teaches
  English to Spanish speakers); and its path-traversal concerns are noise
  for a local single-user tool, which it half-admits.

## 6. Process notes

- **Fast:** the whole five-step session took about 4 minutes (18–64 tokens/s).
- **Grounded:** it read every file before each answer and said so.
- **Self-checking:** its first save of the summary went to AnythingLLM's
  workspace rather than `~/RAG-oct19`. It searched, noticed, and rewrote
  the file to the right path unprompted. The plan file
  (`refactor_python_ornith15.md`) has the same issue: it landed in the
  AnythingLLM workspace.
- **Verification plan:** an end-to-end run after each phase. That's better
  than qwen's (none), but still no behavior-preservation test, and an
  end-to-end run would have exposed traps 1 and 2 immediately.

## 7. Guidance

- **Use ornith for** fast first-pass reviews and readable summaries of a
  codebase. Its structure-level observations (self-review is the weakest
  link; warnings-only error handling) were sound and well put.
- **Don't take its numbers on trust.** Its two concrete settings (120 s,
  4,096 tokens) were invented without looking at real run data, and both
  are wrong by an order of magnitude. Give it real figures, such as a
  run's `manifest.json` timings, before asking for limits or timeouts.
- **Ask it to name the caller and the data behind every fix.** The same
  rules as for qwen (`QWEN_PLAN_COMPARISON.md` §5) apply.
- **Between the two, for code review:** qwen found more of the real
  defects; ornith wrote a clearer explanation. Neither should change
  pipeline code without a test run against real data.

## 8. Cleanup

```
cd ~/RAG && git worktree remove ~/RAG-oct19
```

This removes the review copy (it holds ornith's summary file; copy that
out first if you want to keep it). Ornith's plan file is in the
AnythingLLM workspace, not in either repo.
