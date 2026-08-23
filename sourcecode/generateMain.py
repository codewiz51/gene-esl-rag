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

# Stable, general Cuban-register corrections that apply every week regardless
# of topic. This is "factory" content — edit here only when a general
# register/false-friend error is found, not for anything week-specific.
# Week-specific corrections (e.g. medical terminology for a clinic-focused
# week) belong in a #BEGIN DICTIONARY: WEEKLY_CORRECTIONS block in that
# week's storyboard file instead — see parse_weekly_corrections().
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
    # The block's contents are parsed separately by parse_weekly_corrections()
    # before this function is called.
    text = re.sub(
        r"#BEGIN DICTIONARY:\s*WEEKLY_CORRECTIONS.*?#END DICTIONARY:\s*WEEKLY_CORRECTIONS",
        "", text, flags=re.DOTALL | re.IGNORECASE
    )
    return text

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
            # \b word-boundary wrap assumes the phrase is plain text, matching
            # how BASE_CORRECTIONS entries are written.
            pairs.append((rf"\b{re.escape(wrong)}\b", right))
    return pairs

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

def send_to_ollama(payload, debug_label=None, debug_flag=True):
    # NOTE: Ollama's /api/generate only reads generation parameters
    # (temperature, num_predict, num_ctx, etc.) from a nested "options"
    # object. A top-level "temperature" key is silently ignored - so
    # temperature here matches the qwen38 Modelfile's tuned 0.2 explicitly,
    # rather than assuming the top-level field would take effect.
    #
    # num_ctx is set well above the ~10,000-13,000 tokens a full week's
    # prompt+response typically needs, as a deliberate diagnostic choice:
    # if truncation happens despite this headroom, num_ctx is NOT the
    # cause - check done_reason below instead of assuming.
    #
    # NOTE: "think" is intentionally NOT set here. An earlier experiment
    # with "think": False fixed a mid-generation truncation issue but
    # introduced a worse regression (the model treating one day as a
    # complete task and stopping after Monday, on both Week 31 and Week 32
    # storyboards). That experiment was reverted pending a more careful,
    # isolated retest - see chat history around Aug 22 if revisiting this.
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

    # Surface WHY generation ended, instead of only keeping the text.
    # done_reason "stop" = the model hit a stop token on its own (a
    # model/prompt behavior question, not a resource limit).
    # done_reason "length" = it genuinely hit num_predict/context.
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

    # Ollama returns JSON with a "response" field in earlier versions; handle both str and dict
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

def looks_truncated(text):
    # True if the response opened an <html> tag but never closed it -
    # i.e. generation was cut off mid-document rather than the model
    # producing something malformed or refusing outright.
    opens = len(re.findall(r"<html[^>]*>", text, flags=re.IGNORECASE))
    closes = len(re.findall(r"</html>", text, flags=re.IGNORECASE))
    return opens > closes

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

def validate_html(block):
    required = [
        "Vocabulary",
        "Warmup",
        "Grammar",
        "Examples",
        "Translation Practice",
        "Student Questions"
    ]
    missing = [section for section in required if section not in block]
    if missing:
        print(f"WARNING: main lesson missing sections: {missing}")
    if not any(c in block for c in "áéíóúñ"):
        print("WARNING: main lesson may have lost Spanish accents")

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
    # 4 required args now: identifier, storyboard, template, unifiedPrompt.
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

    storyboard_path = os.path.join(weekly_template_dir, storyboard_file)
    template_path = os.path.join(weekly_template_dir, template_file)
    prompt_path = os.path.join(weekly_template_dir, prompt_file)

    storyboard_raw = read_file(storyboard_path)
    weekly_corrections = parse_weekly_corrections(storyboard_raw)
    corrections = BASE_CORRECTIONS + weekly_corrections
    if weekly_corrections:
        print(f"Loaded {len(weekly_corrections)} weekly correction(s) from storyboard.")
    storyboard = strip_meta(storyboard_raw)

    template = read_file(template_path)
    unified_prompt = read_file(prompt_path)

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
        result_main = send_to_ollama(payload_main, debug_label="main", debug_flag=debug_flag)
    except Exception as e:
        print(f"ERROR: Ollama request failed: {e}")
        if debug_flag:
            with open("debug_main_error.txt", "w", encoding="utf-8") as f:
                f.write(str(e))
        sys.exit(1)

    blocks_main = split_html_blocks(result_main)

    if len(blocks_main) == 0:
        if looks_truncated(result_main if isinstance(result_main, str) else str(result_main)):
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
    main_html = apply_corrections(main_html, corrections)
    validate_html(main_html)
    check_day_heading_format(main_html)
    write_html(main_html, identifier, "MAIN")

    print("Done.")

if __name__ == "__main__":
    main()