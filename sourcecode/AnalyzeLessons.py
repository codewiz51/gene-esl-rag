#!/usr/bin/env python3
"""
Structure discovery pass for the ESL lesson archive.

Does NOT extract vocabulary/verbs/etc. and does NOT touch Postgres.
Purpose: walk every PDF, ask local Qwen to report the section headers
it finds (verbatim, in document order) with a one-line note on what
follows each one. Output is a single JSON report you can read or hand
back for designing the real extraction schema/prompt.

Run this BEFORE writing the real extraction script.
"""

import json
import re
import sys
import time
from pathlib import Path

import pdfplumber
import requests

# ---- Config ----------------------------------------------------------
PDF_DIR = Path("/Users/gene/Documents/English As A Second Language/ESL Lessons")
OUTPUT_FILE = Path("./structure_report.json")
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3.8:27b-mlx"  # adjust to your exact Ollama model tag if different
MAX_CHARS_TO_MODEL = 12000  # keep the discovery prompt cheap; headers usually
                             # aren't buried past this in any file we've seen
RETRY_ATTEMPTS = 2
REQUEST_TIMEOUT = 180  # seconds, generous for a 27B local model

DISCOVERY_PROMPT = """You are scanning an ESL lesson document to report its structure only.

Do NOT summarize the content. Do NOT extract vocabulary or verbs.

List every distinct section header or label you can find in this document,
in the order they appear. Copy each header VERBATIM as it appears in the
text (preserve original casing/spelling). For each header, add a short
one-sentence note describing what kind of content follows it (e.g.
"bilingual story text", "vocabulary table with English/Spanish columns",
"multiple choice quiz with answer key").

Respond with ONLY a JSON array, no other text, in this exact shape:
[
  {{"header": "exact header text", "note": "one sentence describing what follows"}},
  ...
]

If the document has no clear headers at all (just running prose with no
labeled sections), respond with an empty array: []

Document text:
---
{text}
---
"""


def extract_text(pdf_path: Path) -> str:
    """Pull raw text from a PDF. Returns empty string on failure."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(pages)
    except Exception as e:
        print(f"  ! Failed to extract text: {e}")
        return ""


def query_qwen(text: str) -> list | None:
    """Ask Qwen for the header/structure list. Returns parsed list or None on failure."""
    truncated = text[:MAX_CHARS_TO_MODEL]
    prompt = DISCOVERY_PROMPT.format(text=truncated)

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip()

            # Model sometimes wraps JSON in ```json fences despite instructions
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
            print(f"  ! Attempt {attempt}: response was valid JSON but not a list, retrying")
        except json.JSONDecodeError as e:
            print(f"  ! Attempt {attempt}: JSON parse failed ({e}), retrying")
        except requests.RequestException as e:
            print(f"  ! Attempt {attempt}: request failed ({e}), retrying")
        time.sleep(2)

    return None


def main():
    if not PDF_DIR.exists():
        print(f"PDF directory not found: {PDF_DIR}")
        sys.exit(1)

    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files.\n")

    # Resume support: load existing report if present, skip already-done files
    results = {}
    if OUTPUT_FILE.exists():
        results = json.loads(OUTPUT_FILE.read_text())
        print(f"Resuming — {len(results)} files already processed.\n")

    for i, pdf_path in enumerate(pdf_files, 1):
        fname = pdf_path.name
        if fname in results and results[fname].get("status") == "success":
            continue

        print(f"[{i}/{len(pdf_files)}] {fname}")
        text = extract_text(pdf_path)

        if not text.strip():
            results[fname] = {"status": "failed", "reason": "no extractable text"}
            print("  ! No text extracted — flagging for manual review")
            _save(results)
            continue

        headers = query_qwen(text)

        if headers is None:
            results[fname] = {"status": "failed", "reason": "LLM extraction failed after retries"}
            print("  ! Failed after retries — flagging for manual review")
        else:
            results[fname] = {
                "status": "success",
                "char_count": len(text),
                "truncated": len(text) > MAX_CHARS_TO_MODEL,
                "headers": headers,
            }
            print(f"  \u2713 Found {len(headers)} section headers")

        _save(results)  # checkpoint after every file

    # Summary
    succeeded = sum(1 for r in results.values() if r.get("status") == "success")
    failed = sum(1 for r in results.values() if r.get("status") == "failed")
    print(f"\nDone. {succeeded} succeeded, {failed} failed.")
    if failed:
        print("Failed files:")
        for fname, r in results.items():
            if r.get("status") == "failed":
                print(f"  - {fname}: {r.get('reason')}")
    print(f"\nFull report: {OUTPUT_FILE.resolve()}")


def _save(results: dict):
    OUTPUT_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()