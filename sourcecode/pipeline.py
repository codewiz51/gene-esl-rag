#!/usr/bin/env python3
"""
pipeline.py - MAIN lesson orchestrator.

Usage (same positional arguments as always; flags are optional):
    python3 pipeline.py <identifier> <storyboard.md> <template.txt> [Debug|NoDebug] [flags]

Examples:
    python3 pipeline.py 41 Week41StoryBoard.md MainLessonTemplate.txt Debug
    python3 pipeline.py 41 Week41StoryBoard.md MainLessonTemplate.txt Debug --check
    python3 pipeline.py 41 Week41StoryBoard.md MainLessonTemplate.txt Debug --resume
    python3 pipeline.py 41 ... --studio-ip 192.168.4.47      (Macbook, non-default Studio IP)

The machine is detected automatically: on the Macbook every model call
goes to Ollama on the Studio; on the Studio it goes to localhost. See
config.py, and docs/QUICKSTART_MACBOOK.md.

Writes NN_MAIN_PASSPIPELINE_<ts>.md into source_docs/WeeklyLessons/, plus
mainSupport.md (fixed name) as the input for supportPipeline.py. Each run
also gets a folder in RAG/runs/ with run.log, checkpoints and debug files.

Exit codes: 0 ok, 1 input problem, 2 Ollama problem, 3 lesson written but
structurally incomplete, 4 unexpected error, 130 Ctrl-C. See errors.py.
"""

import logging
import os

import cli
import commonFunctions as common
import config
import ollama_client
import passes
import runlog
import runs
from errors import InputError, ResumeError, ValidationFailed
from qa_utils import lint_hints
from state import ALL_DAYS, WeekState
from storyboard_utils import (
    extract_day_focus,
    extract_day_story_requirements,
    extract_day_study_notes,
    extract_day_vocab_suggestions,
    extract_week_notes,
    extract_weekly_verb_focus,
)

log = logging.getLogger("esl")

KIND = "MAIN"
STATE_CHECKPOINT = "state.json"
REVIEW_CHECKPOINT = "self_review.md"


def build_parser():
    p = cli.new_parser(
        "Generate the weekly MAIN lesson from a storyboard.",
        "Example:\n  python3 pipeline.py 41 Week41StoryBoard.md MainLessonTemplate.txt Debug",
    )
    p.add_argument("identifier", nargs="?", help="Week number, e.g. 41")
    p.add_argument("storyboard", nargs="?", help="Storyboard file in source_docs/WeeklyTemplates/")
    p.add_argument("template", nargs="?", help="Lesson template in source_docs/WeeklyTemplates/")
    p.add_argument("debug", nargs="?", help="Debug (default) or NoDebug")
    cli.add_common_args(p)
    return p


def validate_storyboard(story_requirements_by_day, vocab_by_day, storyboard_name):
    """Before any model call: every day needs story bullets and a VOCAB block."""
    problems = []
    for day in ALL_DAYS:
        if not story_requirements_by_day.get(day, "").strip():
            problems.append(f"{day}: no '# {day} STORYBOARD' section")
        if not vocab_by_day.get(day, "").strip():
            problems.append(f"{day}: no '# === VOCAB {day} ===' block (the vocabulary pass would invent words)")
    if problems:
        raise InputError(f"{storyboard_name} can't be used: " + "; ".join(problems))


def main(ctx):
    args = build_parser().parse_args()
    runtime = config.resolve_runtime(args.machine, args.studio_ip, args.timeout, args.model)
    log.info(f"pipeline.py - {runtime.describe()}")

    # ---- which run, which inputs -------------------------------------------
    run = None
    if args.resume:
        run = runs.find_run(common.RUNS_DIR, KIND, args.resume, identifier=args.identifier)
        runs.check_inputs_unchanged(run)
        m = run.manifest
        identifier = m["identifier"]
        storyboard_path = m["inputs"]["storyboard"]["path"]
        template_path = m["inputs"]["template"]["path"]
        for given, recorded, role in ((args.storyboard, storyboard_path, "storyboard"),
                                      (args.template, template_path, "template")):
            if given and os.path.basename(given) != os.path.basename(recorded):
                raise ResumeError(f"--resume: run {run.name} used {role} {os.path.basename(recorded)}, "
                                  f"not {given}.")
        debug_flag = cli.parse_debug(args.debug, default=m.get("debug", True))
        log.info(f"Resuming {run.name}; already finished: {', '.join(m.get('completed_steps', [])) or 'nothing'}")
    else:
        if not (args.identifier and args.storyboard and args.template):
            raise InputError("Usage: python3 pipeline.py <identifier> <storyboard.md> <template.txt> "
                             "[Debug|NoDebug] [--check] [--resume] [--machine ...] [--studio-ip IP]")
        identifier = args.identifier
        storyboard_path = cli.resolve_input(args.storyboard, common.weekly_template_dir, "Storyboard")
        template_path = cli.resolve_input(args.template, common.weekly_template_dir, "Template")
        debug_flag = cli.parse_debug(args.debug)

    storyboard_raw = cli.read_text(storyboard_path, "storyboard")
    template_text = cli.read_text(template_path, "template")

    # ---- validate everything before the first model call -------------------
    passes.check_template(template_text, os.path.basename(template_path))

    weekly_corrections = common.parse_weekly_corrections(storyboard_raw)
    corrections = common.BASE_CORRECTIONS + weekly_corrections
    if weekly_corrections:
        log.info(f"Loaded {len(weekly_corrections)} weekly correction(s) from storyboard.")

    weekly_verb_focus = extract_weekly_verb_focus(storyboard_raw)
    story_requirements_by_day = extract_day_story_requirements(storyboard_raw)
    vocab_by_day = extract_day_vocab_suggestions(storyboard_raw)
    study_notes_by_day = extract_day_study_notes(storyboard_raw)
    week_notes = extract_week_notes(storyboard_raw)
    day_focus_by_day = extract_day_focus(story_requirements_by_day)
    validate_storyboard(story_requirements_by_day, vocab_by_day, os.path.basename(storyboard_path))
    if not weekly_verb_focus:
        log.info("WEEKLY VERB FOCUS is reference-only in this storyboard (not sent to the model); "
                 "each day's focus line carries the verb.")
    if week_notes:
        log.info("WEEK NOTES found.")
    if study_notes_by_day:
        log.info(f"STUDY NOTES found for: {', '.join(study_notes_by_day)}")

    ollama_client.preflight(runtime)

    if args.check:
        log.info("Check passed: inputs, template and Ollama are all OK. Nothing generated (--check).")
        return

    # ---- run folder ---------------------------------------------------------
    if run is None:
        run = runs.new_run(common.RUNS_DIR, identifier, KIND,
                           {"storyboard": storyboard_path, "template": template_path},
                           runtime, debug_flag)
    else:
        run.set_status(runs.STATUS_RUNNING)
    ctx.run = run
    runlog.add_log_file(run.log_file)
    log.info(f"Run folder: {run.path}")
    log.debug(runtime.describe())
    common.init_run(runtime, run.debug_dir if debug_flag else None)
    prior_timings = list(run.manifest.get("timings", []))

    week_state = WeekState()
    if run.is_done("vocabulary"):
        week_state = WeekState.from_dict(run.read_checkpoint_json(STATE_CHECKPOINT))

    def checkpoint(step):
        run.write_checkpoint_json(STATE_CHECKPOINT, week_state.to_dict())
        run.manifest["timings"] = prior_timings + common.TIMINGS
        run.mark_done(step)

    steps = [
        # Layer 1: Vocabulary (needs only the storyboard's VOCAB blocks)
        ("vocabulary", lambda: passes.vocabulary_pass(
            template_text, vocab_by_day, week_state, debug_flag=debug_flag)),
        # Layer 2: Story (needs Story Requirements + finalized Vocabulary)
        ("story", lambda: passes.story_pass(
            template_text, story_requirements_by_day, weekly_verb_focus, week_state,
            debug_flag=debug_flag, week_notes=week_notes)),
        # Layer 3: Warmup + Grammar (needs verb focus + Vocabulary)
        ("warmup_grammar", lambda: passes.warmup_grammar_pass(
            template_text, story_requirements_by_day, weekly_verb_focus, week_state,
            debug_flag=debug_flag, week_notes=week_notes)),
        # Layer 3b: translate the Grammar explanation to Spanish
        ("grammar_translate", lambda: passes.grammar_translate_pass(
            template_text, week_state, debug_flag=debug_flag)),
        # Layer 4: Examples + Translation Practice (needs finished Story)
        ("examples_translation", lambda: passes.examples_translation_pass(
            template_text, week_state, study_notes_by_day=study_notes_by_day, debug_flag=debug_flag,
            week_notes=week_notes, day_focus_by_day=day_focus_by_day)),
        # Layer 5: Student Questions (whole-week context, no repeats)
        ("student_questions", lambda: passes.student_questions_pass(
            template_text, week_state, study_notes_by_day=study_notes_by_day, debug_flag=debug_flag,
            week_notes=week_notes)),
    ]
    for step, fn in steps:
        if run.is_done(step):
            log.info(f"Skipping {step} (finished in an earlier attempt).")
            continue
        fn()
        checkpoint(step)

    # ---- assemble -----------------------------------------------------------
    assembled = week_state.assemble_week(ALL_DAYS)
    for day in ALL_DAYS:
        missing = week_state.missing_sections(day)
        if missing:
            log.warning(f"{day} is missing section(s) after all passes: {missing}")

    # ---- Layer 6: self-review (judgment only) -------------------------------
    if run.is_done("self_review"):
        log.info("Skipping self_review (finished in an earlier attempt).")
        reviewed = run.read_checkpoint(REVIEW_CHECKPOINT)
    else:
        reviewed = passes.self_review_pass(assembled, debug_flag=debug_flag)
        run.write_checkpoint(REVIEW_CHECKPOINT, reviewed)
        run.manifest["timings"] = prior_timings + common.TIMINGS
        run.mark_done("self_review")

    # ---- corrections, checks, write -----------------------------------------
    final_markdown = common.apply_corrections(reviewed, corrections)
    lint_hints(final_markdown, label="main lesson")
    structural = common.validate_markdown(final_markdown, "main lesson", common.MAIN_REQUIRED_SECTIONS)
    structural += common.check_day_heading_format(final_markdown, label="main lesson")

    out_path = common.write_markdown(final_markdown, identifier, "MAIN_PASSPIPELINE")
    support_path = common.write_markdown_fixed(final_markdown, common.MAIN_SUPPORT_FILENAME)
    run.manifest["outputs"] = [out_path, support_path]
    run.set_status(runs.STATUS_COMPLETE_WITH_ERRORS if structural else runs.STATUS_COMPLETE)

    runlog.print_summary(
        log, f"MAIN lesson, week {identifier}: {'FINISHED WITH STRUCTURAL PROBLEMS' if structural else 'done'}",
        timings=run.manifest.get("timings"),
        outputs=[out_path, support_path],
        extra_lines=[f"Run folder: {run.path}",
                     "Compare this output against the corrected lesson before trusting it for students."],
    )
    if structural:
        raise ValidationFailed(f"The lesson was written, but {len(structural)} structural problem(s) were "
                               f"found (listed above). Fix by hand, or rerun.")


if __name__ == "__main__":
    cli.run_cli(main, "pipeline.py")
