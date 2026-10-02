#!/usr/bin/env python3
"""
qa_utils.py - cheap, no-model checks that print warnings about a finished
lesson. They never change the lesson text.
"""

import re

_ENGLISH_HINT_WORDS = {
    "the", "a", "an", "to", "of", "and", "is", "are", "it", "back", "tight", "hang", "hold",
    "get", "give", "have", "take", "check", "reading", "patient", "doctor", "claim", "chart",
}


def lint_hints(markdown_text, label="lesson"):
    """Warn about hints that are too long or look English. Hint = last (...) on a numbered line."""
    warnings = []
    day = "?"
    section = ""
    for line in markdown_text.splitlines():
        m_day = re.match(r"^#\s+([A-Z]+)\s*$", line)
        if m_day:
            day = m_day.group(1)
            continue
        m_sec = re.match(r"^##\s+(.*)$", line)
        if m_sec:
            section = m_sec.group(1).strip()
            continue
        if section not in ("Warmup", "Grammar", "Student Questions"):
            continue
        m = re.match(r"^\s*\d+[.)]\s+.*\(([^()]+)\)\s*$", line)
        if not m:
            continue
        hint = m.group(1).strip()
        words = hint.split()
        if len(words) > 3:
            warnings.append(f"{day} {section}: hint has {len(words)} words: ({hint})")
        elif all(w.lower() in _ENGLISH_HINT_WORDS for w in words):
            warnings.append(f"{day} {section}: hint looks English: ({hint})")
    for w in warnings:
        print(f"HINT WARNING [{label}]: {w}")
    if not warnings:
        print(f"Hint check [{label}]: no problems found.")
    return warnings
