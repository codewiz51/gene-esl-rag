import chromadb

client = chromadb.PersistentClient(path="/Users/gene/RAG/chroma")

collection = client.create_collection(
    name="mometrix_english",
    metadata={"source": "mometrix_english_pdf"}
)

print("Collection created:", collection.name)

