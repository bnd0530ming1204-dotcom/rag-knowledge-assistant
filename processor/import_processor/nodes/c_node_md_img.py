import logging

from processor.import_processor.base import BaseNode
from processor.import_processor.state import ImportGraphState


class NodeMDImg(BaseNode):
    """
    MarkDown图片处理节点：多模态图片理解
    """

    name = "node_md_img"

    def process(self, state: ImportGraphState):
        logging.info(f"{self.name}节点开始执行...")

        # 1 参数处理

        # 2 图片扫描

        # 3 视觉模型摘要

        # 4 上传minio，替换md

        # 5 保存备份md

        return state