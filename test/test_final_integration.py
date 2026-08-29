import unittest
import uuid
from unittest.mock import patch

from processor.query_processor.nodes.b_node_search_embedding import NodeSearchEmbedding
from utils.mongo_history_utils import clear_history, get_recent_messages, save_chat_message


class RetrievalMilvusIntegrationTest(unittest.TestCase):
    @patch("processor.query_processor.nodes.b_node_search_embedding.milvus_config.chunks_collection", "rag_eval_v2_chunks")
    def test_real_embedding_milvus_retrieval_top5(self):
        result = NodeSearchEmbedding().process({"rewritten_query": "A100 V2 使用什么电源？"})
        self.assertEqual(len(result["reranked_docs"]), 5)
        self.assertTrue(all(doc.get("chunk_id") for doc in result["reranked_docs"]))
        self.assertTrue(any(doc.get("file_title") == "eval-a100-v2" for doc in result["reranked_docs"]))


class MongoHistoryIntegrationTest(unittest.TestCase):
    def test_write_then_read_history(self):
        session_id = "acceptance-" + uuid.uuid4().hex
        try:
            save_chat_message(session_id, "user", "history integration marker")
            messages = get_recent_messages(session_id, limit=5)
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0]["text"], "history integration marker")
        finally:
            clear_history(session_id)


if __name__ == "__main__": unittest.main()
