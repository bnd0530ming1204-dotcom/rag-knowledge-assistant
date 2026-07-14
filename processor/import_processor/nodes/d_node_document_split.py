from typing import List, Dict

from processor.import_processor.base import BaseNode
from processor.import_processor.exceptions import StateFieldError
from processor.import_processor.state import ImportGraphState


class NodeDocumentSplit(BaseNode):
    """
    文档切分节点：智能文档切片
    """

    name = "node_document_split"

    def process(self, state: ImportGraphState):
        """
        文档切分节点：智能文档切片
        :param state:
        :return:
        """
        # 1 参数处理
        content, file_title = self._step_1_get_inputs(state)

        # 2 标题切(初切)
        sections, title_count, lines_count = self._step_2_split_by_title(content, file_title)

        # 3 无标题兜底(默认标题)
        sections = self._step_3_handle_no_title(content, sections, title_count, file_title)

        # 4 块精细化处理(长切短合)
        sections = self._step_4_refine_chunks(sections)

        # 5 打印日志
        self._step_5_print_stats(lines_count, sections)

        # 6 备份
        self._step_6_backup(state, sections)

        state["chunks"] = None
        return state

    # 步骤1：参数处理
    def _step_1_get_inputs(self, state):
        print("node_document_split: 步骤1：参数处理")
        content = state.get("md_content")
        if not content:
            raise StateFieldError(field_name="md_content", expected_type=str)

        file_title = state.get("file_title")
        if not file_title:
            raise StateFieldError(field_name="file_title", expected_type=str)

        # 换行符处理
        content = content.replace("\r\n", "\n").replace("\r", "\n")

        return content, file_title

    # 步骤2：标题切(初切)
    def _step_2_split_by_title(self, content, file_title):
        print("node_document_split: 步骤2：标题切(初切)")

        # 参数声明
        sections: List[Dict[str, str]] = []
        title_count = 0
        lines = content.split("\n")
        current_lines = []
        in_code_block = False

        # 切换逻辑(标题切)
        title_pattern = r'\s*#{1,6}\s+.+'


        for line in lines:
            striped_line = line.strip()

            # 判断是否在代码块中
            if striped_line.startwith("````") or striped_line.startwith("~~~"):
                in_code_block = not in_code_block
                current_lines.append(line)


        # 封装sections块的案例代码
        sections.append(
            {
                "title": file_title,
                "content": "\n".join(current_lines),
                "parent_title": "",
                "file_title": file_title
            }
        )

        return sections, title_count, len(lines)

    # 步骤3：无标题兜底(默认标题)
    def _step_3_handle_no_title(self, content, sections, title_count, file_title):
        print("node_document_split: 步骤3：无标题兜底(默认标题)")
        return sections

    # 步骤4：块精细化处理(长切短合)
    def _step_4_refine_chunks(self, sections):
        print("node_document_split: 步骤4：块精细化处理(长切短合)")
        return sections

    def _step_5_print_stats(self, lines_count, sections):
        print("node_document_split: 步骤5：打印日志")
        pass

    def _step_6_backup(self, state, sections):
        print("node_document_split: 步骤6：备份")
        pass


if __name__ == "__main__":
    node = NodeDocumentSplit()

    with open("E:\output\B530\hybrid_auto\B530_new.md", "r", encoding="utf-8") as f:
        md_content = f.read()

    init_state = {
        "md_path": "E:\output\B530\hybrid_auto\B530_new.md",
        "md_content": md_content,
        "file_title": "B530_new",
    }

    process = node.process(init_state)
    print(f"切分节点执行流程:{process}")
