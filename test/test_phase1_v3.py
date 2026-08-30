import asyncio
import os
import queue
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from config.settings import AppSettings
from processor.query_processor.nodes.a_node_prepare_query import NodePrepareQuery
from processor.query_processor.nodes.g_node_answer_output import NodeAnswerOutput
from utils.context_builder import build_fixed_context
from utils.metadata_utils import normalize_chunk_metadata
from utils.observability import create_trace, finish_trace, get_trace, update_trace
from utils.retrieval_errors import GenerationFailed, GenerationTimeout
from utils.sse_utils import SSEEvent, create_sse_queue, get_sse_queue, sse_generator


class Response:
    def __init__(self, content): self.content = content


def settings(**overrides):
    base = dict(max_context_tokens=3000, final_context_top_k=5, llm_timeout=.2,
                query_rewrite_timeout=.2, enable_query_rewrite=True,
                context_selector_mode="fixed", min_contexts=1, max_contexts=5,
                dynamic_score_gap=.25, dynamic_min_score=None)
    base.update(overrides)
    return SimpleNamespace(**base)


class SettingsAndMetadataTests(unittest.TestCase):
    def test_settings_override(self):
        with patch.dict(os.environ, {"HYBRID_CANDIDATE_TOP_N": "12", "MAX_CONTEXT_TOKENS": "2048"}):
            value = AppSettings(_env_file=None)
        self.assertEqual(value.hybrid_candidate_top_n, 12)
        self.assertEqual(value.max_context_tokens, 2048)

    def test_metadata_normalization_and_no_fake_page(self):
        value = normalize_chunk_metadata({"file_title": "manual", "title": "## Setup", "parent_title": "# Root", "chunk_id": 7, "content": "x"})
        self.assertEqual(value["document_name"], "manual")
        self.assertEqual(value["section_title"], "## Setup")
        self.assertEqual(value["chunk_id"], "7")
        self.assertNotIn("page", value)

    def test_context_dedup_parent_and_token_budget(self):
        docs = [
            {"chunk_id": "1", "file_title": "d", "title": "a", "parent_title": "p", "content": "甲" * 20},
            {"chunk_id": "1", "file_title": "d", "title": "a2", "parent_title": "p", "content": "different"},
            {"chunk_id": "2", "file_title": "d", "title": "b", "parent_title": "p", "content": "甲" * 20},
            {"chunk_id": "3", "file_title": "d", "title": "c", "parent_title": "p", "content": "乙" * 20},
            {"chunk_id": "4", "file_title": "d", "title": "d", "parent_title": "p", "content": "丙" * 20},
        ]
        result = build_fixed_context(docs, max_tokens=200, max_contexts=5, max_per_parent=2)
        self.assertEqual([x["chunk_id"] for x in result.documents], ["1", "3"])
        self.assertLessEqual(result.token_count, 200)
        self.assertEqual(result.token_count_method, "approximate_cjk_plus_wordpiece")

    def test_parent_title_enters_context(self):
        result = build_fixed_context([{"chunk_id": "1", "file_title": "d", "title": "s", "parent_title": "REAL_PARENT", "content": "body"}], 100, 5)
        self.assertIn("REAL_PARENT", result.text)


class RewriteAndHistoryFallbackTests(unittest.TestCase):
    def state(self): return {"request_id": "r", "session_id": "s", "original_query": "它多久", "is_stream": False}

    @patch("processor.query_processor.nodes.a_node_prepare_query.save_chat_message", return_value="m")
    @patch("processor.query_processor.nodes.a_node_prepare_query.get_recent_messages", return_value=[{"role": "user", "text": "设备"}])
    @patch("processor.query_processor.nodes.a_node_prepare_query.get_llm_client")
    @patch("processor.query_processor.nodes.a_node_prepare_query.get_settings", return_value=settings(query_rewrite_timeout=.01))
    def test_rewrite_timeout_fallback(self, _, llm, *__):
        llm.return_value.invoke.side_effect = lambda _: (time.sleep(.05), Response("late"))[1]
        self.assertEqual(NodePrepareQuery().process(self.state())["rewritten_query"], "它多久")

    @patch("processor.query_processor.nodes.a_node_prepare_query.save_chat_message", return_value="m")
    @patch("processor.query_processor.nodes.a_node_prepare_query.get_recent_messages", return_value=[{"role": "user", "text": "设备"}])
    @patch("processor.query_processor.nodes.a_node_prepare_query.get_llm_client", side_effect=RuntimeError("down"))
    def test_rewrite_exception_fallback(self, *_):
        self.assertEqual(NodePrepareQuery().process(self.state())["rewritten_query"], "它多久")

    @patch("processor.query_processor.nodes.a_node_prepare_query.save_chat_message", side_effect=RuntimeError("write"))
    @patch("processor.query_processor.nodes.a_node_prepare_query.get_recent_messages", side_effect=RuntimeError("read"))
    def test_mongo_read_failure_is_stateless_and_write_failure_is_recoverable(self, *_):
        create_trace("r", "s", "它多久", .8, .2)
        result = NodePrepareQuery().process(self.state())
        self.assertEqual(result["history"], [])
        self.assertIn("history_read_failure_stateless", get_trace("r").fallbacks)
        self.assertIn("history_write_failure", get_trace("r").fallbacks)


class GenerationStateTests(unittest.TestCase):
    def base(self, request_id):
        create_trace(request_id, "s", "q", .8, .2)
        create_sse_queue(request_id)
        return {"request_id": request_id, "session_id": "s", "original_query": "q", "rewritten_query": "q",
                "history": [], "item_names": [], "reranked_docs": [{"chunk_id": "1", "file_title": "d", "title": "t", "parent_title": "p", "content": "evidence"}], "is_stream": True}

    @patch("processor.query_processor.nodes.g_node_answer_output.save_chat_message")
    @patch("processor.query_processor.nodes.g_node_answer_output.get_settings", return_value=settings())
    @patch("processor.query_processor.nodes.g_node_answer_output.get_llm_client")
    def test_stream_success_delta_final_close_and_history(self, llm, _, save):
        llm.return_value.stream.return_value = iter([Response("a"), Response("b")])
        NodeAnswerOutput().process(self.base("success"))
        events=[]; q=get_sse_queue("success")
        while not q.empty(): events.append(q.get()["event"])
        self.assertEqual(events, [SSEEvent.DELTA, SSEEvent.DELTA, SSEEvent.FINAL, SSEEvent.CLOSE])
        save.assert_called_once()

    @patch("processor.query_processor.nodes.g_node_answer_output.save_chat_message", side_effect=RuntimeError("mongo"))
    @patch("processor.query_processor.nodes.g_node_answer_output.get_settings", return_value=settings())
    @patch("processor.query_processor.nodes.g_node_answer_output.get_llm_client")
    def test_mongo_write_failure_answer_still_completes(self, llm, *_):
        llm.return_value.stream.return_value = iter([Response("answer")])
        state = NodeAnswerOutput().process(self.base("mongo-write"))
        self.assertEqual(state["answer"], "answer")
        self.assertEqual(state["terminal_status"], "COMPLETED")
        self.assertIn("history_write_failure", get_trace("mongo-write").fallbacks)

    @patch("processor.query_processor.nodes.g_node_answer_output.save_chat_message")
    @patch("processor.query_processor.nodes.g_node_answer_output.get_settings", return_value=settings())
    @patch("processor.query_processor.nodes.g_node_answer_output.get_llm_client")
    def test_stream_exception_error_close_no_final_no_history(self, llm, _, save):
        def broken(_):
            yield Response("partial")
            raise RuntimeError("boom")
        llm.return_value.stream.side_effect = broken
        with self.assertRaises(GenerationFailed): NodeAnswerOutput().process(self.base("failed"))
        events=[]; q=get_sse_queue("failed")
        while not q.empty(): events.append(q.get()["event"])
        self.assertEqual(events, [SSEEvent.DELTA, SSEEvent.ERROR, SSEEvent.CLOSE])
        save.assert_not_called()

    @patch("processor.query_processor.nodes.g_node_answer_output.get_settings", return_value=settings(llm_timeout=.01))
    @patch("processor.query_processor.nodes.g_node_answer_output.get_llm_client")
    def test_llm_timeout(self, llm, _):
        def slow(_):
            time.sleep(.1)
            yield Response("late")
        llm.return_value.stream.side_effect = slow
        with self.assertRaises(GenerationTimeout): NodeAnswerOutput().process(self.base("timeout"))
        self.assertEqual(get_trace("timeout").terminal_status, "TIMEOUT")

    def test_client_disconnect_cleanup(self):
        class Request:
            async def is_disconnected(self): return True
        async def consume():
            create_sse_queue("disconnect")
            return [x async for x in sse_generator("disconnect", Request())]
        asyncio.run(consume())
        self.assertIsNone(get_sse_queue("disconnect"))


class TraceTests(unittest.TestCase):
    def test_trace_success_fallback_and_fatal(self):
        create_trace("trace", "s", "q", .8, .2)
        update_trace("trace", candidate_count=10)
        finish_trace("trace", "COMPLETED")
        self.assertEqual(get_trace("trace").terminal_status, "COMPLETED")
        create_trace("fatal", "s", "q", .8, .2)
        finish_trace("fatal", "FAILED", "VECTOR_DATABASE_UNAVAILABLE")
        self.assertEqual(get_trace("fatal").error_type, "VECTOR_DATABASE_UNAVAILABLE")

    def test_unique_request_ids_same_session(self):
        from fastapi.testclient import TestClient
        from web.api.query_service import app
        with patch("web.api.query_service.run_query_graph", return_value={}), patch(
            "web.api.query_service.get_task_result", return_value="answer"
        ):
            client = TestClient(app)
            first = client.post("/chat", json={"query": "q1", "session_id": "same"}).json()
            second = client.post("/chat", json={"query": "q2", "session_id": "same"}).json()
        self.assertNotEqual(first["request_id"], second["request_id"])
        self.assertEqual(first["session_id"], second["session_id"])


if __name__ == "__main__": unittest.main()
