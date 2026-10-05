#!/usr/bin/env python3
"""
storyboard_utils.py

Pulls the three things the pass pipeline needs out of a raw storyboard
file (e.g. Week35StoryBoard.md):
  1. The weekly verb focus block (top of file).
  2. Each day's narrative bullets (between "# MONDAY STORYBOARD" and the
     next day heading, or a "=== VOCAB ===" marker - whichever comes first).
  3. Each day's suggested vocabulary block (between
     "=== VOCAB <DAY> (Suggested) ===" and "=== END VOCAB <DAY> ===").

This intentionally did NOT reuse the retired generateMain.py's parse_storyboard_days(),
because that function expects the "=== START DAY ===" / "=== END DAY ==="
wrapper format generateMain.py's own inject_storyboard_into_template()
produces - not the raw "# MONDAY STORYBOARD" + inline VOCAB markers
format the actual storyboard files (Week35StoryBoard.md) use natively.
"""

import re

ALL_DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]


def extract_weekly_verb_focus(storyboard_text):
    m = re.search(
        r"(?ms)^WEEKLY VERB FOCUS:\s*$(.*?)(?=^WEEKLY VOCABULARY|\Z)",
        storyboard_text,
    )
    return m.group(1).strip() if m else ""


def extract_day_story_requirements(storyboard_text):
    """
    Returns {DAY: bullet_text} - the narrative bullets for each day,
    with any inline "=== VOCAB ... ===" block stripped out (that's
    handled separately by extract_day_vocab_suggestions below).
    """
    result = {}
    for i, day in enumerate(ALL_DAYS):
        next_day_pattern = ALL_DAYS[i + 1] if i + 1 < len(ALL_DAYS) else None
        start_pat = rf"^#\s*{day}\s+STORYBOARD\s*$"
        if next_day_pattern:
            end_pat = rf"^#\s*{next_day_pattern}\s+STORYBOARD\s*$"
            pattern = re.compile(rf"(?ms){start_pat}(.*?)(?={end_pat})")
        else:
            pattern = re.compile(rf"(?ms){start_pat}(.*)")
        m = pattern.search(storyboard_text)
        if not m:
            print(f"WARNING: no storyboard section found for {day}.")
            result[day] = ""
            continue
        chunk = m.group(1)
        # Strip the inline vocab block (handled separately) and the
        # "Introduce/Reinforce ..." + Examples header lines are kept -
        # they're part of the narrative intent, not the vocab pool.
        chunk = re.sub(
            r"(?ms)^# === VOCAB.*?=== END VOCAB.*?===\s*$",
            "",
            chunk,
        )
        # Also strip the optional STUDY NOTES block - it is factual source
        # material for the Examples / Student Questions passes, not story
        # requirements (see extract_day_study_notes below).
        chunk = re.sub(
            r"(?ms)^# === STUDY NOTES.*?=== END STUDY NOTES.*?===\s*$",
            "",
            chunk,
        )
        result[day] = chunk.strip()
    return result


def extract_day_study_notes(storyboard_text):
    """
    Returns {DAY: notes_text} for any day that has an optional block:

        # === STUDY NOTES SATURDAY ===
        ...factual source material (e.g. practice-test questions,
        correct answers, explanations)...
        # === END STUDY NOTES SATURDAY ===

    Days without a block are simply absent from the result. The
    Examples and Student Questions passes use these notes as source
    material; the Story and Vocabulary passes never see them.
    """
    result = {}
    for day in ALL_DAYS:
        pattern = re.compile(
            rf"(?ms)^#?\s*===\s*STUDY\s+NOTES\s+{day}\s*===\s*$(.*?)^#?\s*===\s*END\s+STUDY\s+NOTES\s+{day}\s*===\s*$",
            flags=re.IGNORECASE,
        )
        m = pattern.search(storyboard_text)
        if m and m.group(1).strip():
            result[day] = m.group(1).strip()
    return result


def extract_day_vocab_suggestions(storyboard_text):
    """
    Returns {DAY: vocab_text} - the raw "English - Spanish - example"
    lines from that day's "=== VOCAB DAY (Suggested) ===" block. This
    is the ONLY legal vocabulary source for the Vocabulary pass - do
    not let it pull from the top-of-file WEEKLY VOCABULARY pool.
    """
    result = {}
    for day in ALL_DAYS:
        pattern = re.compile(
            rf"(?ms)^#?\s*===\s*VOCAB\s+{day}\s*(?:\(Suggested\))?\s*===\s*$(.*?)^#?\s*===\s*END\s+VOCAB\s+{day}\s*===\s*$",
            flags=re.IGNORECASE,
        )
        m = pattern.search(storyboard_text)
        if not m:
            print(f"WARNING: no VOCAB block found for {day}.")
            result[day] = ""
            continue
        result[day] = m.group(1).strip()
    return result


def extract_week_notes(storyboard_text):
    """
    Returns the optional whole-week block:

        # === WEEK NOTES ===
        ...facts and cast limits that apply to every day...
        # === END WEEK NOTES ===

    or "" if the storyboard has none. These notes are passed to the
    Story, Warmup/Grammar, Examples and Student Questions passes.
    """
    m = re.search(
        r"(?ms)^#?\s*===\s*WEEK\s+NOTES\s*===\s*$(.*?)^#?\s*===\s*END\s+WEEK\s+NOTES\s*===\s*$",
        storyboard_text,
        flags=re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def extract_day_focus(story_requirements_by_day):
    """
    Returns {DAY: focus_text} - the 'Introduce / Reinforce / Light review'
    lines at the top of each day's storyboard section (everything before
    the first 'Examples' line). Tells later passes which verb(s) the day
    is about.
    """
    result = {}
    for day, req in story_requirements_by_day.items():
        lines = []
        for line in req.splitlines():
            if line.strip().lower().startswith("examples"):
                break
            if re.match(r"^\s*\d+\s*[-.]", line):
                break
            if line.strip():
                lines.append(line.strip())
            if len(lines) >= 3:
                break
        result[day] = "\n".join(lines)
    return result
