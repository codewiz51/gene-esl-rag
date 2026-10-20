#!/usr/bin/env python3
"""
runs.py

Run folders, checkpoints and --resume.

Every run gets its own folder:

    RAG/runs/<id>_<KIND>_<timestamp>/
        manifest.json   what was run, on which machine, input file hashes,
                        which steps are finished, per-call timings, status
        run.log         full log of the run
        checkpoints/    each finished step's output (written after every
                        model call, so a crash loses at most one step)
        debug/          prompts, responses, thinking traces (Debug only)

KIND is MAIN or FIVEMIN. --resume finds the newest unfinished run for the
same week and kind (or the folder you name), checks the input files have
not changed since it started, and skips the steps already done.
"""

import hashlib
import json
import os
from datetime import datetime

from errors import ResumeError

STATUS_RUNNING = "running"
STATUS_FAILED = "failed"
STATUS_INTERRUPTED = "interrupted"
STATUS_COMPLETE = "complete"
STATUS_COMPLETE_WITH_ERRORS = "complete_with_validation_errors"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write_text(path, text):
    """Write via a temp file + rename so a crash never leaves half a file."""
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


class Run:
    def __init__(self, path, manifest):
        self.path = path
        self.manifest = manifest

    # ---- locations ---------------------------------------------------------
    @property
    def log_file(self):
        return os.path.join(self.path, "run.log")

    @property
    def checkpoint_dir(self):
        d = os.path.join(self.path, "checkpoints")
        os.makedirs(d, exist_ok=True)
        return d

    @property
    def debug_dir(self):
        d = os.path.join(self.path, "debug")
        os.makedirs(d, exist_ok=True)
        return d

    @property
    def name(self):
        return os.path.basename(self.path)

    # ---- manifest ----------------------------------------------------------
    def save(self):
        self.manifest["updated"] = datetime.now().isoformat(timespec="seconds")
        atomic_write_text(os.path.join(self.path, "manifest.json"),
                          json.dumps(self.manifest, indent=2, ensure_ascii=False))

    def is_done(self, step):
        return step in self.manifest.get("completed_steps", [])

    def mark_done(self, step):
        steps = self.manifest.setdefault("completed_steps", [])
        if step not in steps:
            steps.append(step)
        self.save()

    def set_status(self, status, message=""):
        self.manifest["status"] = status
        if message:
            self.manifest["status_message"] = message
        self.save()

    def add_timings(self, timings):
        self.manifest.setdefault("timings", []).extend(timings)
        self.save()

    # ---- checkpoints -------------------------------------------------------
    def write_checkpoint(self, name, text):
        atomic_write_text(os.path.join(self.checkpoint_dir, name), text)

    def write_checkpoint_json(self, name, obj):
        self.write_checkpoint(name, json.dumps(obj, indent=2, ensure_ascii=False))

    def read_checkpoint(self, name):
        path = os.path.join(self.checkpoint_dir, name)
        if not os.path.exists(path):
            raise ResumeError(f"Run {self.name} says '{name}' is finished but the checkpoint file is missing. "
                              f"Start a fresh run.")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def read_checkpoint_json(self, name):
        return json.loads(self.read_checkpoint(name))


def new_run(runs_root, identifier, kind, inputs, runtime, debug):
    """inputs: {role: absolute_path}. Hashes are stored for the resume check."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(runs_root, exist_ok=True)
    n = 1
    while True:
        # os.mkdir is atomic: if two runs start in the same second, exactly
        # one gets each name (checking os.path.exists first was a race).
        path = os.path.join(runs_root, f"{identifier}_{kind}_{ts}" + (f"_{n}" if n > 1 else ""))
        try:
            os.mkdir(path)
            break
        except FileExistsError:
            n += 1
    manifest = {
        "identifier": str(identifier),
        "kind": kind,
        "started": datetime.now().isoformat(timespec="seconds"),
        "machine": runtime.machine,
        "mode": runtime.mode,
        "ollama": runtime.base_url,
        "model": runtime.model,
        "debug": bool(debug),
        "inputs": {role: {"path": p, "sha256": sha256_file(p)} for role, p in inputs.items()},
        "completed_steps": [],
        "timings": [],
        "status": STATUS_RUNNING,
    }
    run = Run(path, manifest)
    run.save()
    return run


def _load(path):
    mpath = os.path.join(path, "manifest.json")
    if not os.path.exists(mpath):
        raise ResumeError(f"{path} is not a run folder (no manifest.json).")
    with open(mpath, "r", encoding="utf-8") as f:
        return Run(path, json.load(f))


def find_run(runs_root, kind, resume_arg, identifier=None):
    """
    resume_arg is "latest" or a run folder name/path. "latest" picks the
    newest unfinished run of this kind (and week, if identifier is given).
    """
    if resume_arg and resume_arg != "latest":
        path = resume_arg if os.path.isabs(resume_arg) else os.path.join(runs_root, resume_arg)
        run = _load(path)
        if run.manifest.get("kind") != kind:
            raise ResumeError(f"{run.name} is a {run.manifest.get('kind')} run, not {kind}.")
        return run

    if not os.path.isdir(runs_root):
        raise ResumeError(f"No runs folder yet ({runs_root}) - nothing to resume.")
    candidates = []
    for name in os.listdir(runs_root):
        p = os.path.join(runs_root, name)
        if not os.path.isfile(os.path.join(p, "manifest.json")):
            continue
        try:
            run = _load(p)
        except (ResumeError, ValueError):
            continue
        m = run.manifest
        if m.get("kind") != kind:
            continue
        if identifier is not None and str(m.get("identifier")) != str(identifier):
            continue
        if m.get("status") in (STATUS_COMPLETE, STATUS_COMPLETE_WITH_ERRORS):
            continue
        candidates.append((m.get("started", ""), run))
    if not candidates:
        week = f" for week {identifier}" if identifier is not None else ""
        raise ResumeError(f"No unfinished {kind} run{week} found in {runs_root}.")
    candidates.sort(key=lambda c: c[0])
    return candidates[-1][1]


def check_inputs_unchanged(run):
    changed = []
    for role, info in run.manifest.get("inputs", {}).items():
        p = info["path"]
        if not os.path.exists(p):
            changed.append(f"{role} ({p}) no longer exists")
        elif sha256_file(p) != info["sha256"]:
            changed.append(f"{role} ({os.path.basename(p)}) has been edited")
    if changed:
        raise ResumeError(f"Can't resume {run.name}: " + "; ".join(changed) +
                          ". Finished steps were built from the old version - start a fresh run.")
