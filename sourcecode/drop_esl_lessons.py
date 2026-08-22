import chromadb
client = chromadb.PersistentClient(path="/Users/gene/Documents/RAG/chroma")
client.delete_collection("esl_lessons")
