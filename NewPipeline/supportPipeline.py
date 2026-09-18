#!/usr/bin/env python3
"""
supportPipeline.py

Same command-line shape and inputs/outputs as generateSupport.py, with
one addition: a judgment-only self-review pass over the fully assembled
Five-Minute week, before corrections/validation/write.

generateSupport.py itself is untouched - this is a separate script, the
same relationship pipeline.py has to generateMain.py, so the original
stays available as a known-good fallback.

Usage (identical to generateSupport.py):
    python3 supportPipeline.py <identifier> <main_lesson.md> <storyboard.md> <fiveMinuteTemplate.txt> <unifiedPrompt.md> [Debug|NoDebug]

Example:
    python3 supportPipeline.py 35 mainSupport.md Week35StoryBoard.md FiveMinuteTemplate.txt promptFive.md Debug
"""

import sys
import os

sys.path.insert(0, "/Users/gene/Documents/RAG/sourcecode")
import commonFunctions as common  # noqa: E402
import generateSupport as gs      # noqa: E402  (reuse its extraction helpers rather than duplicate them)

import passes  # noqa: E402


def main():
    if len(sys.argv) not in (6, 7):
        print("Usage: python3 supportPipeline.py <identifier> <main_lesson.md> <storyboard.md> <fiveMinuteTemplate.txt> <unifiedPrompt.md> [Debug|NoDebug]")
        sys.exit(1)

    identifier = sys.argv[1]
    main_lesson_file = sys.argv[2]
    storyboard_file = sys.argv[3]
    five_template_file = sys.argv[4]
    prompt_file = sys.argv[5]
    debug_flag = True
    if len(sys.argv) == 7:
        debug_flag = not sys.argv[6].strip().lower().startswith("n")

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

    vocab_manifest = gs.extract_day_vocab(main_markdown)
    story_manifest = gs.extract_day_story(main_markdown)

    if not vocab_manifest.strip() or not story_manifest.strip():
        print("ERROR: Could not extract per-day vocab and/or story from the main lesson Markdown.")
        print("Aborting before calling Ollama, rather than sending it an empty prompt.")
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
        sys.exit(1)

    five_markdown = common.strip_markdown_fence(result_five if isinstance(result_five, str) else str(result_five))

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

    # --- Self-review: judgment-only pass over the whole assembled week ---
    five_markdown = passes.fiveminute_self_review_pass(five_markdown, debug_flag=debug_flag)

    common.check_day_heading_format(five_markdown, days=supplied_days, label="Five-Minute")

    five_markdown = common.apply_corrections(five_markdown, corrections)
    common.validate_markdown(five_markdown, "Five-Minute lesson", common.SUPPORT_REQUIRED_SECTIONS)

    common.write_markdown(five_markdown, identifier, "FIVEMIN_PASSPIPELINE")
    common.convert_markdown_to_docx(five_markdown, identifier, "FIVEMIN_PASSPIPELINE")

    print("Done.")


if __name__ == "__main__":
    main()
