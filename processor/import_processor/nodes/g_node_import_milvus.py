import json
import logging
from typing import List, Dict, Any

from processor.import_processor.base import BaseNode
from processor.import_processor.state import ImportGraphState


class NodeImportMilvus(BaseNode):
    """
    导入向量库节点：数据持久化
    """

    name = "node_import_milvus"

    def process(self, state: ImportGraphState):
        # 1 数据校验
        chunks_json_data, vector_dimension = self._step_1_check_inputs(state)

        # 2 结构准备(字段+索引)
        milvus_client = self._step_2_prepare_collection(vector_dimension)

        # 3 清理可能的冗余数据(幂等性)
        self._step_3_clean_old_data(milvus_client, chunks_json_data)

        # 4 数据入库,返回数据库主键
        update_chunks = self._step_4_insert_data(milvus_client, chunks_json_data)

        # 5 更新状态
        state["chunks"] = update_chunks

        return state


    # 步骤1 数据校验
    def _step_1_check_inputs(self, state: Dict[str, Any]) -> tuple[List[Dict[str, Any]], int]:
        print("node_import_milvus: 步骤1：数据校验")
        """
        检查
        """
        return None, 0

    # 步骤2 结构准备
    def _step_2_prepare_collection(self, vector_dimension: int):
        print("node_import_milvus: 步骤2：结构准备")
        """
        milvus客户端+集合准备
        """
        # 1 客户端
        milvus_client = None
        return milvus_client

    # 步骤3 清理旧数据
    def _step_3_clean_old_data(self, client, chunks_json_data):
        print("node_import_milvus: 步骤3：清理旧数据")
        pass

    # 步骤4 插入数据
    def _step_4_insert_data(self, client, chunks_json_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        print("node_import_milvus: 步骤4：插入数据")
        """
        批量插入milvus
        """
        return chunks_json_data

if __name__ == "__main__":
    node = NodeImportMilvus()
    node.process(None)
