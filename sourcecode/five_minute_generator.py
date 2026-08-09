import sys
import os
from datetime import datetime
import requests

# =========================================================
# CONFIGURATION — mirrors lesson_generator_ollama.py
# =========================================================

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma4-clean"

base_dir = "/Users/gene/Documents/RAG/source_docs/weeklytemplates"
output_dir = "/Users/gene/Documents/RAG/source_docs/WeeklyLessons"

# =========================================================
# LOAD FILES
# =========================================================

def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# =========================================================
# CALL MODEL (same pattern as lesson generator)
# =========================================================

def call_model(prompt):
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }
    resp = requests.post(OLLAMA_URL, json=payload)
    resp.raise_for_status()
    data = resp.json()
    return data["response"]

# =========================================================
# MAIN FIVE-MINUTE GENERATOR
# =========================================================

def main():
    if len(sys.argv) != 3:
        print("Usage: python five_minute_generator.py FiveMinuteTemplate.txt WeekXXOutput.html")
        sys.exit(1)

    template_name = sys.argv[1]
    weekly_name = sys.argv[2]

    # Build full paths
    template_path = os.path.join(base_dir, template_name)
    weekly_path = os.path.join(output_dir, weekly_name)

    # Load template + weekly lesson
    template = load(template_path)
    weekly_html = load(weekly_path)

    # =====================================================
    # BUILD PROMPT FOR GEMMA
    # =====================================================
    prompt = f"""
You are an ESL teacher creating short 5-minute reinforcing lessons.
You will generate one reinforcing lesson for EACH DAY found in the weekly lesson.

Here is the full weekly lesson (HTML):
{weekly_html}

Here is the 5-minute lesson template:
{template}

TASK:
For each day (SUNDAY, MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY),
generate a short 5-minute reinforcing lesson based on that day's content.

Requirements:
- Follow the template exactly for each day.
- Output ALL days in one single HTML document.
- Do NOT explain anything.
- Only output HTML.
"""

    # =====================================================
    # CALL MODEL
    # =====================================================
    model_output = call_model(prompt)

    # =====================================================
    # BUILD OUTPUT FILENAME (NO DUPLICATE TIMESTAMP)
    # =====================================================
    base_name = os.path.splitext(weekly_name)[0]
    output_filename = f"{base_name}FiveMinute.html"
    output_path = os.path.join(output_dir, output_filename)

    # =====================================================
    # WRITE HTML WRAPPER (same style as lesson generator)
    # =====================================================
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Five Minute Reinforcement Lessons</title>
<style>
    body {
        font-family: "Times New Roman", serif;
        font-size: 14pt;
        line-height: 1.0;
        margin: 40px;
    }
    p {
        font-family: "Times New Roman", serif;
        font-size: 14pt;
    }
    h1 {
        font-size: 18pt;
    }
    h2 {
        font-size: 16pt;
    }
</style>
</head>
<body>
""")

        f.write(model_output)
        f.write("\n</body>\n</html>")

    print(f"\nFive-minute lessons saved to: {output_path}\n")

# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()
