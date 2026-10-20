#!/usr/bin/env python3
"""
config.py

Every setting the pipeline needs, plus the logic that works out which
machine it is running on and where Ollama is.

Two machines, two modes:
    studio   - "local" mode. Pipeline code and Ollama both run on the
               Studio; Ollama is reached at localhost.
    macbook  - "client" mode. Pipeline code runs on the Macbook; every
               model call goes over the network to Ollama on the Studio
               (default 192.168.4.47, override with --studio-ip).

The machine is detected from $HOME (exact match against MACHINES below),
cross-checked against the hostname. --machine overrides detection; so
does the ESL_MACHINE environment variable. If a username or hostname
changes, edit MACHINES - nothing else needs to change.
"""

import os
import socket
from dataclasses import dataclass, field

from errors import InputError

# ---------------------------------------------------------------------------
# Model and generation settings
# ---------------------------------------------------------------------------

# The one model the pipeline uses. It is a Modelfile wrapper around the
# qwen3.8:27b-mlx weights on the Studio. --model exists only for testing
# error handling; production runs never change this.
MODEL_NAME = "pipeline-qwen38:latest"

# Ollama's /api/generate reads generation parameters only from this nested
# "options" object; top-level keys are silently ignored. temperature 0.5
# matches the Modelfile; num_ctx is far above the ~10-13k tokens a week's
# prompt+response needs, so a "length" stop is a real signal, not a limit
# we set too low. "think" is deliberately not set (Aug 28, 2026 test:
# think=False made the model stop after one day).
GENERATION_OPTIONS = {
    "temperature": 0.5,
    "num_ctx": 65536,
    "num_predict": -1,
}

OLLAMA_PORT = 11434
DEFAULT_STUDIO_IP = "192.168.4.47"

# ---------------------------------------------------------------------------
# Timeouts and retries
# ---------------------------------------------------------------------------

# Seconds allowed to open the TCP connection.
CONNECT_TIMEOUT = 10

# Seconds Ollama may go silent before the call is treated as hung. The
# response is streamed, so this is "no new data for N seconds", not a cap
# on the whole call: a long, steady generation never trips it. It does
# include the wait for the first token (model load + prompt processing).
# Started at 300 on Oct 20, 2026; tune from the timings in run.log.
INACTIVITY_TIMEOUT = 300

# Extra attempts after a retryable failure (connection drop, timeout,
# server error, empty answer). 2 means up to 3 attempts in total.
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = [10, 30]

# Seconds for the startup check that Ollama is up and has the model.
PREFLIGHT_TIMEOUT = 10

# While a response is streaming, print a progress line this often.
HEARTBEAT_SECONDS = 30

# ---------------------------------------------------------------------------
# Output-quality guards
# ---------------------------------------------------------------------------

# If a pass's output is missing a day or a section it was asked for, run
# that pass again this many times before keeping what it has.
PASS_COVERAGE_RETRIES = 1

# A self-review pass returns the whole week. Its answer replaces the
# original only if it still has every day and section and its length is
# within these ratios of the original; otherwise the original is kept.
SELF_REVIEW_MIN_LENGTH_RATIO = 0.70
SELF_REVIEW_MAX_LENGTH_RATIO = 1.50

ALL_DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]

# ---------------------------------------------------------------------------
# Machines
# ---------------------------------------------------------------------------

MACHINES = {
    "macbook": {
        "home": "/Users/Gene",
        "hostname_hints": ["macbook"],
        "mode": "client",
    },
    "studio": {
        "home": "/Users/gene",
        "hostname_hints": ["studio"],
        "mode": "local",
    },
}


@dataclass
class Runtime:
    machine: str
    mode: str                    # "local" or "client"
    base_url: str                # e.g. http://192.168.4.47:11434
    model: str
    detected_by: str
    connect_timeout: float = CONNECT_TIMEOUT
    inactivity_timeout: float = INACTIVITY_TIMEOUT
    max_retries: int = MAX_RETRIES
    retry_backoff: list = field(default_factory=lambda: list(RETRY_BACKOFF_SECONDS))
    options: dict = field(default_factory=lambda: dict(GENERATION_OPTIONS))

    def describe(self):
        where = "Ollama on this machine" if self.mode == "local" else "Ollama on the Studio"
        return (f"machine={self.machine} ({self.detected_by}), mode={self.mode} -> {where} "
                f"at {self.base_url}, model={self.model}, "
                f"inactivity timeout={self.inactivity_timeout:g}s")


def _hostname():
    try:
        return socket.gethostname().lower()
    except OSError:
        return ""


def _machine_for_hostname(hostname):
    hits = [name for name, m in MACHINES.items()
            if any(h in hostname for h in m["hostname_hints"])]
    return hits[0] if len(hits) == 1 else None


def detect_machine():
    """Return (machine_name, how_detected). Raises InputError if unsure."""
    home = os.path.expanduser("~")
    hostname = _hostname()
    by_home = [name for name, m in MACHINES.items() if m["home"] == home]
    by_host = _machine_for_hostname(hostname)

    if len(by_home) == 1:
        machine = by_home[0]
        if by_host and by_host != machine:
            raise InputError(
                f"Machine detection disagrees: $HOME={home} says '{machine}', "
                f"hostname '{hostname}' says '{by_host}'. "
                f"Pass --machine macbook or --machine studio, or fix MACHINES in config.py."
            )
        return machine, f"detected from $HOME={home}"
    if by_host:
        return by_host, f"detected from hostname '{hostname}'"
    raise InputError(
        f"Can't tell which machine this is ($HOME={home}, hostname '{hostname}'). "
        f"Pass --machine macbook or --machine studio, or add this machine to MACHINES in config.py."
    )


def resolve_runtime(machine=None, studio_ip=None, timeout=None, model=None):
    """
    Build the Runtime from command-line values (any may be None).
    Precedence: command line, then environment (ESL_MACHINE, ESL_STUDIO_IP),
    then auto-detection / defaults.
    """
    machine = machine or os.environ.get("ESL_MACHINE")
    if machine:
        machine = machine.strip().lower()
        if machine not in MACHINES:
            raise InputError(f"Unknown machine '{machine}'. Use one of: {', '.join(MACHINES)}.")
        detected_by = "set with --machine / ESL_MACHINE"
    else:
        machine, detected_by = detect_machine()

    mode = MACHINES[machine]["mode"]
    studio_ip_given = studio_ip or os.environ.get("ESL_STUDIO_IP")

    if mode == "local":
        if studio_ip_given and studio_ip_given not in ("localhost", "127.0.0.1"):
            raise InputError(
                f"--studio-ip {studio_ip_given} was given, but this is the Studio, which uses its own "
                f"Ollama at localhost. Drop --studio-ip, or pass --machine macbook if this is the Macbook."
            )
        host = "localhost"
    else:
        host = studio_ip_given or DEFAULT_STUDIO_IP

    # "IP" or "IP:port" (the port form is for tools/mock_ollama.py testing).
    base_url = f"http://{host}" if ":" in host else f"http://{host}:{OLLAMA_PORT}"
    rt = Runtime(
        machine=machine,
        mode=mode,
        base_url=base_url,
        model=model or MODEL_NAME,
        detected_by=detected_by,
    )
    if timeout is not None:
        if timeout <= 0:
            raise InputError("--timeout must be a positive number of seconds.")
        rt.inactivity_timeout = float(timeout)
    return rt
