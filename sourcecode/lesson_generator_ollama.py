import chromadb
from chromadb.config import Settings
from datetime import datetime
import requests
import os
import sys

# =========================================================
# CONFIGURATION SECTION
# ---------------------------------------------------------
# This script stays the same every week.
# You only change the template file, not this script.
# =========================================================

CHROMA_PATH = "/Users/gene/Documents/RAG/chroma"
COLLECTIONS = ["esl_lessons", "mometrix_english", "mometrix_spanish"]

OLLAMA_URL = "http://localhost:11434/api/generate"
# MODEL_NAME = "qwen2.5:14b"   # Change here if you switch models
MODEL_NAME = "gemma4-clean"   # Change here if you switch models

TOP_K = 4

# =========================================================
# LOAD TEMPLATE FILE
# ---------------------------------------------------------
# This loads your weekly template (Week 27, Week 28, etc.)
# You will edit the template file, not this script.
# =========================================================

def load_template(template_path):
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template file not found: {template_path}")
    with open(template_path, "r") as f:
        return f.read()

# =========================================================
# BUILD PROMPT
# ---------------------------------------------------------
# This assembles:
# - system instructions
# - your weekly template
# - retrieved context
# - task instructions
# =========================================================

def build_prompt(user_request, template_text, context):
    system_instructions = (
        "You are an ESL teacher creating bilingual English–Spanish lessons "
        "for adult learners. Use the retrieved context and the weekly template "
        "to stay accurate to the curriculum. Follow Gene’s teaching voice: "
        "clear, structured, friendly, bilingual, and practical."
    )

    # -----------------------------------------------------
    # TASK INSTRUCTIONS (same every week)
    # -----------------------------------------------------
    task_instructions = (
        "TASK:\n"
        "Using the weekly template provided, generate the specific lesson requested.\n\n"
        "Include:\n"
        "- Warm-up (English + Spanish)\n"
        "- Vocabulary list (English → Spanish)\n"
        "- Weekly verb focus\n"
        "- BILINGUAL STORY:\n"
        "  Write the full story in English first as one complete block.\n"
        "  Then write the full story in Spanish as one complete block.\n"
        "  The Spanish block MUST be a faithful translation, but it MUST use Cuban Spanish vocabulary, phrasing, and idiomatic expressions appropriate for adult learners.\n"
        "  Do NOT interleave English and Spanish.\n\n"
        "- Grammar point (A2 level)\n"
        "- Example sentences (English + Spanish)\n"
        "- Mini Translation Practice (exactly 2 English sentences + Spanish translations)\n"
        "- Role-play activity (must stay within the weekly storyline)\n"
        "- Student practice questions\n"
        "- Closing summary\n"
    )

    prompt = (
        f"{system_instructions}\n\n"
        f"=== WEEKLY TEMPLATE ===\n{template_text}\n\n"
        f"=== USER REQUEST ===\n{user_request}\n\n"
        f"=== RETRIEVED CONTEXT ===\n{context}\n\n"
        f"{task_instructions}"
    )

    return prompt

def lookup_mometrix_pages(collection, start_page, end_page):
    results = collection.query(
        query_texts=["dummy"],
        where={
            "$and": [
                {"printed_page": {"$gte": start_page}},
                {"printed_page": {"$lte": end_page}}
            ]
        },
        n_results=100
    )

    docs = results["documents"][0]

    if not docs:
        return f"[No Mometrix content found for pages {start_page}-{end_page}]"

    return " ".join(docs)

import re

def parse_mometrix_macro(line):
    """
    Parse a line like:
    #MOMETRIX_SUMMARY(35, 37, 6)
    Returns: (start_page, end_page, sentences)
    """

    pattern = r"#MOMETRIX_SUMMARY\((\d+),\s*(\d+),\s*(\d+)\)"
    match = re.search(pattern, line)

    if not match:
        return None

    start_page = int(match.group(1))
    end_page = int(match.group(2))
    sentences = int(match.group(3))

    return start_page, end_page, sentences


# =========================================================
# CHROMA RETRIEVAL
# ---------------------------------------------------------
# Retrieves relevant chunks from:
# - esl_lessons (your living curriculum)
# - mometrix_english / mometrix_spanish (static)
# =========================================================

def get_client():
    return chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False)
    )

def retrieve_context(client, query):
    all_chunks = []

    for name in COLLECTIONS:
        col = client.get_collection(name)
        results = col.query(query_texts=[query], n_results=TOP_K)

        docs = results["documents"][0]
        metas = results["metadatas"][0]

        for doc, meta in zip(docs, metas):
            source = meta.get("source", "unknown")
            all_chunks.append(f"[{name} | {source}]\n{doc}\n")

    return "\n\n".join(all_chunks)

# =========================================================
# OLLAMA CALL
# ---------------------------------------------------------
# Sends the assembled prompt to the model.
# =========================================================

def call_ollama(prompt):
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
# MAIN LESSON GENERATOR
# ---------------------------------------------------------
# This ties everything together.
# =========================================================

def generate_lesson(user_request, template_path):
    print("Loading template...")
    template_text = load_template(template_path)

    print("Retrieving context...")
    client = get_client()
    context = retrieve_context(client, user_request)
    print("Building prompt...")
    
    prompt = build_prompt(user_request, template_text, context)
    print("Calling Ollama...")
    
    lesson = call_ollama(prompt)
    print("\n=== GENERATED LESSON ===\n")
    print(lesson)

def extract_day_block(template_text, day):
    lines = template_text.splitlines()
    start = f"=== {day.upper()} ==="
    collecting = False
    block_lines = []

    for line in lines:
        if line.strip() == start:
            collecting = True
            continue
        if collecting:
            if line.strip().startswith("==="):  # next day begins
                break
            block_lines.append(line)

    return "\n".join(block_lines)

# =========================================================
# ENTRY POINT
# ---------------------------------------------------------
# Run with:
# python lesson_generator_ollama.py
# User types: Week27.txt
# Script loads:
# /Users/gene/Documents/RAG/source_docs/weeklytemplates/Week27.txt
# =========================================================

if __name__ == "__main__":
    print("Ollama ESL Lesson Generator")

    # ---------------------------------------------
    # 1. Template filename comes from command line
    # ---------------------------------------------
    if len(sys.argv) < 2:
        print("Usage: python lesson_generator_ollama.py WeekXX.txt")
        sys.exit(1)

    user_template = sys.argv[1].strip()

    base_dir = "/Users/gene/Documents/RAG/source_docs/weeklytemplates"
    template_path = os.path.join(base_dir, user_template)

    # ---------------------------------------------
    # 2. Load template and extract days
    # ---------------------------------------------
    template_text = load_template(template_path)

    # Days are simply the lines that start with a day name
    DAYS = ["monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday"]

    days_in_template = []
    for line in template_text.lower().splitlines():
        line_stripped = line.strip()
        for d in DAYS:
            header = f"=== {d.upper()} ==="
            if line_stripped == header.lower():
                days_in_template.append(d.capitalize())

    if not days_in_template:
        print("No days found in template. Nothing to generate.")
        sys.exit(0)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    # Remove .txt from input filename
    base_name = os.path.splitext(user_template)[0]

    output_dir = "/Users/gene/Documents/RAG/source_docs/WeeklyLessons"
    output_filename = f"{base_name}Output{timestamp}.html"
    output_path = os.path.join(output_dir, output_filename)
    print("DEBUG cwd:", os.getcwd())
    print("DEBUG output_path:", output_path)
    print("DEBUG dir exists:", os.path.exists(output_dir))
    # Open output file for writing
    output_file = open(output_path, "w", encoding="utf-8")

    # Write HTML header
    output_file.write("""<!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <title>Weekly Lesson Output</title>
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

    # ---------------------------------------------
    # 3. Generate each day’s lesson and stream output
    # ---------------------------------------------
    client = get_client()
    # Load the Mometrix English collection
    mometrix_english_collection = client.get_or_create_collection("mometrix_english")

    for day in days_in_template:
        print(f"\nGENERATING {day.upper()}\n")

        user_request = f"Generate the {day} lesson"

        context = retrieve_context(client, user_request)
        prompt = build_prompt(user_request, template_text, context)

        # ---------------------------------------------------------
        # BLOCK 3 — Mometrix Macro Integration
        # ---------------------------------------------------------
        day_block = extract_day_block(template_text, day)
        mometrix_macro = parse_mometrix_macro(day_block)

        if mometrix_macro:
            start_page, end_page, num_sentences = mometrix_macro

            raw_mometrix = lookup_mometrix_pages(
                mometrix_english_collection,
                start_page,
                end_page
            )

            mometrix_summary_prompt = f"""
Summarize the following Mometrix content into {num_sentences} clear, concise sentences.

Content:
{raw_mometrix}
"""

            mometrix_summary = call_ollama(mometrix_summary_prompt).strip()

            prompt += f"\n\nMOMETRIX SUMMARY:\n{mometrix_summary}\n"
        # ---------------------------------------------------------
        lesson = call_ollama(prompt)

        # Stream to terminal
        print(lesson)

        # Write to output file
        output_file.write(f"<h1>{day.upper()}</h1>\n")
        output_file.write(f"<div class='day-block'>\n{lesson}\n</div>\n")
        # output_file.write(lesson)

    # Close HTML document
    with open(output_path, "a", encoding="utf-8") as output_file:
        output_file.write("\n</body>\n</html>")
    output_file.close()
    print(f"\nWeekly lesson saved to: {output_path}\n")