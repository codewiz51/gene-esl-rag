#!/usr/bin/env python3
"""
passes.py

Each function here is one "layer" in the 3D-printer sense: it only
depends on layers already in WeekState, only sees the rule blocks it
needs, and writes its own section(s) for every day in one model call.

Order enforced by pipeline.py:
    1. vocabulary_pass      (storyboard VOCAB blocks -> ## Vocabulary)
    2. story_pass           (storyboard bullets + finalized Vocabulary -> ## Story)
    3. warmup_grammar_pass  (verb focus + Vocabulary -> ## Warmup, ## Grammar)
    4. examples_translation_pass (finished Story + Vocabulary -> ## Examples, ## Translation Practice)
    5. student_questions_pass    (whole week context -> ## Student Questions)
    6. self_review_pass    (whole assembled week -> corrected whole week)

Each pass function returns nothing - it writes directly into the
WeekState passed in.

NOTE: the rule_names/dictionary_names/section_subblocks lists below are
a first cut at "what does this pass actually need to see." Tune them as
you observe real output - that mapping is the main thing worth
iterating on, more than the code structure itself.
"""

import re
import sys

sys.path.insert(0, "/Users/gene/Documents/RAG/sourcecode")
import commonFunctions as common  # noqa: E402

from rule_utils import assemble_rules
from state import ALL_DAYS


def _run_pass(label, rules_text, data_text, output_instructions, debug_flag):
    payload = (
        f"{rules_text}\n\n"
        f"{data_text}\n\n"
        f"{output_instructions}\n"
    )
    if debug_flag:
        with open(f"debug_pass_{label}_prompt.txt", "w", encoding="utf-8") as f:
            f.write(payload)
    print(f"Running pass: {label} ...")
    result = common.send_to_ollama(payload, debug_label=f"pass_{label}", debug_flag=debug_flag)
    text = common.strip_markdown_fence(result if isinstance(result, str) else str(result))
    if debug_flag:
        with open(f"debug_pass_{label}_response.txt", "w", encoding="utf-8") as f:
            f.write(text)
    return text


def _extract_section_per_day(markdown_text, section_name, days=None):
    """
    Given a pass's raw output (day-headed markdown containing only the
    section(s) that pass produces), pull out {DAY: section_text} for one
    named section, using the same "## Section" marker convention as the
    full pipeline.
    """
    days = days or ALL_DAYS
    day_blocks = common.split_markdown_days(markdown_text, days)
    out = {}
    for day, chunk in day_blocks.items():
        m = re.search(
            rf"(?ms)^##\s*{re.escape(section_name)}\s*$(.*?)(?=^##\s|\Z)",
            chunk,
        )
        out[day] = m.group(1).strip() if m else ""
        if not out[day]:
            print(f"WARNING: pass output missing '## {section_name}' for {day}.")
    return out


GENERAL_META = """
You are an ESL lesson generator. Follow all rules given above exactly.
Do NOT add new rules. Do NOT override any rule. Do NOT explain your
reasoning. Do NOT include any HTML tags of any kind anywhere in the
output - this is plain Markdown, not HTML.
""".strip()

OUTPUT_FORMAT_COMMON = GENERAL_META + "\n\n" + """
OUTPUT FORMAT (mandatory):
For EACH of the seven days, output a day heading exactly as:
  # MONDAY
  # TUESDAY
  # WEDNESDAY
  # THURSDAY
  # FRIDAY
  # SATURDAY
  # SUNDAY
(day name only, one "#", ALL CAPS, nothing else on that line)
followed immediately by ONLY the section heading(s) named below for
this pass, in "## Section Name" form. Do NOT output any other section
headings. Do NOT add commentary before or after. Do NOT wrap in a code
fence. Preserve Spanish accents (UTF-8).
""".strip()


def vocabulary_pass(template_text, storyboard_vocab_by_day, week_state, debug_flag=True):
    rules = assemble_rules(
        template_text,
        rule_names=["STORY_LENGTH", "MARKDOWN_LAYOUT"],
        section_subblocks=["Vocabulary"],
    )
    data_parts = ["#BEGIN DAILY VOCAB SOURCE BLOCKS"]
    for day in ALL_DAYS:
        data_parts.append(f"#BEGIN {day}_VOCAB_SOURCE\n{storyboard_vocab_by_day.get(day, '')}\n#END {day}_VOCAB_SOURCE")
    data_parts.append("#END DAILY VOCAB SOURCE BLOCKS")
    data_text = "\n\n".join(data_parts)

    instructions = OUTPUT_FORMAT_COMMON + "\n\nThis pass produces ONLY: ## Vocabulary\n" \
        "Vocabulary MUST come only from that day's VOCAB SOURCE block above - never invent, never import another day's."

    raw = _run_pass("vocabulary", rules, data_text, instructions, debug_flag)
    per_day = _extract_section_per_day(raw, "Vocabulary")
    for day, text in per_day.items():
        week_state.set_section(day, "Vocabulary", text)


def story_pass(template_text, story_requirements_by_day, weekly_verb_focus, week_state, debug_flag=True):
    rules = assemble_rules(
        template_text,
        rule_names=[
            "LANGUAGE_LEVEL", "SENTENCE_STYLE", "SPANISH_ACCURACY",
            "STORY_LENGTH", "MARKDOWN_LAYOUT",
            "NARRATIVE_REWRITE", "STORY_QUALITY",
        ],
        dictionary_names=["CHARACTERS", "CUBAN_REGISTER"],
    )
    data_parts = [f"#BEGIN WEEKLY_VERB_FOCUS\n{weekly_verb_focus}\n#END WEEKLY_VERB_FOCUS"]
    for day in ALL_DAYS:
        vocab = week_state.get_section(day, "Vocabulary")
        data_parts.append(
            f"#BEGIN {day}_STORY_REQUIREMENTS\n{story_requirements_by_day.get(day, '')}\n#END {day}_STORY_REQUIREMENTS"
        )
        data_parts.append(f"#BEGIN {day}_FINALIZED_VOCAB\n{vocab}\n#END {day}_FINALIZED_VOCAB")
    data_text = "\n\n".join(data_parts)

    instructions = OUTPUT_FORMAT_COMMON + "\n\nThis pass produces ONLY: ## Story\n" \
        "Use the exact English:/Spanish: structure from MARKDOWN_LAYOUT rule 3 " \
        "(bold '**English:**' and '**Spanish:**' labels, paragraphs below each). " \
        "You are seeing all seven days at once specifically so you can vary " \
        "emotional register across the week (STORY_QUALITY) - do not make every day read the same."

    raw = _run_pass("story", rules, data_text, instructions, debug_flag)
    per_day = _extract_section_per_day(raw, "Story")
    for day, text in per_day.items():
        week_state.set_section(day, "Story", text)


def warmup_grammar_pass(template_text, story_requirements_by_day, weekly_verb_focus, week_state, debug_flag=True):
    rules = assemble_rules(
        template_text,
        rule_names=["LANGUAGE_LEVEL", "HINTS_AND_BLANKS", "STORY_QUALITY", "MARKDOWN_LAYOUT"],
        section_subblocks=["Warmup", "Grammar"],
    )
    data_parts = [f"#BEGIN WEEKLY_VERB_FOCUS\n{weekly_verb_focus}\n#END WEEKLY_VERB_FOCUS"]
    for day in ALL_DAYS:
        vocab = week_state.get_section(day, "Vocabulary")
        req = story_requirements_by_day.get(day, "")
        data_parts.append(f"#BEGIN {day}_FINALIZED_VOCAB\n{vocab}\n#END {day}_FINALIZED_VOCAB")
        data_parts.append(f"#BEGIN {day}_STORY_REQUIREMENTS\n{req}\n#END {day}_STORY_REQUIREMENTS")
    data_text = "\n\n".join(data_parts)

    instructions = OUTPUT_FORMAT_COMMON + "\n\nThis pass produces ONLY: ## Warmup and ## Grammar (in that order, per day). " \
        "Each day's STORY_REQUIREMENTS block above states which verb or tense that day teaches or " \
        "reinforces (e.g. \"Introduce the verb 'have'\", \"Introduce 'can' - reinforce 'have'\", " \
        "\"Light review of 'have' and 'can'\", \"explore past tense: had, could, got\", " \
        "\"explore future tense: will have, will get, will be able to\"). The Grammar explanation " \
        "and Pattern Practice frame for that day MUST teach exactly that verb/tense - do NOT invent " \
        "or substitute a different grammar point (e.g. do not teach \"should\" or \"going to\" on a " \
        "day whose STORY_REQUIREMENTS names \"can\" or a \"have\"/\"can\" review). WEEKLY_VERB_FOCUS " \
        "gives the general definitions for the week; STORY_REQUIREMENTS tells you which of those this " \
        "specific day is actually about. " \
        "Write the Grammar explanation paragraph in English (max 3 sentences), plus the Pattern " \
        "Practice frame sentences in English with blanks and hints as HINTS_AND_BLANKS requires. " \
        "A later pass translates the Grammar explanation to Spanish - do not attempt that here."

    raw = _run_pass("warmup_grammar", rules, data_text, instructions, debug_flag)
    warmup = _extract_section_per_day(raw, "Warmup")
    grammar = _extract_section_per_day(raw, "Grammar")
    for day in ALL_DAYS:
        week_state.set_section(day, "Warmup", warmup.get(day, ""))
        week_state.set_section(day, "Grammar", grammar.get(day, ""))


def grammar_translate_pass(template_text, week_state, debug_flag=True):
    """
    Narrow, single-purpose pass: translate each day's already-written
    English Grammar explanation into Cuban Spanish. This is deliberately
    split out from warmup_grammar_pass rather than asked for up front,
    because "write the explanation" and "translate it, but leave quoted
    spans and the Pattern Practice list untouched" are different kinds
    of task - bundling them risks the same kind of thrashing that
    TRAILING_TIME_EXPRESSION caused in the old monolithic prompt.
    Established practice (see Week 34 lessons): the Grammar explanation
    is written entirely in Spanish; the Pattern Practice frame sentences
    stay in English exactly as generated.
    """
    rules = assemble_rules(template_text, rule_names=["SPANISH_ACCURACY"], dictionary_names=["CUBAN_REGISTER"])

    data_parts = []
    for day in ALL_DAYS:
        grammar = week_state.get_section(day, "Grammar")
        data_parts.append(f"#BEGIN {day}_GRAMMAR_ENGLISH\n{grammar}\n#END {day}_GRAMMAR_ENGLISH")
    data_text = "\n\n".join(data_parts)

    instructions = GENERAL_META + "\n\n" + f"""
For EACH of the seven days, output a day heading exactly as "# MONDAY"
(day name only, ALL CAPS) followed by "## Grammar" containing that
day's translated content.

Task: translate the Grammar explanation paragraph above (the plain-prose
sentences before "Pattern Practice:") into natural Cuban Spanish.
  - Translate ONLY the explanatory prose sentences.
  - Leave anything inside quotation marks exactly as given, untranslated
    (these are the English target words/phrases being taught).
  - Leave the "Pattern Practice:" label and its entire numbered list
    exactly as given, untranslated, blanks and hints unchanged.
  - Do not add, remove, or reorder any sentence. This is translation,
    not rewriting.
Preserve Spanish accents (UTF-8). Do not wrap in a code fence. Do not
add commentary.
""".strip()

    raw = _run_pass("grammar_translate", rules, data_text, instructions, debug_flag)
    translated = _extract_section_per_day(raw, "Grammar")
    for day in ALL_DAYS:
        if translated.get(day):
            week_state.set_section(day, "Grammar", translated[day])
        else:
            print(f"WARNING: grammar_translate_pass produced nothing for {day} - keeping English original.")


def examples_translation_pass(template_text, week_state, debug_flag=True):
    rules = assemble_rules(
        template_text,
        rule_names=["LANGUAGE_LEVEL", "SENTENCE_STYLE", "SPANISH_ACCURACY", "STORY_LENGTH", "READING_TRANSLATION", "MARKDOWN_LAYOUT"],
        dictionary_names=["CHARACTERS", "CUBAN_REGISTER"],
        section_subblocks=["Examples", "Translation Practice"],
    )
    data_parts = []
    for day in ALL_DAYS:
        story = week_state.get_section(day, "Story")
        vocab = week_state.get_section(day, "Vocabulary")
        data_parts.append(f"#BEGIN {day}_FINISHED_STORY\n{story}\n#END {day}_FINISHED_STORY")
        data_parts.append(f"#BEGIN {day}_FINALIZED_VOCAB\n{vocab}\n#END {day}_FINALIZED_VOCAB")
    data_text = "\n\n".join(data_parts)

    instructions = OUTPUT_FORMAT_COMMON + "\n\nThis pass produces ONLY: ## Examples and ## Translation Practice (in that order, per day). " \
        "The Examples dialogue MUST NOT contradict or add events beyond the FINISHED_STORY above. " \
        "Translation Practice MUST NOT reuse vocabulary words unless they appear naturally in that day's finished story. " \
        "LANGUAGE DIRECTION IS MANDATORY: every item under 'Spanish → English' MUST be written IN SPANISH " \
        "(the student translates it into English) - never write that item in English. Every item under " \
        "'English → Spanish' MUST be written IN ENGLISH. This applies to the required professional-register " \
        "reading item too (READING_TRANSLATION) - write that item's clinical/professional content in natural " \
        "Cuban Spanish, in the Spanish → English list, not in English."

    raw = _run_pass("examples_translation", rules, data_text, instructions, debug_flag)
    examples = _extract_section_per_day(raw, "Examples")
    translation = _extract_section_per_day(raw, "Translation Practice")
    for day in ALL_DAYS:
        week_state.set_section(day, "Examples", examples.get(day, ""))
        week_state.set_section(day, "Translation Practice", translation.get(day, ""))


def student_questions_pass(template_text, week_state, debug_flag=True):
    rules = assemble_rules(
        template_text,
        rule_names=["LANGUAGE_LEVEL", "HINTS_AND_BLANKS", "STORY_QUALITY", "MARKDOWN_LAYOUT"],
        section_subblocks=["Student Questions"],
    )
    data_parts = []
    for day in ALL_DAYS:
        story = week_state.get_section(day, "Story")
        vocab = week_state.get_section(day, "Vocabulary")
        data_parts.append(f"#BEGIN {day}_FINISHED_STORY\n{story}\n#END {day}_FINISHED_STORY")
        data_parts.append(f"#BEGIN {day}_FINALIZED_VOCAB\n{vocab}\n#END {day}_FINALIZED_VOCAB")
    data_text = "\n\n".join(data_parts)

    instructions = OUTPUT_FORMAT_COMMON + "\n\nThis pass produces ONLY: ## Student Questions.\n" \
        "You are seeing all seven days at once specifically so no question is repeated across the week - check before writing each day's set."

    raw = _run_pass("student_questions", rules, data_text, instructions, debug_flag)
    per_day = _extract_section_per_day(raw, "Student Questions")
    for day, text in per_day.items():
        week_state.set_section(day, "Student Questions", text)


def self_review_pass(assembled_week_markdown, debug_flag=True):
    """
    Judgment-only review: register variety across days, dialogue
    naturalness, A2 prose level. Countable/format rules (item counts,
    hint format, no reused vocab) are NOT this pass's job - those stay
    in commonFunctions.validate_markdown(), which is deterministic and
    doesn't get fooled by the model grading its own homework.
    Returns the (possibly revised) full week markdown.
    """
    rubric = """
Review the full week of lessons below for PROSE JUDGMENT ISSUES ONLY:
  - Do any two days share the same emotional register (STORY_QUALITY)?
    If so, revise ONE of them to feel different.
  - Does any Examples dialogue read like a textbook exchange rather than
    a real conversation? If so, revise it.
  - Does any Story paragraph use B1-level vocabulary in the prose
    (not the Vocabulary list, the prose itself)? If so, simplify it.
Do NOT flag or restructure sentences ending in a time expression
(now, today, ahora, hoy, etc.) - trailing time words are natural in
everyday spoken Spanish and in the students' own speech; this is not
a defect.
Do NOT change item counts, hints, or vocabulary selection - those are
checked separately by code, not by you.
Output the FULL corrected week, in the exact same Markdown structure
you were given (same day headings, same section headings, same order).
If nothing needs revision, output the week unchanged.
Do not add commentary before or after the markdown.
""".strip()

    payload = f"{GENERAL_META}\n\n{rubric}\n\n#BEGIN WEEK_TO_REVIEW\n{assembled_week_markdown}\n#END WEEK_TO_REVIEW"
    if debug_flag:
        with open("debug_pass_selfreview_prompt.txt", "w", encoding="utf-8") as f:
            f.write(payload)
    print("Running pass: self_review ...")
    result = common.send_to_ollama(payload, debug_label="pass_selfreview", debug_flag=debug_flag)
    text = common.strip_markdown_fence(result if isinstance(result, str) else str(result))
    if debug_flag:
        with open("debug_pass_selfreview_response.txt", "w", encoding="utf-8") as f:
            f.write(text)
    return text


def fiveminute_self_review_pass(assembled_five_minute_markdown, debug_flag=True):
    """
    Judgment-only review for the Five-Minute lesson, mirroring
    self_review_pass()'s scope discipline: fixes what requires judgment,
    leaves what's countable/mechanical to code. Currently checks exactly
    one thing - FIVEMINUTE_FORMAT rule 4's "character must be the
    subject" requirement for Grammar Focus - because that's the one
    defect class we've seen this pass actually catches reliably that a
    regex can't (a real character acting, e.g. "Marisol writes...", vs.
    the word itself being defined, e.g. "'have' still shows what he
    must do next").

    Deliberately does NOT touch: Mini Story word-count-per-sentence,
    comma limits, or the and/but/because connector restriction - those
    are FIVEMINUTE_FORMAT/SENTENCE_CONTROL rules that belong in a
    deterministic checker (none exists yet in commonFunctions.py for
    the Five-Minute template's sentence rules; that's a real gap, but
    a separate piece of work from this pass).
    """
    rubric = """
Review the full week of Five-Minute lessons below for ONE specific issue:
In each day's Grammar Focus paragraph, a CHARACTER must be the subject
performing an action (e.g. "Marisol writes...", "Dra. Pérez tells him...",
"Mr. Vega says..."). Do NOT let the WORD ITSELF be the subject of a
definition (e.g. "'have' still shows what he must do next", "'should'
means obligation" - these are NOT allowed, because they explain what the
word represents instead of what the character does).
If a day's Grammar Focus has this problem, rewrite ONLY that day's
Grammar Focus paragraph so a character is the one acting - keep the same
grammar point and the same English target words in quotes, just change
who is doing the acting.
Do NOT change anything else: not Vocabulary Review, not Mini Story
sentences (word counts, commas, and connector choice are checked
separately by code, not by you), not Translation Practice, not Student
Questions.
Output the FULL corrected week, in the exact same Markdown structure and
day/section order you were given, including the "---" separator between
days. If no day has this problem, output the week completely unchanged.
Do not add commentary before or after the markdown.
""".strip()

    payload = f"{GENERAL_META}\n\n{rubric}\n\n#BEGIN FIVE_MINUTE_WEEK_TO_REVIEW\n{assembled_five_minute_markdown}\n#END FIVE_MINUTE_WEEK_TO_REVIEW"
    if debug_flag:
        with open("debug_five_selfreview_prompt.txt", "w", encoding="utf-8") as f:
            f.write(payload)
    print("Running pass: five_minute_self_review ...")
    result = common.send_to_ollama(payload, debug_label="five_selfreview", debug_flag=debug_flag)
    text = common.strip_markdown_fence(result if isinstance(result, str) else str(result))
    if debug_flag:
        with open("debug_five_selfreview_response.txt", "w", encoding="utf-8") as f:
            f.write(text)
    return text
