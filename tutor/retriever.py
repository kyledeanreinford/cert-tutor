import chromadb

from tutor.openai_client import OpenAIEmbedder


def retrieve(
    query: str, embedder: OpenAIEmbedder, chroma_dir: str, top_k: int
) -> list[dict[str, str | int | float]]:
    embedding = embedder.embed(query)
    chroma = chromadb.PersistentClient(path=chroma_dir)
    collection = chroma.get_collection("cert_docs")

    results = collection.query(query_embeddings=[embedding], n_results=top_k)

    chunks: list[dict[str, str | int | float]] = []
    for i in range(len(results["ids"][0])):
        chunks.append({
            "text": results["documents"][0][i],
            "source": results["metadatas"][0][i]["source"],
            "page": results["metadatas"][0][i]["page"],
            "score": results["distances"][0][i] if results["distances"] else 0.0,
        })
    return chunks
