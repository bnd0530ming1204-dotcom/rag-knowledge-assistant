import asyncio
import json
import unittest
import uuid
from unittest.mock import MagicMock, patch

from processor.query_processor.main_graph import KBQueryWorkflow
from processor.query_processor.nodes.a_node_prepare_query import NodePrepareQuery
from processor.query_processor.nodes.b_node_search_embedding import NodeSearchEmbedding
from utils.retrieval_errors import EmbeddingUnavailable, VectorDatabaseUnavailable
from utils.sse_utils import SSEEvent, create_sse_queue, sse_generator


def hit(chunk_id="c1", score=.8):
    return {"distance": score, "entity": {"chunk_id": chunk_id, "content": "evidence", "title": "T", "file_title": "D"}}


class RetrievalUnitTests(unittest.TestCase):
    def test_default_graph_contains_only_prepare_search_answer(self):
        graph = KBQueryWorkflow().workflow
        self.assertEqual(set(graph.nodes), {"node_prepare_query", "node_search_embedding", "node_answer_output"})

    @patch("processor.query_processor.nodes.b_node_search_embedding.hybrid_search")
    @patch("processor.query_processor.nodes.b_node_search_embedding.get_milvus_client")
    @patch("processor.query_processor.nodes.b_node_search_embedding.generate_embeddings")
    def test_hybrid_08_02_budget10_final_top5(self, embed, get_client, search):
        embed.return_value = {"dense": [[.1]], "sparse": [{1: .2}]}
        search.return_value = [[hit(str(i), 1-i/100) for i in range(10)]]
        result = NodeSearchEmbedding().process({"rewritten_query": "q"})
        self.assertEqual(search.call_args.kwargs["ranker_weights"], (.8, .2))
        self.assertEqual(search.call_args.kwargs["limit"], 10)
        self.assertEqual(len(result["reranked_docs"]), 5)
        get_client.return_value.load_collection.assert_called_once()

    @patch("processor.query_processor.nodes.b_node_search_embedding.generate_embeddings", side_effect=RuntimeError("secret-key-value"))
    def test_embedding_failure_is_sanitized(self, _):
        with self.assertRaisesRegex(EmbeddingUnavailable, "Query embedding is unavailable"):
            NodeSearchEmbedding().process({"rewritten_query": "q"})

    @patch("processor.query_processor.nodes.b_node_search_embedding.get_milvus_client")
    @patch("processor.query_processor.nodes.b_node_search_embedding.generate_embeddings")
    def test_milvus_exception_is_not_empty_result(self, embed, get_client):
        embed.return_value = {"dense": [[.1]], "sparse": [{1: .2}]}
        get_client.side_effect = RuntimeError("internal host and password")
        with self.assertRaisesRegex(VectorDatabaseUnavailable, "Vector database is unavailable"):
            NodeSearchEmbedding().process({"rewritten_query": "q"})

    @patch("processor.query_processor.nodes.b_node_search_embedding.hybrid_search", return_value=[[]])
    @patch("processor.query_processor.nodes.b_node_search_embedding.get_milvus_client")
    @patch("processor.query_processor.nodes.b_node_search_embedding.generate_embeddings")
    def test_real_empty_result_is_normal(self, embed, _, __):
        embed.return_value = {"dense": [[.1]], "sparse": [{1: .2}]}
        result = NodeSearchEmbedding().process({"rewritten_query": "q"})
        self.assertEqual(result["reranked_docs"], [])


class RewriteAndHistoryTests(unittest.TestCase):
    @patch("processor.query_processor.nodes.a_node_prepare_query.save_chat_message", return_value="m1")
    @patch("processor.query_processor.nodes.a_node_prepare_query.get_recent_messages", return_value=[])
    def test_no_history_uses_original(self, _, __):
        result = NodePrepareQuery().process({"session_id": "s", "original_query": "原问题"})
        self.assertEqual(result["rewritten_query"], "原问题")

    @patch("processor.query_processor.nodes.a_node_prepare_query.get_llm_client", side_effect=RuntimeError("offline"))
    @patch("processor.query_processor.nodes.a_node_prepare_query.save_chat_message", return_value="m1")
    @patch("processor.query_processor.nodes.a_node_prepare_query.get_recent_messages", return_value=[{"role": "user", "text": "A100 V2"}])
    def test_rewrite_failure_falls_back_original(self, _, __, ___):
        result = NodePrepareQuery().process({"session_id": "s", "original_query": "它怎么升级"})
        self.assertEqual(result["rewritten_query"], "它怎么升级")
        self.assertEqual(len(result["history"]), 1)

    @patch("processor.query_processor.nodes.a_node_prepare_query.get_llm_client")
    @patch("processor.query_processor.nodes.a_node_prepare_query.save_chat_message", return_value="m1")
    @patch("processor.query_processor.nodes.a_node_prepare_query.get_recent_messages", return_value=[{"role": "user", "text": "A100 V2"}])
    def test_history_enters_rewrite(self, _, __, llm):
        llm.return_value.invoke.return_value.content = "A100 V2 如何升级"
        result = NodePrepareQuery().process({"session_id": "s", "original_query": "它怎么升级"})
        self.assertEqual(result["rewritten_query"], "A100 V2 如何升级")
        self.assertIn("A100 V2", llm.return_value.invoke.call_args.args[0][1].content)


class SSEBehaviorTests(unittest.TestCase):
    def test_delta_final_and_error_termination(self):
        class Request:
            async def is_disconnected(self): return False
        async def collect(events):
            sid = uuid.uuid4().hex; q = create_sse_queue(sid)
            for event, data in events: q.put({"event": event, "data": data})
            output=[]
            async for item in sse_generator(sid, Request()): output.append(item)
            return "".join(output)
        normal=asyncio.run(collect([(SSEEvent.DELTA,{"delta":"a"}),(SSEEvent.FINAL,{"answer":"a","sources":[]}),(SSEEvent.CLOSE,{})]))
        self.assertIn("event: delta", normal); self.assertIn("event: final", normal)
        failed=asyncio.run(collect([(SSEEvent.ERROR,{"code":"VECTOR_DATABASE_UNAVAILABLE"}),(SSEEvent.CLOSE,{})]))
        self.assertIn("event: error", failed); self.assertIn("VECTOR_DATABASE_UNAVAILABLE", failed)


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from web.api.query_service import app
        cls.client=TestClient(app)

    @patch("web.api.query_service.get_task_result", return_value="answer")
    @patch("web.api.query_service.run_query_graph", return_value={"sources":[{"chunk_id":"c1"}],"image_urls":[]})
    def test_chat_success(self, *_):
        response=self.client.post('/chat',json={"query":"q","session_id":"s","is_stream":False})
        self.assertEqual(response.status_code,200); self.assertEqual(response.json()["sources"][0]["chunk_id"],"c1")

    def test_invalid_request(self):
        self.assertEqual(self.client.post('/chat',json={"query":"q"}).status_code,422)

    @patch("web.api.query_service.run_query_graph", side_effect=VectorDatabaseUnavailable("sensitive"))
    def test_retrieval_failure_is_structured_503(self, _):
        response=self.client.post('/chat',json={"query":"q","session_id":"s"})
        self.assertEqual(response.status_code,503); self.assertEqual(response.json()['detail']['code'],'VECTOR_DATABASE_UNAVAILABLE'); self.assertNotIn('sensitive',response.text)

if __name__ == "__main__": unittest.main()
