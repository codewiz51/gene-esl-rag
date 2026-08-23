#!/usr/bin/env python3
import sys
import os
import re

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
    # Remove the WEEKLY_CORRECTIONS dictionary block itself (if present) so
    # it never gets treated as story content by parse_storyboard_days().
    # The block's contents are parsed separately by
    # common.parse_weekly_corrections() before this function is called.
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

def check_day_heading_format(main_html):
    # WeekXX.txt rule 12 requires day headings to be exactly <h1>DAY</h1>,
    # with nothing else in the tag. This check surfaces it loudly when the
    # model doesn't follow the rule, so drift doesn't go unnoticed.
    days = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    for day in days:
        exact = re.search(rf"<h1>{day}</h1>", main_html, flags=re.IGNORECASE)
        if not exact:
            loose = re.search(rf"<h[1-4][^>]*>\s*{day}\b[^<]*</h[1-4]>", main_html, flags=re.IGNORECASE)
            if loose:
                print(f"WARNING: {day} heading doesn't match the required <h1>{day}</h1> format exactly: {loose.group(0)!r}")
            else:
                print(f"WARNING: {day} heading not found in expected form at all.")

MAIN_REQUIRED_SECTIONS = [
    "Vocabulary",
    "Warmup",
    "Grammar",
    "Examples",
    "Translation Practice",
    "Student Questions"
]

def main():
    # 4 required args: identifier, storyboard, template, unifiedPrompt.
    # No FiveMinuteTemplate.txt - this script only produces the main lesson.
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

    payload_main = f"{template_with_stories}\n\n{unified_prompt}"

    if debug_flag:
        with open("debug_main_prompt.txt", "w", encoding="utf-8") as f:
            f.write(payload_main)

    print("Generating main lesson...")
    try:
        result_main = common.send_to_ollama(payload_main, debug_label="main", debug_flag=debug_flag)
    except Exception as e:
        print(f"ERROR: Ollama request failed: {e}")
        if debug_flag:
            with open("debug_main_error.txt", "w", encoding="utf-8") as f:
                f.write(str(e))
        sys.exit(1)

    blocks_main = common.split_html_blocks(result_main)

    if len(blocks_main) == 0:
        if common.looks_truncated(result_main if isinstance(result_main, str) else str(result_main)):
            print("ERROR: The main lesson response was cut off mid-generation (opened <html> but never closed it).")
            print("Check the 'done_reason' printed above and debug_main_metadata.txt: 'length' means")
            print("it hit num_predict/context; 'stop' means the model ended its own turn early -")
            print("these have different causes and different fixes, so don't assume which one it is.")
        else:
            print("ERROR: No <html> block found in main lesson.")
        if debug_flag:
            with open("debug_main_raw_response.txt", "w", encoding="utf-8") as f:
                f.write(result_main if isinstance(result_main, str) else str(result_main))
        sys.exit(1)

    main_html = blocks_main[0]
    main_html = common.apply_corrections(main_html, corrections)
    common.validate_html(main_html, "main lesson", MAIN_REQUIRED_SECTIONS)
    check_day_heading_format(main_html)
    common.write_html(main_html, identifier, "MAIN")

    print("Done.")

if __name__ == "__main__":
    main()
