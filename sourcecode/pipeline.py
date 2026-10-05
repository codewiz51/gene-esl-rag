#!/usr/bin/env python3
"""
pipeline.py

Usage:
    python3 pipeline.py <identifier> <storyboard.md> <template.txt> [Debug|NoDebug]

Example:
    python3 pipeline.py 35 Week35StoryBoard.md MainLessonTemplate.txt Debug

Runs the pass pipeline end to end and writes NN_MAIN_PASSPIPELINE_<ts>.md
into commonFunctions.lesson_dir, plus mainSupport.md (fixed name) as the
input for supportPipeline.py.
"""

import sys
import os

import commonFunctions as common

from storyboard_utils import (
    extract_weekly_verb_focus,
    extract_day_story_requirements,
    extract_day_vocab_suggestions,
    extract_day_study_notes,
    extract_week_notes,
    extract_day_focus,
)
from state import WeekState, ALL_DAYS
import passes
from qa_utils import lint_hints


def main():
    if len(sys.argv) not in (4, 5):
        print("Usage: python3 pipeline.py <identifier> <storyboard.md> <template.txt> [Debug|NoDebug]")
        sys.exit(1)

    identifier = sys.argv[1]
    storyboard_file = sys.argv[2]
    template_file = sys.argv[3]
    debug_flag = True
    if len(sys.argv) == 5:
        debug_flag = not sys.argv[4].strip().lower().startswith("n")

    storyboard_path = os.path.join(common.weekly_template_dir, storyboard_file)
    template_path = os.path.join(common.weekly_template_dir, template_file)

    storyboard_raw = common.read_file(storyboard_path)
    template_text = common.read_file(template_path)

    weekly_corrections = common.parse_weekly_corrections(storyboard_raw)
    corrections = common.BASE_CORRECTIONS + weekly_corrections

    weekly_verb_focus = extract_weekly_verb_focus(storyboard_raw)
    story_requirements_by_day = extract_day_story_requirements(storyboard_raw)
    vocab_by_day = extract_day_vocab_suggestions(storyboard_raw)
    study_notes_by_day = extract_day_study_notes(storyboard_raw)
    week_notes = extract_week_notes(storyboard_raw)
    day_focus_by_day = extract_day_focus(story_requirements_by_day)
    if week_notes:
        print("WEEK NOTES found.")
    if study_notes_by_day:
        print(f"STUDY NOTES found for: {', '.join(study_notes_by_day)}")

    week_state = WeekState()

    # --- Layer 1: Vocabulary (needs only the storyboard's VOCAB blocks) ---
    passes.vocabulary_pass(template_text, vocab_by_day, week_state, debug_flag=debug_flag)

    # --- Layer 2: Story (needs Story Requirements + finalized Vocabulary) ---
    passes.story_pass(template_text, story_requirements_by_day, weekly_verb_focus, week_state, debug_flag=debug_flag, week_notes=week_notes)

    # --- Layer 3: Warmup + Grammar (needs verb focus + Vocabulary) ---
    passes.warmup_grammar_pass(template_text, story_requirements_by_day, weekly_verb_focus, week_state, debug_flag=debug_flag, week_notes=week_notes)

    # --- Layer 3b: translate the Grammar explanation to Spanish, narrow single-purpose pass ---
    passes.grammar_translate_pass(template_text, week_state, debug_flag=debug_flag)

    # --- Layer 4: Examples + Translation Practice (needs finished Story) ---
    passes.examples_translation_pass(template_text, week_state, study_notes_by_day=study_notes_by_day, debug_flag=debug_flag, week_notes=week_notes, day_focus_by_day=day_focus_by_day)

    # --- Layer 5: Student Questions (whole-week context, no repeats) ---
    passes.student_questions_pass(template_text, week_state, study_notes_by_day=study_notes_by_day, debug_flag=debug_flag, week_notes=week_notes)

    # --- Assemble the week from all layers ---
    assembled = week_state.assemble_week(ALL_DAYS)

    for day in ALL_DAYS:
        missing = week_state.missing_sections(day)
        if missing:
            print(f"WARNING: {day} is missing section(s) after all passes: {missing}")

    # --- Layer 6: self-review (judgment only - register variety, prose level) ---
    reviewed = passes.self_review_pass(assembled, debug_flag=debug_flag)

    final_markdown = common.apply_corrections(reviewed, corrections)

    lint_hints(final_markdown, label="main lesson")
    common.validate_markdown(final_markdown, "pass-pipeline main lesson", common.MAIN_REQUIRED_SECTIONS)
    common.check_day_heading_format(final_markdown, label="pass-pipeline")

    common.write_markdown(final_markdown, identifier, "MAIN_PASSPIPELINE")
    common.write_markdown_fixed(final_markdown, common.MAIN_SUPPORT_FILENAME)

    print("Done. Compare this output against the current NN_MAIN_corrected.md before trusting it for students.")


if __name__ == "__main__":
    main()
