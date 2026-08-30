import re
import queue
import threading
import time
from typing import List, Dict, Tuple

from config.settings import get_settings
from processor.query_processor.prompt.answer_prompt import ANSWER_PROMPT

from processor.query_processor.base import NodeBase
from processor.query_processor.state import QueryGraphState
from utils.llm_utils import get_llm_client
from utils.mongo_history_utils import save_chat_message
from utils.sse_utils import push_to_session, SSEEvent, get_cancel_event
from utils.task_utils import set_task_result, add_done_task
from utils.context_builder import build_fixed_context, select_context
from utils.metadata_utils import normalize_chunk_metadata
from utils.observability import add_fallback, finish_trace, update_trace
from utils.retrieval_errors import GenerationFailed, GenerationTimeout


class NodeAnswerOutput(NodeBase):
    """
    节点功能: 答案输出
    流程: 检查已有答案 → 构建提示词 → LLM 生成 → 写入历史 → 发送结束事件
    """

    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_answer_output"

    def process(self, state: QueryGraphState) -> QueryGraphState:
        """
        1 判断state 中的answer是否已经存在，如果存在直接输出answer中的答案，注意判断是否需要流式输出需要则流式输出
        2 根据state中的问题、重新问题、历史对话、提问商品（item_names）、 重排内容 组织prompt 并调用llm 生成答案
        3 调用大模型输出答案 注意判断是否需要流式输出需要则流式输出
        4 把答案写入到mongodb的history中 利用utils/mongo_history_utils.py中的save_chat_message方法
        5 做最后一次push操作（主要是为了触发前端图片渲染)
             {
                "answer": "HAK 180 烫金机的操作面板位于...（大模型生成的纯文本）...",
                "status": "completed",
                "image_urls": [
                    "http://local-server/images/panel_view.jpg",
                    "http://local-server/images/button_detail.jpg"
                ]
              }
        """
        request_id = state.get("request_id", state.get("session_id"))
        answer_exists = self._step_1_check_answer(state)

        # # 阶段二  如果没有answer则 构建 Prompt
        if not answer_exists:
            prompt = self._step_2_construct_prompt(state)
            state["prompt"] = prompt

            # 阶段三：  如果没有answer则 调用大模型输出答案
            try:
                self._step_3_generate_response(state, prompt)
            except (GenerationFailed, GenerationTimeout) as exc:
                state["answer"] = ""
                if state.get("terminal_status") != "CANCELLED":
                    state["terminal_status"] = "TIMEOUT" if isinstance(exc, GenerationTimeout) else "FAILED"
                if state.get("is_stream") and state["terminal_status"] != "CANCELLED":
                    push_to_session(request_id, SSEEvent.ERROR, {"code": exc.code, "message": "Generation failed"})
                    push_to_session(request_id, SSEEvent.CLOSE, {})
                finish_trace(request_id, state["terminal_status"], exc.code)
                raise

        # 阶段四： 提取图片URL（用于历史记录和前端展示）
        used_context_docs = state.get("used_context_docs") or []
        image_urls = self._extract_images_from_docs(used_context_docs)
        state["image_urls"] = image_urls
        sources = self._extract_sources_from_docs(used_context_docs)
        state["sources"] = sources

        # 阶段五：把答案写入到mongodb的history中
        if state.get("answer") and state.get("terminal_status") not in {"FAILED", "TIMEOUT", "CANCELLED"}:
            print("---写入MongoDB历史记录---")
            self._step_4_write_history(state, image_urls=image_urls, sources=sources)

        # Terminal SSE ordering is delta* -> final/error -> close; do not interleave progress.
        add_done_task(request_id, self.name, False)

        # 阶段六: 流式输出结束，发送 final 事件 [最后兜底，确保图片都能争取渲染和结束]
        print(f"---发送 final 事件---图片为：{image_urls}")
        state["terminal_status"] = "COMPLETED"
        if state.get("is_stream"):
            push_to_session(
                request_id,
                SSEEvent.FINAL,
                {
                    "answer": state["answer"],
                    "status": "completed",
                    "image_urls": image_urls,  # 发送图片URL给前端
                    "sources": sources,
                    "request_id": request_id,
                    "context_count": state.get("context_count", 0),
                    "context_token_count": state.get("context_token_count", 0),
                }
            )
            push_to_session(request_id, SSEEvent.CLOSE, {})
        finish_trace(request_id, "COMPLETED")

        print("---node_answer_output 节点处理结束---")
        return state

    def _step_1_check_answer(self, state) -> bool:
        """
        阶段一：检查 state 中是否已有 answer。
        - 若已存在：按需推送流式 delta（用于 SSE），并返回 True
        - 若不存在：返回 False
        """
        answer = state.get("answer")
        is_stream = state.get("is_stream")
        if answer:
            if is_stream:
                print("---Step 1: 发现已有答案，执行流式推送---")
                push_to_session(state.get("request_id", state["session_id"]), SSEEvent.DELTA, {"delta": answer})
            else:
                set_task_result(state.get("request_id", state["session_id"]), "answer", answer)
            return True
        else:
            return False

    def _step_2_construct_prompt(self, state: QueryGraphState) -> str:

        """
        阶段二：构建 Prompt
        根据state中的问题、重新问题、历史对话、提问商品（item_names）、 重排内容 组装 LLM 提示词
        """
        # 1. 获取问题和商品名
        # 优先使用重写后的问题
        question = state.get("rewritten_query") or state.get("original_query", "")
        item_names = state.get("item_names") or []

        # 2. 格式化上下文文档
        settings = get_settings()
        context_result = select_context(
            state.get("reranked_docs") or [], settings.context_selector_mode,
            settings.max_context_tokens, settings.final_context_top_k,
            settings.min_contexts, settings.max_contexts,
            settings.dynamic_score_gap, settings.dynamic_min_score,
        )
        context_str, used_context_docs = context_result.text, context_result.documents
        state["used_context_docs"] = used_context_docs
        state["context_count"] = len(used_context_docs)
        state["context_token_count"] = context_result.token_count
        update_trace(state.get("request_id", state.get("session_id", "")),
                     selected_context_count=len(used_context_docs),
                     context_token_count=context_result.token_count,
                     context_token_count_method=context_result.token_count_method,
                     context_selector_mode=settings.context_selector_mode,
                     selection_reason=context_result.selection_reason)

        # 3. 格式化历史对话
        history_str, _ = self._format_chat_history(state.get("history") or [], settings.max_context_tokens * 4)

        # 4. 格式化 Item Names (提问商品)
        item_names_str = ", ".join(item_names) if item_names else "无指定商品"

        # 5. 组装提示词
        prompt = ANSWER_PROMPT.format(
            context=context_str or "无参考内容",
            history=history_str if history_str else "暂无历史对话",
            item_names=item_names_str,
            question=question,
        )
        print(f"组装后的提示词为：{prompt}")
        return prompt

    def _format_reranked_docs(self, reranked_docs: List[Dict], char_budget: int) -> Tuple[str, int, List[Dict]]:
        """Backward-compatible adapter; char_budget is treated as approximate tokens."""
        result = build_fixed_context(reranked_docs, char_budget, get_settings().final_context_top_k)
        return result.text, max(0, char_budget - result.token_count), result.documents

    def _format_chat_history(self, chat_history: List[Dict], char_budget: int) -> Tuple[str, int]:
        """格式化历史对话"""
        formatted_lines = []
        used_chars = 0

        role_label_map = {"user": "用户", "assistant": "助手"}

        for message in chat_history:
            role = message.get("role", "")
            text = message.get("text", "")
            if not text or role not in role_label_map:
                continue

            formatted_line = f"{role_label_map[role]}: {text}"
            used_chars += len(formatted_line) + 1

            if used_chars > char_budget:
                return "\n".join(formatted_lines), char_budget - used_chars

            formatted_lines.append(formatted_line)

        return "\n".join(formatted_lines), char_budget - used_chars

    def _step_3_generate_response(self, state: QueryGraphState, prompt: str) -> QueryGraphState:
        """
        阶段三：生成回答
        调用llm生成答案，支持流式输出
        """
        print("---Step 3: 开始生成回答 (LLM Generation)---")

        # 获取 LLM 客户端
        # 注意：这里我们使用统一的 get_llm_client 获取实例
        llm = get_llm_client()

        # 判断是否需要流式输出
        # 通常 state 中会注入 stream_queue 用于 SSE 推送
        request_id = state.get("request_id", state.get("session_id"))
        is_stream = state.get("is_stream")
        timeout = get_settings().llm_timeout
        started = time.perf_counter()

        if is_stream:
            print(f"模式: 流式输出 (Streaming), Request: {request_id}")
            final_text, output = "", queue.Queue()
            cancel_event = get_cancel_event(request_id)
            def consume():
                try:
                    for chunk in llm.stream(prompt):
                        if cancel_event.is_set():
                            break
                        output.put(("delta", getattr(chunk, "content", "") or ""))
                    output.put(("done", None))
                except Exception as exc:
                    output.put(("error", exc))
            threading.Thread(target=consume, daemon=True).start()
            deadline = time.perf_counter() + timeout
            while True:
                if cancel_event.is_set():
                    state["terminal_status"] = "CANCELLED"
                    update_trace(request_id, llm_latency_ms=round((time.perf_counter() - started) * 1000, 3))
                    finish_trace(request_id, "CANCELLED")
                    raise GenerationFailed("generation cancelled")
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    cancel_event.set()
                    update_trace(request_id, llm_latency_ms=round((time.perf_counter() - started) * 1000, 3))
                    raise GenerationTimeout("generation timed out")
                try:
                    kind, value = output.get(timeout=min(0.1, remaining))
                except queue.Empty:
                    continue
                if kind == "error":
                    update_trace(request_id, llm_latency_ms=round((time.perf_counter() - started) * 1000, 3))
                    raise GenerationFailed("generation failed") from value
                if kind == "done":
                    break
                if value:
                    final_text += value
                    push_to_session(request_id, SSEEvent.DELTA, {"delta": value})
            state["answer"] = final_text
        else:
            # 非流式直接调用
            print(f"模式: 非流式输出 (Blocking), Request: {request_id}")
            output = queue.Queue()
            threading.Thread(target=lambda: self._invoke_into_queue(llm, prompt, output), daemon=True).start()
            try:
                kind, response = output.get(timeout=timeout)
                if kind == "error":
                    raise response
                content = response.content
                state["answer"] = content
                set_task_result(request_id, "answer", content)
                print(f"生成回答完成，长度: {len(content)}")
            except queue.Empty as exc:
                update_trace(request_id, llm_latency_ms=round((time.perf_counter() - started) * 1000, 3))
                raise GenerationTimeout("generation timed out") from exc
            except Exception as exc:
                update_trace(request_id, llm_latency_ms=round((time.perf_counter() - started) * 1000, 3))
                raise GenerationFailed("generation failed") from exc

        update_trace(request_id, llm_latency_ms=round((time.perf_counter() - started) * 1000, 3))

        return state

    @staticmethod
    def _invoke_into_queue(llm, prompt, output):
        try:
            output.put(("ok", llm.invoke(prompt)))
        except Exception as exc:
            output.put(("error", exc))

    def _extract_images_from_docs(self, docs):
        """
        辅助方法：从文档列表中提取图片URL

        核心逻辑：
        1. 遍历所有相关文档（包括本地知识库切片和联网搜索结果）。
        2. 策略一：直接检查文档的 'url' 字段（常见于联网搜索结果）。
           - 验证后缀名是否为图片格式 (.jpg, .png 等)。
        3. 策略二：使用正则表达式扫描文档 'text' 正文内容（常见于本地 Markdown 文档）。
           - 匹配 Markdown 图片语法: ![alt text](image_url)。
        4. 对提取到的 URL 进行去重处理，返回唯一图片列表。

        :param docs: 文档列表，每个文档为字典格式
        :return: 图片 URL 字符串列表
        """
        images = []
        seen = set()  # 用于去重，避免同一张图片重复出现
        if not docs:
            return []
        # ---------------------------------------------------------
        # 正则表达式解释：r'!\[.*?\]\((.*?)\)'
        # 1. !\[   -> 匹配 Markdown 图片语法的开头 "![" (注意 [ 需要转义)
        # 2. .*?   -> 非贪婪匹配图片描述文本 (Alt Text)，即 [] 中间的内容
        # 3. \]    -> 匹配描述文本的结束符 "]"
        # 4. \(    -> 匹配 URL 部分的开始符 "("
        # 5. (.*?) -> 捕获组 (Group 1)：非贪婪匹配括号内的实际 URL 内容
        # 6. \)    -> 匹配 URL 部分的结束符 ")"
        # ( ... ) （不带反斜杠）：这就是 捕获组 。
        # 它的作用是告诉程序：“虽然我匹配了整个 ![...](...) 结构，但我 只要 这括号里的内容”。
        # ---------------------------------------------------------
        # md_img_pattern = re.compile(r'!\[.*?\]\((.*?)\)')
        md_img_pattern = re.compile(r'!\[.*?\]\((.*?\.(?:png|jpg|jpeg|gif|webp|bmp|svg))\)')
        print(f"开始提取图片，待处理文档数: {len(docs)}")

        for i, doc in enumerate(docs):
            # 1. 优先检查 url 字段 (主要针对 Web Search 结果)
            url = (doc.get("url") or "").strip()
            if url:
                # 简单后缀判断：确保是静态图片资源
                if url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg')):
                    if url not in seen:
                        print(f"文档[{i}] 发现图片 URL (字段): {url}")
                        seen.add(url)
                        images.append(url)

            # 2. 检查 text 字段中的 Markdown 图片 (主要针对 Local Chunk)
            text = (doc.get("content") or "").strip()
            if text:
                # findall 机制解释：
                # 正则表达式 r'!\[.*?\]\((.*?)\)' 中包含一个捕获组 (.*?)
                # 当存在捕获组时，findall 只返回括号内匹配到的内容（即 URL），而不是整个 ![...](...) 字符串
                # 示例：
                # 输入 text: "参考图片 ![面板图](http://img.com/1.jpg) 如下"
                # 返回 matches: ['http://img.com/1.jpg']
                matches = md_img_pattern.findall(text)
                for img_url in matches:
                    img_url = img_url.strip()
                    if img_url and img_url not in seen:
                        print(f"文档[{i}] 正文发现 Markdown 图片: {img_url}")
                        seen.add(img_url)
                        images.append(img_url)

        print(f"图片提取完成，共找到 {len(images)} 张唯一图片: {images}")
        return images

    def _extract_sources_from_docs(self, docs):
        """从最终 rerank 结果提取可展示的来源，不推断不存在的页码。"""
        sources = []
        seen = set()
        for doc in docs or []:
            doc = normalize_chunk_metadata(doc)
            file_name = doc["document_name"]
            document_source = (doc.get("url") or doc.get("source") or "").strip()
            page = None
            for page_key in ("page", "page_num", "page_number", "page_no"):
                if doc.get(page_key) is not None:
                    page = doc.get(page_key)
                    break
            key = (file_name, doc["chunk_id"], doc["title"], doc["parent_title"],
                   document_source, str(page) if page is not None else "")
            if key in seen or not any(key):
                continue
            seen.add(key)
            item = {
                "file_name": file_name,
                "document_id": doc["document_id"],
                "document_name": doc["document_name"],
                "document_source": document_source,
                "title": (doc.get("title") or "").strip(),
                "parent_title": doc["parent_title"],
                "chunk_id": str(doc.get("chunk_id") or ""),
            }
            if page is not None:
                item["page"] = page
            sources.append(item)
        return sources

    def _step_4_write_history(seld, state: QueryGraphState, image_urls=None, sources=None) -> QueryGraphState:
        """
        阶段四：把本轮答案写入 MongoDB history。
        利用 utils/mongo_history_utils.py 中的 save_chat_messages 方法。
        """
        session_id = state.get("session_id", "default")
        answer = (state.get("answer") or "").strip()
        item_names = state.get("item_names") or []

        try:
            if answer:
                save_chat_message(
                    session_id=session_id,
                    role="assistant",
                    text=answer,
                    rewritten_query="",
                    item_names=item_names,
                    image_urls=image_urls,
                    message_id=None,
                    sources=sources
                )
        except Exception as e:
            # 写历史失败不应影响主链路
            add_fallback(state.get("request_id", state.get("session_id", "")), "history_write_failure")

        return state


if __name__ == "__main__":
    print("开始测试: 答案生成节点")

    # 1. 构造模拟数据
    # 模拟重排序后的文档列表 (reranked_docs)
    # 包含：本地文档（带Markdown图片）、联网结果（带URL字段）、纯文本文档
    mock_reranked_docs = [
        {
            "chunk_id": "local_101",
            "source": "local",
            "title": "HAK 180 烫金机操作手册_v2",
            "score": 0.95,
            "url": None,
            "content": """
HAK 180 烫金机的操作面板位于机器正前方。
开启电源后，您需要先设置温度，默认建议设置在 110℃ 左右。
具体的操作面板布局请参考下图：
![操作面板布局图](http://192.168.100.100:9000/knowledge-base/upload-images/hak180产品安全手册/048c005b198be5c9fff80ad6a6ba02496f38fa109ec20dbaabde3110f3eb1574.jpg)

如果是进行局部烫金，请调节侧面的旋钮。
![侧面旋钮细节](http://192.168.100.100:9000/knowledge-base/upload-images/hak180产品安全手册/f77da4df52517fc50b9efb528540e1351dd1a08dce6f801cf08366540f2c59ce.jpg)
"""
        },
        {
            "chunk_id": None,
            "source": "web",
            "title": "HAK 180 常见故障排除 - 官网",
            "score": 0.88,
            "url": "http://192.168.100.100:9000/knowledge-base/upload-images/%E5%8D%8E%E4%B8%BA%E6%93%8E%E4%BA%91G740%E7%94%A8%E6%88%B7%E6%8C%87%E5%8D%97-(KLVG-16Z,Windows11_02,zh-cn)/c28a751c315a89fb5f3b52736a7996b56971c9a260a0e2b850eb5ef18beabf3c.jpg",
            # 这是一个直接指向图片的URL（虽然少见，但用于测试提取）
            "content": "如果机器无法加热，请检查保险丝是否熔断..."
        },
        {
            "chunk_id": "local_102",
            "source": "local",
            "title": "安全注意事项",
            "score": 0.82,
            "url": None,
            "content": "操作时请务必佩戴隔热手套，避免高温烫伤。"
        }
    ]

    # 模拟历史记录
    mock_history = [
        {"role": "user", "text": "你好，这款机器怎么用？"},
        {"role": "assistant", "text": "您好！请问您具体指的是哪一款机器？"},
        {"role": "user", "text": "HAK 180 烫金机"}
    ]

    # 模拟输入状态
    mock_state = {
        "session_id": "test_answer_session_001",
        "original_query": "HAK 180 烫金机怎么操作？",
        "rewritten_query": "HAK 180 烫金机的具体操作步骤和面板设置方法",
        "item_names": ["HAK180烫金机"],
        "history": mock_history,
        "reranked_docs": mock_reranked_docs,
        "is_stream": False,  # 测试非流式
        # "is_stream": True, # 若要测试流式，需确保 SSE 环境或 mock 相关函数
        "answer": None  # 初始无答案
    }

    # 运行节点
    node_answer_output = NodeAnswerOutput()
    result = node_answer_output(mock_state)

    print(result)
