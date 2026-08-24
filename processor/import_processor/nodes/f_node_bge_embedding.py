import json
from pathlib import Path
from typing import List, Dict

from processor.import_processor.base import BaseNode
from processor.import_processor.exceptions import StateFieldError
from processor.import_processor.parent_context import build_embedding_text
from processor.import_processor.state import ImportGraphState
from utils.embedding_utils import generate_embeddings


class NodeBGEEmbedding(BaseNode):
    """
    混合向量化节点：使用 BGE-M3 模型将文本转换为向量
    """

    name = "node_bge_embedding"

    def process(self, state: ImportGraphState):
        # 1 参数校验
        chunks = self._step_1_validate_paths(state)

        # 2 数据向量化
        output_data = self._step_generate_embeddings(chunks)
        # for item in output_data:
        #     item_name = item.get("item_name")
        #     content = item.get("content")
        #     print(f"{item_name}")
        #     sparse_vector = item.get("sparse_vector")
        #     print(sparse_vector)
        path = f"{Path(state.get('md_path')).parent}/{state.get('file_title')}_new_new_new_chunks.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                output_data,
                f,
                ensure_ascii=False,
                indent=2
            )

        # 3 返回结果
        state["chunks"] = output_data

        return state

    # 步骤1
    def _step_1_validate_paths(self, state: ImportGraphState) -> List[Dict]:
        print("node_bge_embedding: 步骤1：参数校验")
        # 校验参数
        chunks = state.get("chunks")

        if not chunks:
            raise ValueError("参数错误：chunks")

        if not isinstance(chunks, list):
            raise StateFieldError(field_name="chunks", message="chunks数据类型不正确", expected_type=list)

        return chunks

    # 步骤2
    def _step_generate_embeddings(self, chunks: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        使用父级章节语境增强向量输入，同时保持原始content不变。
        """
        print("node_bge_embedding: 步骤2：数据向量化")
        output_data = []
        batch_size = 5  # 批量处理
        for i in range(0, len(chunks), batch_size):
            five_ready_xlh_texts = []
            five_texts = chunks[i:i + batch_size]  # 第一次从0块取到4块，一共取5块
            for doc in five_texts:
                doc.setdefault("item_name", "")
                five_ready_xlh_texts.append(build_embedding_text(doc))

            embeddings = generate_embeddings(five_ready_xlh_texts)  # 向量化结果

            for j, doc in enumerate(five_texts):
                item = doc.copy()
                dense = embeddings["dense"][j]
                item["dense_vector"] = dense
                sparse = embeddings["sparse"][j]
                item["sparse_vector"] = sparse
                output_data.append(item)

        return output_data


if __name__ == "__main__":
    node = NodeBGEEmbedding()
    with open(
            "./output/example/example_chunks.json",
            "r", encoding="utf-8") as f:
        chunks_content = f.read()

    json_state = json.loads(chunks_content)

    init_state = {
        "chunks": json_state
    }

    response = node(init_state)
    # print(response)
    # dumps = json.dumps(response, ensure_ascii=False, indent=4)
    # print(dumps)
