"""
retrieval/retriever.py
----------------------
In-memory RAG vector search and policy retrieval module.
- Chunks markdown policy documents by section and header hierarchy.
- Generates normalized TF-IDF + subword n-gram semantic embeddings (with cosine similarity).
- Stores chunks in an in-memory vector store with zero external database dependencies.
- Exposes `retrieve_policy(query, k=2)` and async `Retriever.search(query, top_k)`.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ── Data Models ────────────────────────────────────────────────────────────────

@dataclass
class PolicyChunk:
    chunk_id: str
    policy_title: str
    section_title: str
    content: str
    file_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Dict[str, float] = field(default_factory=dict)

    def to_dict(self, score: float = 0.0) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "policy_title": self.policy_title,
            "section_title": self.section_title,
            "content": self.content,
            "file_name": self.file_name,
            "score": round(score, 4),
            "metadata": self.metadata,
        }


# ── Text Processing & Embedding Generator ─────────────────────────────────────

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so",
    "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll",
    "they're", "they've", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves"
}

SYNONYMS = {
    "insufficient": ["low", "balance", "funds", "nsf", "empty", "overdraft"],
    "funds": ["balance", "money", "insufficient", "account", "debit"],
    "card": ["card_expired", "credit", "debit", "expiry", "expired", "vault", "tokenized"],
    "expired": ["expiration", "expiry", "card_expired", "renew", "validity"],
    "timing": ["hours", "quiet", "night", "blackout", "schedule", "dnc", "window", "timezone"],
    "night": ["quiet", "blackout", "timing", "hours", "late", "evening", "20:00", "08:00"],
    "abandoned": ["abandonment", "drop", "cart", "checkout_abandonment", "left", "incomplete"],
    "cart": ["checkout", "abandoned", "basket", "items", "shopper"],
    "dunning": ["subscription", "recurring", "renewal", "grace", "downgrade", "retries"],
    "subscription": ["recurring", "dunning", "renewal", "plan", "tier", "saas", "membership"],
    "unrecoverable": ["writeoff", "write_off", "closed", "fraud", "fatal", "account_closed"],
    "closed": ["account_closed", "deactivated", "unrecoverable", "terminated", "frozen"],
}


class SemanticVectorizer:
    """
    Subword & Lexical TF-IDF Vectorizer with Cosine Normalization.
    Extracts words, character 3-4 n-grams, and domain-synonym expansion for high
    retrieval precision across semantic and keyword queries.
    """

    def __init__(self) -> None:
        self.doc_frequencies: Dict[str, int] = {}
        self.total_docs: int = 0

    def tokenize(self, text: str) -> List[str]:
        cleaned = re.sub(r"[^\w\s\:]", " ", text.lower())
        tokens = [t for t in cleaned.split() if t and t not in STOPWORDS]

        expanded_tokens: List[str] = list(tokens)
        # Add bigrams
        for i in range(len(tokens) - 1):
            expanded_tokens.append(f"{tokens[i]}_{tokens[i+1]}")

        # Add synonyms and subwords for domain tokens
        for token in tokens:
            if token in SYNONYMS:
                expanded_tokens.extend(SYNONYMS[token])
            # Character n-grams for root-word matching (e.g. "recover", "recovering", "recovery")
            if len(token) >= 5:
                for n in (4, 5):
                    for j in range(len(token) - n + 1):
                        expanded_tokens.append(f"ng:{token[j:j+n]}")

        return expanded_tokens

    def fit(self, documents: List[str]) -> None:
        self.total_docs = len(documents)
        self.doc_frequencies.clear()

        for doc in documents:
            unique_terms = set(self.tokenize(doc))
            for term in unique_terms:
                self.doc_frequencies[term] = self.doc_frequencies.get(term, 0) + 1

    def transform(self, text: str) -> Dict[str, float]:
        tokens = self.tokenize(text)
        if not tokens:
            return {}

        term_counts: Dict[str, int] = {}
        for t in tokens:
            term_counts[t] = term_counts.get(t, 0) + 1

        vector: Dict[str, float] = {}
        norm_sq = 0.0

        for term, count in term_counts.items():
            tf = 1.0 + math.log(count)
            df = self.doc_frequencies.get(term, 1)
            idf = math.log((self.total_docs + 1.0) / (df + 1.0)) + 1.0
            weight = tf * idf
            vector[term] = weight
            norm_sq += weight * weight

        # L2-normalize
        if norm_sq > 0:
            norm = math.sqrt(norm_sq)
            for term in vector:
                vector[term] /= norm

        return vector


# ── In-Memory Vector Store ────────────────────────────────────────────────────

class InMemoryVectorStore:
    """In-memory cosine similarity vector store for PolicyChunk objects."""

    def __init__(self) -> None:
        self.chunks: List[PolicyChunk] = []
        self.vectorizer = SemanticVectorizer()

    def add_chunks(self, chunks: List[PolicyChunk]) -> None:
        self.chunks.extend(chunks)
        # Re-fit vectorizer over all chunk texts
        corpus = [f"{c.policy_title} {c.section_title} {c.content}" for c in self.chunks]
        self.vectorizer.fit(corpus)
        # Compute and store normalized embeddings
        for chunk, text in zip(self.chunks, corpus):
            chunk.embedding = self.vectorizer.transform(text)

    @staticmethod
    def cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
        """Compute cosine similarity between two normalized sparse vectors."""
        if not vec_a or not vec_b:
            return 0.0
        # Iterate over the smaller vector
        if len(vec_a) > len(vec_b):
            vec_a, vec_b = vec_b, vec_a
        return sum(val * vec_b.get(term, 0.0) for term, val in vec_a.items())

    def search(self, query: str, k: int = 2) -> List[Tuple[PolicyChunk, float]]:
        query_vec = self.vectorizer.transform(query)
        if not query_vec:
            return []

        scored: List[Tuple[PolicyChunk, float]] = []
        for chunk in self.chunks:
            score = self.cosine_similarity(query_vec, chunk.embedding)
            if score > 0:
                scored.append((chunk, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]


# ── Document Loader & Chunker ─────────────────────────────────────────────────

def find_policies_dir() -> Path:
    """Resolve directory containing policy markdown files."""
    cwd = Path.cwd()
    script_dir = Path(__file__).resolve().parent

    candidates = [
        cwd / "policies",
        cwd / "backend" / "policies",
        cwd / "recoup" / "backend" / "policies",
        cwd / "recoup" / "policies",
        script_dir.parent.parent / "policies",
        script_dir.parent.parent.parent / "policies",
        script_dir / "policies",
    ]

    for candidate in candidates:
        if candidate.exists() and any(candidate.glob("*.md")):
            return candidate

    return cwd / "policies"


def chunk_markdown_file(file_path: Path) -> List[PolicyChunk]:
    """Parse and chunk a markdown policy file into section-level PolicyChunks."""
    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    policy_title = file_path.stem.replace("_", " ").title()
    chunks: List[PolicyChunk] = []

    current_section = "Overview"
    current_lines: List[str] = []
    chunk_index = 0

    for line in lines:
        if line.startswith("# "):
            policy_title = line.lstrip("# ").strip()
        elif line.startswith("## "):
            if current_lines:
                content = "\n".join(current_lines).strip()
                if content:
                    chunk_index += 1
                    chunks.append(
                        PolicyChunk(
                            chunk_id=f"{file_path.stem}_{chunk_index}",
                            policy_title=policy_title,
                            section_title=current_section,
                            content=content,
                            file_name=file_path.name,
                            metadata={"file_path": str(file_path), "section": current_section},
                        )
                    )
                current_lines = []
            current_section = line.lstrip("## ").strip()
        else:
            current_lines.append(line)

    if current_lines:
        content = "\n".join(current_lines).strip()
        if content:
            chunk_index += 1
            chunks.append(
                PolicyChunk(
                    chunk_id=f"{file_path.stem}_{chunk_index}",
                    policy_title=policy_title,
                    section_title=current_section,
                    content=content,
                    file_name=file_path.name,
                    metadata={"file_path": str(file_path), "section": current_section},
                )
            )

    return chunks


def load_all_policies(policies_dir: Optional[Path | str] = None) -> InMemoryVectorStore:
    """Load and index all policy documents into an InMemoryVectorStore."""
    if policies_dir is None:
        p_dir = find_policies_dir()
    else:
        p_dir = Path(policies_dir)

    vector_store = InMemoryVectorStore()
    all_chunks: List[PolicyChunk] = []

    if p_dir.exists():
        for md_file in sorted(p_dir.glob("*.md")):
            chunks = chunk_markdown_file(md_file)
            all_chunks.extend(chunks)

    vector_store.add_chunks(all_chunks)
    return vector_store


# ── Global Singleton & Public API ─────────────────────────────────────────────

_GLOBAL_VECTOR_STORE: Optional[InMemoryVectorStore] = None


def get_vector_store() -> InMemoryVectorStore:
    global _GLOBAL_VECTOR_STORE
    if _GLOBAL_VECTOR_STORE is None:
        _GLOBAL_VECTOR_STORE = load_all_policies()
    return _GLOBAL_VECTOR_STORE


def retrieve_policy(query: str, k: int = 2) -> List[Dict[str, Any]]:
    """
    Public retrieval interface.
    Retrieves the top-k most relevant policy chunks for a given natural language query.

    Args:
        query: User or agent question / scenario string.
        k: Number of relevant policy chunks to return (default: 2).

    Returns:
        List of dictionaries with keys: chunk_id, policy_title, section_title,
        content, score, file_name, metadata.
    """
    store = get_vector_store()
    results = store.search(query, k=k)
    return [chunk.to_dict(score=score) for chunk, score in results]


class Retriever:
    """
    Retriever class for dependency injection and FastAPI route integration.
    """

    def __init__(self, policies_dir: Optional[Path | str] = None) -> None:
        self.store = load_all_policies(policies_dir) if policies_dir else get_vector_store()

    async def search(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """Async interface for agentic reasoning and FastAPI services."""
        results = self.store.search(query, k=top_k)
        return [chunk.to_dict(score=score) for chunk, score in results]

    def retrieve(self, query: str, k: int = 2) -> List[Dict[str, Any]]:
        """Synchronous wrapper."""
        return retrieve_policy(query, k=k)
