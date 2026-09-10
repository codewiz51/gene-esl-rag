#!/usr/bin/env python3
"""
Real extraction pipeline for the ESL lesson archive -> Postgres.

Unlike discover_structure.py, this sends FULL document text per logical
unit (not truncated), because a missing vocabulary/answer-key section here
means missing DATA, not just missing metadata about structure.

Requires: pip install pdfplumber requests psycopg2-binary pydantic
Requires: structure_report.json (from discover_structure.py) in the same dir
Requires: Postgres schema + 03_schema_updates.sql already applied
"""

import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

import pdfplumber
import psycopg2
import requests
from pydantic import BaseModel, ValidationError

# ---- Config ------------------------------------------------------------
PDF_DIR = Path("/Users/gene/Documents/English As A Second Language/ESL Lessons")
STRUCTURE_REPORT = Path("./structure_report.json")
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen38:latest"
RETRY_ATTEMPTS = 3
REQUEST_TIMEOUT = 300

DB_DSN = "dbname=esl_lessons user=esl_extractor password=300CricketHollow host=localhost"
# NOTE: rotate this password before this DB is ever exposed beyond localhost.

DAY_DIVIDER_RE = re.compile(
    r"(week\s*\d+\s*[\u2013\-]\s*day\s*\d+|day\s*\d+\s*[\u2013\-]\s*"
    r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b)",
    re.IGNORECASE,
)
PREVIEW_RE = re.compile(r"preview|previa", re.IGNORECASE)
SUMMARY_RE = re.compile(r"summary|resumen", re.IGNORECASE)

# ---- Filename parsing ---------------------------------------------------

FNAME_PATTERNS = [
    # Week N Day D-D (range) — check before single-day pattern
    (re.compile(r"week\s*(\d+)\s*day\s*(\d+)\s*[\-\u2013]\s*(\d+)", re.I),
     lambda m: {"week": int(m.group(1)), "day": None,
                "day_range": f"{m.group(2)}-{m.group(3)}"}),
    # Week N Day D Part P
    (re.compile(r"week\s*(\d+)\s*day\s*(\d+)\s*part\s*(\d+)", re.I),
     lambda m: {"week": int(m.group(1)), "day": int(m.group(2)),
                "day_range": None, "part": int(m.group(3))}),
    # Week N Day D  (single day, any suffix after)
    (re.compile(r"week\s*(\d+)\s*day\s*(\d+)", re.I),
     lambda m: {"week": int(m.group(1)), "day": int(m.group(2)), "day_range": None}),
    # Week N Days D-D
    (re.compile(r"week\s*(\d+)\s*days\s*(\d+)\s*[\-\u2013]\s*(\d+)", re.I),
     lambda m: {"week": int(m.group(1)), "day": None,
                "day_range": f"{m.group(2)}-{m.group(3)}"}),
    # Plain "Week N.pdf" or "WEEK N"
    (re.compile(r"week\s*(\d+)\b", re.I),
     lambda m: {"week": int(m.group(1)), "day": None, "day_range": None}),
]


def parse_filename(fname: str) -> dict:
    """Best-effort parse of week/day from filename. Flags unparseable names."""
    result = {"week": None, "day": None, "day_range": None, "part": None,
              "parse_ok": False}
    for pattern, extractor in FNAME_PATTERNS:
        m = pattern.search(fname)
        if m:
            result.update(extractor(m))
            result["parse_ok"] = True
            break

    lower = fname.lower()
    if PREVIEW_RE.search(lower):
        result["doc_type_hint"] = "preview"
    elif SUMMARY_RE.search(lower):
        result["doc_type_hint"] = "summary"
    elif result["week"] is None:
        result["doc_type_hint"] = "supplemental"
    else:
        result["doc_type_hint"] = "weekly_lesson" if result["week"] and result["week"] >= 9 else "daily_lesson"

    result["source_of_truth"] = "filename" if (result["week"] or 0) < 9 else "header"
    return result


# ---- Document segmentation (uses structure_report.json headers) --------

def segment_document(full_text: str) -> list:
    """
    Split a document's full text into logical units at day-divider
    boundaries, found by scanning the FULL text directly (not relying on
    structure_report.json's header list, which was built during a
    truncated discovery pass and may be missing boundaries past ~12k
    characters -- confirmed to cause silent over-merging on Week 9.pdf).
    Falls back to one unit = whole document if no day dividers are found
    (the normal case for pre-Week-9 daily files).
    """
    matches = list(DAY_DIVIDER_RE.finditer(full_text))
    if not matches:
        return [{"day_label": None, "text": full_text}]

    boundaries = []
    for m in matches:
        start = m.start()
        line_end = full_text.find("\n", start)
        if line_end == -1:
            line_end = len(full_text)
        label = full_text[start:line_end].strip()
        boundaries.append((start, label))

    # dedupe matches that landed on the same line (regex alternation can
    # double-match, e.g. "Week 9 - Day 3" tripping both the "week N day D"
    # and a weekday-name branch)
    deduped = []
    for start, label in boundaries:
        if deduped and start - deduped[-1][0] < 20:
            continue
        deduped.append((start, label))

    units = []
    for i, (start, label) in enumerate(deduped):
        end = deduped[i + 1][0] if i + 1 < len(deduped) else len(full_text)
        units.append({"day_label": label, "text": full_text[start:end]})
    return units


def extract_day_number(label):
    if not label:
        return None
    m = re.search(r"day\s*(\d+)", label, re.IGNORECASE)
    return int(m.group(1)) if m else None


# ---- PDF text extraction -------------------------------------------------

def extract_full_text(pdf_path: Path) -> str:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception as e:
        print(f"  ! PDF extraction failed: {e}")
        return ""


# ---- Extraction schema (pydantic) ---------------------------------------

class VocabItem(BaseModel):
    english: str
    spanish: Optional[str] = None
    category: Optional[str] = "general"  # general / high_frequency / medical


class VerbItem(BaseModel):
    verb: str
    meaning: Optional[str] = None
    tense: Optional[str] = None
    is_explicit: bool = True  # False = inferred from an undifferentiated word list


class PhraseItem(BaseModel):
    phrase: str
    translation: Optional[str] = None


class ExtractionResult(BaseModel):
    doc_type: str
    cefr_estimate: Optional[str] = None
    pronunciation_style: Optional[str] = None
    comprehension_format: Optional[str] = None
    vocabulary: list = []
    verbs: list = []
    idioms: list = []
    clinic_language: list = []
    characters: list = []
    spanish_register_narrative: Optional[str] = None
    spanish_register_clinical: Optional[str] = None
    register_notes: Optional[str] = None


EXTRACTION_PROMPT = """You are extracting structured data from one unit of an
ESL lesson (for native Spanish speakers, clinic/medical-assistant themed).
This archive spans 33+ weeks with inconsistent, evolving formatting -- do
not assume a fixed template.

Extract the following, using ONLY what is actually in the text (never
invent content):

1. VOCABULARY -- every English/Spanish word or phrase pair presented as
   vocabulary. This may appear under headers like "Vocabulary", "VOCABULARY
   LIST", "Target words", "Word Pairs", or similar. Tag each item's
   category as "high_frequency", "medical", or "general" based on context
   (e.g. a section explicitly split into "3 HF + 3 Medical" should be
   tagged accordingly).

2. VERBS (focus verbs for this lesson) -- two cases:
   a. EXPLICIT: if there's a labeled section like "Verb Focus: to make, to
      need, to take" or "This week's verbs", extract those verbs with
      is_explicit=true.
   b. INFERRED: if there is NO such labeled section, scan the vocabulary
      list itself for any verbs that are given multiple example sentences
      across different tenses (present/past/future) -- that pattern
      indicates they were the intended focus even though not labeled.
      Extract those with is_explicit=false. If you cannot confidently
      identify any, leave verbs empty rather than guessing.

3. IDIOMS -- any idiomatic expressions explicitly called out (not every
   figure of speech in the story text, only ones presented as teaching
   content).

4. CLINIC_LANGUAGE -- medical-assistant / clinic-procedural phrases
   presented as teaching content (e.g. "take vitals", "make a copy of
   the ID"). Distinct from general vocabulary -- only include
   clinic-specific procedural language.

5. CHARACTERS -- names of recurring or one-off people in the story/
   dialogue portion of this unit.

6. PRONUNCIATION_STYLE -- one of: "phonetic_spelling" (e.g. "checked" ->
   "chekt"), "minimal_pairs" (e.g. "take/tape"), "tongue_twister" (e.g.
   "Fun Pronunciation Sentences"), "mixed" (more than one style present),
   or "absent".

7. COMPREHENSION_FORMAT -- one of: "multiple_choice_with_key",
   "open_ended", "exam_style" (CMA/SMA-formatted practice questions), or
   "absent".

8. SPANISH REGISTER -- this archive has a documented rule (from Week 2
   onward, inconsistently maintained later) that narrative/idiom Spanish
   should use Cuban dialect, while clinic-related Spanish should use
   professional medical/scientific register. Report what you actually
   observe:
   - spanish_register_narrative: describe the register used in
     story/dialogue Spanish (e.g. "Cuban dialect markers present", "neutral,
     standard Spanish, no clear regional marking", "Mexican-influenced
     vocabulary present")
   - spanish_register_clinical: describe the register used in clinic-
     related Spanish (e.g. "professional medical terminology used
     correctly", "informal, non-technical Spanish used for medical
     content")
   - register_notes: any other relevant observation (e.g. explicit
     regional dialect labels found in the text itself, like "estilo
     cubano")

9. CEFR_ESTIMATE -- your best rough estimate (A1/A2/B1/B2/C1) of the
   English proficiency level this unit targets, based on vocabulary
   complexity, sentence structure, and grammatical forms used. This is a
   rough heuristic, not a certification -- give your best single estimate.

10. DOC_TYPE -- one of: "daily_lesson", "weekly_lesson_day" (one day within
    a combined weekly file), "preview", "summary", "supplemental".

Respond with ONLY a JSON object matching this exact shape, no other text:
{{
  "doc_type": "...",
  "cefr_estimate": "...",
  "pronunciation_style": "...",
  "comprehension_format": "...",
  "vocabulary": [{{"english": "...", "spanish": "...", "category": "..."}}],
  "verbs": [{{"verb": "...", "meaning": "...", "tense": "...", "is_explicit": true}}],
  "idioms": [{{"phrase": "...", "translation": "..."}}],
  "clinic_language": [{{"phrase": "...", "translation": "..."}}],
  "characters": ["..."],
  "spanish_register_narrative": "...",
  "spanish_register_clinical": "...",
  "register_notes": "..."
}}

Lesson text:
---
{text}
---
"""


def call_qwen(text: str):
    prompt = EXTRACTION_PROMPT.format(text=text)
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={"model": MODEL, "prompt": prompt, "stream": False,
                      "options": {"temperature": 0.1}},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            data = json.loads(raw)
            return ExtractionResult(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"  ! Attempt {attempt}: invalid response ({e}), retrying")
        except requests.RequestException as e:
            print(f"  ! Attempt {attempt}: request failed ({e}), retrying")
        time.sleep(2)
    return None


# ---- Postgres -------------------------------------------------------------

def get_conn():
    return psycopg2.connect(DB_DSN)


def log_status(conn, unit_key, status, error=None, document_id=None):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO extraction_log (unit_key, document_id, status, attempt_count, error_message, last_attempted)
            VALUES (%s, %s, %s, 1, %s, NOW())
            ON CONFLICT (unit_key) DO UPDATE SET
                status = EXCLUDED.status,
                document_id = COALESCE(EXCLUDED.document_id, extraction_log.document_id),
                attempt_count = extraction_log.attempt_count + 1,
                error_message = EXCLUDED.error_message,
                last_attempted = NOW()
            """,
            (unit_key, document_id, status, error),
        )
    conn.commit()


def already_done(conn, unit_key) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT status FROM extraction_log WHERE unit_key = %s", (unit_key,))
        row = cur.fetchone()
        return row is not None and row[0] == "success"


def insert_result(conn, filename, meta, day_label, unit_key, result, mismatch):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents
                (filename, unit_key, week, day, day_range, doc_type, source_of_truth,
                 week_day_mismatch, cefr_estimate, pronunciation_style,
                 comprehension_format, spanish_register_narrative,
                 spanish_register_clinical, register_notes, raw_extraction,
                 processed_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
            RETURNING id
            """,
            (
                filename, unit_key, meta["week"], meta["day"] or extract_day_number(day_label),
                meta["day_range"], meta["doc_type_hint"], meta["source_of_truth"],
                mismatch, result.cefr_estimate, result.pronunciation_style,
                result.comprehension_format, result.spanish_register_narrative,
                result.spanish_register_clinical, result.register_notes,
                json.dumps(result.model_dump()),
            ),
        )
        doc_id = cur.fetchone()[0]

        for v in result.vocabulary:
            cur.execute(
                "INSERT INTO vocabulary (document_id, english, spanish, category) VALUES (%s,%s,%s,%s)",
                (doc_id, v.get("english"), v.get("spanish"), v.get("category", "general")),
            )
        for vb in result.verbs:
            cur.execute(
                "INSERT INTO verbs (document_id, verb, meaning, tense, is_explicit) VALUES (%s,%s,%s,%s,%s)",
                (doc_id, vb.get("verb"), vb.get("meaning"), vb.get("tense"), vb.get("is_explicit", True)),
            )
        for i in result.idioms:
            cur.execute(
                "INSERT INTO idioms (document_id, phrase, translation) VALUES (%s,%s,%s)",
                (doc_id, i.get("phrase"), i.get("translation")),
            )
        for c in result.clinic_language:
            cur.execute(
                "INSERT INTO clinic_language (document_id, phrase, translation) VALUES (%s,%s,%s)",
                (doc_id, c.get("phrase"), c.get("translation")),
            )
        for name in result.characters:
            cur.execute(
                "INSERT INTO characters (document_id, name) VALUES (%s,%s)",
                (doc_id, name),
            )
    conn.commit()
    return doc_id


# ---- Main -----------------------------------------------------------------

def main():
    structure = {}
    if STRUCTURE_REPORT.exists():
        structure = json.loads(STRUCTURE_REPORT.read_text())
    # NOTE: structure_report.json is no longer required for segmentation --
    # day-boundary detection now scans full extracted text directly. Kept
    # loaded here only in case a future pass wants to cross-reference it.

    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    conn = get_conn()

    total_units = 0
    for i, pdf_path in enumerate(pdf_files, 1):
        fname = pdf_path.name
        meta = parse_filename(fname)
        if not meta["parse_ok"] and meta["doc_type_hint"] != "supplemental":
            print(f"[{i}/{len(pdf_files)}] {fname}  ! Unparseable filename -- flagging for manual review")

        full_text = extract_full_text(pdf_path)
        if not full_text.strip():
            print(f"[{i}/{len(pdf_files)}] {fname}  ! No extractable text, skipping")
            continue

        headers = structure.get(fname, {}).get("headers", [])  # kept for reference only, not used for segmentation
        units = segment_document(full_text)

        print(f"[{i}/{len(pdf_files)}] {fname}  -> {len(units)} unit(s)")

        for unit in units:
            day_label = unit["day_label"]
            unit_key = f"{fname}::{day_label}" if day_label else fname
            total_units += 1

            if already_done(conn, unit_key):
                continue

            result = call_qwen(unit["text"])
            if result is None:
                log_status(conn, unit_key, "failed", "extraction failed after retries")
                print(f"    ! {unit_key} -- failed after {RETRY_ATTEMPTS} attempts")
                continue

            # Per-unit doc_type override: a file-level hint of "weekly_lesson"
            # needs refining per slice -- a day slice, a preview, or a summary
            # within the same combined file are three different doc_types,
            # not one. Pre-Week-9 daily files (one unit = whole file) keep
            # the file-level hint unchanged.
            unit_meta = dict(meta)
            if day_label:
                if PREVIEW_RE.search(day_label):
                    unit_meta["doc_type_hint"] = "preview"
                elif SUMMARY_RE.search(day_label):
                    unit_meta["doc_type_hint"] = "summary"
                else:
                    unit_meta["doc_type_hint"] = "weekly_lesson_day"

            day_mismatch = False
            doc_id = insert_result(conn, fname, unit_meta, day_label, unit_key, result, day_mismatch)
            log_status(conn, unit_key, "success", document_id=doc_id)
            print(f"    \u2713 {unit_key} -- {len(result.vocabulary)} vocab, {len(result.verbs)} verbs")

    conn.close()
    print(f"\nDone. {total_units} total units processed across {len(pdf_files)} files.")


if __name__ == "__main__":
    main()
