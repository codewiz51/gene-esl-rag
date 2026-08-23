#!/usr/bin/env python3
import sys
import os
import re

import commonFunctions as common

def _split_main_html_by_day(main_html):
    # Locate each day heading and return (day_name, chunk_text) in order.
    # The main lesson template does not reliably pin a fixed heading level
    # OR exact heading content for day names - observed as <h1>, <h2>, and
    # with trailing text (e.g. "Monday - Do / Did") across different runs.
    # This matches the day name at the START of any h1-h4 heading.
    day_pattern = re.compile(
        r"<h[1-4][^>]*>\s*(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY)\b",
        flags=re.IGNORECASE
    )
    markers = [(m.start(), m.group(1).upper()) for m in day_pattern.finditer(main_html)]
    markers.sort(key=lambda x: x[0])
    chunks = []
    for idx, (pos, day) in enumerate(markers):
        end = markers[idx + 1][0] if idx + 1 < len(markers) else len(main_html)
        chunks.append((day, main_html[pos:end]))
    return chunks

def extract_day_vocab(main_html):
    # Look for a Vocabulary heading within each day's own chunk, so the
    # label attached to each vocab list is the day it actually belongs to.
    vocab_manifest = []
    for day, chunk in _split_main_html_by_day(main_html):
        vocab_match = re.search(
            r"<h[1-4][^>]*>\s*Vocabulary(?: Review)?\s*</h[1-4]>(.*?)(?=<h[1-4]|$)",
            chunk, flags=re.DOTALL | re.IGNORECASE
        )
        if not vocab_match:
            print(f"WARNING: no Vocabulary block found for {day}; Five-Minute vocab for {day} will be empty.")
            continue
        text = re.sub(r"<[^>]+>", "", vocab_match.group(1)).strip()
        vocab_manifest.append(f"#BEGIN {day}_VOCAB\n{text}\n#END {day}_VOCAB\n")
    return "\n".join(vocab_manifest)

def extract_day_story(main_html):
    # Returns the English half of each day's Story table as a manifest
    # the Five-Minute prompt can compress. The Story table can appear
    # immediately after the day heading or after other sections (e.g. a
    # Warm-Up block), so it's located within each day's own chunk.
    manifest = []
    for day, chunk in _split_main_html_by_day(main_html):
        story_match = re.search(
            r"<table>.*?<td>(.*?)</td>",
            chunk, flags=re.DOTALL | re.IGNORECASE
        )
        if not story_match:
            print(f"WARNING: no Story block found for {day}; Five-Minute lesson for {day} will have no source story.")
            continue
        text = re.sub(r"<[^>]+>", " ", story_match.group(1))
        text = re.sub(r"\s+", " ", text).strip()
        manifest.append(f"#BEGIN {day}_STORY\n{text}\n#END {day}_STORY\n")
    return "\n".join(manifest)

FIVE_REQUIRED_SECTIONS = [
    "Vocabulary Review",
    "Grammar Focus",
    "Mini Story",
    "Translation Practice",
    "Student Questions"
]

def main():
    if len(sys.argv) not in (6, 7):
        print("Usage: python3 generateSupport.py <identifier> <main_lesson.html> <storyboard.md> <fiveMinuteTemplate.txt> <unifiedPrompt.md> [Debug|NoDebug]")
        print("  main_lesson.html is looked up in the lessons output directory.")
        print("  storyboard.md, fiveMinuteTemplate.txt, unifiedPrompt.md are looked up in the templates directory.")
        sys.exit(1)

    identifier = sys.argv[1]
    main_lesson_file = sys.argv[2]
    storyboard_file = sys.argv[3]
    five_template_file = sys.argv[4]
    prompt_file = sys.argv[5]
    debug_flag = True
    if len(sys.argv) == 7:
        arg6 = sys.argv[6].strip().lower()
        if arg6.startswith("n"):
            debug_flag = False

    main_lesson_path = os.path.join(common.lesson_dir, main_lesson_file)
    storyboard_path = os.path.join(common.weekly_template_dir, storyboard_file)
    five_template_path = os.path.join(common.weekly_template_dir, five_template_file)
    prompt_path = os.path.join(common.weekly_template_dir, prompt_file)

    main_html = common.read_file(main_lesson_path)
    storyboard_raw = common.read_file(storyboard_path)
    five_template = common.read_file(five_template_path)
    unified_prompt = common.read_file(prompt_path)

    weekly_corrections = common.parse_weekly_corrections(storyboard_raw)
    corrections = common.BASE_CORRECTIONS + weekly_corrections
    if weekly_corrections:
        print(f"Loaded {len(weekly_corrections)} weekly correction(s) from storyboard.")

    vocab_manifest = extract_day_vocab(main_html)
    story_manifest = extract_day_story(main_html)

    if not vocab_manifest.strip() or not story_manifest.strip():
        print("ERROR: Could not extract per-day vocab and/or story from the main lesson HTML.")
        print("This means the main lesson's day-heading or Story/Vocabulary structure")
        print("doesn't match what the extractor expects. Aborting BEFORE calling Ollama,")
        print("rather than sending it an empty prompt.")
        if debug_flag:
            with open("debug_extraction_failure.txt", "w", encoding="utf-8") as f:
                f.write(f"vocab_manifest ({len(vocab_manifest)} chars):\n{vocab_manifest}\n\n")
                f.write(f"story_manifest ({len(story_manifest)} chars):\n{story_manifest}\n")
        sys.exit(1)

    payload_five = f"{five_template}\n\n{story_manifest}\n\n{vocab_manifest}\n\n{unified_prompt}"

    if debug_flag:
        with open("debug_five_prompt.txt", "w", encoding="utf-8") as f:
            f.write(payload_five)

    print("Generating Five-Minute lesson...")
    try:
        result_five = common.send_to_ollama(payload_five, debug_label="five", debug_flag=debug_flag)
    except Exception as e:
        print(f"ERROR: Ollama request failed: {e}")
        if debug_flag:
            with open("debug_five_error.txt", "w", encoding="utf-8") as f:
                f.write(str(e))
        sys.exit(1)

    blocks_five = common.split_html_blocks(result_five)

    if len(blocks_five) == 0:
        if common.looks_truncated(result_five if isinstance(result_five, str) else str(result_five)):
            print("ERROR: The Five-Minute response was cut off mid-generation (opened <html> but never closed it).")
            print("Check the 'done_reason' printed above and debug_five_metadata.txt.")
        else:
            print("ERROR: No <html> block found in Five-Minute lesson.")
        if debug_flag:
            with open("debug_five_raw_response.txt", "w", encoding="utf-8") as f:
                f.write(result_five if isinstance(result_five, str) else str(result_five))
        sys.exit(1)

    five_html = blocks_five[0]
    five_html = common.apply_corrections(five_html, corrections)
    common.validate_html(five_html, "Five-Minute lesson", FIVE_REQUIRED_SECTIONS)
    common.write_html(five_html, identifier, "FIVEMIN")

    print("Done.")

if __name__ == "__main__":
    main()
