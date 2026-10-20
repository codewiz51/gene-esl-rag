#!/usr/bin/env python3
# commonFunctions.py
#
# Shared "library" module for the ESL lesson generation pipeline.
# (Oct 2026: generateMain.py/generateSupport.py were retired - see git
# tag pre-consolidation. References below now name their replacements.)
# pipeline.py and supportPipeline.py both import from this file rather
# than each keeping their own copy - this is the fix for the drift risk
# discovered when the same corrections dictionary lived separately in two
# template files and got out of sync. Edit shared logic here once; both
# scripts pick it up automatically.
#
# This module has no main() and does nothing when imported - it's meant
# to be imported, never run directly (equivalent to a shared library / DLL,
# not an executable).
#
# CHANGED (Aug 2026): model output format migrated from HTML to Markdown,
# converted to .docx via Pandoc for printing/formatting in Word/Pages.
# The old split_html_blocks / looks_truncated / validate_html / write_html
# functions are retired in favor of Markdown-aware equivalents below.
#
# CHANGED (Oct 20, 2026): client/server refactor. Model settings and the
# machine/endpoint logic moved to config.py; the HTTP call moved to
# ollama_client.py (streaming, inactivity timeout, retries, typed errors).
# send_to_ollama() below is now a thin wrapper so passes.py is unchanged.
# Messages go through the "esl" logger (runlog.py) instead of print().
# convert_markdown_to_docx() was removed - nothing called it, and its
# top-level pypandoc import stopped the pipeline starting on a machine
# without pypandoc. toDocx.py does the .docx step.

import logging
import os
import re
from datetime import datetime

import config
from config import ALL_DAYS  # noqa: F401  (re-exported: other modules use common.ALL_DAYS)

log = logging.getLogger("esl")

# Kept as names other code may still refer to; the values live in config.py.
MODEL_NAME = config.MODEL_NAME

# Paths are derived from this file's own location (RAG/sourcecode/), so
# the repo can be moved or renamed without editing code. ~/RAG is the
# repo root on both the Macbook and the Studio.
SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
RAG_ROOT = os.path.dirname(SOURCE_DIR)
weekly_template_dir = os.path.join(RAG_ROOT, "source_docs", "WeeklyTemplates")
lesson_dir = os.path.join(RAG_ROOT, "source_docs", "WeeklyLessons")
RUNS_DIR = os.path.join(RAG_ROOT, "runs")

# ---------------------------------------------------------------------------
# Per-run state, set once by the orchestrator through init_run().
# ---------------------------------------------------------------------------
RUNTIME = None        # config.Runtime: which Ollama, which model, timeouts
DEBUG_DIR = None      # this run's debug/ folder (None when debug is off)
TIMINGS = []          # one dict per model call, for the summary/manifest


def init_run(runtime, debug_dir=None):
    global RUNTIME, DEBUG_DIR, TIMINGS
    RUNTIME = runtime
    DEBUG_DIR = debug_dir
    TIMINGS = []


def debug_path(filename):
    # Debug files go in the current run's debug/ folder. If called before
    # init_run() (e.g. a helper used on its own), fall back to the old
    # sourcecode/debug/ location.
    d = DEBUG_DIR or os.path.join(SOURCE_DIR, "debug")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, filename)

# Optional Pandoc reference-doc for Word heading styles (Heading 1 for day
# headings, Heading 2 for section headings). Used by toDocx.py; if this
# file doesn't exist it falls back to Pandoc's default styling. Build it
# once in Word: create a .docx, define Heading 1 / Heading 2 the way you
# want them to look, save it here.
reference_doc_path = os.path.join(weekly_template_dir, "reference.docx")

# Fixed filename pipeline.py also writes the Main lesson to, alongside
# its normal timestamped file, so supportPipeline.py can be called with a
# constant path instead of the caller having to copy the timestamp out of
# pipeline.py's console output. Gets silently overwritten by the next
# pipeline.py run - the timestamped file from write_markdown() remains
# the permanent record; this one is a workflow convenience only.
MAIN_SUPPORT_FILENAME = "mainSupport.md"

MAIN_REQUIRED_SECTIONS = [
    "Warmup",
    "Vocabulary",
    "Story",
    "Grammar",
    "Examples",
    "Translation Practice",
    "Student Questions",
]

# NEW: Five-Minute lesson's own section list, distinct from Main's -
# supportPipeline.py passes this to validate_markdown() and
# markdown_looks_truncated() instead of MAIN_REQUIRED_SECTIONS.
SUPPORT_REQUIRED_SECTIONS = [
    "Vocabulary Review",
    "Grammar Focus",
    "Mini Story",
    "Translation Practice",
    "Student Questions",
]

# Stable, general Cuban-register corrections that apply every week regardless
# of topic. This is "factory" content — edit here only when a general
# register/false-friend error is found, not for anything week-specific.
# Week-specific corrections (e.g. medical terminology for a clinic-focused
# week) belong in a #BEGIN DICTIONARY: WEEKLY_CORRECTIONS block in that
# week's storyboard file instead — see parse_weekly_corrections().
BASE_CORRECTIONS = [
    (r"\bir a rastras\b", "un rutero"),
    (r"\bcarpular\b", "un rutero"),
    # Gene's decision, Oct 20, 2026: sack lunch = "almuerzo para llevar"
    # (both templates' register lists agree). Previously this rule turned
    # the template's own "almuerzo en bolsa" into "almuerzo en llevar".
    (r"\balmuerzo en (?:bolsa|llevar)\b", "almuerzo para llevar"),
    (r"\bchamba\b", "trabajo"),
    (r"\bparte del tiempo\b", "pronóstico del tiempo"),
    (r"\bmoqueo\b", "moco"),
    (r"\bmoquito\b", "moco"),
    (r"\bpl[aá]tica\b", "charla"),
    (r"\bse mete(n)? en el carro\b", "se sube\\1 al carro"),
    (r"\bno paraba de\b", "no dejaba de"),
    # Moved here from the retired LANGUAGE_CORRECTIONS template blocks.
    (r"\bhacer un error\b", "cometer un error"),
    (r"\bhacer tan bien\b", "hacerlo tan bien"),
    (r"\bdel cl[ií]nica\b", "de la clínica"),
    (r"\btomar el examen\b", "hacer el examen"),
    (r"\bcompresas h[uú]medas calientes\b", "paños calientes húmedos"),
    (r"\bnarices goteando\b", "nariz que gotea"),
    # apply_corrections() is case-insensitive; this phrase almost always
    # opens a sentence, so the replacement is capitalized.
    (r"\beso es la vida\b", "Así es la vida"),    
    # From CUBAN_REGISTER dictionary - forbidden in any context.
    # All four forms (the old rule matched only "calientito", so
    # "mantas calientitas" slipped through in the Week 41 runs). Plural
    # keeps its plural: calientitos/calientitas -> calientes.
    (r"\bcalientit[oa]s\b", "calientes"),
    (r"\bcalientit[oa]\b", "caliente"),
    (r"¿puedo tener (un[ao]) ([a-záéíóúñ]+)\?", r"¿me puedo comer \1 \2?"),
]

def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def parse_weekly_corrections(storyboard_text):
    # Optional per-storyboard corrections block. Not every week has one —
    # some weeks (e.g. resume-writing, non-clinical topics) may have no
    # corrections at all, and that's expected, not an error.
    # Format, one pair per line:
    #   wrong phrase → right phrase
    match = re.search(
        r"#BEGIN DICTIONARY:\s*WEEKLY_CORRECTIONS(.*?)#END DICTIONARY:\s*WEEKLY_CORRECTIONS",
        storyboard_text, flags=re.DOTALL | re.IGNORECASE
    )
    if not match:
        return []
    pairs = []
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or "→" not in line:
            continue
        wrong, right = line.split("→", 1)
        wrong = wrong.strip()
        right = right.strip()
        if wrong and right:
            # \b word-boundary wrap assumes the phrase is plain text, matching
            # how BASE_CORRECTIONS entries are written.
            pairs.append((rf"\b{re.escape(wrong)}\b", right))
    return pairs

def send_to_ollama(payload, debug_label=None, debug_flag=True):
    # Thin wrapper kept so passes.py and supportPipeline.py call the model
    # the same way they always have. The real work - streaming, the
    # inactivity timeout, retries, typed errors, done_reason/thinking
    # capture - is in ollama_client.generate(); settings are in config.py
    # (including the notes on num_ctx, "think", and the Aug 28 thinking-
    # trace diagnostic that used to live here).
    #
    # Raises an errors.OllamaError subclass if no usable answer comes back
    # after retries; never returns a stringified error object as if it
    # were lesson text (the old code could).
    if RUNTIME is None:
        raise RuntimeError("commonFunctions.init_run() was not called before send_to_ollama().")
    label = debug_label or "call"
    debug_dir = None
    if debug_flag and debug_label:
        debug_dir = os.path.dirname(debug_path("x"))
    import ollama_client  # imported here so toDocx.py works without the requests package
    result = ollama_client.generate(RUNTIME, payload, label, debug_dir=debug_dir, timings=TIMINGS)
    return result.text

def strip_markdown_fence(text):
    # The prompt explicitly forbids code fences, but models sometimes wrap
    # output in ```markdown ... ``` anyway. Strip it if present so downstream
    # parsing (day-heading regexes, Pandoc conversion) sees clean Markdown.
    text = text.strip()
    text = re.sub(r"^```(?:markdown|md)?\s*\n", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n```\s*$", "", text)
    return text.strip()

def split_markdown_days(text, days=None):
    # Splits raw Markdown model output into {DAY: day_block_text}.
    # A day block starts at its "# DAY" heading (MARKDOWN_LAYOUT /
    # FIVEMINUTE_FORMAT rule 1) and runs until the next "# DAY" heading
    # or end of text.
    days = days or ALL_DAYS
    pattern = re.compile(r"(?m)^#\s+(" + "|".join(days) + r")\s*$", flags=re.IGNORECASE)
    matches = list(pattern.finditer(text))
    blocks = {}
    for i, m in enumerate(matches):
        day = m.group(1).upper()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks[day] = text[start:end].strip()
    return blocks

def markdown_looks_truncated(text, days, required_sections=None):
    # Heuristic for cut-off Markdown generation. There's no closing tag to
    # check (unlike </html>), so instead: if the LAST requested day's block
    # is missing one of the required sections, generation likely stopped
    # partway through that day rather than ending cleanly.
    required_sections = required_sections or MAIN_REQUIRED_SECTIONS
    if not days:
        return False
    blocks = split_markdown_days(text, days)
    last_day = days[-1].upper()
    if last_day not in blocks:
        return True
    last_block = blocks[last_day]
    missing = [s for s in required_sections if f"## {s}" not in last_block]
    return bool(missing)

def validate_markdown(text, label, required_sections, days=None):
    # Shared by both scripts: pipeline.py passes MAIN_REQUIRED_SECTIONS,
    # supportPipeline.py passes SUPPORT_REQUIRED_SECTIONS.
    # Check each day separately - a section missing from one day (e.g. Sunday
    # losing Student Questions) is invisible to a whole-document check when
    # the other six days still have it.
    #
    # Returns the list of STRUCTURAL problems (a whole day missing, or a
    # day missing a required section, or a section heading with nothing
    # under it). The orchestrators exit with code 3 when this list is not
    # empty. Everything else (accents, HTML, arrows, fences) is a warning
    # only - logged, collected in the run summary, but not fatal.
    structural = []
    expected_days = [d.upper() for d in (days or ALL_DAYS)]
    day_blocks = split_markdown_days(text, expected_days)
    if day_blocks:
        for day in expected_days:
            if day not in day_blocks:
                structural.append(f"{label}: {day} is missing entirely")
                continue
            block = day_blocks[day]
            missing = [s for s in required_sections if f"## {s}" not in block]
            if missing:
                structural.append(f"{label} {day} missing sections: {missing}")
            empty = [s for s in required_sections
                     if f"## {s}" in block and not _section_body(block, s)]
            if empty:
                structural.append(f"{label} {day} has empty section(s): {empty}")
    else:
        structural.append(f"{label}: no day headings found at all")
    for problem in structural:
        log.warning(problem)

    if re.search(r"(?m)^\d+\. .+ → .+$", text):
        log.warning(f"{label} has a numbered item containing '→' - "
                    f"Translation Practice may include answers.")
    if not any(c in text for c in "áéíóúñ"):
        log.warning(f"{label} may have lost Spanish accents")
    if re.search(r"</?[a-zA-Z][^>]*>", text):
        log.warning(f"{label} contains what looks like an HTML tag - Markdown output should have none")
    if "```" in text:
        log.warning(f"{label} contains a code fence that strip_markdown_fence() didn't catch")
    # Known Pandoc failure mode: a "Spanish → English" / "English → Spanish"
    # label directly followed by a numbered list with no blank line in
    # between gets merged into one run-on paragraph in the docx - the list
    # numbering and line breaks are silently lost. Catch it here so it
    # surfaces as a warning instead of only being visible after opening
    # the .docx.
    if re.search(r"(Spanish\s*→\s*English|English\s*→\s*Spanish)\n1\.", text):
        log.warning(f"{label} has a Translation Practice label directly followed by "
                    f"'1.' with no blank line - this will merge into a run-on paragraph in the docx.")
    return structural


def _section_body(day_block, section_name):
    m = re.search(rf"(?ms)^##\s*{re.escape(section_name)}\s*$(.*?)(?=^##\s|^---\s*$|\Z)", day_block)
    return m.group(1).strip() if m else ""


def check_day_heading_format(markdown_text, days=None, label=""):
    # Both pipeline.py and supportPipeline.py require the exact
    # "# DAY" heading format (see MARKDOWN_LAYOUT / FIVEMINUTE_FORMAT
    # rule 1 in their respective templates). Centralized here so both
    # scripts check it the same way rather than keeping two copies that
    # can drift apart. Returns the list of problems found.
    days = days or ALL_DAYS
    prefix = f"{label}: " if label else ""
    problems = []
    for day in days:
        exact = re.search(rf"(?m)^#\s+{day}\s*$", markdown_text, flags=re.IGNORECASE)
        if not exact:
            loose = re.search(rf"(?m)^#{{1,3}}\s*{day}\b.*$", markdown_text, flags=re.IGNORECASE)
            if loose:
                problems.append(f"{prefix}{day} heading doesn't match the required '# {day}' format exactly: {loose.group(0)!r}")
            else:
                problems.append(f"{prefix}{day} heading not found in expected form at all.")
    for p in problems:
        log.warning(p)
    return problems


def accept_full_week_review(original, reviewed, required_sections, label):
    """
    Guard for the self-review passes, which return the WHOLE week and used
    to replace it unchecked - an empty, truncated or restructured answer
    became the final lesson. The review is accepted only if it still has
    every day the original had, every required section in each of those
    days, and a length within config's ratio band. Otherwise the original
    is kept and a warning says why.
    """
    days = list(split_markdown_days(original).keys())
    reasons = []
    if not reviewed or not reviewed.strip():
        reasons.append("the review came back empty")
    else:
        rblocks = split_markdown_days(reviewed, days or None)
        for day in days:
            if day not in rblocks:
                reasons.append(f"{day} is missing")
                continue
            missing = [s for s in required_sections if f"## {s}" not in rblocks[day]]
            if missing:
                reasons.append(f"{day} lost {missing}")
        ratio = len(reviewed) / max(1, len(original))
        if ratio < config.SELF_REVIEW_MIN_LENGTH_RATIO:
            reasons.append(f"it is only {ratio:.0%} of the original length (probably cut off)")
        elif ratio > config.SELF_REVIEW_MAX_LENGTH_RATIO:
            reasons.append(f"it is {ratio:.0%} of the original length (probably added commentary)")
    if reasons:
        log.warning(f"{label}: review rejected, keeping the un-reviewed week - " + "; ".join(reasons[:6])
                    + (" ..." if len(reasons) > 6 else ""))
        return original, False
    log.info(f"{label}: review accepted.")
    return reviewed, True


def apply_corrections(text, corrections):
    for wrong, right in corrections:
        text = re.sub(wrong, right, text, flags=re.IGNORECASE)
    return text


def _atomic_write(full_path, text):
    # Temp file + rename: a crash or Ctrl-C mid-write never leaves a
    # half-written lesson behind.
    tmp = f"{full_path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, full_path)


def write_markdown(text, identifier, suffix):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{identifier}_{suffix}_{timestamp}.md"
    full_path = os.path.join(lesson_dir, filename)
    os.makedirs(lesson_dir, exist_ok=True)
    _atomic_write(full_path, text)
    log.info(f"Saved: {full_path}")
    return full_path

def write_markdown_fixed(text, filename):
    # Writes to a constant filename (no timestamp), overwriting whatever
    # was there before. See MAIN_SUPPORT_FILENAME above - this is purely a
    # command-line convenience, not a second copy of record.
    full_path = os.path.join(lesson_dir, filename)
    os.makedirs(lesson_dir, exist_ok=True)
    _atomic_write(full_path, text)
    log.info(f"Saved: {full_path}")
    return full_path

# ---------------------------------------------------------------------------
# Day-section extractors used by supportPipeline.py to build the Five-Minute
# prompt from the finished Main lesson. Moved here from the retired
# generateSupport.py (Oct 2026) so nothing imports that script any more.
# ---------------------------------------------------------------------------

def extract_day_vocab(main_markdown):
    # Look for a "## Vocabulary" section within each day's own block, so
    # the vocab handed to the Five-Minute prompt is labeled with the day
    # it actually belongs to.
    vocab_manifest = []
    day_blocks = split_markdown_days(main_markdown)
    for day in ALL_DAYS:
        chunk = day_blocks.get(day)
        if not chunk:
            continue
        vocab_match = re.search(
            r"(?ms)^##\s*Vocabulary\s*$(.*?)(?=^##\s|\Z)",
            chunk
        )
        if not vocab_match:
            log.warning(f"no Vocabulary section found for {day}; Five-Minute vocab for {day} will be empty.")
            continue
        text = vocab_match.group(1).strip()
        vocab_manifest.append(f"#BEGIN {day}_VOCAB\n{text}\n#END {day}_VOCAB\n")
    return "\n".join(vocab_manifest)

def extract_day_story(main_markdown):
    # Returns ONLY the English half of each day's Story section (per
    # MARKDOWN_LAYOUT rule 3 in MainLessonTemplate.txt: "**English:**"
    # ... "**Spanish:**" ... ). The Five-Minute lesson never includes a
    # Spanish mini-story, so the model never needs the Spanish half.
    manifest = []
    day_blocks = split_markdown_days(main_markdown)
    for day in ALL_DAYS:
        chunk = day_blocks.get(day)
        if not chunk:
            continue
        story_match = re.search(
            r"(?ms)^##\s*Story\s*$.*?\*\*English:\*\*\s*(.*?)\*\*Spanish:\*\*",
            chunk
        )
        if not story_match:
            log.warning(f"no Story/English block found for {day}; Five-Minute lesson for {day} will have no source story.")
            continue
        text = re.sub(r"\s+", " ", story_match.group(1)).strip()
        manifest.append(f"#BEGIN {day}_STORY\n{text}\n#END {day}_STORY\n")
    return "\n".join(manifest)
