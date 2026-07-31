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
MODEL_NAME = "qwen32b"   # Change here if you switch models

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

    # -----------------------------------------------------
    # FINAL PROMPT ASSEMBLY
    # -----------------------------------------------------
    prompt = (
        f"{system_instructions}\n\n"
        f"=== WEEKLY TEMPLATE ===\n{template_text}\n\n"
        f"=== USER REQUEST ===\n{user_request}\n\n"
        f"=== RETRIEVED CONTEXT ===\n{context}\n\n"
        f"{task_instructions}"
    )

    return prompt

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
        print("Usage: python lesson_generator_ollama.py Week27.txt")
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
    output_filename = f"{base_name}Output{timestamp}.txt"
    output_path = os.path.join(output_dir, output_filename)
    print("DEBUG cwd:", os.getcwd())
    print("DEBUG output_path:", output_path)
    print("DEBUG dir exists:", os.path.exists(output_dir))
    # Open output file for writing
    output_file = open(output_path, "w", encoding="utf-8")
    
    # ---------------------------------------------
    # 3. Generate each day’s lesson and stream output
    # ---------------------------------------------
    client = get_client()

    for day in days_in_template:
        print(f"\nGENERATING {day.upper()}\n")

        user_request = f"Generate the {day} lesson"

        context = retrieve_context(client, user_request)
        prompt = build_prompt(user_request, template_text, context)
        lesson = call_ollama(prompt)

        # Stream to terminal
        print(lesson)

        # Write to output file
        output_file.write(f"\n\n=== {day.upper()} ===\n\n")
        output_file.write(lesson)

    output_file.close()
    print(f"\nWeekly lesson saved to: {output_path}\n")