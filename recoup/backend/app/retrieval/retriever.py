"""
retrieval/retriever.py
----------------------
RAG / vector-search retrieval logic.

TODO: Implement document chunking, embedding, and similarity search.
      Suggested libraries: langchain, llama-index, or a plain pgvector / chromadb client.
"""


class Retriever:
    """
    Stub retriever.  Replace this with a real vector-store client.

    Usage (future):
        retriever = Retriever()
        chunks = await retriever.search(query="refund policy", top_k=5)
    """

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Return relevant document chunks for *query*.  Not yet implemented."""
        # TODO: embed query → vector store lookup → return ranked chunks
        raise NotImplementedError("Retriever.search() is not yet implemented.")
