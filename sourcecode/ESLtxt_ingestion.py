import os
import chromadb
from chromadb.config import Settings
import uuid
from chromadb.utils import embedding_functions
embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="/Users/gene/Models/bge-m3"
)

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

#Change the directory path to match your folder structure
FILE_DIR = "/Users/gene/Documents/RAG/source_docs/ESL"
# Change to your Chroma path
CHROMA_PATH = "/Users/gene/Documents/RAG/chroma"
# Change to the correct collection name
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
# TXT TEXT EXTRACTION
# ---------------------------------------------------------

def extract_text_from_txt(txt_path):
    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(f"Error reading {txt_path}: {e}")
        return ""


# ---------------------------------------------------------
# MAIN INGESTION LOGIC
# ---------------------------------------------------------

def ingest_esl_txts():
    print("Connecting to Chroma DB...")
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    print(f"Creating/Loading collection: {COLLECTION_NAME}")
    collection = client.get_or_create_collection(COLLECTION_NAME, embedding_function=embedder)

    print(f"Scanning directory: {FILE_DIR}")
    files = [f for f in os.listdir(FILE_DIR) if f.lower().endswith(".txt")]

    print(f"Found {len(files)} TXT files.")

    for filename in files:
        txt_path = os.path.join(FILE_DIR, filename)
        print(f"\nProcessing: {filename}")

        text = extract_text_from_txt(txt_path)
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
    ingest_esl_txts()

