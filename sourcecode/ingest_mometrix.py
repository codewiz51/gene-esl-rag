import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from chromadb.utils import embedding_functions

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

ENGLISH_PDF = "/Users/gene/Documents/RAG/source_docs/Mometrix/MometrixComplete.pdf"
SPANISH_PDF = "/Users/gene/Documents/RAG/source_docs/Mometrix/MometrixCMAEspañolCompleto.pdf"

CHROMA_PATH = "/Users/gene/Documents/RAG/chroma"  # kept for clarity, not used by Client()

CHUNK_SIZE = 800
OVERLAP = 100

# Page offsets
ENGLISH_OFFSET = 8
SPANISH_OFFSET = 6

# ---------------------------------------------------------
# INITIALIZE CHROMA (SIMPLE CLIENT + PERSIST)
# ---------------------------------------------------------

client = chromadb.PersistentClient(path=CHROMA_PATH)

embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="BAAI/bge-m3"
)

english_collection = client.get_or_create_collection(
    name="mometrix_english",
    embedding_function=embedder
)

spanish_collection = client.get_or_create_collection(
    name="mometrix_spanish",
    embedding_function=embedder
)

# ---------------------------------------------------------
# LOAD EMBEDDING MODEL
# ---------------------------------------------------------

model = SentenceTransformer("BAAI/bge-m3")

# ---------------------------------------------------------
# PDF TEXT EXTRACTION
# ---------------------------------------------------------

def extract_pdf_text(path):
    reader = PdfReader(path)
    pages = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text()
        except:
            text = ""
        pages.append((i + 1, text))  # pdf_page_number, text
    return pages

# ---------------------------------------------------------
# CHUNKING FUNCTION
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
# INGEST PDF INTO CHROMA
# ---------------------------------------------------------

def ingest_pdf(pdf_path, collection, language_label, offset):
    print(f"\nIngesting {language_label} PDF: {pdf_path}")

    pages = extract_pdf_text(pdf_path)

    all_chunks = []
    for pdf_page, text in tqdm(pages, desc=f"Chunking {language_label}"):
        printed_page = pdf_page - offset

        # Skip junk pages (printed_page <= 0)
        if printed_page <= 0:
            continue

        if text:
            chunks = chunk_text(text, printed_page, pdf_page)
            all_chunks.extend(chunks)

    print(f"{language_label}: {len(all_chunks)} chunks created.")

    # Embed and insert
    for idx, chunk in enumerate(tqdm(all_chunks, desc=f"Embedding {language_label}")):
        emb = model.encode(chunk["text"]).tolist()
        collection.add(
            documents=[chunk["text"]],
            embeddings=[emb],
            metadatas=[{
                "printed_page": chunk["printed_page"],
                "pdf_page": chunk["pdf_page"]
            }],
            ids=[f"{language_label}_{chunk['pdf_page']}_{idx}"]
        )

    print(f"{language_label} ingestion complete.")

# ---------------------------------------------------------
# RUN INGESTION
# ---------------------------------------------------------

ingest_pdf(ENGLISH_PDF, english_collection, "english", ENGLISH_OFFSET)
ingest_pdf(SPANISH_PDF, spanish_collection, "spanish", SPANISH_OFFSET)

# ---------------------------------------------------------
# SAVE TO DISK
# ---------------------------------------------------------

print("\nAll ingestion complete and saved to disk.")

