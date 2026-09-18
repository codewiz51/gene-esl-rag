#!/usr/bin/env python3
"""
rule_utils.py

MainLessonTemplate.txt already tags every rule block with
    #BEGIN RULES: NAME ... #END RULES: NAME
    #BEGIN DICTIONARY: NAME ... #END DICTIONARY: NAME
This module pulls those blocks out by name so each pass can be handed
only the rules relevant to it, instead of the entire template. This is
the mechanism that gives each pass a "lower cognitive load" - fewer
simultaneous rule categories per call, not just less text.

NOTE ON SECTION_CONTENT: that one block covers Warmup, Vocabulary,
Grammar, Examples, Translation Practice, and Student Questions all
together, each under its own "Name:" sub-heading. get_section_subblock()
pulls just one of those sub-headings out, so e.g. the Vocabulary pass
doesn't see the Examples dialogue rules.
"""

import re


def get_rule_block(template_text, name, kind="RULES"):
    """
    kind is "RULES" or "DICTIONARY". Returns the block's inner text
    (not including the #BEGIN/#END markers), or "" with a printed
    warning if the block isn't found - callers should treat a missing
    block as a hard stop, not silently proceed without rules.
    """
    pattern = re.compile(
        rf"#BEGIN {kind}:\s*{re.escape(name)}\s*\n(.*?)\n#END {kind}:\s*{re.escape(name)}",
        flags=re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(template_text)
    if not m:
        print(f"WARNING: rule block {kind}:{name} not found in template.")
        return ""
    return m.group(1).strip()


def get_section_subblock(section_content_text, heading):
    """
    Within the already-extracted SECTION_CONTENT block, pull out the
    text under one "Heading:" line, up to the next top-level "Heading:"
    line or end of text. heading should match exactly as it appears,
    e.g. "Warmup", "Vocabulary", "Grammar", "Examples",
    "Translation Practice", "Student Questions".
    """
    # Top-level sub-headings in SECTION_CONTENT are single words/phrases
    # at column 0 followed by a colon and a newline.
    headings = [
        "Warmup",
        "Vocabulary",
        "Grammar",
        "Examples",
        "Translation Practice",
        "Student Questions",
    ]
    pattern = re.compile(
        rf"(?ms)^{re.escape(heading)}:\s*$(.*?)(?=^(?:{'|'.join(re.escape(h) for h in headings)}):\s*$|\Z)"
    )
    m = pattern.search(section_content_text)
    if not m:
        print(f"WARNING: section subblock '{heading}' not found in SECTION_CONTENT.")
        return ""
    return m.group(1).strip()


def assemble_rules(template_text, rule_names=None, dictionary_names=None, section_subblocks=None):
    """
    Convenience: build one text blob of just the rule/dictionary blocks
    (and SECTION_CONTENT sub-sections) a given pass needs, each still
    wrapped in its own #BEGIN/#END markers so the model sees the same
    labeled-block shape it's used to from the full template.

    rule_names: list of RULES block names, e.g. ["LANGUAGE_LEVEL", "SENTENCE_CONTROL"]
    dictionary_names: list of DICTIONARY block names, e.g. ["CHARACTERS", "CUBAN_REGISTER"]
    section_subblocks: list of SECTION_CONTENT sub-heading names, e.g. ["Vocabulary"]
    """
    parts = []
    for name in rule_names or []:
        block = get_rule_block(template_text, name, kind="RULES")
        if block:
            parts.append(f"#BEGIN RULES: {name}\n{block}\n#END RULES: {name}")
    for name in dictionary_names or []:
        block = get_rule_block(template_text, name, kind="DICTIONARY")
        if block:
            parts.append(f"#BEGIN DICTIONARY: {name}\n{block}\n#END DICTIONARY: {name}")
    if section_subblocks:
        section_content = get_rule_block(template_text, "SECTION_CONTENT", kind="RULES")
        for heading in section_subblocks:
            sub = get_section_subblock(section_content, heading)
            if sub:
                parts.append(f"#BEGIN SECTION_CONTENT: {heading}\n{sub}\n#END SECTION_CONTENT: {heading}")
    return "\n\n".join(parts)
