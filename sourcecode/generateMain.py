#!/usr/bin/env python3
import sys
import os
import re
import textwrap

import commonFunctions as common

def strip_meta(text):
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        if line.strip().startswith("#IGNORE"):
            continue
        if line.strip().startswith("#MOMETRIX"):
            continue
        cleaned.append(line)
    text = "\n".join(cleaned)
    text = re.sub(
        r"#BEGIN DICTIONARY:\s*WEEKLY_CORRECTIONS.*?#END DICTIONARY:\s*WEEKLY_CORRECTIONS",
        "", text, flags=re.DOTALL | re.IGNORECASE
    )
    return text

def parse_storyboard_days(storyboard_text):
    days = ["MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY","SATURDAY","SUNDAY"]
    result = {d: "" for d in days}
    lines = storyboard_text.splitlines()
    current = None
    buffer = []
    for line in lines:
        header = None
        for d in days:
            if re.match(rf"^\s*#\s*{d}\s+STORYBOARD\s*$", line, flags=re.IGNORECASE) or \
               re.match(rf"^\s*{d}\s+STORYBOARD\s*$", line, flags=re.IGNORECASE) or \
               re.match(rf"^\s*===\s*START\s+{d}\s*===\s*$", line, flags=re.IGNORECASE):
                header = d
                break
        if header:
            if current:
                result[current] = "\n".join(buffer).strip()
            current = header
            buffer = []
            continue
        if re.match(r"^\s*===\s*END\s+\w+\s*===\s*$", line, flags=re.IGNORECASE):
            if current:
                result[current] = "\n".join(buffer).strip()
                current = None
                buffer = []
            continue
        if current:
            buffer.append(line)
    if current:
        result[current] = "\n".join(buffer).strip()
    for k in result:
        result[k] = result[k].strip()
    return result

def inject_storyboard_into_template(template_text, day_map):
    for day, content in day_map.items():
        start_marker = rf"=== START {day} ==="
        end_marker = rf"=== END {day} ==="
        replacement_block = f"{start_marker}\nStory Requirements:\n{content}\n{end_marker}"
        pattern = re.compile(rf"({re.escape(start_marker)})(.*?)(\s*{re.escape(end_marker)})", flags=re.DOTALL)
        if pattern.search(template_text):
            template_text = pattern.sub(replacement_block, template_text)
        else:
            if "+++ END WEEK" in template_text:
                template_text = template_text.replace("+++ END WEEK XX +++", f"{replacement_block}\n\n+++ END WEEK XX +++")
            else:
                template_text = template_text + "\n\n" + replacement_block
    return template_text

def extract_partial_template(template_text, days_to_keep):
    # Strips the day blocks for days NOT in days_to_keep, so a split call
    # only sees the storyboard content it's actually responsible for.
    # Rule blocks (everything above DAILY_STORIES) are untouched - they
    # apply to every call regardless of which days it covers.
    all_days = ["MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY","SATURDAY","SUNDAY"]
    for day in all_days:
        if day in days_to_keep:
            continue
        pattern = re.compile(
            rf"=== START {day} ===.*?=== END {day} ===\s*",
            flags=re.DOTALL | re.IGNORECASE
        )
        template_text = pattern.sub("", template_text)
    return template_text

def check_day_heading_format(main_html, days=None):
    # WeekXX.txt rule 12 requires day headings to be exactly <h1>DAY</h1>,
    # with nothing else in the tag. This check surfaces it loudly when the
    # model doesn't follow the rule, so drift doesn't go unnoticed.
    days = days or ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    for day in days:
        exact = re.search(rf"<h1>{day}</h1>", main_html, flags=re.IGNORECASE)
        if not exact:
            loose = re.search(rf"<h[1-4][^>]*>\s*{day}\b[^<]*</h[1-4]>", main_html, flags=re.IGNORECASE)
            if loose:
                print(f"WARNING: {day} heading doesn't match the required <h1>{day}</h1> format exactly: {loose.group(0)!r}")
            else:
                print(f"WARNING: {day} heading not found in expected form at all.")

def build_part_reminder(days):
    day_list = ", ".join(d.title() for d in days)
    return textwrap.dedent(f"""
    ============================================================
    PART OVERRIDE — DAYS FOR THIS CALL ONLY
    ============================================================
    Ignore any earlier instruction in this prompt that says to
    produce all seven days in one document. This call is only
    part of the week.

    For THIS call, produce ONLY these days, in this order:
    {day_list}.

    Do not add any other days.
    Do not add extra explanation, commentary, or reasoning.
    Output ONE <html> document containing ONLY the days listed
    above, following all template rules (Sentence Control,
    Trailing Adverb, Character Dictionary, Cuban Register,
    Translation Practice, HTML structure, Vocabulary rules,
    Story length rules).
    """).strip()

def strip_extra_head_blocks(html_inner):
    # Used when merging two parts: keeps the first <head>...</head>,
    # removes any additional ones so the merged document has exactly one.
    parts = re.split(r"(<head.*?</head>)", html_inner, flags=re.DOTALL | re.IGNORECASE)
    seen_head = False
    out = []
    for chunk in parts:
        if re.match(r"<head.*?</head>", chunk, flags=re.DOTALL | re.IGNORECASE):
            if seen_head:
                continue
            seen_head = True
        out.append(chunk)
    return "".join(out)

def merge_html_parts(html_part1, html_part2):
    inner_pattern = re.compile(r"<html[^>]*>(.*?)</html>", flags=re.DOTALL | re.IGNORECASE)
    m1 = inner_pattern.search(html_part1)
    m2 = inner_pattern.search(html_part2)
    inner1 = m1.group(1).strip() if m1 else html_part1.strip()
    inner2 = m2.group(1).strip() if m2 else html_part2.strip()
    merged_inner = strip_extra_head_blocks(inner1 + "\n" + inner2)
    return f"<html>\n{merged_inner}\n</html>"

MAIN_REQUIRED_SECTIONS = [
    "Vocabulary",
    "Warmup",
    "Grammar",
    "Examples",
    "Translation Practice",
    "Student Questions"
]

DAY_GROUPS = [
    ("part1", ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY"]),
    ("part2", ["FRIDAY", "SATURDAY", "SUNDAY"]),
]

def generate_part(label, days, template_with_stories, unified_prompt, debug_flag):
    partial_template = extract_partial_template(template_with_stories, days)
    part_reminder = build_part_reminder(days)
    payload = f"{partial_template}\n\n{unified_prompt}\n\n{part_reminder}"

    if debug_flag:
        with open(f"debug_main_{label}_prompt.txt", "w", encoding="utf-8") as f:
            f.write(payload)

    print(f"Generating main lesson ({label}: {', '.join(d.title() for d in days)})...")
    try:
        result = common.send_to_ollama(payload, debug_label=f"main_{label}", debug_flag=debug_flag)
    except Exception as e:
        print(f"ERROR: Ollama request failed on {label}: {e}")
        if debug_flag:
            with open(f"debug_main_{label}_error.txt", "w", encoding="utf-8") as f:
                f.write(str(e))
        sys.exit(1)

    blocks = common.split_html_blocks(result)
    if len(blocks) == 0:
        if common.looks_truncated(result if isinstance(result, str) else str(result)):
            print(f"ERROR: {label} response was cut off mid-generation (opened <html> but never closed it).")
            print("Check the 'done_reason' printed above and the matching debug_main_*_metadata.txt: 'length' means")
            print("it hit num_predict/context; 'stop' means the model ended its own turn early -")
            print("these have different causes and different fixes, so don't assume which one it is.")
        else:
            print(f"ERROR: No <html> block found in {label}.")
        if debug_flag:
            with open(f"debug_main_{label}_raw_response.txt", "w", encoding="utf-8") as f:
                f.write(result if isinstance(result, str) else str(result))
        sys.exit(1)

    check_day_heading_format(blocks[0], days=days)
    return blocks[0]

def main():
    if len(sys.argv) not in (5, 6):
        print("Usage: python3 generateMain.py <identifier> <storyboard.md> <template.txt> <unifiedPrompt.md> [Debug|NoDebug]")
        sys.exit(1)

    identifier = sys.argv[1]
    storyboard_file = sys.argv[2]
    template_file = sys.argv[3]
    prompt_file = sys.argv[4]
    debug_flag = True
    if len(sys.argv) == 6:
        arg5 = sys.argv[5].strip().lower()
        if arg5.startswith("n"):
            debug_flag = False

    storyboard_path = os.path.join(common.weekly_template_dir, storyboard_file)
    template_path = os.path.join(common.weekly_template_dir, template_file)
    prompt_path = os.path.join(common.weekly_template_dir, prompt_file)

    storyboard_raw = common.read_file(storyboard_path)
    weekly_corrections = common.parse_weekly_corrections(storyboard_raw)
    corrections = common.BASE_CORRECTIONS + weekly_corrections
    if weekly_corrections:
        print(f"Loaded {len(weekly_corrections)} weekly correction(s) from storyboard.")
    storyboard = strip_meta(storyboard_raw)

    template = common.read_file(template_path)
    unified_prompt = common.read_file(prompt_path)

    template = template.replace("WEEK XX", f"WEEK {identifier}")

    day_map = parse_storyboard_days(storyboard)
    template_with_stories = inject_storyboard_into_template(template, day_map)

    part_htmls = []
    for label, days in DAY_GROUPS:
        html_part = generate_part(label, days, template_with_stories, unified_prompt, debug_flag)
        part_htmls.append(html_part)

    main_html = merge_html_parts(part_htmls[0], part_htmls[1])
    main_html = common.apply_corrections(main_html, corrections)
    common.validate_html(main_html, "main lesson", MAIN_REQUIRED_SECTIONS)
    check_day_heading_format(main_html)
    common.write_html(main_html, identifier, "MAIN")

    print("Done.")

if __name__ == "__main__":
    main()