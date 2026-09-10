import lancedb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

ENGLISH_PDF = "/Users/gene/Documents/RAG/source_docs/Mometrix/MometrixComplete.pdf"
SPANISH_PDF = "/Users/gene/Documents/RAG/source_docs/Mometrix/MometrixCMAEspañolCompleto.pdf"

LANCEDB_PATH = "/Users/gene/Documents/RAG/lancedb"

CHUNK_SIZE = 800
OVERLAP = 100

# Page offsets (PDF page index -> printed page number in the book)
ENGLISH_OFFSET = 8
SPANISH_OFFSET = 6

EMBEDDING_MODEL = "BAAI/bge-m3"

# ---------------------------------------------------------
# INITIALIZE LANCEDB + EMBEDDING MODEL
# ---------------------------------------------------------
# lancedb.connect() just points at a directory on disk - no server process,
# no daemon to manage. It creates LANCEDB_PATH if it doesn't exist yet.

db = lancedb.connect(LANCEDB_PATH)
model = SentenceTransformer(EMBEDDING_MODEL)

# ---------------------------------------------------------
# PDF TEXT EXTRACTION
# ---------------------------------------------------------

def extract_pdf_text(path):
    reader = PdfReader(path)
    pages = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text()
        except Exception:
            text = ""
        pages.append((i + 1, text))  # pdf_page_number, text
    return pages

# ---------------------------------------------------------
# CHUNKING FUNCTION (unchanged from the Chroma version)
# ---------------------------------------------------------

def chunk_text(text, printed_page, pdf_page):
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]
        chunks.append({
            "text": chunk,
            "printed_page": printed_page,
            "pdf_page": pdf_page
        })
        start = end - OVERLAP
    return chunks

# ---------------------------------------------------------
# BUILD RECORDS FOR ONE LANGUAGE
# ---------------------------------------------------------

def build_records(pdf_path, language_label, offset):
    print(f"\nExtracting {language_label} PDF: {pdf_path}")
    pages = extract_pdf_text(pdf_path)

    all_chunks = []
    for pdf_page, text in tqdm(pages, desc=f"Chunking {language_label}"):
        printed_page = pdf_page - offset

        # Skip junk pages (front matter, before the printed page numbering starts)
        if printed_page <= 0:
            continue

        if text:
            all_chunks.extend(chunk_text(text, printed_page, pdf_page))

    print(f"{language_label}: {len(all_chunks)} chunks created.")

    # NOTE: the original script called model.encode() once per chunk inside
    # the insert loop. Batch-encoding all chunk texts in one call is
    # meaningfully faster (the model processes them together instead of
    # one at a time) at the cost of holding all chunks for a language in
    # memory at once - not a real concern at this book's size.
    texts = [c["text"] for c in all_chunks]
    print(f"Embedding {len(texts)} {language_label} chunks...")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)

    records = []
    for idx, (chunk, emb) in enumerate(zip(all_chunks, embeddings)):
        records.append({
            "id": f"{language_label}_{chunk['pdf_page']}_{idx}",
            "text": chunk["text"],
            "printed_page": chunk["printed_page"],
            "pdf_page": chunk["pdf_page"],
            "language": language_label,
            "vector": emb.tolist()
        })

    return records

# ---------------------------------------------------------
# INGEST ONE LANGUAGE INTO ITS OWN TABLE
# ---------------------------------------------------------

def ingest(pdf_path, table_name, language_label, offset):
    records = build_records(pdf_path, language_label, offset)

    # mode="overwrite" makes this script safely re-runnable - re-running it
    # replaces the table cleanly instead of appending duplicate chunks.
    table = db.create_table(table_name, data=records, mode="overwrite")
    print(f"{language_label} ingestion complete: {table.count_rows()} rows in '{table_name}'")

# ---------------------------------------------------------
# RUN INGESTION
# ---------------------------------------------------------

if __name__ == "__main__":
    ingest(ENGLISH_PDF, "mometrix_english", "english", ENGLISH_OFFSET)
    ingest(SPANISH_PDF, "mometrix_spanish", "spanish", SPANISH_OFFSET)

    print("\nAll ingestion complete and saved to disk at:", LANCEDB_PATH)

    # ---------------------------------------------------------
    # QUICK SANITY-CHECK QUERY (optional - comment out if not needed)
    # ---------------------------------------------------------
    test_table = db.open_table("mometrix_english")
    query_text = "What is the scope of practice for a medical assistant?"
    query_vector = model.encode(query_text).tolist()
    results = test_table.search(query_vector).limit(3).to_list()

    print(f"\nTop matches for test query: \"{query_text}\"")
    for r in results:
        print(f"  page {r['printed_page']} (pdf page {r['pdf_page']}): {r['text'][:100]}...")

