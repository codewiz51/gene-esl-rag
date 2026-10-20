# ESL lesson pipeline — project documentation

Last updated: October 20, 2026 (client/server refactor, branch
`refactor/client-server-pipeline`).

## 1. What it does

Each week Gene writes a storyboard (`WeekNNStoryBoard.md`): a weekly verb
focus, optional week notes, and for each day the story bullets and a
vocabulary block. The pipeline turns it into two lessons for his
A2/A2+ Cuban adult learners:

- **MAIN lesson** (`pipeline.py`): seven days, each with Warmup,
  Vocabulary, Story (English + Cuban Spanish), Grammar (explained in
  Spanish), Examples, Translation Practice, Student Questions.
- **Five-Minute lesson** (`supportPipeline.py`): a short afternoon review
  for each day, built from the finished MAIN lesson: Vocabulary Review,
  Grammar Focus, Mini Story, Translation Practice, Student Questions.

Both write Markdown. Gene corrects the output by hand (or with Claude),
then `toDocx.py` makes the .docx files.

The model is `pipeline-qwen38:latest` on Ollama: a Modelfile wrapper
around the `qwen3.8:27b-mlx` weights, installed on the Studio.

## 2. Machines and modes

| Machine | `$HOME` | Hostname | Mode | Ollama used |
|---|---|---|---|---|
| Macbook Pro | `/Users/Gene` | `MacBook-Pro.local` | **client** | Studio, `http://192.168.4.47:11434` |
| Mac Studio | `/Users/gene` | `studio.local` | **local** | `http://localhost:11434` |

- The repo is `~/RAG` on both machines. All paths are worked out from
  the location of `sourcecode/commonFunctions.py`, so nothing hardcodes a
  user folder.
- Python: the `rag_env` virtual environment on each machine (`rag` alias
  activates it). Needs `requests`; `pypandoc` is optional
  (`requirements.txt`). Code works on Python 3.7+; both venvs run 3.14.
- **Detection** (`config.py`): `$HOME` is matched exactly against the
  `MACHINES` table, then cross-checked with the hostname. If they
  disagree, or neither matches, the run stops and asks for `--machine`.
- **Overrides**: `--machine macbook|studio` (or env `ESL_MACHINE`),
  `--studio-ip IP` (or env `ESL_STUDIO_IP`; also accepts `IP:port`).
  `--studio-ip` is refused on the Studio, so a typo can't send a local
  run across the network.
- The Studio's Ollama must listen on the network (`OLLAMA_HOST=0.0.0.0`).
  It does; AnythingLLM on the Macbook uses the same path.

GitHub (`codewiz51/gene-esl-rag`) is the source of truth. Work happens on
a branch on the Macbook, is pushed, and is pulled on the Studio. The
sandbox Claude works in cannot push, so pushes come from Gene's terminal.

## 3. Repository layout

```
RAG/
  docs/                         this file, QUICKSTART_MACBOOK.md
  requirements.txt
  runs/                         one folder per run (git-ignored, per machine)
  source_docs/
    WeeklyTemplates/            storyboards, MainLessonTemplate.txt,
                                FiveMinuteTemplate.txt, promptFive.md,
                                reference.docx
    WeeklyLessons/              generated and corrected lessons
  sourcecode/
    pipeline.py                 MAIN orchestrator (CLI)
    supportPipeline.py          Five-Minute orchestrator (CLI)
    passes.py                   the MAIN passes + Five-Minute self-review
    commonFunctions.py          paths, corrections, validation, writers
    config.py                   settings, machine detection, endpoint
    ollama_client.py            the only code that talks to Ollama
    errors.py                   error types and exit codes
    runs.py                     run folders, checkpoints, --resume
    runlog.py                   logging, run.log, end-of-run summary
    cli.py                      shared flags and exit handling
    state.py                    WeekState: sections filled in by passes
    storyboard_utils.py         storyboard parsing
    rule_utils.py               pulls named rule blocks from the template
    qa_utils.py                 hint checker
    toDocx.py                   corrected .md -> .docx (Pandoc)
    tools/mock_ollama.py        fake Ollama for testing (section 10)
```

## 4. The storyboard

Parsed by `storyboard_utils.py`. Required:

- `WEEKLY VERB FOCUS:` block at the top (any text may sit between
  `FOCUS` and the colon). It runs to `WEEKLY VOCABULARY`, the first `#`
  line, or end of file, and is sent to the Story and Warmup/Grammar
  passes.
- For each day, `# MONDAY STORYBOARD` … with the day's bullets. The first
  lines before `Examples` (e.g. `Introduce "feel" – "sentirse"`) become
  that day's **focus line**, used by the Examples pass.
- For each day, a vocabulary block. It is the only vocabulary source the
  Vocabulary pass may use:
  ```
  # === VOCAB MONDAY ===
  light-headed – mareado / mareada
  # === END VOCAB MONDAY ===
  ```

A missing day or VOCAB block stops the run before any model call (exit 1).

Optional:

- **WEEK NOTES**: real facts and cast limits for the whole week, such
  as clinic hours, who appears on which day, and scope of practice. Sent
  to the Story, Warmup/Grammar, Examples and Student Questions passes,
  which are told to obey them. Write them as facts, not instructions.
  ```
  # === WEEK NOTES ===
  ...
  # === END WEEK NOTES ===
  ```
- **STUDY NOTES** for one day: exact source material such as
  certification practice questions with answers. Only the Examples and
  Student Questions passes see it, and only for that day. Examples
  become one item per question and the dialogue is waived. The day's
  bullets must still say what the character is doing, because the Story
  pass can't see the notes.
  ```
  # === STUDY NOTES SATURDAY ===
  ...
  # === END STUDY NOTES SATURDAY ===
  ```
- **Weekly corrections**: week-specific find/replace pairs, applied
  after the base corrections.
  ```
  #BEGIN DICTIONARY: WEEKLY_CORRECTIONS
  wrong phrase → right phrase
  #END DICTIONARY: WEEKLY_CORRECTIONS
  ```

## 5. MAIN pipeline (`pipeline.py`)

Before any model call: the arguments are resolved, the template is
checked for every rule block the passes need (`passes.check_template`),
the storyboard is parsed and validated, and the Ollama preflight runs
(server reachable, model installed). `--check` stops here.

Then, one model call per pass. Each pass sees only the template blocks
listed for it in `passes.PASS_RULES`, plus the layers already written:

1. **vocabulary**: from each day's VOCAB block only.
2. **story**: story bullets + finished vocabulary + verb focus + week
   notes. Sees all seven days at once so the emotional register can
   vary across the week.
3. **warmup_grammar**: each day's story bullets name the verb or tense
   to teach. Grammar is written in English here.
4. **grammar_translate**: translates only the Grammar explanation prose
   into Cuban Spanish. Quoted English targets and the Pattern Practice
   list are left untouched.
5. **examples_translation**: built from the finished story + vocabulary
   + focus line (+ study notes). Language direction is enforced:
   Spanish→English items are written in Spanish.
6. **student_questions**: whole week visible, so no question repeats.
   Hint rule: one Spanish word or a short phrase, never English, never
   the answer.
7. **self_review**: judgment only, over the assembled week (register
   variety, natural dialogue, A2 prose, the "te ves cansada" pattern).
   Counts, hints and vocabulary are left to code.

After each of passes 1–6, the pass's output must contain every day and
every section that pass was asked for. If not, the pass is run once
more (`config.PASS_COVERAGE_RETRIES`), and if it is still incomplete, it
is kept with a warning.

The self-review returns the whole week. Its answer replaces the week
only if every day and section survived and its length is 70–150% of
the original (`commonFunctions.accept_full_week_review`). Otherwise the
un-reviewed week is kept with a warning.

Then: base + weekly corrections (`BASE_CORRECTIONS` in
`commonFunctions.py`), hint check, structural validation, write
`NN_MAIN_PASSPIPELINE_<ts>.md` and `mainSupport.md`.

## 6. Five-Minute pipeline (`supportPipeline.py`)

Inputs: the MAIN lesson (usually `mainSupport.md`, or the corrected
`NN_MAIN_corrected.md`), storyboard (for weekly corrections only),
`FiveMinuteTemplate.txt`, `promptFive.md`.

1. **generate**: one call. The prompt is the Five-Minute template + the
   English half of each day's Story + each day's Vocabulary + the
   prompt file. Coverage is checked as above, with one retry.
2. **self_review**: one narrow check. In Grammar Focus, a character must
   be the subject ("Marisol tells…"), not the word itself ("'have'
   shows…"). Guarded the same way as the MAIN review.

Then corrections, hint check, validation, write
`NN_FIVEMIN_PASSPIPELINE_<ts>.md`.

## 7. Talking to Ollama (`ollama_client.py`, `config.py`)

- **Streaming** `/api/generate`. `requests` uses a connect timeout of
  10 s and a **read (inactivity) timeout of 300 s**: the call fails only
  if Ollama sends nothing for 300 s. A long, steady generation never
  trips it. The 300 s includes the wait for the first token (model load +
  prompt processing).
- **Retries**: connection errors, timeouts, HTTP 5xx, an empty answer,
  or a stream that ends before "done" are retried twice (after 10 s,
  then 30 s). HTTP 4xx and a missing model are not retried.
- **Recorded per call**: done_reason, prompt/response tokens, wall time,
  seconds to first data, longest pause between tokens, attempts. Also
  the thinking trace (debug mode).
- **`done_reason=length`** (context exhausted) is logged as a warning;
  coverage checks then catch the missing content.
- **Generation options** (`config.GENERATION_OPTIONS`): temperature 0.5,
  num_ctx 65536, num_predict -1. `think` is deliberately not set: on
  Aug 28, 2026, `think: False` made the model stop after one day.

## 8. Runs, checkpoints, resume (`runs.py`)

Every run creates `RAG/runs/<id>_<MAIN|FIVEMIN>_<timestamp>/`:

| File | Contents |
|---|---|
| `manifest.json` | machine, mode, Ollama URL, model, input files + SHA-256, finished steps, per-call timings, status, outputs |
| `run.log` | every message with timestamps; tracebacks for unexpected errors |
| `checkpoints/` | MAIN: `state.json` (all sections so far) after each pass, `self_review.md`. Five-Minute: raw attempts, `five_generated.md`, `five_reviewed.md` |
| `debug/` | (Debug only) each call's prompt, response, thinking trace, metadata |

`--resume` (no value) picks the newest unfinished run of that kind for
that week. `--resume <folder name>` picks a specific one. Finished steps
are skipped. If a storyboard, template or prompt file has changed since
the run started (SHA-256 differs), resume is refused, because the saved
steps were built from the old text.

Output files are written to a temp file and renamed, so an interrupted
write never leaves half a lesson.

## 9. Errors and exit codes (`errors.py`, `cli.py`)

| Code | Meaning | Examples |
|---|---|---|
| 0 | success | |
| 1 | input problem | file not found (with did-you-mean), storyboard missing a day/VOCAB block, template missing a rule block, bad flag, resume mismatch, machine can't be detected |
| 2 | Ollama problem | can't connect, model not installed, silent > timeout, HTTP error, empty answer (after retries) |
| 3 | lesson written but structurally incomplete | a day or required section missing or empty |
| 4 | unexpected error (bug) | traceback in `run.log` |
| 130 | Ctrl-C | |

Every failure prints one `ERROR:` line, no traceback. If a run folder
exists, it also prints the finished steps and the exact `--resume`
command. Each run ends with a summary listing every warning once.

## 10. Testing without the Studio

`sourcecode/tools/mock_ollama.py` imitates Ollama: well-formed
nonsense, shaped like whatever pass is asking. It tests the plumbing,
not lesson quality.

```bash
python3 tools/mock_ollama.py --port 11500 &                 # normal
python3 tools/mock_ollama.py --port 11501 --mode hang &     # also: error500, flaky,
                                                            # empty, dropday, badreview, failat:N
python3 pipeline.py 41 Week41StoryBoard.md MainLessonTemplate.txt Debug \
    --machine macbook --studio-ip 127.0.0.1:11500
```

Verified on Oct 20, 2026: with identical model answers, the refactored
code produces byte-identical prompts (all 9) and lesson files to the
pre-refactor code (tag `pre-refactor-oct20`). Each failure mode above
produced the expected message and exit code, and `--resume` continued
correctly after a failure at pass 4 and after Ctrl-C.

## 11. Reference run: Week 41, Oct 20, 2026 (Macbook → Studio)

Zero warnings, no retries, every call `done_reason=stop`, both reviews
accepted.

| Call | Seconds | First data (s) | Prompt tokens | Response tokens* |
|---|---:|---:|---:|---:|
| vocabulary | 40 | 15 | 2,003 | 1,440 |
| story | 718 | 36 | 7,125 | 30,827 |
| warmup_grammar | 211 | 31 | 6,238 | 8,736 |
| grammar_translate | 77 | 8 | 1,718 | 3,571 |
| examples_translation | 345 | 37 | 7,467 | 14,547 |
| student_questions | 189 | 29 | 5,982 | 7,080 |
| self_review | 258 | 45 | 7,928 | 10,850 |
| **MAIN total** | **1,838 (30.6 min)** | | | |
| five (generate) | 463 | 24 | 4,910 | 19,813 |
| five_selfreview | 66 | 12 | 2,420 | 2,861 |
| **Five-Minute total** | **529 (8.8 min)** | | | |

\* Response tokens include the thinking trace, which is most of them.
In the story pass, about 26,200 of 30,827 were thinking.

Output vs. the Claude-built baseline (`41_*_rewrite.md`): same
structure, total length within 2% (MAIN 4,897 vs 5,005 words;
Five-Minute 1,348 vs 1,317), and identical vocabulary counts.

### Studio run (local mode), same day

Same code (`main` at `61473ce`), run on the Studio itself: `machine=studio`,
`mode=local`, Ollama at localhost. Zero warnings, no retries, both
self-reviews accepted.

| | Macbook → Studio | Studio (local) |
|---|---:|---:|
| MAIN total | 30.6 min | 33.6 min |
| Five-Minute total | 8.8 min | 9.9 min |
| Story pass | 718 s | 755 s |
| Longest wait for first data | 45 s | 44 s |
| **Longest pause between tokens** | not measured | **0.7 s** |

- The network adds nothing measurable; the Studio's model does all the
  work in both modes. Timing differences between runs are model
  variation (the warmup_grammar pass thought for 14,955 vs 8,736 tokens).
- Story-pass prompts were identical on both machines (7,125 tokens).
  The lesson text differs between the two runs, as expected at
  temperature 0.5. Structure, section lists, vocabulary counts and
  day count match; MAIN length 4,698 vs 4,897 words.
- **Timeout:** the longest pause between tokens was 0.7 s and the
  longest wait for a first token 45 s. The 300 s inactivity timeout is
  about 7× the worst real wait. A value near 120 s would still allow
  for a slow model load and catch a hang much sooner. Not changed yet
  (`config.INACTIVITY_TIMEOUT`).

## 12. Change history

**Oct 20, 2026 — client/server refactor** (commits `efd79a7`,
`5cf2198`, `42a596e` on `refactor/client-server-pipeline`; rollback tag
`pre-refactor-oct20`):

- Macbook/Studio detection, client mode over the network, `--machine`,
  `--studio-ip`.
- Streaming client with inactivity timeout and retries (the old
  `requests.post` had no timeout, so a stalled Studio hung forever).
- Checkpoints after every step, `--resume`, run folders, `run.log`,
  end-of-run summary.
- `--check`, typed errors, exit codes, no tracebacks.
- Corrections:
  - **Weekly verb focus was never sent to the model.** Since Week 35
    the storyboard header read "WEEKLY VERB FOCUS (reference only …):",
    wording written for the retired `generateMain.py`. The pass
    pipeline matched only the bare header, so every pass-pipeline run
    sent an empty verb focus. Fixed in the parser; the Week 41 header is
    now plain.
  - Self-review output replaced the week unchecked → now guarded.
  - A failed pass lost all earlier passes → checkpoints + resume.
  - `send_to_ollama` could return `str(json)` as if it were lesson text.
  - Missing template blocks / storyboard days / VOCAB blocks were
    mid-run warnings → now checked before the first call.
  - A pass dropping a whole day went unreported until assembly → now
    detected per pass, with one retry.
  - Validation only warned → structural gaps now exit 3 (the lesson is
    still written).
  - Unused `convert_markdown_to_docx()` and its top-level `pypandoc`
    import removed.
  - Atomic file writes. `ALL_DAYS` defined once.
- Debug files moved from `sourcecode/debug/` to each run's `debug/`.

Earlier history: `sourcecode/README.md` ("Fixed so far") and the git log.

## 13. Known gaps / next phase

Prompt and template work (not code):

- `BASE_CORRECTIONS`: "almuerzo en bolsa" → **"almuerzo en llevar"** looks
  wrong. Standard is "almuerzo para llevar".
- Week 41 review (Thursday) showed:
  - "bring = traer o llevar" in Grammar, and a Warmup item hinted
    "(llevar)", which blurs bring/take.
  - A WEEK NOTES rule ("she never names a disease") leaking into the
    story as narration.
  - A Translation item with the wrong gender and wrong person.
  - Examples mostly copying story sentences.
- Most generation time is thinking (about 85% of tokens in the story
  pass). That's worth testing per pass for speed and quality; note the
  Aug 28 `think: False` regression.
- No deterministic checks yet for Mini Story sentence length (8–12
  words), comma limit, the and/but/because rule, or Translation Practice
  language direction. These are prompt-only today.
- Model Spanish still needs a read: English titles inside Spanish
  sentences, wrong gender on acronyms, the answer repeated in a hint.
- The 300 s timeout is about 7× the longest wait seen (45 s). Use the
  "longest pause" figures from the next runs to decide whether to lower
  it.
