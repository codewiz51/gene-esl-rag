"""Shared test setup: import path, quiet logging, repo file locations."""
import logging
import os
import sys

SOURCE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SOURCE_DIR not in sys.path:
    sys.path.insert(0, SOURCE_DIR)
TOOLS_DIR = os.path.join(SOURCE_DIR, "tools")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

import runlog  # noqa: E402

REPO = os.path.dirname(SOURCE_DIR)
TEMPLATES = os.path.join(REPO, "source_docs", "WeeklyTemplates")


def quiet_logging():
    """Collect warnings (runlog.collected_warnings) but print nothing."""
    runlog.setup_logging()
    for h in logging.getLogger("esl").handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, runlog.WarningCollector):
            h.setLevel(logging.CRITICAL + 1)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()
