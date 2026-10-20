# First-time setup: everything needed before the first pipeline run

Do this once per machine. After it, the weekly routine is in
`QUICKSTART_STUDIO.md` (running on the Studio) or `QUICKSTART_MACBOOK.md`
(running on the Macbook, with the model on the Studio).

**Reference setup** (Oct 20, 2026, the versions the pipeline was last
tested with):

| Item | Studio | Macbook |
|---|---|---|
| Hardware | Mac Studio M4 Max, 36 GB | MacBook Pro M3 Pro, 18 GB |
| macOS | 27.0.1 | |
| Ollama | 0.40.6 | not needed for the pipeline |
| Model | `pipeline-qwen38:latest` (over `qwen3.8:27b-mlx`, 18 GB) | not needed |
| Python | 3.14.7 (Homebrew) in `~/rag_env` | 3.14.8 (Homebrew) in `~/rag_env` |
| Python packages | requests 2.34.2, pypandoc 1.17 | requests 2.34.2 |
| pandoc | 3.11 (Homebrew) | optional |

The code itself needs **Python 3.7 or later** and has been tested on
3.10, 3.13 and 3.14.

**Who needs what:**

- **The Studio** runs the model, so it needs everything below.
- **The Macbook**, as a client, needs only git, Python with `requests`,
  and the repo. It does every step except step 2.

---

## 1. Command-line tools: Homebrew, git, Python, pandoc

```bash
# Apple's command-line tools (gives git)
xcode-select --install

# Homebrew, from https://brew.sh (follow the install line on that page)

brew install python      # Python 3 (3.14 at the time of writing)
brew install pandoc      # only needed for toDocx.py (.md -> .docx)
```

Check:

```bash
git --version
python3 --version         # 3.7 or later
pandoc --version | head -1
```

## 2. Ollama and the model (Studio only)

1. Install Ollama from https://ollama.com (the Mac app), or with
   `brew install ollama`. Check with `ollama --version`.
2. Start it, either by opening the Ollama app, or in its own Terminal
   tab:
   ```bash
   OLLAMA_HOST=0.0.0.0 ollama serve
   ```
   `OLLAMA_HOST=0.0.0.0` lets the Macbook reach it (see step 7). Leave
   that tab open while the pipeline runs.
3. Pull the base model, then build the pipeline model from the recipe
   in the repo (the repo is cloned in step 3):
   ```bash
   ollama pull qwen3.8:27b-mlx
   ollama create pipeline-qwen38 -f ~/RAG/pipeline-qwen38.modelfile
   ollama list | grep -E "qwen3.8:27b-mlx|pipeline-qwen38"
   ```
   `qwen3.8:27b-mlx` is the base tag installed on the Studio (`ollama
   list`). If a pull can't find it, look up the current Qwen 3.8 27B MLX
   tag on https://ollama.com and change the `FROM` line in the Modelfile
   to match.
   `pipeline-qwen38.modelfile` adds the sampling settings (temperature
   0.5, top_k 20, top_p 0.9, min_p 0, repeat_penalty 1, num_ctx 65536)
   and a short, mechanical system prompt. It deliberately has **no
   persona**: the lesson templates are the only instructions the model
   sees. Don't use `gene-qwen38` (the AnythingLLM chat persona) for the
   pipeline.
4. **Memory:** the model takes about 18 GB, plus room for its 64k-token
   context, on a 36 GB machine. Don't run another large model (gemma4,
   ornith, medgemma…) while a lesson run is going. Ollama will unload
   one, but the run gets slower or fails.

`*-mlx` models need Apple Silicon and an Ollama version with MLX support.

## 3. The repository

The repo lives on GitHub and is the source of truth:

```bash
git clone https://github.com/codewiz51/gene-esl-rag.git ~/RAG
```

The repo is private, so git asks you to sign in. A GitHub personal
access token works as the password, or run `gh auth login` first if you
use the GitHub CLI. If `~/RAG` already exists, `cd ~/RAG && git pull`
instead.

**Folders the code expects**, all relative to the repo root (the code
finds the root from where `sourcecode/` sits, so the repo could live
elsewhere, but every doc and alias assumes `~/RAG`):

| Folder / file | Used for |
|---|---|
| `sourcecode/` | the pipeline; run every command from here |
| `source_docs/WeeklyTemplates/` | **inputs:** `WeekNNStoryBoard.md`, `MainLessonTemplate.txt`, `FiveMinuteTemplate.txt`, `promptFive.md`, `reference.docx` (Word styles for `toDocx.py`) |
| `source_docs/WeeklyLessons/` | **outputs:** `NN_MAIN_PASSPIPELINE_<time>.md`, `NN_FIVEMIN_PASSPIPELINE_<time>.md`, `mainSupport.md`, and your `NN_*_corrected.md` files |
| `runs/` | created automatically: one folder per run (log, checkpoints, debug files). Git-ignored, so it stays on each machine. |
| `pipeline-qwen38.modelfile` | the model recipe (step 2) |
| `Modelfile` (repo root) | historical: an old Qwen 2.5 setup, not used by the pipeline |

## 4. Python environment

The convention is a virtual environment at `~/rag_env`:

```bash
python3 -m venv ~/rag_env
source ~/rag_env/bin/activate
pip install -r ~/RAG/requirements.txt     # requests (+ pypandoc, optional)
```

The pipeline needs only `requests`. `pypandoc` is optional, since
`toDocx.py` falls back to the `pandoc` command.

**The `rag` shortcut.** Add one line to `~/.zshrc`, then open a new
Terminal window:

```bash
alias rag='source ~/rag_env/bin/activate && cd ~/RAG/sourcecode'
```

The Studio's current alias is `source ~/rag_env/bin/activate` only, so
it leaves you in `~/RAG`; that's why the quick starts say to
`cd ~/RAG/sourcecode` after it. The line above does both.

## 5. Machine settings in the code

`sourcecode/config.py` holds every setting. Two parts are tied to
specific machines:

```python
MACHINES = {
    "macbook": {"home": "/Users/Gene", "hostname_hints": ["macbook"], "mode": "client"},
    "studio":  {"home": "/Users/gene", "hostname_hints": ["studio"],  "mode": "local"},
}
DEFAULT_STUDIO_IP = "192.168.4.47"
```

- A machine is recognised by its exact home folder (`echo $HOME`),
  cross-checked against its hostname (`hostname`).
- **New Mac or new username:** edit the matching entry, or add one. A
  machine with `"mode": "local"` runs the model itself; `"client"` sends
  model calls to the Studio.
- Without an edit, `--machine studio` or `--machine macbook` overrides
  detection for a single run.
- Other settings in the same file: model name, timeouts, retries, the
  context warning level.

## 6. Verify the code (no model needed)

```bash
rag                                            # activate + cd (step 4)
python3 -m unittest discover -s tests -t .
```

Expect `Ran 90 tests … OK` in a few seconds. This proves Python, the
packages and the repo are right before any model is involved.

## 7. Network: Macbook → Studio only

Skip this if you only run on the Studio.

1. **The Studio's Ollama must listen on the network:** start it with
   `OLLAMA_HOST=0.0.0.0 ollama serve`. If you use the Ollama app instead,
   run `launchctl setenv OLLAMA_HOST 0.0.0.0` once, then quit and reopen
   the app.
2. **Firewall:** if macOS asks whether Ollama may accept incoming
   connections, allow it.
3. **A fixed address for the Studio:** reserve 192.168.4.47 for it in
   the router (DHCP reservation). If the address ever changes, pass
   `--studio-ip <new address>`, or change `DEFAULT_STUDIO_IP` in
   `config.py`.
4. **Test from the Macbook:**
   ```bash
   curl -s -m 5 http://192.168.4.47:11434/api/tags | head -c 200
   ```
   A JSON list of models means the network path works.

## 8. First real check

From `~/RAG/sourcecode`, with the venv active:

```bash
python3 pipeline.py 41 Week41StoryBoard.md MainLessonTemplate.txt Debug --check
```

Expect `machine=studio … mode=local` (or `machine=macbook … mode=client`),
`Ollama OK … model 'pipeline-qwen38:latest' is installed`, and
`Check passed`. It takes seconds and generates nothing.

You're set up. Each week, follow the quick start for the machine you're
on. The first full run of Week 41 (about 45 minutes) is a good end-to-end
test: compare it with the tagged output `week41-review-fixes-output`.

## If something fails

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'requests'` | the venv isn't active: run `rag` (or `source ~/rag_env/bin/activate`), or `pip install -r ~/RAG/requirements.txt` |
| `Can't tell which machine this is` | step 5: add the machine to `MACHINES`, or pass `--machine` |
| `Cannot reach Ollama at http://localhost:11434` | Ollama isn't running on this Mac (step 2) |
| `Cannot reach Ollama at http://192.168.4.47:11434` | step 7: Studio awake? `OLLAMA_HOST=0.0.0.0`? right IP? |
| `Model 'pipeline-qwen38:latest' is not installed` | step 2.3: `ollama create pipeline-qwen38 -f ~/RAG/pipeline-qwen38.modelfile` |
| `toDocx.py` fails | `brew install pandoc` |
| `can't open file … pipeline.py` | you're not in `~/RAG/sourcecode` |
