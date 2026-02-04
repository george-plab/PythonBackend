import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Tuple

import logging
import numpy as np

try:
    import faiss  # type: ignore
except Exception as exc:  # pragma: no cover - runtime error path
    faiss = None
    _FAISS_IMPORT_ERROR = exc

from services.llmsettings import LLMSettings

logger = logging.getLogger("rag")

_DEFAULT_TOP_K = int(os.getenv("TOP_K", "3"))
_RAG_DEBUG = os.getenv("RAG_DEBUG", "false").lower() == "true"


def _load_playbooks(playbooks_dir: str) -> List[Tuple[str, str]]:
    root = Path(playbooks_dir)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"playbooks_dir not found: {playbooks_dir}")
    items: List[Tuple[str, str]] = []
    for path in sorted(root.glob("*.md")):
        items.append((path.name, path.read_text(encoding="utf-8")))
    return items


def _hash_playbooks(items: List[Tuple[str, str]]) -> str:
    h = hashlib.sha256()
    for name, text in items:
        h.update(name.encode("utf-8"))
        h.update(b"\n")
        h.update(text.encode("utf-8"))
        h.update(b"\n---\n")
    return h.hexdigest()


def _chunk_text(text: str, chunk_size: int = 700, overlap: int = 120) -> List[str]:
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


def _embed_texts(client, model: str, texts: List[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    vectors: List[List[float]] = []
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        resp = client.embeddings.create(model=model, input=batch)
        for item in resp.data:
            vectors.append(item.embedding)
    arr = np.array(vectors, dtype=np.float32)
    return arr


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    if vectors.size == 0:
        return vectors
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


@dataclass
class RagIndex:
    index: Any
    chunks: List[Dict[str, Any]]
    model: str
    top_k_default: int
    manifest: Dict[str, Any]
    loaded_from_cache: bool

    def retrieve(self, client, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        
        logger.info("[RAG] retrieve() called")
        if not query:
            return []
        k = top_k if top_k is not None else self.top_k_default
        q = _embed_texts(client, self.model, [query])
        q = _l2_normalize(q)
        scores, indices = self.index.search(q, k)
        results: List[Dict[str, Any]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
            chunk = self.chunks[idx]
             
            results.append({
                "source": chunk["source"],
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],
                "score": float(score),
            })
        if _RAG_DEBUG:
            debug_items = ", ".join([f"{c['source']}:{c['score']:.4f}" for c in results])
            print(f"[RAG_DEBUG] top_k={k} {debug_items}")
        # if not results:
        #     logger.info("[RAG] No context retrieved (empty)")
        # else:
        #     logger.info(f"[RAG] Retrieved {len(results)} chunks")

        return results

    def status(self) -> Dict[str, Any]:
        return {
            "loaded_from_cache": self.loaded_from_cache,
            "embedding_model": self.model,
            "hash": self.manifest.get("hash"),
            "created_at": self.manifest.get("created_at"),
        }


class _SimpleIndex:
    def __init__(self, embeddings: np.ndarray) -> None:
        self.embeddings = embeddings

    def search(self, q: np.ndarray, k: int):
        if self.embeddings.size == 0:
            return np.zeros((1, 0), dtype=np.float32), np.zeros((1, 0), dtype=np.int64)
        scores = q @ self.embeddings.T
        idx = np.argsort(-scores, axis=1)[:, :k]
        top_scores = np.take_along_axis(scores, idx, axis=1)
        return top_scores, idx


class RagFaissService:
    def __init__(
        self,
        llm: LLMSettings,
        playbooks_dir: str = "playbooks",
        cache_dir: str = ".rag_cache",
        disable_faiss: bool = False,
    ) -> None:
        self.llm = llm
        self.playbooks_dir = playbooks_dir
        self.cache_dir = cache_dir
        self.disable_faiss = disable_faiss
        self._index: RagIndex | None = None

    def build_or_load(self) -> RagIndex:
        if faiss is None and not self.disable_faiss:
            raise RuntimeError(f"faiss not available: {_FAISS_IMPORT_ERROR}")

        client = self.llm.openai_client
        model = self.llm.embedding_model

        items = _load_playbooks(self.playbooks_dir)
        content_hash = _hash_playbooks(items)

        cache_root = Path(self.cache_dir)
        cache_root.mkdir(parents=True, exist_ok=True)

        manifest_path = cache_root / "manifest.json"
        chunks_path = cache_root / "chunks.json"
        embeds_path = cache_root / "embeddings.npy"
        index_path = cache_root / "faiss.index"

        if manifest_path.exists() and chunks_path.exists() and embeds_path.exists() and index_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest.get("hash") == content_hash and manifest.get("embedding_model") == model:
                    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
                    if self.disable_faiss:
                        embeddings = np.load(str(embeds_path))
                        index = _SimpleIndex(embeddings)
                    else:
                        index = faiss.read_index(str(index_path))
                    self._index = RagIndex(
                        index=index,
                        chunks=chunks,
                        model=model,
                        top_k_default=_DEFAULT_TOP_K,
                        manifest=manifest,
                        loaded_from_cache=True
                    )
                    return self._index
            except Exception:
                pass

        if client is None:
            raise RuntimeError("OPENAI_API_KEY missing for RAG embeddings")

        chunks: List[Dict[str, Any]] = []
        texts: List[str] = []
        for name, text in items:
            pb_id = Path(name).stem
            pb_chunks = _chunk_text(text)
            for idx, chunk in enumerate(pb_chunks):
                chunks.append({
                    "source": name,
                    "chunk_id": f"{pb_id}:{idx}",
                    "text": chunk,
                })
                texts.append(chunk)

        embeddings = _embed_texts(client, model, texts)
        embeddings = _l2_normalize(embeddings)

        if self.disable_faiss:
            index = _SimpleIndex(embeddings)
        else:
            dim = embeddings.shape[1] if embeddings.size else 0
            index = faiss.IndexFlatIP(dim)
            if embeddings.size:
                index.add(embeddings)

        chunks_path.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
        np.save(str(embeds_path), embeddings)
        if self.disable_faiss:
            index_path.write_text("disabled", encoding="utf-8")
        else:
            faiss.write_index(index, str(index_path))

        manifest = {
            "hash": content_hash,
            "embedding_model": model,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        self._index = RagIndex(
            index=index,
            chunks=chunks,
            model=model,
            top_k_default=_DEFAULT_TOP_K,
            manifest=manifest,
            loaded_from_cache=False
        )
        return self._index

    def retrieve(self, query: str, top_k: int = 3) -> str:
        if not query:
            return ""
        if self._index is None:
            raise RuntimeError("RAG index not initialized")
        client = self.llm.openai_client
        if client is None:
            return ""
        rag_chunks = self._index.retrieve(client, query, top_k=top_k)
        if not rag_chunks:
            return ""
        rag_context = "RAG_CONTEXT_START\n"
        for item in rag_chunks:
            rag_context += f"[source={item['source']} id={item['chunk_id']} score={item['score']:.4f}]\n"
            rag_context += item["text"] + "\n---\n"
        rag_context += "RAG_CONTEXT_END"
        return rag_context
