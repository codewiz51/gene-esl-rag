#!/usr/bin/env python3
import sys
import os
import re
import requests
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen38"

weekly_template_dir = "/Users/gene/Documents/RAG/source_docs/weeklytemplates"
output_dir = "/Users/gene/Documents/RAG/source_docs/WeeklyLessons"

def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def strip_meta(text):
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        if line.strip().startswith("#IGNORE"):
            continue
        if line.strip().startswith("#MOMETRIX"):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)

def parse_storyboard_days(storyboard_text):
    days = ["MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY","SATURDAY","SUNDAY"]
    result = {d: "" for d in days}
    # Normalize and split
    lines = storyboard_text.splitlines()
    current = None
    buffer = []
    for line in lines:
        header = None
        for d in days:
            # Match either "# MONDAY STORYBOARD" or "MONDAY STORYBOARD" or "=== START MONDAY ==="
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
        # Also stop at explicit end markers
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
    # Trim leading/trailing blank lines from each day
    for k in result:
        result[k] = result[k].strip()
    return result

def inject_storyboard_into_template(template_text, day_map):
    for day, content in day_map.items():
        start_marker = rf"=== START {day} ==="
        end_marker = rf"=== END {day} ==="
        # Build replacement block
        replacement_block = f"{start_marker}\nStory Requirements:\n{content}\n{end_marker}"
        pattern = re.compile(rf"({re.escape(start_marker)})(.*?)(\s*{re.escape(end_marker)})", flags=re.DOTALL)
        if pattern.search(template_text):
            template_text = pattern.sub(replacement_block, template_text)
        else:
            # If markers not found, try to find the DAILY_STORIES section and insert before its end
            if "+++ END WEEK" in template_text:
                template_text = template_text.replace("+++ END WEEK XX +++", f"{replacement_block}\n\n+++ END WEEK XX +++")
            else:
                # As a fallback, append at the end
                template_text = template_text + "\n\n" + replacement_block
    return template_text

def _split_main_html_by_day(main_html):
    # Shared helper: locate each <h1>DAY</h1> heading and return
    # (day_name, chunk_text_from_that_heading_to_the_next) in order.
    day_pattern = re.compile(
        r"<h1>\s*(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY)\s*</h1>",
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
    # label attached to each vocab list is the day it actually belongs
    # to (not a positional guess).
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
    # Warm-Up block), so it's located within each day's own chunk rather
    # than assumed to be adjacent to the heading.
    manifest = []
    for day, chunk in _split_main_html_by_day(main_html):
        story_match = re.search(
            r"<h3>\s*Story\s*</h3>\s*<table>.*?<td>(.*?)</td>",
            chunk, flags=re.DOTALL | re.IGNORECASE
        )
        if not story_match:
            print(f"WARNING: no Story block found for {day}; Five-Minute lesson for {day} will have no source story.")
            continue
        text = re.sub(r"<[^>]+>", " ", story_match.group(1))
        text = re.sub(r"\s+", " ", text).strip()
        manifest.append(f"#BEGIN {day}_STORY\n{text}\n#END {day}_STORY\n")
    return "\n".join(manifest)

def send_to_ollama(payload):
    data = {
        "model": MODEL_NAME,
        "prompt": payload,
        "stream": False,
        "temperature": 0
    }
    response = requests.post(OLLAMA_URL, json=data)
    response.raise_for_status()
    # Ollama returns JSON with a "response" field in earlier versions; handle both str and dict
    resp_json = response.json()
    if isinstance(resp_json, dict) and "response" in resp_json:
        return resp_json["response"]
    # Fallback if API returns raw text
    return resp_json if isinstance(resp_json, str) else str(resp_json)

def split_html_blocks(text):
    blocks = []
    pattern = re.compile(r"<html.*?>.*?</html>", flags=re.DOTALL | re.IGNORECASE)
    for match in pattern.findall(text):
        blocks.append(match)
    return blocks

def validate_html(block, label):
    required_main = [
        "Vocabulary",
        "Warmup",
        "Grammar",
        "Examples",
        "Translation Practice",
        "Student Questions"
    ]
    required_five = [
        "Vocabulary Review",
        "Grammar Focus",
        "Mini Story",
        "Translation Practice",
        "Student Questions"
    ]
    missing = []
    if label == "main":
        for section in required_main:
            if section not in block:
                missing.append(section)
    if label == "five":
        for section in required_five:
            if section not in block:
                missing.append(section)
    if missing:
        print(f"WARNING: {label} lesson missing sections: {missing}")
    if not any(c in block for c in "áéíóúñ"):
        print(f"WARNING: {label} lesson may have lost Spanish accents")

def apply_corrections(html):
    corrections = [
        (r"\bir a rastras\b", "ir en el carro de alguien"),
        (r"\bcarpular\b", "subirse al carro"),
        (r"\balmuerzo en bolsa\b", "almuerzo en llevar")
    ]
    for wrong, right in corrections:
        html = re.sub(wrong, right, html, flags=re.IGNORECASE)
    return html

def write_html(block, identifier, suffix):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{identifier}_{suffix}_{timestamp}.html"
    full_path = os.path.join(output_dir, filename)
    os.makedirs(output_dir, exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(block)
    print(f"Saved: {full_path}")

def main():
    # Accept 6 or 7 args now: identifier, storyboard, template, unifiedPrompt, fiveTemplate, [Debug|NoDebug]
    if len(sys.argv) not in (6, 7):
        print("Usage: python3 generateLesson.py <identifier> <storyboard.md> <template.txt> <unifiedPrompt.md> <fiveMinuteTemplate.txt> [Debug|NoDebug]")
        sys.exit(1)

    identifier = sys.argv[1]
    storyboard_file = sys.argv[2]
    template_file = sys.argv[3]
    prompt_file = sys.argv[4]
    five_file = sys.argv[5]
    debug_flag = True
    if len(sys.argv) == 7:
        arg6 = sys.argv[6].strip().lower()
        if arg6.startswith("n"):
            debug_flag = False

    storyboard_path = os.path.join(weekly_template_dir, storyboard_file)
    template_path = os.path.join(weekly_template_dir, template_file)
    prompt_path = os.path.join(weekly_template_dir, prompt_file)
    five_path = os.path.join(weekly_template_dir, five_file)

    storyboard_raw = read_file(storyboard_path)
    storyboard = strip_meta(storyboard_raw)

    template = read_file(template_path)
    unified_prompt = read_file(prompt_path)
    five_template = read_file(five_path)

    template = template.replace("WEEK XX", f"WEEK {identifier}")

    # Parse storyboard into day blocks and inject into template
    day_map = parse_storyboard_days(storyboard)
    template_with_stories = inject_storyboard_into_template(template, day_map)

    payload_main = f"{template_with_stories}\n\n{unified_prompt}"

    if debug_flag:
        with open("debug_main_prompt.txt", "w", encoding="utf-8") as f:
            f.write(payload_main)

    print("Generating main lesson...")
    try:
        result_main = send_to_ollama(payload_main)
    except Exception as e:
        print(f"ERROR: Ollama request failed: {e}")
        if debug_flag:
            with open("debug_main_error.txt", "w", encoding="utf-8") as f:
                f.write(str(e))
        sys.exit(1)

    blocks_main = split_html_blocks(result_main)

    if len(blocks_main) == 0:
        print("ERROR: No <html> block found in main lesson.")
        if debug_flag:
            with open("debug_main_raw_response.txt", "w", encoding="utf-8") as f:
                f.write(result_main if isinstance(result_main, str) else str(result_main))
        sys.exit(1)

    main_html = blocks_main[0]
    main_html = apply_corrections(main_html)
    validate_html(main_html, "main")
    write_html(main_html, identifier, "MAIN")

    vocab_manifest = extract_day_vocab(main_html)
    story_manifest = extract_day_story(main_html)

    payload_five = f"{five_template}\n\n{story_manifest}\n\n{vocab_manifest}\n\n{unified_prompt}"

    if debug_flag:
        with open("debug_five_prompt.txt", "w", encoding="utf-8") as f:
            f.write(payload_five)

    print("Generating FiveMinute lesson...")
    try:
        result_five = send_to_ollama(payload_five)
    except Exception as e:
        print(f"ERROR: Ollama request failed for FiveMinute: {e}")
        if debug_flag:
            with open("debug_five_error.txt", "w", encoding="utf-8") as f:
                f.write(str(e))
        sys.exit(1)

    blocks_five = split_html_blocks(result_five)

    if len(blocks_five) == 0:
        print("ERROR: No <html> block found in FiveMinute lesson.")
        if debug_flag:
            with open("debug_five_raw_response.txt", "w", encoding="utf-8") as f:
                f.write(result_five if isinstance(result_five, str) else str(result_five))
        sys.exit(1)

    five_html = blocks_five[0]
    five_html = apply_corrections(five_html)
    validate_html(five_html, "five")
    write_html(five_html, identifier, "FIVEMIN")

    print("Done.")

if __name__ == "__main__":
    main()
