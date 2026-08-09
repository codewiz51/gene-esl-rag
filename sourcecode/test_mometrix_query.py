import chromadb
from chromadb.config import Settings

CHROMA_PATH = "/Users/gene/Documents/RAG/chroma"

client = chromadb.PersistentClient(
    path=CHROMA_PATH,
    settings=Settings(anonymized_telemetry=False)
)

col = client.get_collection("mometrix_english")

start_page = 30
end_page = 32

results = col.query(
    query_texts=["test"],
    where={
        "$and": [
            {"printed_page": {"$gte": start_page}},
            {"printed_page": {"$lte": end_page}}
        ]
    },
    n_results=100
)

docs = results["documents"][0]

for i, d in enumerate(docs):
    print(f"\n--- CHUNK {i} ---\n")
    print(d)

print(f"Returned documents: {len(docs)}")
print("\n--- SAMPLE TEXT ---\n")
print(docs[0][:800])

