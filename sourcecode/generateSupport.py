#!/usr/bin/env python3
import sys
import os
import re

import commonFunctions as common

def extract_day_vocab(main_markdown):
    # Look for a "## Vocabulary" section within each day's own block, so
    # the vocab handed to the Five-Minute prompt is labeled with the day
    # it actually belongs to. Reuses common.split_markdown_days() - the
    # same day-splitting logic generateMain.py's own validation uses, so
    # this stays in sync automatically if that function's day-heading
    # regex ever changes.
    vocab_manifest = []
    day_blocks = common.split_markdown_days(main_markdown)
    for day in common.ALL_DAYS:
        chunk = day_blocks.get(day)
        if not chunk:
            continue
        vocab_match = re.search(
            r"(?ms)^##\s*Vocabulary\s*$(.*?)(?=^##\s|\Z)",
            chunk
        )
        if not vocab_match:
            print(f"WARNING: no Vocabulary section found for {day}; Five-Minute vocab for {day} will be empty.")
            continue
        text = vocab_match.group(1).strip()
        vocab_manifest.append(f"#BEGIN {day}_VOCAB\n{text}\n#END {day}_VOCAB\n")
    return "\n".join(vocab_manifest)

def extract_day_story(main_markdown):
    # Returns ONLY the English half of each day's Story section (per
    # MARKDOWN_LAYOUT rule 3 in MainLessonTemplate.txt: "**English:**"
    # ... "**Spanish:**" ... ), as a manifest the Five-Minute prompt can
    # compress. The Five-Minute lesson never includes a Spanish mini-story,
    # so there's no reason to hand the model the Spanish half at all.
    manifest = []
    day_blocks = common.split_markdown_days(main_markdown)
    for day in common.ALL_DAYS:
        chunk = day_blocks.get(day)
        if not chunk:
            continue
        story_match = re.search(
            r"(?ms)^##\s*Story\s*$.*?\*\*English:\*\*\s*(.*?)\*\*Spanish:\*\*",
            chunk
        )
        if not story_match:
            print(f"WARNING: no Story/English block found for {day}; Five-Minute lesson for {day} will have no source story.")
            continue
        text = re.sub(r"\s+", " ", story_match.group(1)).strip()
        manifest.append(f"#BEGIN {day}_STORY\n{text}\n#END {day}_STORY\n")
    return "\n".join(manifest)

def main():
    if len(sys.argv) not in (6, 7):
        print("Usage: python3 generateSupport.py <identifier> <main_lesson.md> <storyboard.md> <fiveMinuteTemplate.txt> <unifiedPrompt.md> [Debug|NoDebug]")
        print("  main_lesson.md is looked up in the lessons output directory (the .md file")
        print("  generateMain.py writes, NOT the .docx).")
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

    main_markdown = common.read_file(main_lesson_path)
    storyboard_raw = common.read_file(storyboard_path)
    five_template = common.read_file(five_template_path)
    unified_prompt = common.read_file(prompt_path)

    weekly_corrections = common.parse_weekly_corrections(storyboard_raw)
    corrections = common.BASE_CORRECTIONS + weekly_corrections
    if weekly_corrections:
        print(f"Loaded {len(weekly_corrections)} weekly correction(s) from storyboard.")

    vocab_manifest = extract_day_vocab(main_markdown)
    story_manifest = extract_day_story(main_markdown)

    if not vocab_manifest.strip() or not story_manifest.strip():
        print("ERROR: Could not extract per-day vocab and/or story from the main lesson Markdown.")
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

    five_markdown = common.strip_markdown_fence(result_five if isinstance(result_five, str) else str(result_five))

    # Five-Minute always covers whatever days had source material - not
    # necessarily all seven (extraction warnings above already flagged any
    # day that's missing vocab/story), so check against the days we
    # actually supplied rather than assuming a full week.
    supplied_days = [d for d in common.ALL_DAYS if f"#BEGIN {d}_STORY" in story_manifest]

    day_blocks = common.split_markdown_days(five_markdown, supplied_days)
    if len(day_blocks) == 0:
        print("ERROR: No day headings found in the Five-Minute response at all "
              f"(expected: {', '.join(supplied_days)}).")
        if debug_flag:
            with open("debug_five_raw_response.txt", "w", encoding="utf-8") as f:
                f.write(five_markdown)
        sys.exit(1)

    missing_days = [d for d in supplied_days if d not in day_blocks]
    if missing_days:
        print(f"WARNING: Five-Minute lesson is missing day(s): {', '.join(missing_days)}")

    if common.markdown_looks_truncated(five_markdown, supplied_days, common.SUPPORT_REQUIRED_SECTIONS):
        print("WARNING: Five-Minute response may be cut off mid-generation "
              "(the last supplied day is missing one or more required sections).")
        print("Check the 'done_reason' printed above and debug_five_metadata.txt.")

    common.check_day_heading_format(five_markdown, days=supplied_days, label="Five-Minute")

    five_markdown = common.apply_corrections(five_markdown, corrections)
    common.validate_markdown(five_markdown, "Five-Minute lesson", common.SUPPORT_REQUIRED_SECTIONS)

    common.write_markdown(five_markdown, identifier, "FIVEMIN")
    common.convert_markdown_to_docx(five_markdown, identifier, "FIVEMIN")

    print("Done.")

if __name__ == "__main__":
    main()
