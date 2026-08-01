from langchain_core.messages import HumanMessage, SystemMessage

from processor.query_processor.base import NodeBase
from processor.query_processor.state import QueryGraphState
from tool.logger import logger
from utils.llm_utils import get_llm_client
from utils.mongo_history_utils import get_recent_messages, save_chat_message


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

        history = get_recent_messages(session_id, limit=10)
        message_id = save_chat_message(session_id, "user", original_query)
        history_text = "\n".join(
            f"{message.get('role', '')}: {message.get('text', '')}"
            for message in history
        )

        rewritten_query = original_query
        if history_text:
            try:
                response = get_llm_client().invoke([
                    SystemMessage(content=(
                        "你是知识库检索问题改写助手。结合历史对话，把当前问题改写成"
                        "语义完整、可独立检索的一句话。只输出改写后的问题，不要回答。"
                    )),
                    HumanMessage(content=f"历史对话：\n{history_text}\n\n当前问题：{original_query}"),
                ])
                candidate = (response.content or "").strip()
                if candidate:
                    rewritten_query = candidate
            except Exception as exc:
                logger.warning(f"问题改写失败，使用原始问题继续检索: {exc}")

        return {
            "history": history,
            "message_id": message_id,
            "rewritten_query": rewritten_query,
            "item_names": [],
        }
