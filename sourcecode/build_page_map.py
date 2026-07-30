import json
import chromadb

CHROMA_PATH = "/Users/gene/Documents/RAG/chroma"

# ---------------------------------------------------------
# CONNECT TO PERSISTENT CHROMA
# ---------------------------------------------------------

client = chromadb.PersistentClient(path=CHROMA_PATH)

english = client.get_collection("mometrix_english")
spanish = client.get_collection("mometrix_spanish")

# ---------------------------------------------------------
# FUNCTION TO BUILD PAGE MAP FROM A COLLECTION
# ---------------------------------------------------------

def build_map(collection, label):
    page_map = {}

    # Must include documents to get ids in Chroma v0.3.x
    results = collection.get(include=["metadatas", "documents"])

    metadatas = results["metadatas"]
    ids = results["ids"]

    for meta, chunk_id in zip(metadatas, ids):
        printed_page = meta["printed_page"]
        pdf_page = meta["pdf_page"]

        if printed_page not in page_map:
            page_map[printed_page] = {
                "pdf_page": pdf_page,
                "english_chunks": [],
                "spanish_chunks": []
            }

        page_map[printed_page][f"{label}_chunks"].append(chunk_id)

    return page_map

# ---------------------------------------------------------
# BUILD ENGLISH + SPANISH MAPS
# ---------------------------------------------------------

english_map = build_map(english, "english")
spanish_map = build_map(spanish, "spanish")

# ---------------------------------------------------------
# MERGE MAPS
# ---------------------------------------------------------

merged = {}

all_pages = sorted(set(list(english_map.keys()) + list(spanish_map.keys())))

for page in all_pages:
    merged[page] = {
        "pdf_page_english": english_map.get(page, {}).get("pdf_page"),
        "pdf_page_spanish": spanish_map.get(page, {}).get("pdf_page"),
        "english_chunks": english_map.get(page, {}).get("english_chunks", []),
        "spanish_chunks": spanish_map.get(page, {}).get("spanish_chunks", [])
    }

# ---------------------------------------------------------
# SAVE JSON
# ---------------------------------------------------------

with open("page_map.json", "w") as f:
    json.dump(merged, f, indent=2)

print("Page map written to page_map.json")

