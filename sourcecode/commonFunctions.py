#!/usr/bin/env python3
# commonFunctions.py
#
# Shared "library" module for the ESL lesson generation pipeline.
# generateMain.py and generateSupport.py both import from this file rather
# than each keeping their own copy - this is the fix for the drift risk
# discovered when the same corrections dictionary lived separately in two
# template files and got out of sync. Edit shared logic here once; both
# scripts pick it up automatically.
#
# This module has no main() and does nothing when imported - it's meant
# to be imported, never run directly (equivalent to a shared library / DLL,
# not an executable).

import os
import re
import requests
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen38"

weekly_template_dir = "/Users/gene/Documents/RAG/source_docs/weeklytemplates"
lesson_dir = "/Users/gene/Documents/RAG/source_docs/WeeklyLessons"

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
    # NOTE: "think" is intentionally NOT set here. An experiment with
    # "think": False fixed a mid-generation truncation issue but introduced
    # a worse regression (the model treating one day as a complete task
    # and stopping early, on both Week 31 and Week 32 storyboards). That
    # experiment was reverted pending a more careful, isolated retest.
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

def validate_html(block, label, required_sections):
    # Shared by both scripts: generateMain.py passes the main-lesson
    # section list, generateSupport.py passes the five-minute one.
    missing = [section for section in required_sections if section not in block]
    if missing:
        print(f"WARNING: {label} missing sections: {missing}")
    if not any(c in block for c in "áéíóúñ"):
        print(f"WARNING: {label} may have lost Spanish accents")

def apply_corrections(html, corrections):
    for wrong, right in corrections:
        html = re.sub(wrong, right, html, flags=re.IGNORECASE)
    return html

def write_html(block, identifier, suffix):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{identifier}_{suffix}_{timestamp}.html"
    full_path = os.path.join(lesson_dir, filename)
    os.makedirs(lesson_dir, exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(block)
    print(f"Saved: {full_path}")
