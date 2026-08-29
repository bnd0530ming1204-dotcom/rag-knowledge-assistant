from dotenv import load_dotenv
from langgraph.constants import END
from langgraph.graph import StateGraph

from processor.query_processor.nodes.a_node_prepare_query import NodePrepareQuery
from processor.query_processor.nodes.b_node_search_embedding import NodeSearchEmbedding
from processor.query_processor.nodes.g_node_answer_output import NodeAnswerOutput
from processor.query_processor.state import QueryGraphState

load_dotenv()


class KBQueryWorkflow:

    # 构造
    def __init__(self):
        print("初始化查询工作流...")
        # 1 工作流状态
        self.workflow = StateGraph(QueryGraphState)

        # 2 实例化所有节点
        self._init_nodes()

        # 3 注册所有节点(添加节点)
        self._register_nodes()

        # 4 设置路由规则(设置边)
        self._setup_routes()

        # 5 编译工作流（懒加载，首次执行时编译）
        self._compiled_app = None

    # 实例化
    def _init_nodes(self):
        print("实例化所有节点...")
        self.node_prepare_query = NodePrepareQuery()
        self.node_search_embedding = NodeSearchEmbedding()
        self.node_answer_output = NodeAnswerOutput()

    # 注册
    def _register_nodes(self):
        print("注册所有节点...")
        self.workflow.add_node("node_prepare_query", self.node_prepare_query)
        self.workflow.add_node("node_search_embedding", self.node_search_embedding)
        self.workflow.add_node("node_answer_output", self.node_answer_output)

    # 路由
    def _setup_routes(self):
        print("设置路由规则...")
        # 入口
        self.workflow.set_entry_point("node_prepare_query")
        # self.workflow.add_node(START,"node_item_name_confirm")

        self.workflow.add_edge("node_prepare_query", "node_search_embedding")
        self.workflow.add_edge("node_search_embedding", "node_answer_output")
        self.workflow.add_edge("node_answer_output", END)

    # 编译图
    def compile(self):
        print("编译图...")
        if not self._compiled_app:
            self._compiled_app = self.workflow.compile()
        return self._compiled_app

    # 调用
    def run(self, initial_state: QueryGraphState, stream: bool = False) -> QueryGraphState:
        print("调用图...")
        """
        统一执行入口，支持切换invoke/stream
        """
        if not self._compiled_app:
            self.compile()
        if stream:
            return self._compiled_app.stream(initial_state)
        else:
            return self._compiled_app.invoke(initial_state)


if __name__ == "__main__":
    # 调用图
    workflow = KBQueryWorkflow()
    response = workflow.run({"original_query": "哥们儿，华为擎云B530计算机这个东东咋鼓捣上啊？", "session_id": "123"}, stream=True)
    # print(response)
    for res in response:
        print(res)

    # 画图
    # print(workflow.compile().get_graph().draw_ascii())
