#!/usr/bin/env python3
# commonFunctions.py
#
# Shared "library" module for the ESL lesson generation pipeline.
# generateMain.py and generateSupport.py both import from this file rather
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
# convert_markdown_to_docx() is new - it's the Pandoc step. Both
# generateMain.py and generateSupport.py now use these same helpers.

import os
import re
import requests
import pypandoc
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen38"

weekly_template_dir = "/Users/gene/Documents/RAG/source_docs/weeklytemplates"
lesson_dir = "/Users/gene/Documents/RAG/source_docs/WeeklyLessons"

# Optional Pandoc reference-doc for Word heading styles (Heading 1 for day
# headings, Heading 2 for section headings). If this file doesn't exist,
# convert_markdown_to_docx() falls back to Pandoc's default styling rather
# than failing - build this once in Word: create a .docx, define Heading 1
# / Heading 2 the way you want them to look, save it here.
reference_doc_path = os.path.join(weekly_template_dir, "reference.docx")

ALL_DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]

# Fixed filename generateMain.py also writes the Main lesson to, alongside
# its normal timestamped file, so generateSupport.py can be called with a
# constant path instead of the caller having to copy the timestamp out of
# generateMain.py's console output. Gets silently overwritten by the next
# generateMain.py run - the timestamped file from write_markdown() remains
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
# generateSupport.py passes this to validate_markdown() and
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
    (r"\balmuerzo en bolsa\b", "almuerzo en llevar"),
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
    (r"\bcalientito\b", "caliente"),
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
    # NOTE: Ollama's /api/generate only reads generation parameters
    # (temperature, num_predict, num_ctx, etc.) from a nested "options"
    # object. A top-level "temperature" key is silently ignored - so
    # temperature here matches the qwen38 Modelfile's tuned 0.5 explicitly,
    # rather than assuming the top-level field would take effect.
    #
    # num_ctx is set well above the ~10,000-13,000 tokens a full week's
    # prompt+response typically needs, as a deliberate diagnostic choice:
    # if truncation happens despite this headroom, num_ctx is NOT the
    # cause - check done_reason below instead of assuming.
    #
    # NOTE: "think" is intentionally NOT set here (reverted from a brief
    # "think": False test on Aug 28, 2026). An earlier attempt at
    # "think": False (pre-dating the Mon-Thu/Fri-Sun call split and the
    # Markdown rewrite) fixed a mid-generation truncation issue but
    # introduced a worse regression (the model treating one day as a
    # complete task and stopping early, on both Week 31 and Week 32
    # storyboards).
    #
    # DIAGNOSTIC RUN (Aug 28, 2026): eval_count for a real run came back
    # at ~89,500 response tokens total (part1+part2) against a final
    # saved document of only ~4,600 words (~6,400 tokens est.) - a ~14x
    # gap. The leading theory is that most of that gap is an invisible
    # thinking trace: Ollama returns reasoning output in a separate
    # "thinking" JSON field on models with thinking enabled, which this
    # function has never read (only "response" below) - so it's been
    # silently costing generation time without ever showing up in the
    # saved file or being counted by anything downstream. This run
    # captures that field (if present) to debug_{label}_thinking.txt so
    # it can actually be read, instead of just inferred from token math.
    data = {
        "model": MODEL_NAME,
        "prompt": payload,
        "stream": False,
        "options": {
            "temperature": 0.5,
            "num_ctx": 65536,
            "num_predict": -1
        }
    }
    response = requests.post(OLLAMA_URL, json=data)
    response.raise_for_status()
    resp_json = response.json()

    # Surface WHY generation ended, instead of only keeping the text.
    # done_reason "stop" = the model hit a stop token on its own (a
    # model/prompt behavior question, not a resource limit).
    # done_reason "length" = it genuinely hit num_predict/context.
    if isinstance(resp_json, dict):
        done_reason = resp_json.get("done_reason", "unknown")
        eval_count = resp_json.get("eval_count", "?")
        prompt_eval_count = resp_json.get("prompt_eval_count", "?")
        print(f"Ollama finished (label={debug_label}): done_reason={done_reason}, "
              f"prompt_tokens={prompt_eval_count}, response_tokens={eval_count}")
        if debug_flag and debug_label:
            with open(f"debug_{debug_label}_metadata.txt", "w", encoding="utf-8") as f:
                for key in ("done", "done_reason", "prompt_eval_count", "eval_count",
                            "total_duration", "load_duration", "prompt_eval_duration", "eval_duration"):
                    f.write(f"{key}: {resp_json.get(key, '(not present)')}\n")

        # DIAGNOSTIC: capture the thinking trace, if Ollama returned one,
        # completely separate from the response text used for the lesson.
        # This never touches the saved .md/.docx - it's purely for reading
        # what the model was actually doing with the extra tokens.
        thinking = resp_json.get("thinking")
        if thinking:
            thinking_words = len(thinking.split())
            print(f"Ollama returned a thinking trace (label={debug_label}): ~{thinking_words} words")
            if debug_flag and debug_label:
                with open(f"debug_{debug_label}_thinking.txt", "w", encoding="utf-8") as f:
                    f.write(thinking)
        elif debug_flag and debug_label:
            print(f"NOTE: no 'thinking' field in Ollama's response for label={debug_label} "
                  f"(either this model/version doesn't separate it, or there's nothing to show).")

    # Ollama returns JSON with a "response" field in earlier versions; handle both str and dict
    if isinstance(resp_json, dict) and "response" in resp_json:
        return resp_json["response"]
    # Fallback if API returns raw text
    return resp_json if isinstance(resp_json, str) else str(resp_json)

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

def validate_markdown(text, label, required_sections):
    # Shared by both scripts: generateMain.py passes MAIN_REQUIRED_SECTIONS,
    # generateSupport.py passes SUPPORT_REQUIRED_SECTIONS.
    # Check each day separately - a section missing from one day (e.g. Sunday
    # losing Student Questions) is invisible to a whole-document check when
    # the other six days still have it.
    day_blocks = split_markdown_days(text)
    if day_blocks:
        for day, block in day_blocks.items():
            missing = [s for s in required_sections if f"## {s}" not in block]
            if missing:
                print(f"WARNING: {label} {day} missing sections: {missing}")
    else:
        missing = [section for section in required_sections if f"## {section}" not in text]
        if missing:
            print(f"WARNING: {label} missing sections: {missing}")
    if re.search(r"(?m)^\d+\. .+ → .+$", text):
        print(f"WARNING: {label} has a numbered item containing '→' - "
              f"Translation Practice may include answers.")
    if not any(c in text for c in "áéíóúñ"):
        print(f"WARNING: {label} may have lost Spanish accents")
    if re.search(r"</?[a-zA-Z][^>]*>", text):
        print(f"WARNING: {label} contains what looks like an HTML tag - Markdown output should have none")
    if "```" in text:
        print(f"WARNING: {label} contains a code fence that strip_markdown_fence() didn't catch")
    # Known Pandoc failure mode: a "Spanish → English" / "English → Spanish"
    # label directly followed by a numbered list with no blank line in
    # between gets merged into one run-on paragraph in the docx - the list
    # numbering and line breaks are silently lost. Catch it here so it
    # surfaces as a warning instead of only being visible after opening
    # the .docx.
    if re.search(r"(Spanish\s*→\s*English|English\s*→\s*Spanish)\n1\.", text):
        print(f"WARNING: {label} has a Translation Practice label directly followed by "
              f"'1.' with no blank line - this will merge into a run-on paragraph in the docx.")

def check_day_heading_format(markdown_text, days=None, label=""):
    # Both generateMain.py and generateSupport.py require the exact
    # "# DAY" heading format (see MARKDOWN_LAYOUT / FIVEMINUTE_FORMAT
    # rule 1 in their respective templates). Centralized here so both
    # scripts check it the same way rather than keeping two copies that
    # can drift apart.
    days = days or ALL_DAYS
    prefix = f"{label}: " if label else ""
    for day in days:
        exact = re.search(rf"(?m)^#\s+{day}\s*$", markdown_text, flags=re.IGNORECASE)
        if not exact:
            loose = re.search(rf"(?m)^#{{1,3}}\s*{day}\b.*$", markdown_text, flags=re.IGNORECASE)
            if loose:
                print(f"WARNING: {prefix}{day} heading doesn't match the required '# {day}' format exactly: {loose.group(0)!r}")
            else:
                print(f"WARNING: {prefix}{day} heading not found in expected form at all.")

def apply_corrections(text, corrections):
    for wrong, right in corrections:
        text = re.sub(wrong, right, text, flags=re.IGNORECASE)
    return text

def write_markdown(text, identifier, suffix):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{identifier}_{suffix}_{timestamp}.md"
    full_path = os.path.join(lesson_dir, filename)
    os.makedirs(lesson_dir, exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Saved: {full_path}")
    return full_path

def write_markdown_fixed(text, filename):
    # Writes to a constant filename (no timestamp), overwriting whatever
    # was there before. See MAIN_SUPPORT_FILENAME above - this is purely a
    # command-line convenience, not a second copy of record.
    full_path = os.path.join(lesson_dir, filename)
    os.makedirs(lesson_dir, exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Saved: {full_path}")
    return full_path

def convert_markdown_to_docx(markdown_text, identifier, suffix):
    # Converts the final Markdown text to a .docx via Pandoc. If
    # reference_doc_path exists, Pandoc maps "#"/"##" to that document's
    # Heading 1 / Heading 2 styles - build reference.docx once in Word and
    # every future lesson picks up the same look automatically.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{identifier}_{suffix}_{timestamp}.docx"
    full_path = os.path.join(lesson_dir, filename)
    os.makedirs(lesson_dir, exist_ok=True)

    extra_args = ["--standalone"]
    if os.path.exists(reference_doc_path):
        extra_args.append(f"--reference-doc={reference_doc_path}")
    else:
        print(f"NOTE: no reference-doc found at {reference_doc_path} - using Pandoc's default docx styling")

    pypandoc.convert_text(
        markdown_text,
        to="docx",
        format="markdown+hard_line_breaks",
        outputfile=full_path,
        extra_args=extra_args,
    )
    print(f"Saved: {full_path}")
    return full_path
