# Backup pipeline: AnythingLLM ingest, closeout plan, run card (summary, Oct 20-21, 2026)

## Goal
The qwen/Python ESL pipeline is stable and now a backup (Claude drafts lessons day to day). Gene wanted the GitHub repo ingested into AnythingLLM (ALLM, embedder bge-m3 via Ollama) so the backup can be queried locally, then wanted a proper closeout (git cleanup, tests, docs, handoff) and a run card in his notes app. Embedded finding: GitHub is source of truth; ingest was done from branch `refactor/client-server-pipeline`.

## GitHub ingest procedure (what worked)
1. Workspace -> upload dialog -> Data Connectors -> GitHub Repo.
2. Repo URL, branch, personal access token. Fine-grained token, one repo, Contents read-only, ~30-day expiry. Classic token with `repo` scope only as fallback. Revoke after ingest.
3. Collect, then **move files to workspace and Save and Embed**. Collect alone only downloads files; this was the cause of an early "MA-only" answer.
4. It is a one-time snapshot, not a sync. Use ignore-paths (bin/, obj/, node_modules/, lock files, build output, binaries, big data).
5. Chunk size/overlap are global (Settings -> Text Splitter & Chunking), not per workspace. Suggested 1500-2000 chars, ~200 overlap, set before embedding. (Earlier advice that they were per-workspace was wrong.)
6. Workspace: Query mode, snippets 8-10, similarity threshold none/low, agent tools off when testing retrieval.

## Test findings
- First test answer came from qwen's direct file access, not the vector DB. Agent/filesystem tools bypass Query mode and citations.
- The existing workspace is mixed: about 390 entries (all lessons, Mometrix MA/CMA study files, a few python files).
- With the python/docs pinned, answers were correct but pinning injects the full docs, so it proved nothing about retrieval.
- After unpinning: retrieval worked. Citations included passes.py, pipeline.py, state.py, commonFunctions.py, supportPipeline.py, README.md, PROJECT_DOCUMENTATION.md, and the Zambia-free lesson/Mometrix material did not crowd them out. Two independent runs agreed (seven passes, 70-150% acceptance guard, self-review checks).
- A practical "exact commands to run main and five-minute" query returned the QUICKSTART_MACBOOK.md commands with citations.
- Decision: no separate code-only workspace for now; build one only if vague questions drift to lesson material.
- Also retrieved: CODE_REVIEW_ANSWER_KEY_7cf6883.md and QWEN_PLAN_COMPARISON.md. Point-in-time docs that can contradict current code; recommended removing them from the workspace (Remove, not delete).
- Speed: qwen on M4/36 GiB is slow (prompt processing). Options: point ALLM at Studio Ollama, smaller model for retrieval tests, fewer snippets, check thinking mode and num_ctx. Gene: slow is worth it.

## Still to verify
- Canary query: "What does MODEL_NAME point at in commonFunctions.py?" Expect `pipeline-qwen38:latest` with a code citation (not yet run).
- Confirm qa_utils.py is embedded (hint checker) and consistent with commonFunctions.validate_markdown().
- toDocx.py vs the md2docx shell function: confirm which is current (Gene's working path is md2docx: Pandoc, reference.docx, single column, Times New Roman).
- Spot-check the 70%/150% bounds and PASS_COVERAGE_RETRIES against code.
- Re-ingest from the tagged main after merge/tag (current snapshot points at a refactor branch).

## Closeout plan (also the basis for a blog post)
1. Freeze: git status, commit.
2. Clean branches: `git fetch --prune`, `git branch --merged main`, delete only merged branches with `-d`, local and remote.
3. Tag a known-good release (e.g. v1.0-backup-pipeline), push with tags.
4. Document: README.md, requirements.txt (pip freeze from rag_env), HANDOFF.md (done, not built, model names and why, known issues, how to resume), optional DECISIONS.md. Tests first, then README so the quick-start cites commands already seen passing.
5. Cold-start test: fresh clone in /tmp, follow the quick-start; fix any gaps.
6. Loose ends: revoke GitHub token, pull on the other machine, re-ingest tagged main.
- Tests: required. Existing runner is `python3 -m unittest discover -s tests -t .` (use that, not pytest). Commit sample data under tests/ (fictional sample storyboard, known-good sample output). Deterministic tests for parsing/rules/state, mocked Ollama for pass sequencing and error handling, one optional slow smoke test on the Studio.
- Blog/LinkedIn/Substack angle: "walk away and sleep at night." Outline: the problem of a deployed project you don't trust; the closeout sequence; the two-command hello world; the honest slips (qwen reading files instead of vectors, collected-not-embedded); the close. Concrete before/after numbers recommended.

## Run card (Gene's notes-app note, "How to run a lesson pipeline"; corrected version)
Swap week number/storyboard name. No `#` comment lines in pasted zsh commands.

Pre-flight (on whichever machine runs the pipeline):
```
cd ~/RAG && git pull
rag
cd ~/RAG/sourcecode
```
(`rag` activates ~/rag_env. Storyboard goes in ~/RAG/source_docs/WeeklyTemplates/ as WeekNNStoryBoard.md.) Unit tests if code changed:
```
python3 -m unittest discover -s tests -t .
```
Check (5 s, generates nothing; expect "Check passed"):
```
python3 pipeline.py 42 Week42StoryBoard.md MainLessonTemplate.txt Debug --check
```
Combined run (Main ~30 min, then Five-Minute ~9 min; support runs only if main succeeds; chime always; voice says done or failed):
```
time python3 pipeline.py 42 Week42StoryBoard.md MainLessonTemplate.txt Debug && time python3 supportPipeline.py 42 mainSupport.md Week42StoryBoard.md FiveMinuteTemplate.txt promptFive.md Debug ; r=$? ; afplay /System/Library/Sounds/Glass.aiff ; if [ $r -eq 0 ]; then say "pipeline done"; else say "pipeline failed"; fi
```
Outputs in ~/RAG/source_docs/WeeklyLessons/: 42_MAIN_PASSPIPELINE_<timestamp>.md, mainSupport.md, 42_FIVEMIN_PASSPIPELINE_<timestamp>.md. For Five-Minute from a corrected Main (recommended Week 39+), use 42_MAIN_corrected.md in place of mainSupport.md. After the run: correct both lessons, save as NN_MAIN_corrected.md / NN_FIVEMIN_corrected.md, make docx with md2docx, commit and push.
Notes: MacBook auto-detects itself and calls Ollama on the Studio at 192.168.4.47:11434 (no flags unless IP changes). Long "thinking / 0 response tokens" in the story pass is normal. If a run dies, rerun with `--resume` (refuses if storyboard/template changed). `Debug` writes prompts/responses/thinking; `NoDebug` skips.
To verify once: point the command at a nonexistent storyboard and run `echo $?`; nonzero confirms the && chain and the "failed" announcement work.

## Failure scenarios
- The MacBook cannot run the pipeline (18 GiB, ~12B model at best; inadequate). It needs the Studio.
- Internet down (e.g. Dobson outage, the likeliest case): LAN, Studio, Ollama, ALLM, bge-m3, pipeline all work; `git pull` fails (skip it, pull both machines beforehand); web-dependent steps (search, research) fail. Realistic test: unplug the router/modem, not MacBook Wi-Fi.
- Studio down or out of town: generate lessons with Claude from storyboard and templates, or draft by hand; MacBook 12B models only for narrow checks (spelling, bullet counts, Spanish naturalness).
- Both down: manual, using repo and notes.
- Second opinion: gemma4 in a clean thread, giving it the source and question, not qwen's answer. Gene's assessment: the backup is roughly 50-75% of Claude's capability, workable if responses are verified.

## Apple Notes via ALLM @agent
- Integration exists (App Integrations -> Apple Notes, On).
- Found "How to run a lesson pipeline" from a vague description and quoted the pre-flight commands correctly. Siri could not.
- Mechanism is literal keyword search, not meaning: multi-word queries and plurals ("subscriptions") missed; the model retried keywords until one hit (~2 min). Fix: add a Keywords line near the top of important notes (singular and plural).
- Cannot see checkbox state; said the note had no checkboxes and counted 33 items (about 37 actual). Known limitation; use `[ ]`/`[x]` text markers if state matters. Don't let the agent edit the master list.
- Gene's use: finding the note matters more than summarizing it; open and read it yourself before running commands.
- Recommended (not confirmed): keep RUNCARD.md in the repo as the versioned master and the note as the quick-glance copy.

## Open items
Run canary and verify list above; finish closeout and tag; re-ingest tagged main; remove point-in-time review docs from the workspace; revoke token; add Keywords lines to notes; draft the blog post.
