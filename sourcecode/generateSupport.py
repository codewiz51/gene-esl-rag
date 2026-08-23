#!/usr/bin/env python3
import sys
import os
import re
import requests
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen38"

weekly_template_dir = "/Users/gene/Documents/RAG/source_docs/weeklytemplates"
lesson_dir = "/Users/gene/Documents/RAG/source_docs/WeeklyLessons"
output_dir = "/Users/gene/Documents/RAG/source_docs/WeeklyLessons"

# Stable, general Cuban-register corrections that apply every week regardless
# of topic. This is "factory" content — edit here only when a general
# register/false-friend error is found, not for anything week-specific.
# Kept identical to generateMain.py's copy — if this list ever needs a
# permanent addition, add it in both files.
BASE_CORRECTIONS = [
    (r"\bir a rastras\b", "subirse al carro"),
    (r"\bcarpular\b", "subirse al carro"),
    (r"\balmuerzo en bolsa\b", "almuerzo en llevar"),
    (r"\bchamba\b", "trabajo"),
    (r"\bparte del tiempo\b", "pronóstico del tiempo"),
    (r"\bmoqueo\b", "moco"),
    (r"\bmoquito\b", "moco"),
    (r"\bpl[aá]tica\b", "charla"),
    (r"\bse mete(n)? en el carro\b", "se sube\\1 al carro"),
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
            pairs.append((rf"\b{re.escape(wrong)}\b", right))
    return pairs

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

def send_to_ollama(payload, debug_label=None, debug_flag=True):
    # Same call shape as generateMain.py's send_to_ollama - kept consistent
    # deliberately so both scripts behave identically at the Ollama layer.
    # "think" is intentionally NOT set - see generateMain.py's note on why
    # think:false was tried and reverted.
    data = {
        "model": MODEL_NAME,
        "prompt": payload,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_ctx": 32768,
            "num_predict": -1
        }
    }
    response = requests.post(OLLAMA_URL, json=data)
    response.raise_for_status()
    resp_json = response.json()

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

    if isinstance(resp_json, dict) and "response" in resp_json:
        return resp_json["response"]
    return resp_json if isinstance(resp_json, str) else str(resp_json)

def split_html_blocks(text):
    blocks = []
    pattern = re.compile(r"<html.*?>.*?</html>", flags=re.DOTALL | re.IGNORECASE)
    for match in pattern.findall(text):
        blocks.append(match)
    return blocks

def looks_truncated(text):
    opens = len(re.findall(r"<html[^>]*>", text, flags=re.IGNORECASE))
    closes = len(re.findall(r"</html>", text, flags=re.IGNORECASE))
    return opens > closes

def validate_html(block):
    required = [
        "Vocabulary Review",
        "Grammar Focus",
        "Mini Story",
        "Translation Practice",
        "Student Questions"
    ]
    missing = [section for section in required if section not in block]
    if missing:
        print(f"WARNING: Five-Minute lesson missing sections: {missing}")
    if not any(c in block for c in "áéíóúñ"):
        print("WARNING: Five-Minute lesson may have lost Spanish accents")

def apply_corrections(html, corrections):
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

    main_lesson_path = os.path.join(lesson_dir, main_lesson_file)
    storyboard_path = os.path.join(weekly_template_dir, storyboard_file)
    five_template_path = os.path.join(weekly_template_dir, five_template_file)
    prompt_path = os.path.join(weekly_template_dir, prompt_file)

    main_html = read_file(main_lesson_path)
    storyboard_raw = read_file(storyboard_path)
    five_template = read_file(five_template_path)
    unified_prompt = read_file(prompt_path)

    weekly_corrections = parse_weekly_corrections(storyboard_raw)
    corrections = BASE_CORRECTIONS + weekly_corrections
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
        result_five = send_to_ollama(payload_five, debug_label="five", debug_flag=debug_flag)
    except Exception as e:
        print(f"ERROR: Ollama request failed: {e}")
        if debug_flag:
            with open("debug_five_error.txt", "w", encoding="utf-8") as f:
                f.write(str(e))
        sys.exit(1)

    blocks_five = split_html_blocks(result_five)

    if len(blocks_five) == 0:
        if looks_truncated(result_five if isinstance(result_five, str) else str(result_five)):
            print("ERROR: The Five-Minute response was cut off mid-generation (opened <html> but never closed it).")
            print("Check the 'done_reason' printed above and debug_five_metadata.txt.")
        else:
            print("ERROR: No <html> block found in Five-Minute lesson.")
        if debug_flag:
            with open("debug_five_raw_response.txt", "w", encoding="utf-8") as f:
                f.write(result_five if isinstance(result_five, str) else str(result_five))
        sys.exit(1)

    five_html = blocks_five[0]
    five_html = apply_corrections(five_html, corrections)
    validate_html(five_html)
    write_html(five_html, identifier, "FIVEMIN")

    print("Done.")

if __name__ == "__main__":
    main()

