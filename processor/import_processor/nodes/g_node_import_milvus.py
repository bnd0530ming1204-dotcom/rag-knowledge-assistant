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