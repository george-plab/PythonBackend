import os
import tempfile

import pytest

from services.service_rag_faiss import RagFaissService


np = pytest.importorskip("numpy")


class FakeLLM:
    def __init__(self, openai_client):
        self.openai_client = openai_client
        self.embedding_model = "text-embedding-test"


def _fake_embed_texts(_client, _model, texts):
    vecs = []
    for t in texts:
        if "alpha" in t:
            vecs.append([1.0, 0.0])
        elif "beta" in t:
            vecs.append([0.0, 1.0])
        else:
            vecs.append([0.7, 0.7])
    return np.array(vecs, dtype=np.float32)


def test_retrieve_returns_empty_if_no_openai_client():
    llm = FakeLLM(openai_client=None)
    service = RagFaissService(llm, disable_faiss=True)
    service._index = object()

    assert service.retrieve("hola", top_k=1) == ""


def test_build_or_load_creates_cache_manifest(monkeypatch):
    llm = FakeLLM(openai_client=object())
    with tempfile.TemporaryDirectory() as tmp:
        playbooks_dir = os.path.join(tmp, "playbooks")
        cache_dir = os.path.join(tmp, "cache")
        os.makedirs(playbooks_dir, exist_ok=True)
        with open(os.path.join(playbooks_dir, "a.md"), "w", encoding="utf-8") as f:
            f.write("alpha content")

        monkeypatch.setattr("services.service_rag_faiss._embed_texts", _fake_embed_texts)
        service = RagFaissService(llm, playbooks_dir=playbooks_dir, cache_dir=cache_dir, disable_faiss=True)
        service.build_or_load()

        assert os.path.exists(os.path.join(cache_dir, "manifest.json"))
        assert os.path.exists(os.path.join(cache_dir, "chunks.json"))
        assert os.path.exists(os.path.join(cache_dir, "embeddings.npy"))
