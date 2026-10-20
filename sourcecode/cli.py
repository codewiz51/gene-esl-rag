#!/usr/bin/env python3
"""
cli.py

Command-line pieces shared by pipeline.py and supportPipeline.py:
the common flags, input-file lookup, and run_cli(), which turns every
expected failure into a one-line message and an exit code (errors.py)
instead of a traceback, and tells you how to resume.
"""

import argparse
import difflib
import logging
import os
import sys

import runlog
import runs
from errors import (INTERRUPTED_EXIT, UNEXPECTED_ERROR_EXIT, InputError,
                    PipelineError)

log = logging.getLogger("esl")


def add_common_args(parser):
    g = parser.add_argument_group("machine and Ollama")
    g.add_argument("--machine", choices=["macbook", "studio"],
                   help="Override auto-detection. macbook = client mode (Ollama on the Studio); "
                        "studio = local mode (Ollama on localhost).")
    g.add_argument("--studio-ip", metavar="IP",
                   help="Studio address when running on the Macbook (default 192.168.4.47).")
    g.add_argument("--timeout", type=float, metavar="SECONDS",
                   help="Inactivity timeout for each model call (default from config.py: 300).")
    g.add_argument("--model", metavar="NAME",
                   help="TESTING ONLY - use a different Ollama model. Production runs never set this.")

    r = parser.add_argument_group("run control")
    r.add_argument("--resume", nargs="?", const="latest", metavar="RUN",
                   help="Continue an unfinished run, skipping the steps it already finished. "
                        "With no value: the newest unfinished run for this week. "
                        "Or give a run folder name from RAG/runs/.")
    r.add_argument("--check", action="store_true",
                   help="Check inputs, template and the Ollama connection, then stop (no generation).")
    r.add_argument("--verbose", action="store_true", help="Show debug-level messages on screen.")


def parse_debug(value, default=True):
    """The optional last positional: Debug / NoDebug (only the first letter matters)."""
    if value is None:
        return default
    v = value.strip().lower()
    if v.startswith("n"):
        return False
    if v.startswith("d"):
        return True
    raise InputError(f"Last argument must be Debug or NoDebug, not '{value}'.")


def resolve_input(name, default_dir, role):
    """Accept an absolute/relative path or a bare file name in default_dir."""
    if name is None:
        raise InputError(f"Missing {role} file name.")
    candidates = [name] if os.path.isabs(name) else [os.path.join(default_dir, name), os.path.abspath(name)]
    for c in candidates:
        if os.path.isfile(c):
            return os.path.abspath(c)
    hint = ""
    if os.path.isdir(default_dir):
        close = difflib.get_close_matches(os.path.basename(name), os.listdir(default_dir), n=3, cutoff=0.6)
        if close:
            hint = f" Did you mean: {', '.join(close)}?"
    raise InputError(f"{role} file '{name}' not found in {default_dir}.{hint}")


def read_text(path, role):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError as e:
        raise InputError(f"{role} file {path} is not UTF-8 text ({e}).") from e
    except OSError as e:
        raise InputError(f"Can't read {role} file {path}: {e}") from e


class RunContext:
    """What run_cli needs to report a failure: the run (once created)."""
    def __init__(self, script_name):
        self.script_name = script_name
        self.run = None


def run_cli(main_fn, script_name):
    """
    Call main_fn(ctx) and exit with the right code. main_fn returns
    normally on success and raises a PipelineError for expected failures.
    """
    ctx = RunContext(script_name)
    runlog.setup_logging(verbose="--verbose" in sys.argv)
    try:
        main_fn(ctx)
        sys.exit(0)
    except KeyboardInterrupt:
        log.error("Interrupted (Ctrl-C).")
        _record_failure(ctx, runs.STATUS_INTERRUPTED, "interrupted")
        sys.exit(INTERRUPTED_EXIT)
    except PipelineError as e:
        log.error(str(e))
        if e.exit_code != 3:  # 3 = lesson written; status already set
            _record_failure(ctx, runs.STATUS_FAILED, str(e))
        sys.exit(e.exit_code)
    except SystemExit:
        raise
    except Exception as e:  # a bug: full traceback to run.log, short message on screen
        log.debug("Unexpected error", exc_info=True)
        where = f" Full traceback in {ctx.run.log_file}." if ctx.run else ""
        log.error(f"Unexpected error: {e.__class__.__name__}: {e}.{where}")
        if not ctx.run:
            import traceback
            traceback.print_exc()
        _record_failure(ctx, runs.STATUS_FAILED, f"{e.__class__.__name__}: {e}")
        sys.exit(UNEXPECTED_ERROR_EXIT)


def _record_failure(ctx, status, message):
    run = ctx.run
    if run is None:
        return
    try:
        run.set_status(status, message)
    except OSError:
        pass
    done = run.manifest.get("completed_steps", [])
    runlog.print_summary(
        log, f"RUN STOPPED: {run.name}",
        timings=run.manifest.get("timings"),
        extra_lines=[
            f"Finished steps (saved): {', '.join(done) if done else 'none'}",
            f"To continue from here, rerun the same command with --resume "
            f"(or: python3 {ctx.script_name} --resume {run.name})",
            f"Log: {run.log_file}",
        ],
    )


def new_parser(description, epilog):
    return argparse.ArgumentParser(
        description=description, epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
