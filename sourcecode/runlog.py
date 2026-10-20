#!/usr/bin/env python3
"""
runlog.py

Logging for a pipeline run. Every module logs through the "esl" logger:

    console  - the same plain messages the scripts always printed; warnings
               and errors are prefixed "WARNING:" / "ERROR:".
    run.log  - in the run's folder: every message with a timestamp, plus
               debug detail and full tracebacks for unexpected errors.

Every warning is also collected so the run can end with one summary
instead of leaving them scattered through the scroll-back.
"""

import logging
import sys

LOGGER_NAME = "esl"


class _ConsoleFormatter(logging.Formatter):
    def format(self, record):
        msg = record.getMessage()
        if record.levelno >= logging.ERROR:
            return f"ERROR: {msg}"
        if record.levelno >= logging.WARNING:
            return f"WARNING: {msg}"
        return msg


class WarningCollector(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.messages = []

    def emit(self, record):
        if record.levelno == logging.WARNING:
            self.messages.append(record.getMessage())


_collector = None
_file_handler = None


def setup_logging(log_file=None, verbose=False):
    """Configure the 'esl' logger. Safe to call more than once."""
    global _collector, _file_handler
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(_ConsoleFormatter())
    logger.addHandler(console)

    _collector = WarningCollector()
    logger.addHandler(_collector)

    _file_handler = None
    if log_file:
        add_log_file(log_file)
    return logger


def add_log_file(log_file):
    """Attach (or move) the run.log file handler; used once the run folder exists."""
    global _file_handler
    logger = logging.getLogger(LOGGER_NAME)
    if _file_handler is not None:
        logger.removeHandler(_file_handler)
        _file_handler.close()
    _file_handler = logging.FileHandler(log_file, encoding="utf-8")
    _file_handler.setLevel(logging.DEBUG)
    _file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s",
                                                 datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(_file_handler)


def collected_warnings():
    return list(_collector.messages) if _collector else []


def print_summary(log, title, timings=None, outputs=None, extra_lines=None):
    """End-of-run summary: timings, outputs written, and every warning once."""
    log.info("")
    log.info("=" * 70)
    log.info(title)
    log.info("=" * 70)
    if timings:
        total = sum(t["seconds"] for t in timings)
        log.info(f"Model calls: {len(timings)}, total {total / 60:.1f} min")
        for t in timings:
            retry = f", {t['attempts']} attempts" if t.get("attempts", 1) > 1 else ""
            gap = f"  longest pause {t['max_gap_seconds']:>5.1f}s" if "max_gap_seconds" in t else ""
            log.info(f"  {t['label']:<32} {t['seconds']:>6.0f}s  first data {t['first_data_seconds']:>4.0f}s"
                     f"{gap}  done={t['done_reason']}{retry}")
    for line in outputs or []:
        log.info(f"Wrote: {line}")
    for line in extra_lines or []:
        log.info(line)
    warnings = collected_warnings()
    seen, unique = set(), []
    for w in warnings:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    if unique:
        log.info(f"{len(unique)} warning(s) during this run:")
        for w in unique:
            log.info(f"  - {w}")
    else:
        log.info("No warnings.")
    log.info("=" * 70)
