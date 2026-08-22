#!/usr/bin/env python3
import sys
import json
import requests
import os
from datetime import datetime

# =========================================================
# CONFIGURATION
# =========================================================

CHROMA_PATH = "/Users/gene/Documents/RAG/chroma"
COLLECTIONS = ["esl_lessons"]

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen38"

weekly_template_dir = "/Users/gene/Documents/RAG/source_docs/weeklytemplates"
output_dir = "/Users/gene/Documents/RAG/source_docs/WeeklyLessons"


# =========================================================
# HELPERS
# =========================================================

def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def send_to_ollama(payload):
    data = {
        "model": MODEL_NAME,
        "prompt": payload,
        "stream": False
    }
    response = requests.post(OLLAMA_URL, json=data)
    response.raise_for_status()
    return response.json()["response"]

def split_html_blocks(text):
    blocks = []
    start = 0

    while True:
        open_tag = text.find("<html>", start)
        if open_tag == -1:
            break
        close_tag = text.find("</html>", open_tag)
        if close_tag == -1:
            break

        block = text[open_tag:close_tag + len("</html>")]
        blocks.append(block)
        start = close_tag + len("</html>")

    return blocks

def write_html(block, identifier, suffix):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{identifier}_{timestamp}{suffix}.html"
    full_path = os.path.join(output_dir, filename)

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(block)

    print(f"Saved: {full_path}")


# =========================================================
# MAIN
# =========================================================

def main():
    start_time = datetime.now()
    print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    sys.stdout.flush()

    if len(sys.argv) != 5:
        print("Usage: python3 generateLesson.py <identifier> <storyboard.md> <template.txt> <unifiedPrompt.md>")
        sys.exit(1)

    identifier = sys.argv[1]
    storyboard_file = sys.argv[2]
    template_file = sys.argv[3]
    prompt_file = sys.argv[4]

    # Resolve full paths
    storyboard_path = storyboard_file
    template_path = os.path.join(weekly_template_dir, template_file)
    prompt_path = prompt_file

    # Resolve full paths
    storyboard_path = os.path.join(weekly_template_dir, storyboard_file)
    template_path = os.path.join(weekly_template_dir, template_file)
    prompt_path = os.path.join(weekly_template_dir, prompt_file)

    # Read files
    storyboard = read_file(storyboard_path)
    template = read_file(template_path)
    unified_prompt = read_file(prompt_path)

    # Build payload
    payload = f"{template}\n\n{storyboard}\n\n{unified_prompt}"
    # DEBUG: write the exact prompt being sent to Qwen
    with open("debug_prompt.txt", "w", encoding="utf-8") as f:
        f.write(payload)

    print("Sending to Ollama...")
    sys.stdout.flush()
    result = send_to_ollama(payload)

    print("Splitting HTML blocks...")
    sys.stdout.flush()
    blocks = split_html_blocks(result)

    if len(blocks) < 2:
        print("ERROR: Expected two <html> blocks but found:", len(blocks))
        sys.stdout.flush()
        sys.exit(1)

    write_html(blocks[0], identifier, "")
    write_html(blocks[1], identifier, "_FiveMinute")
    end_time = datetime.now()
    print(f"End time:   {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration:   {end_time - start_time}")
    sys.stdout.flush()

if __name__ == "__main__":
    main()
