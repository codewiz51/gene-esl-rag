import sys
import os
from datetime import datetime
import requests
import chromadb
from chromadb.config import Settings
import re

# =========================================================
# CONFIGURATION
# =========================================================

CHROMA_PATH = "/Users/gene/Documents/RAG/chroma"
COLLECTIONS = ["esl_lessons", "mometrix_english", "mometrix_spanish"]

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma4-clean"

weekly_template_dir = "/Users/gene/Documents/RAG/source_docs/weeklytemplates"
output_dir = "/Users/gene/Documents/RAG/source_docs/WeeklyLessons"

SECTION_MARKERS = [
    "WARMUP", "VOCABULARY", "STORY_EN", "STORY_ES",
    "GRAMMAR", "EXAMPLES", "TRANSLATION_ES_EN", "TRANSLATION_EN_ES",
    "QUESTIONS", "CLOSING"
]

# =========================================================
# BASIC HELPERS
# =========================================================

def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def call_model(prompt):
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "think": False
    }
    resp = requests.post(OLLAMA_URL, json=payload)
    resp.raise_for_status()
    return resp.json()["response"]

# =========================================================
# CHROMA RETRIEVAL
# =========================================================

def get_client():
    return chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False)
    )

## query() always returns its n_results nearest neighbors, even when
## none of them are actually relevant — there's no built-in "nothing
## matched" case. A hail/car-maintenance day has no business pulling in
## CMA exam content just because mometrix_english was asked for its 4
## closest chunks regardless of how far away they are. DISTANCE_THRESHOLD
## drops chunks past a cutoff instead of forcing them in.
##
## 1.0 is a starting point, not a calibrated value — your collections'
## actual embedding distances haven't been measured here. Cheapest way
## to tune it: run retrieve_context() for a couple of days you know are
## clinic-relevant (should return low distances) and a couple you know
## aren't (should return high ones), print the distances, and set the
## threshold between the two clusters — the same approach the OneDrive
## dedup report used to find its own cutoff.
DISTANCE_THRESHOLD = 1.0

def retrieve_context(client, query, distance_threshold=DISTANCE_THRESHOLD):
    """Semantic search across the three collections, keyed on whatever
    query text is passed in. Quality of the results is only as good as
    the query — see build_retrieval_query() below."""
    all_chunks = []
    for name in COLLECTIONS:
        col = client.get_collection(name)
        results = col.query(
            query_texts=[query],
            n_results=4,
            include=["documents", "metadatas", "distances"],
        )
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0]
        for doc, meta, dist in zip(docs, metas, dists):
            if dist > distance_threshold:
                continue  # too far to be genuinely relevant — drop it
            source = meta.get("source", "unknown")
            all_chunks.append(f"[{name} | {source} | dist={dist:.3f}]\n{doc}\n")
    if not all_chunks:
        return "[No closely relevant prior lesson content found for this day.]"
    return "\n\n".join(all_chunks)


def build_retrieval_query(day, day_block):
    """Turn a day's actual template content into the retrieval query,
    instead of a generic 'Generate the Monday lesson' string.

    Uses the whole day_block (Story Requirements, vocabulary themes,
    language focus, etc.) rather than cherry-picking specific line
    prefixes. That's deliberately the more robust choice over parsing
    out just the '-' bullets: your template's exact line prefixes have
    already changed a few times this conversation (Vocabulary vs.
    Vocabulary themes, etc.), and a whole-block query keeps working
    even as that formatting evolves, at the cost of including a little
    boilerplate noise (e.g. "Story Format: Must use the 2-column...").
    That noise is a small fraction of the text and shouldn't meaningfully
    hurt the embedding — but if you ever want tighter retrieval, the
    alternative is to only pass lines starting with "-" plus any line
    containing "Vocabulary" or "Language focus".
    """
    text = day_block.strip()
    if not text:
        return f"Generate the {day} lesson"  # fallback if a day has no content
    return text

# =========================================================
# MOMETRIX MACRO SUPPORT
# =========================================================

def parse_mometrix_macro(line):
    pattern = r"#MOMETRIX_SUMMARY\((\d+),\s*(\d+),\s*(\d+)\)"
    match = re.search(pattern, line)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))

def lookup_mometrix_pages(collection, start_page, end_page):
    """Pull all chunks in a page range.

    This is a pure metadata filter, not a similarity search, so it uses
    collection.get() rather than collection.query(). The previous version
    used query(query_texts=["dummy"], where=..., n_results=100) — with a
    meaningless "dummy" query, the embedding similarity ranking used to
    pick the top 100 results was arbitrary. That's harmless if a page
    range has fewer than 100 chunks (you'd get all of them regardless of
    ranking), but silently unreliable if a range ever has more: you'd get
    a similarity-ranked-by-nonsense subset instead of a complete,
    deterministic one. get() skips the embedding step entirely and
    returns every matching chunk directly.
    """
    results = collection.get(
        where={"$and": [
            {"printed_page": {"$gte": start_page}},
            {"printed_page": {"$lte": end_page}}
        ]},
    )
    docs = results["documents"]
    if not docs:
        return f"[No Mometrix content found for pages {start_page}-{end_page}]"
    return " ".join(docs)

def extract_day_block(template_text, day):
    week_part, day_part = day.rsplit(" ", 1)  # "WEEK 30", "MONDAY"
    week_start = f"+++ START {week_part} +++"
    week_end = f"+++ END {week_part} +++"
    day_start = f"=== START {day_part} ==="
    day_end = f"=== END {day_part} ==="

    lines = template_text.splitlines()
    in_target_week = False
    collecting = False
    block_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped == week_start:
            in_target_week = True
            continue
        if stripped == week_end:
            break
        if in_target_week and stripped == day_start:
            collecting = True
            continue
        if collecting and stripped == day_end:
            break
        if collecting:
            block_lines.append(line)
    return "\n".join(block_lines)

# =========================================================
# SECTION PARSING AND HTML RENDERING
# =========================================================

def parse_sections(response_text):
    """Split model output into a dict keyed by marker name. Missing
    markers come back as empty strings so rendering never KeyErrors."""
    sections = {name: "" for name in SECTION_MARKERS}
    pattern = r"\[(" + "|".join(SECTION_MARKERS) + r")\]"
    parts = re.split(pattern, response_text)
    it = iter(parts[1:])  # parts[0] is any stray preamble before the first marker
    for marker, content in zip(it, it):
        sections[marker] = content.strip()
    return sections

def render_line_list(text, tag="ul"):
    """One input line -> one <li>. Strips any bullet/number the model
    added despite instructions not to, so output stays clean either way."""
    items = []
    for line in text.splitlines():
        line = re.sub(r"^[\-\*\d\.\)]+\s*", "", line.strip())
        if line:
            items.append(f"<li>{line}</li>")
    return f"<{tag}>\n" + "\n".join(items) + f"\n</{tag}>"

def render_story_table(story_en, story_es):
    return f"""<table class="story-table" style="width: 100%; table-layout: fixed; border-collapse: collapse;">
  <tbody>
    <tr>
      <td style="width: 50%; vertical-align: top; padding-right: 10px;">
        <p>{story_en}</p>
      </td>
      <td style="width: 50%; vertical-align: top; padding-left: 10px;">
        <p>{story_es}</p>
      </td>
    </tr>
  </tbody>
</table>"""

def render_day_html(week_part, day_part, sections):
    html = [f"<h1>{day_part} ({week_part.title()})</h1>"]

    html.append("<h2>Warm-up / Calentamiento</h2>")
    html.append(f"<p>{sections['WARMUP']}</p>")

    html.append("<h2>Vocabulary / Vocabulario</h2>")
    html.append(render_line_list(sections['VOCABULARY']))

    html.append("<h2>Story / Historia</h2>")
    html.append(render_story_table(sections['STORY_EN'], sections['STORY_ES']))

    html.append("<h2>Grammar Point / Punto Gramatical</h2>")
    html.append(f"<p>{sections['GRAMMAR']}</p>")

    html.append("<h2>Example Sentences / Oraciones de Ejemplo</h2>")
    html.append(render_line_list(sections['EXAMPLES']))

    html.append("<h2>Translation Practice / Práctica de Traducción</h2>")
    html.append("<h3>Spanish to English:</h3>")
    html.append(render_line_list(sections['TRANSLATION_ES_EN'], tag="ol"))
    html.append("<h3>English to Spanish:</h3>")
    html.append(render_line_list(sections['TRANSLATION_EN_ES'], tag="ol"))

    html.append("<h2>Student Questions / Preguntas del Estudiante</h2>")
    html.append(render_line_list(sections['QUESTIONS']))

    html.append("<h2>Closing Summary / Resumen Final</h2>")
    html.append(f"<p>{sections['CLOSING']}</p>")

    return "\n".join(html)

# =========================================================
# WEEKLY LESSON GENERATION
# =========================================================

def generate_weekly_lesson(weekly_template_path):
    template_text = load(weekly_template_path)

    days_in_template = []
    current_week = None
    for line in template_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("+++ START WEEK"):
            current_week = stripped.replace("+++ START", "").replace("+++", "").strip()  # "WEEK 30"
            continue
        if stripped.startswith("+++ END WEEK"):
            current_week = None
            continue
        if current_week and stripped.startswith("=== START ") and stripped.endswith(" ==="):
            day_name = stripped.replace("=== START", "").replace("===", "").strip()  # "MONDAY"
            days_in_template.append(f"{current_week} {day_name}")  # "WEEK 30 MONDAY"

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    base_name = os.path.splitext(os.path.basename(weekly_template_path))[0]
    weekly_output_filename = f"{base_name}Output{timestamp}.html"
    weekly_output_path = os.path.join(output_dir, weekly_output_filename)

    output_file = open(weekly_output_path, "w", encoding="utf-8")
    output_file.write("""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Weekly Lesson Output</title>
<style>
    body { font-family: "Times New Roman", serif; font-size: 14pt; margin: 40px; }
    h1 { font-size: 18pt; }
    h2 { font-size: 16pt; }
</style>
</head>
<body>
""")

    client = get_client()
    # Fetched lazily, only if a day actually has a Mometrix macro (see
    # below) — a week with no macros at all should never need this
    # collection to exist, let alone fail loudly for it.
    mometrix_english = None

    for day in days_in_template:
        day_block = extract_day_block(template_text, day)

        query = build_retrieval_query(day, day_block)
        context = retrieve_context(client, query)

        prompt = (
            "You are an ESL teacher creating bilingual English–Spanish lessons.\n"
            f"=== WEEKLY TEMPLATE ===\n{template_text}\n\n"
            f"=== TODAY'S REQUIREMENTS ({day}) ===\n{day_block}\n\n"
            f"=== RETRIEVED CONTEXT ===\n{context}\n\n"
            "TASK:\n"
            "Respond in plain text only, using exactly these markers, each on its own\n"
            "line, in this exact order, with no extra commentary before, between, or\n"
            "after them:\n"
            "[WARMUP]\n"
            "[VOCABULARY]\n"
            "[STORY_EN]\n"
            "[STORY_ES]\n"
            "[GRAMMAR]\n"
            "[EXAMPLES]\n"
            "[TRANSLATION_ES_EN]\n"
            "[TRANSLATION_EN_ES]\n"
            "[QUESTIONS]\n"
            "[CLOSING]\n"
            "Follow the exact Translation Practice sentence counts for long vs short days.\n"
        )

        macro = parse_mometrix_macro(day_block)
        if macro:
            start_page, end_page, num_sentences = macro
            if mometrix_english is None:
                # get_collection (not get_or_create_collection): if this
                # name or the Chroma path ever drifts, fail loudly here
                # instead of silently creating an empty collection and
                # returning "[No Mometrix content found]" as if that were
                # a normal empty page range.
                mometrix_english = client.get_collection("mometrix_english")
            raw_mometrix = lookup_mometrix_pages(mometrix_english, start_page, end_page)
            summary_prompt = (
                f"Summarize the following Mometrix content into {num_sentences} sentences:\n\n"
                f"{raw_mometrix}"
            )
            summary = call_model(summary_prompt).strip()
            prompt += f"\n\nMOMETRIX SUMMARY:\n{summary}\n"

        lesson = call_model(prompt)

        week_part, day_part = day.rsplit(" ", 1)
        sections = parse_sections(lesson)
        output_file.write(render_day_html(week_part, day_part, sections) + "\n")

    output_file.write("\n</body>\n</html>")
    output_file.close()

    return weekly_output_path

# =========================================================
# FIVE-MINUTE REINFORCEMENT GENERATION
# =========================================================

def generate_five_minute(weekly_html_path, five_minute_template_path):
    weekly_html = load(weekly_html_path)
    template = load(five_minute_template_path)

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

    model_output = call_model(prompt)

    base_name = os.path.splitext(os.path.basename(weekly_html_path))[0]
    output_filename = f"{base_name}FiveMinute.html"
    output_path = os.path.join(output_dir, output_filename)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Five Minute Reinforcement Lessons</title>
<style>
    body { font-family: "Times New Roman", serif; font-size: 14pt; margin: 40px; }
    h1 { font-size: 18pt; }
    h2 { font-size: 16pt; }
</style>
</head>
<body>
""")
        f.write(model_output)
        f.write("\n</body>\n</html>")

    return output_path

# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 combined_generator.py WeekXX.txt FiveMinuteTemplate.txt")
        sys.exit(1)

    weekly_template = sys.argv[1]
    five_minute_template = sys.argv[2]

    weekly_template_path = os.path.join(weekly_template_dir, weekly_template)
    five_minute_template_path = os.path.join(weekly_template_dir, five_minute_template)

    print("\n=== Generating Weekly Lesson ===")
    weekly_html_path = generate_weekly_lesson(weekly_template_path)
    print(f"Weekly lesson saved to: {weekly_html_path}")

    print("\n=== Generating Five-Minute Reinforcement ===")
    five_minute_path = generate_five_minute(weekly_html_path, five_minute_template_path)
    print(f"Five-minute lessons saved to: {five_minute_path}\n")