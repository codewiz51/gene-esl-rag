import chromadb
from chromadb.config import Settings

CHROMA_PATH = "/Users/gene/Documents/RAG/chroma"
COLLECTIONS = ["esl_lessons"]

client = chromadb.PersistentClient(path=CHROMA_PATH, settings=Settings(anonymized_telemetry=False))

def show_distances(label, query_text):
    print(f"\n=== {label} ===")
    print(f"Query: {query_text[:80]}...")
    for name in COLLECTIONS:
        col = client.get_collection(name)
        results = col.query(query_texts=[query_text], n_results=4, include=["distances", "metadatas"])
        dists = results["distances"][0]
        metas = results["metadatas"][0]
        for dist, meta in zip(dists, metas):
            source = meta.get("source", "unknown")
            print(f"  {name} | dist={dist:.3f} | {source}")

show_distances(
    "Relevant (clinic day)",
    "Rico arrives at the clinic with severe fatigue and joint pain from a tick bite."
)

show_distances(
    "Irrelevant (control)",
    "Car tires and windshield washer fluid after a hail storm."
)
