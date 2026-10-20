# Quick start: weekly lesson run on the Studio (local mode)

Same pipeline, same commands as the Macbook (`QUICKSTART_MACBOOK.md`).
The only difference is where the model calls go: on the Studio the
pipeline detects `$HOME=/Users/gene` and uses its own Ollama at
`http://localhost:11434`. No network, no `--studio-ip`.

## 0. Before the run

```bash
cd ~/RAG && git pull          # GitHub is the source of truth
rag                           # activates ~/rag_env; leaves you in ~/RAG
cd ~/RAG/sourcecode           # the scripts run from here
```

(On the Studio, `rag` leaves you in `~/RAG`, not `~/RAG/sourcecode`.)

If the code changed since the last run, run the unit tests first (2 seconds):
`python3 -m unittest discover -s tests -t .`

## 1. Check (5 seconds)

```bash
python3 pipeline.py 42 Week42StoryBoard.md MainLessonTemplate.txt Debug --check
```

Expect `machine=studio (detected from $HOME=/Users/gene), mode=local ->
Ollama on this machine at http://localhost:11434` and `Check passed`.

## 2. Run both lessons (~44 minutes)

```bash
time python3 pipeline.py 42 Week42StoryBoard.md MainLessonTemplate.txt Debug ; afplay /System/Library/Sounds/Glass.aiff
time python3 supportPipeline.py 42 mainSupport.md Week42StoryBoard.md FiveMinuteTemplate.txt promptFive.md Debug ; afplay /System/Library/Sounds/Glass.aiff && say "pipeline done"
```

Reference run (Week 41, Oct 20, 2026): MAIN 33.6 min, Five-Minute 9.9
min, zero warnings. Output goes to `~/RAG/source_docs/WeeklyLessons/`;
the run folder (log, checkpoints, debug) to `~/RAG/runs/`.

Running on the Studio while the Macbook also uses it for another run
makes both slower, since they share one model.

## 3. Problems, resume, options

Identical to the Macbook guide: exit codes, `--resume`, `--check`,
`--timeout`. Two Studio-specific notes:

- `--studio-ip` is refused on the Studio (exit 1). That is intended.
- "Cannot reach Ollama at http://localhost:11434" means Ollama is not
  running on the Studio: open the Ollama app, or run `ollama serve`.

## 4. Keeping the machines in sync

Lessons you generate are local files on the machine that made them.
Commit the ones you want to keep and `git push`, then `git pull` on the
other machine. Run folders (`runs/`) are never committed.
