import os
from pathlib import Path
from typing import List, Dict, Any

_EMBED_MODEL = "text-embedding-3-small"

_INDEX: Dict[str, Any] = {
    "chunks": [],
    "vectors": [],
    "norms": [],
    "ready": False,
}


def load_playbooks(playbooks_dir: str = "playbooks") -> List[Dict[str, str]]:
    root = Path(playbooks_dir)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"playbooks_dir not found: {playbooks_dir}")

    items: List[Dict[str, str]] = []
    for path in sorted(root.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        items.append({
            "id": path.stem,
            "source": path.name,
            "text": text,
        })
    return items


def chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> List[str]:
    if not text:
        return []
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: List[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = end - overlap
    return chunks


def embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []

    from openai import OpenAI
    client = OpenAI()
    vectors: List[List[float]] = []
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        resp = client.embeddings.create(
            model=_EMBED_MODEL,
            input=batch
        )
        for item in resp.data:
            vectors.append(item.embedding)
    return vectors


def _vector_norm(vec: List[float]) -> float:
    return sum(x * x for x in vec) ** 0.5


def _cosine_similarity(a: List[float], b: List[float], norm_a: float, norm_b: float) -> float:
    if norm_a == 0 or norm_b == 0:
        return 0.0
    dot = 0.0
    for x, y in zip(a, b):
        dot += x * y
    return dot / (norm_a * norm_b)


def init_rag_index(playbooks_dir: str = "playbooks", chunk_size: int = 600, overlap: int = 100) -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing for RAG embeddings")

    playbooks = load_playbooks(playbooks_dir=playbooks_dir)

    chunks: List[Dict[str, Any]] = []
    texts: List[str] = []
    for pb in playbooks:
        pb_chunks = chunk_text(pb["text"], chunk_size=chunk_size, overlap=overlap)
        for idx, chunk in enumerate(pb_chunks):
            chunks.append({
                "source": pb["source"],
                "chunk_id": f"{pb['id']}:{idx}",
                "text": chunk,
            })
            texts.append(chunk)

    vectors = embed_texts(texts)
    norms = [_vector_norm(vec) for vec in vectors]

    _INDEX["chunks"] = chunks
    _INDEX["vectors"] = vectors
    _INDEX["norms"] = norms
    _INDEX["ready"] = True


def retrieve_playbook_chunks(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    if not _INDEX.get("ready"):
        raise RuntimeError("RAG index not initialized")
    if not query:
        return []

    query_vec = embed_texts([query])[0]
    query_norm = _vector_norm(query_vec)

    scored: List[Dict[str, Any]] = []
    for chunk, vec, norm in zip(_INDEX["chunks"], _INDEX["vectors"], _INDEX["norms"]):
        score = _cosine_similarity(query_vec, vec, query_norm, norm)
        scored.append({
            "source": chunk["source"],
            "chunk_id": chunk["chunk_id"],
            "text": chunk["text"],
            "score": score,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:max(1, top_k)]

    if os.getenv("RAG_DEBUG", "false").lower() == "true":
        debug_items = ", ".join([f"{c['source']}:{c['score']:.4f}" for c in top])
        print(f"[RAG_DEBUG] top_k={top_k} {debug_items}")

    return top


def build_rag_context(chunks: List[Dict[str, Any]]) -> str:
    if not chunks:
        return "RAG_CONTEXT_START\n(no playbook context)\nRAG_CONTEXT_END"

    parts = ["RAG_CONTEXT_START"]
    for item in chunks:
        parts.append(f"[source={item['source']} id={item['chunk_id']} score={item['score']:.4f}]")
        parts.append(item["text"])
        parts.append("---")
    parts.append("RAG_CONTEXT_END")
    return "\n".join(parts)


def retrieve_playbook_context(query: str, top_k: int = 3) -> str:
    chunks = retrieve_playbook_chunks(query=query, top_k=top_k)
    return build_rag_context(chunks)
