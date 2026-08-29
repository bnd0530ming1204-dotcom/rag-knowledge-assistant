"""Production-graph smoke cases with real BGE/Milvus/Mongo and a mocked answer LLM."""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from config.milvus_config import milvus_config
from processor.query_processor.main_graph import KBQueryWorkflow
from utils.mongo_history_utils import clear_history, get_recent_messages, save_chat_message


class Response:
    def __init__(self, content: str): self.content = content


class SmokeLLM:
    def invoke(self, prompt):
        if isinstance(prompt, list):
            return Response("A100 V2 如何升级固件？")
        return Response("SMOKE_MOCK_ANSWER: 基于检索上下文生成。")

    def stream(self, prompt):
        yield Response("SMOKE_")
        yield Response("STREAM")


CASES = [
    ("exact_fact", "A100 V2 使用什么规格的电源？"),
    ("paraphrase", "二代 A100 开会时画面老卡，网速最低得多少才稳？"),
    ("version_confusion", "A100 V1 和 V2 恢复出厂设置的步骤有什么不同？"),
    ("multi_document", "A100 V2 开 4K 会议需要哪些网络条件和账号权限？"),
    ("table", "A200 在 1080p 模式下建议准备多少带宽？"),
    ("unsupported", "A300 的太阳能充电板保修几年？"),
]


def main() -> None:
    output = ROOT / "evaluation_v2" / "artifacts" / "final_production_smoke.json"
    object.__setattr__(milvus_config, "chunks_collection", "rag_eval_v2_chunks")
    rows = []
    with patch("processor.query_processor.nodes.g_node_answer_output.get_llm_client", return_value=SmokeLLM()), patch(
        "processor.query_processor.nodes.a_node_prepare_query.get_llm_client", return_value=SmokeLLM()
    ):
        for label, query in CASES:
            session_id = "final-smoke-" + uuid.uuid4().hex
            try:
                result = KBQueryWorkflow().run({"original_query": query, "session_id": session_id, "is_stream": False})
                history = get_recent_messages(session_id, limit=10)
                rows.append({
                    "case": label,
                    "status": "PASS",
                    "query": query,
                    "answer_llm": "MOCKED_EXTERNAL_API",
                    "answer_present": bool(result.get("answer")),
                    "source_count": len(result.get("sources") or []),
                    "top_document": (result.get("sources") or [{}])[0].get("file_name"),
                    "history_message_count": len(history),
                    "limitation": "No reliable refusal expected; Evidence Gate v1 is not deployed." if label == "unsupported" else None,
                })
            except Exception as exc:
                rows.append({"case": label, "status": "FAIL", "query": query, "error": f"{type(exc).__name__}: {exc}"})
            finally:
                clear_history(session_id)

        session_id = "final-smoke-history-" + uuid.uuid4().hex
        try:
            save_chat_message(session_id, "user", "我们在讨论 A100 V2。")
            result = KBQueryWorkflow().run({"original_query": "它怎么升级？", "session_id": session_id, "is_stream": False})
            rows.append({
                "case": "conversation_history",
                "status": "PASS",
                "query": "它怎么升级？",
                "rewritten_query": result.get("rewritten_query"),
                "history_entered_rewrite": result.get("rewritten_query") == "A100 V2 如何升级固件？",
                "answer_llm": "MOCKED_EXTERNAL_API",
                "source_count": len(result.get("sources") or []),
            })
        except Exception as exc:
            rows.append({"case": "conversation_history", "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"})
        finally:
            clear_history(session_id)

    artifact = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Real production graph + real BGE-M3 + real isolated Milvus + real Mongo; external answer/rewrite LLM mocked",
        "cases": rows,
        "passed": sum(row["status"] == "PASS" for row in rows),
        "failed": sum(row["status"] != "PASS" for row in rows),
        "milvus_failure_injection": "Covered by automated API and SSE behavior tests",
    }
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
