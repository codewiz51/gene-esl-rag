import os
import chromadb
from chromadb.config import Settings
from pypdf import PdfReader
import uuid
from chromadb.utils import embedding_functions
embedder = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-m3")

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

PDF_DIR = "/Users/gene/Documents/English As A Second Language/ESL Lessons"
CHROMA_PATH = "/Users/gene/Documents/RAG/chroma"
COLLECTION_NAME = "esl_lessons"

# ---------------------------------------------------------
# CHUNKING FUNCTION
# ---------------------------------------------------------

def chunk_text(text, chunk_size=800, overlap=100):
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap

    return chunks

# ---------------------------------------------------------
# PDF TEXT EXTRACTION
# ---------------------------------------------------------

def extract_text_from_pdf(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
        return ""

# ---------------------------------------------------------
# MAIN INGESTION LOGIC
# ---------------------------------------------------------

def ingest_esl_pdfs():
    print("Connecting to Chroma DB...")
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    print(f"Creating/Loading collection: {COLLECTION_NAME}")
    collection = client.get_or_create_collection(COLLECTION_NAME, embedding_function=embedder)

    print(f"Scanning directory: {PDF_DIR}")
    files = [f for f in os.listdir(PDF_DIR) if f.lower().endswith(".pdf")]

    print(f"Found {len(files)} PDF files.")

    for filename in files:
        pdf_path = os.path.join(PDF_DIR, filename)
        print(f"\nProcessing: {filename}")

        text = extract_text_from_pdf(pdf_path)
        if not text:
            print(f"Skipping {filename} (no text extracted).")
            continue

        chunks = chunk_text(text)
        print(f"Extracted {len(chunks)} chunks.")

        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = [{"source": filename, "type": "esl_lesson"} for _ in chunks]

        collection.add(
            documents=chunks,
            metadatas=metadatas,
            ids=ids
        )

        print(f"Ingested {filename} into collection '{COLLECTION_NAME}'.")

    print("\nIngestion complete!")

# ---------------------------------------------------------
# RUN
# ---------------------------------------------------------

if __name__ == "__main__":
    ingest_esl_pdfs()

