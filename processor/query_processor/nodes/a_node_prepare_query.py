import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

from langchain_core.messages import HumanMessage, SystemMessage

from config.settings import get_settings
from processor.query_processor.base import NodeBase
from processor.query_processor.state import QueryGraphState
from tool.logger import logger
from utils.llm_utils import get_llm_client
from utils.mongo_history_utils import get_recent_messages, save_chat_message
from utils.observability import add_fallback, update_trace
from utils.rewrite_decision import decide_rewrite


class NodePrepareQuery(NodeBase):
    """Load history and rewrite the current question for retrieval."""

    name = "node_prepare_query"

    def process(self, state: QueryGraphState) -> QueryGraphState:
        session_id = state.get("session_id")
        original_query = (state.get("original_query") or "").strip()
        if not session_id:
            raise ValueError("session_id is required")
        if not original_query:
            raise ValueError("query is required")

        request_id = state.get("request_id", session_id)
        try:
            history = get_recent_messages(session_id, limit=10)
        except Exception:
            history = []
            add_fallback(request_id, "history_read_failure_stateless")
        try:
            message_id = save_chat_message(session_id, "user", original_query)
        except Exception:
            message_id = ""
            add_fallback(request_id, "history_write_failure")
        history_text = "\n".join(
            f"{message.get('role', '')}: {message.get('text', '')}"
            for message in history
        )

        settings = get_settings()
        rewritten_query = original_query
        try:
            decision = decide_rewrite(original_query, history, settings.rewrite_decision_mode)
        except Exception:
            # A decision failure must not suppress a history-dependent rewrite.
            decision = decide_rewrite(original_query, history, "history")
            add_fallback(request_id, "rewrite_decision_failure_history_fallback")
        rewrite_required = bool(settings.enable_query_rewrite and decision.required)
        rewrite_success = False
        rewrite_fallback = False
        rewrite_started = time.perf_counter()
        if rewrite_required:
            try:
                messages = [SystemMessage(content=(
                    "你是知识库检索问题改写助手。结合历史对话，把当前问题改写成"
                    "语义完整、可独立检索的一句话。只输出改写后的问题，不要回答。"
                )), HumanMessage(content=f"历史对话：\n{history_text}\n\n当前问题：{original_query}")]
                executor = ThreadPoolExecutor(max_workers=1)
                future = executor.submit(get_llm_client().invoke, messages)
                try:
                    response = future.result(timeout=settings.query_rewrite_timeout)
                except FutureTimeout as exc:
                    future.cancel()
                    raise TimeoutError("query rewrite timed out") from exc
                finally:
                    executor.shutdown(wait=False, cancel_futures=True)
                candidate = (response.content or "").strip()
                if candidate:
                    rewritten_query = candidate
                    rewrite_success = True
                else:
                    rewrite_fallback = True
                    add_fallback(request_id, "rewrite_empty_original_query")
            except Exception as exc:
                logger.warning(f"问题改写失败，使用原始问题继续检索: {exc}")
                rewrite_fallback = True
                add_fallback(request_id, "rewrite_failure_original_query")

        update_trace(
            request_id,
            history_count=len(history),
            rewrite_required=rewrite_required,
            rewrite_decision="REWRITE" if rewrite_required else "NO_REWRITE",
            rewrite_reason=decision.reason if settings.enable_query_rewrite else "rewrite_disabled",
            rewrite_success=rewrite_success,
            rewrite_query=rewritten_query,
            rewrite_fallback=rewrite_fallback,
            rewrite_latency_ms=round((time.perf_counter() - rewrite_started) * 1000, 3) if rewrite_required else 0.0,
        )

        return {
            "history": history,
            "message_id": message_id,
            "rewritten_query": rewritten_query,
            "item_names": [],
        }
