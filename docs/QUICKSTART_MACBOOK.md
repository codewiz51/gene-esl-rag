# Quick start: weekly lesson run on the Macbook (Ollama on the Studio)

The pipeline code runs on the Macbook. Every model call goes over the
network to Ollama on the Studio (192.168.4.47), using
`pipeline-qwen38:latest`. The Macbook detects this by itself — no flag
needed.

## 0. Before the first run of the week

On the **Studio**: awake, on the network, Ollama running. Nothing else.

On the **Macbook**:

```bash
cd ~/RAG && git pull                 # GitHub is the source of truth
rag                                  # activates ~/rag_env
cd ~/RAG/sourcecode                  # the scripts run from here
```

The storyboard goes in `~/RAG/source_docs/WeeklyTemplates/` as
`WeekNNStoryBoard.md`.

If the code changed since the last run, run the unit tests first (2 seconds):
`python3 -m unittest discover -s tests -t .`

## 1. Check (5 seconds, generates nothing)

```bash
python3 pipeline.py 42 Week42StoryBoard.md MainLessonTemplate.txt Debug --check
```

Expect:

```
pipeline.py - machine=macbook (detected from $HOME=/Users/Gene), mode=client -> Ollama on the Studio at http://192.168.4.47:11434, model=pipeline-qwen38:latest, inactivity timeout=120s
WEEKLY VERB FOCUS found (6 lines).
WEEK NOTES found.
Ollama OK at http://192.168.4.47:11434; model 'pipeline-qwen38:latest' is installed.
Check passed: inputs, template and Ollama are all OK. Nothing generated (--check).
```

Anything else is a one-line `ERROR:` saying what to fix (see section 5).

## 2. Run the MAIN lesson (~30 minutes)

```bash
time python3 pipeline.py 42 Week42StoryBoard.md MainLessonTemplate.txt Debug ; afplay /System/Library/Sounds/Glass.aiff
```

A progress line prints every 30 seconds. Long stretches of
`thinking ... / 0 response tokens` are normal — qwen reasons before it
writes (the story pass thinks for about 10 minutes).

Writes to `~/RAG/source_docs/WeeklyLessons/`:
- `42_MAIN_PASSPIPELINE_<timestamp>.md` — the lesson
- `mainSupport.md` — same text, fixed name, input for step 3

## 3. Run the Five-Minute lesson (~9 minutes)

```bash
time python3 supportPipeline.py 42 mainSupport.md Week42StoryBoard.md FiveMinuteTemplate.txt promptFive.md Debug ; afplay /System/Library/Sounds/Glass.aiff && say "pipeline done"
```

To build it from your corrected main lesson instead, replace
`mainSupport.md` with `42_MAIN_corrected.md`.

Writes `42_FIVEMIN_PASSPIPELINE_<timestamp>.md`.

## 4. Read the summary

Each run ends with a box like this:

```
======================================================================
MAIN lesson, week 41: done
======================================================================
Model calls: 7, total 30.6 min
  pass_vocabulary        40s  first data   15s  longest pause  …s  done=stop
  pass_story            718s  first data   36s  longest pause  …s  done=stop
  ...
Wrote: .../41_MAIN_PASSPIPELINE_20261020_071933.md
No warnings.
======================================================================
```

Every warning from the run is listed there once. `HINT [...]` warnings
point at hints to fix by hand. Full details are in the run folder:
`~/RAG/runs/42_MAIN_<timestamp>/run.log` (prompts, responses and
thinking traces are in its `debug/` folder).

## 5. When something goes wrong

| Exit | Message starts with | What to do |
|---|---|---|
| 1 | `Storyboard file ... not found` / `... can't be used` / `... is missing block(s)` | Fix the file name or the storyboard/template; rerun. |
| 2 | `Cannot reach Ollama at http://192.168.4.47:11434` | Wake the Studio, check Ollama is running there; rerun with `--resume`. |
| 2 | `Model 'pipeline-qwen38:latest' is not installed` | On the Studio: `ollama list`. |
| 2 | `Ollama went silent for more than 120s` | Studio hung or asleep. Check it, then rerun with `--resume`. |
| 3 | `The lesson was written, but N structural problem(s)` | A day or section is missing — listed in the summary. Fix by hand, or rerun. |
| 130 | `Interrupted (Ctrl-C)` | Rerun with `--resume` when ready. |

Connection drops, timeouts and server errors are retried twice
automatically before the run stops.

### Resume

Every finished pass is saved. To continue a stopped run, repeat the same
command with `--resume` added:

```bash
python3 pipeline.py 42 Week42StoryBoard.md MainLessonTemplate.txt Debug --resume
```

It skips the passes already done. It refuses if you edited the
storyboard or template since the run started (the saved passes came from
the old version) — then start a fresh run without `--resume`.

## 6. Options

| Flag | Use |
|---|---|
| `--check` | Validate inputs + Ollama connection only. |
| `--resume` | Continue the newest unfinished run for that week. |
| `--studio-ip 192.168.4.50` | The Studio's address changed. |
| `--timeout 600` | Allow longer silence before a call counts as hung (default 120s). |
| `--machine macbook` | Only if auto-detection ever fails. |
| `NoDebug` (instead of `Debug`) | Skip prompt/response/thinking files. `run.log` and checkpoints are always written. |

## 7. After the run

1. Correct the lessons (save as `42_MAIN_corrected.md`,
   `42_FIVEMIN_corrected.md` in `WeeklyLessons/`).
2. `python3 toDocx.py 42` for the .docx files.
3. Commit what you want kept and `git push`.

Running on the Studio itself is the same commands; it detects that it is
the Studio and uses its own Ollama at localhost. `--studio-ip` is refused
there.
