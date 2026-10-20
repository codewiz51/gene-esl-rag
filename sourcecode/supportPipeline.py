#!/usr/bin/env python3
"""
supportPipeline.py - Five-Minute lesson orchestrator.

Generates the Five-Minute lesson from the finished Main lesson, then runs
a judgment-only self-review pass over the fully assembled Five-Minute
week, before corrections/validation/write. (Replaces the retired
generateSupport.py - see git tag pre-consolidation.)

Usage (same positional arguments as always; flags are optional):
    python3 supportPipeline.py <identifier> <main_lesson.md> <storyboard.md> <fiveMinuteTemplate.txt> <unifiedPrompt.md> [Debug|NoDebug] [flags]

Example:
    python3 supportPipeline.py 41 mainSupport.md Week41StoryBoard.md FiveMinuteTemplate.txt promptFive.md Debug

<main_lesson.md> is looked up in source_docs/WeeklyLessons/ (pipeline.py
writes mainSupport.md there); the other three in source_docs/WeeklyTemplates/.
Same flags as pipeline.py: --check, --resume, --machine, --studio-ip, --timeout.

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
from errors import InputError, OllamaBadResponse, ResumeError, ValidationFailed
from qa_utils import lint_hints, lint_student_life, lint_translation_direction

log = logging.getLogger("esl")

KIND = "FIVEMIN"
GENERATE_CHECKPOINT = "five_generated.md"
REVIEW_CHECKPOINT = "five_reviewed.md"
ROLES = ("main_lesson", "storyboard", "five_template", "prompt")


def build_parser():
    p = cli.new_parser(
        "Generate the weekly Five-Minute lesson from the finished Main lesson.",
        "Example:\n  python3 supportPipeline.py 41 mainSupport.md Week41StoryBoard.md "
        "FiveMinuteTemplate.txt promptFive.md Debug",
    )
    p.add_argument("identifier", nargs="?", help="Week number, e.g. 41")
    p.add_argument("main_lesson", nargs="?", help="Main lesson .md in source_docs/WeeklyLessons/ (usually mainSupport.md)")
    p.add_argument("storyboard", nargs="?", help="Storyboard file in source_docs/WeeklyTemplates/")
    p.add_argument("five_template", nargs="?", help="Five-Minute template in source_docs/WeeklyTemplates/")
    p.add_argument("prompt", nargs="?", help="Five-Minute prompt in source_docs/WeeklyTemplates/")
    p.add_argument("debug", nargs="?", help="Debug (default) or NoDebug")
    cli.add_common_args(p)
    return p


def main(ctx):
    args = build_parser().parse_args()
    runtime = config.resolve_runtime(args.machine, args.studio_ip, args.timeout, args.model)
    log.info(f"supportPipeline.py - {runtime.describe()}")

    # ---- which run, which inputs -------------------------------------------
    run = None
    if args.resume:
        run = runs.find_run(common.RUNS_DIR, KIND, args.resume, identifier=args.identifier)
        runs.check_inputs_unchanged(run)
        m = run.manifest
        identifier = m["identifier"]
        paths = {role: m["inputs"][role]["path"] for role in ROLES}
        for role in ROLES:
            given = getattr(args, role)
            if given and os.path.basename(given) != os.path.basename(paths[role]):
                raise ResumeError(f"--resume: run {run.name} used {role} {os.path.basename(paths[role])}, "
                                  f"not {given}.")
        debug_flag = cli.parse_debug(args.debug, default=m.get("debug", True))
        log.info(f"Resuming {run.name}; already finished: {', '.join(m.get('completed_steps', [])) or 'nothing'}")
    else:
        if not all(getattr(args, r) for r in ("identifier",) + ROLES):
            raise InputError("Usage: python3 supportPipeline.py <identifier> <main_lesson.md> <storyboard.md> "
                             "<fiveMinuteTemplate.txt> <unifiedPrompt.md> [Debug|NoDebug] [--check] [--resume] ...")
        identifier = args.identifier
        try:
            main_path = cli.resolve_input(args.main_lesson, common.lesson_dir, "Main lesson")
        except InputError as e:
            raise InputError(f"{e} Run pipeline.py for this week first.") from e
        paths = {
            "main_lesson": main_path,
            "storyboard": cli.resolve_input(args.storyboard, common.weekly_template_dir, "Storyboard"),
            "five_template": cli.resolve_input(args.five_template, common.weekly_template_dir, "Five-Minute template"),
            "prompt": cli.resolve_input(args.prompt, common.weekly_template_dir, "Prompt"),
        }
        debug_flag = cli.parse_debug(args.debug)

    main_markdown = cli.read_text(paths["main_lesson"], "main lesson")
    storyboard_raw = cli.read_text(paths["storyboard"], "storyboard")
    five_template = cli.read_text(paths["five_template"], "Five-Minute template")
    unified_prompt = cli.read_text(paths["prompt"], "prompt")

    # ---- validate before the first model call -------------------------------
    weekly_corrections = common.parse_weekly_corrections(storyboard_raw)
    corrections = common.BASE_CORRECTIONS + weekly_corrections
    if weekly_corrections:
        log.info(f"Loaded {len(weekly_corrections)} weekly correction(s) from storyboard.")

    vocab_manifest = common.extract_day_vocab(main_markdown)
    story_manifest = common.extract_day_story(main_markdown)
    if not vocab_manifest.strip() or not story_manifest.strip():
        raise InputError(f"Could not extract per-day vocab and/or story from {os.path.basename(paths['main_lesson'])}. "
                         f"Is it a finished Main lesson?")
    supplied_days = [d for d in common.ALL_DAYS if f"#BEGIN {d}_STORY" in story_manifest]
    if len(supplied_days) < len(common.ALL_DAYS):
        absent = [d for d in common.ALL_DAYS if d not in supplied_days]
        log.warning(f"Main lesson has no usable Story for: {', '.join(absent)} - those days will be skipped.")

    payload_five = f"{five_template}\n\n{story_manifest}\n\n{vocab_manifest}\n\n{unified_prompt}"

    ollama_client.preflight(runtime)

    if args.check:
        log.info("Check passed: inputs and Ollama are all OK. Nothing generated (--check).")
        return

    # ---- run folder ---------------------------------------------------------
    if run is None:
        run = runs.new_run(common.RUNS_DIR, identifier, KIND, paths, runtime, debug_flag)
    else:
        run.set_status(runs.STATUS_RUNNING)
    ctx.run = run
    runlog.add_log_file(run.log_file)
    log.info(f"Run folder: {run.path}")
    common.init_run(runtime, run.debug_dir if debug_flag else None)
    prior_timings = list(run.manifest.get("timings", []))

    if debug_flag:
        with open(common.debug_path("debug_five_prompt.txt"), "w", encoding="utf-8") as f:
            f.write(payload_five)

    # ---- step 1: generate ---------------------------------------------------
    if run.is_done("generate"):
        log.info("Skipping generate (finished in an earlier attempt).")
        five_markdown = run.read_checkpoint(GENERATE_CHECKPOINT)
    else:
        attempts = 1 + config.PASS_COVERAGE_RETRIES
        five_markdown = ""
        for attempt in range(1, attempts + 1):
            log.info("Generating Five-Minute lesson..." if attempt == 1
                     else "Generating Five-Minute lesson again (coverage retry)...")
            label = "five" if attempt == 1 else f"five_retry{attempt - 1}"
            result = common.send_to_ollama(payload_five, debug_label=label, debug_flag=debug_flag)
            five_markdown = common.strip_markdown_fence(result)
            run.write_checkpoint(f"five_raw_attempt{attempt}.md", five_markdown)
            gaps = passes._coverage_gaps(five_markdown, common.SUPPORT_REQUIRED_SECTIONS, supplied_days)
            if not gaps:
                break
            desc = "; ".join(f"{d}: {', '.join(m)}" for d, m in gaps)
            if attempt < attempts:
                log.warning(f"Five-Minute output is missing {desc} - generating again.")
            else:
                log.warning(f"Five-Minute output is still missing {desc} after {attempts} attempt(s).")

        if not common.split_markdown_days(five_markdown, supplied_days):
            raise OllamaBadResponse(
                f"No day headings in the Five-Minute response at all (expected: {', '.join(supplied_days)}). "
                f"Raw text saved in {run.checkpoint_dir}. Rerun with --resume to try again.",
                retryable=False)
        if common.markdown_looks_truncated(five_markdown, supplied_days, common.SUPPORT_REQUIRED_SECTIONS):
            log.warning("Five-Minute response may be cut off mid-generation "
                        "(the last supplied day is missing one or more required sections).")
        run.write_checkpoint(GENERATE_CHECKPOINT, five_markdown)
        run.manifest["timings"] = prior_timings + common.TIMINGS
        run.mark_done("generate")

    # ---- step 2: self-review (judgment only) --------------------------------
    if run.is_done("self_review"):
        log.info("Skipping self_review (finished in an earlier attempt).")
        five_markdown = run.read_checkpoint(REVIEW_CHECKPOINT)
    else:
        five_markdown = passes.fiveminute_self_review_pass(five_markdown, debug_flag=debug_flag)
        run.write_checkpoint(REVIEW_CHECKPOINT, five_markdown)
        run.manifest["timings"] = prior_timings + common.TIMINGS
        run.mark_done("self_review")

    # ---- corrections, checks, write -----------------------------------------
    structural = common.check_day_heading_format(five_markdown, days=supplied_days, label="Five-Minute")
    five_markdown = common.apply_corrections(five_markdown, corrections)
    lint_hints(five_markdown, label="five-minute")
    lint_student_life(five_markdown, label="five-minute")
    lint_translation_direction(five_markdown, label="five-minute")
    structural += common.validate_markdown(five_markdown, "Five-Minute lesson",
                                           common.SUPPORT_REQUIRED_SECTIONS, days=supplied_days)

    out_path = common.write_markdown(five_markdown, identifier, "FIVEMIN_PASSPIPELINE")
    run.manifest["outputs"] = [out_path]
    run.set_status(runs.STATUS_COMPLETE_WITH_ERRORS if structural else runs.STATUS_COMPLETE)

    runlog.print_summary(
        log, f"FIVE-MINUTE lesson, week {identifier}: "
             f"{'FINISHED WITH STRUCTURAL PROBLEMS' if structural else 'done'}",
        timings=run.manifest.get("timings"),
        outputs=[out_path],
        extra_lines=[f"Run folder: {run.path}"],
    )
    if structural:
        raise ValidationFailed(f"The lesson was written, but {len(structural)} structural problem(s) were "
                               f"found (listed above). Fix by hand, or rerun.")


if __name__ == "__main__":
    cli.run_cli(main, "supportPipeline.py")
