import unittest
from unittest.mock import patch

from services import rag_playbooks


class TestRagPlaybooks(unittest.TestCase):
    def setUp(self):
        self._prev_index = dict(rag_playbooks._INDEX)

    def tearDown(self):
        rag_playbooks._INDEX = self._prev_index

    def test_chunk_text_overlap(self):
        text = "a" * 1200
        chunks = rag_playbooks.chunk_text(text, chunk_size=600, overlap=100)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len(chunks[0]), 600)
        self.assertEqual(len(chunks[1]), 600)
        self.assertTrue(chunks[0][-100:] == chunks[1][:100])

    def test_build_rag_context(self):
        chunks = [
            {"source": "a.md", "chunk_id": "a:0", "text": "hello", "score": 0.9},
            {"source": "b.md", "chunk_id": "b:1", "text": "world", "score": 0.8},
        ]
        context = rag_playbooks.build_rag_context(chunks)
        self.assertIn("RAG_CONTEXT_START", context)
        self.assertIn("RAG_CONTEXT_END", context)
        self.assertIn("[source=a.md id=a:0 score=0.9000]", context)

    def test_retrieve_playbook_chunks_ranking(self):
        rag_playbooks._INDEX = {
            "chunks": [
                {"source": "a.md", "chunk_id": "a:0", "text": "alpha"},
                {"source": "b.md", "chunk_id": "b:0", "text": "beta"},
            ],
            "vectors": [[1.0, 0.0], [0.0, 1.0]],
            "norms": [1.0, 1.0],
            "ready": True,
        }

        with patch("services.rag_playbooks.embed_texts", return_value=[[1.0, 0.0]]):
            results = rag_playbooks.retrieve_playbook_chunks("alpha", top_k=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "a.md")


if __name__ == "__main__":
    unittest.main()
