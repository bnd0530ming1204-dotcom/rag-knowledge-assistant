import json
import logging
import os
import time
from collections import deque
from pathlib import Path
from typing import Tuple, re, List, Dict, Deque

from processor.import_processor.base import BaseNode, setup_logging
from processor.import_processor.exceptions import StateFieldError, FileProcessingError
from processor.import_processor.state import ImportGraphState


class NodeMDImg(BaseNode):
    """
    MarkDown图片处理节点：多模态图片理解
    """

    name = "node_md_img"

    def process(self, state: ImportGraphState):
        logging.info(f"{self.name}节点开始执行...")

        # 1 参数处理
        md_content, md_path_obj, images_dir = self._step_1_get_content(state)
        print(f"md_content:{md_content},md_path_obj:{md_path_obj},images_dir:{images_dir}")

        # 2 图片扫描
        target_images = self._step_2_scan_images(md_content, images_dir)  # List[(str,str,Tuple[str,str])]
        print(f"target_images:{target_images}")

        # 3 视觉模型摘要
        summaries = self._step_3_generate_summaries(md_path_obj.stem, target_images)

        # 4 上传minio，替换md
        new_md_content = self._step_4_upload_and_replace(md_path_obj.stem, target_images, summaries, md_content)

        # 5 保存备份md
        new_md_file_name = self._step_5_backup_new_md_file(state['md_path'], new_md_content)

        state["md_content"] = new_md_content
        state["md_path"] = new_md_file_name
        return state

    # 步骤1
    def _step_1_get_content(self, state):
        # 1 校验参数
        md_path = state.get("md_path")
        if not md_path:
            raise StateFieldError(field_name="md_path", expected_type=str)
        md_path_obj = Path(md_path)

        if not md_path_obj.exists():
            raise FileProcessingError(message=f"输入文件不存在: {md_path}")

        md_content = state["md_content"]

        # 测试用代码
        if not md_content:
            with open(md_path, "r", encoding="utf-8") as md_file:
                md_content = md_file.read()

        # 2 图片路径,和md文档所在目录同级的images图片路径
        images_dir = md_path_obj.parent / "images"

        return md_content, md_path_obj, images_dir

    # 步骤2
    def _step_2_scan_images(self, md_content, images_dir):

        # 1 返回结果
        target_images = []

        # 2 扫描图片
        for image_file in os.listdir(images_dir):
            file_ext = os.path.splitext(image_file)[1].lower()
            if file_ext not in self.config.image_extensions:
                self.logger.warning(f"图片格式不支持，跳过：{image_file}")
                continue

            img_path = images_dir / image_file  # 图片路径
            context = self._find_image_in_md(md_content, image_file)  # 找到图片的上下文

            # 过滤MD中未引用的图片
            # if not context:
            #     self.logger.warning(f"图片未在MD中引用，跳过处理：{image_file}")
            #     continue

            target_images.append((image_file, img_path, context))  # List[(str,str,Tuple(pre,post))]

        return target_images

    # 步骤2方法1
    def _find_image_in_md(self, md_content: str, image_file: str, context_len: int = 100) -> Tuple[str, str]:
        """
            找到图片并且截取上下文
        """
        partern = re.compile(r"!\[.*?\]\(.*?" + re.escape(image_file) + r".*?\)")
        match = partern.search(md_content)
        if not match:
            return None

        start, end = match.span()

        pre_text = md_content[max(0, start - context_len):start]  # 文件上文
        post_text = md_content[end:min(len(md_content), end + context_len)]  # 文件下文
        return pre_text, post_text

    # 步骤3
    def _step_3_generate_summaries(self, doc_stem: str, target_images: List[Tuple[str, str, Tuple[str, str]]]) -> Dict[
        str, str]:
        summaries = {}
        request_deque = deque()

        for img_file,image_path,context in target_images:
            self._apply_api_rate_limit(request_deque, max_requests=10)
            # 调用视觉模型
            summaries[img_file] = self._summarize_image(image_path,root_folder=doc_stem , image_content=context) # 图片摘要
        return summaries

    # 步骤3方法1
    def _apply_api_rate_limit(
            self,
            request_times: Deque[float],
            max_requests: int,
            window_seconds: int = 60
    ) -> None:
        """
        通用滑动窗口API速率限制器（抽离为公共工具）
        核心逻辑：维护请求时间戳双端队列，窗口内请求数超上限则自动等待，防止触发第三方API限流
        :param request_times: 存储请求时间戳的双端队列，需外部初始化（全局/单例），跨调用复用
        :param max_requests: 速率限制窗口内的最大允许请求次数
        :param window_seconds: 速率限制滑动窗口时长，默认60秒（1分钟）
        :return: None，超出限制时会阻塞等待
        """
        current_time = time.time()

        # 1. 清理滑动窗口外的过期请求时间戳，保证队列仅存窗口内的请求
        while request_times and current_time - request_times[0] >= window_seconds:
            request_times.popleft()

        # 2. 窗口内请求数达上限，计算并阻塞等待剩余时间
        if len(request_times) >= max_requests:
            # 计算需要等待的时长（窗口总时长 - 最早请求已存在的时长）
            sleep_duration = window_seconds - (current_time - request_times[0])
            if sleep_duration > 0:
                logging.getLogger().info(
                    f"触发API速率限制，窗口{window_seconds}秒内最多{max_requests}次，需等待：{sleep_duration:.2f} 秒")
                time.sleep(sleep_duration)
                # 等待后更新当前时间，重新清理过期请求（避免等待期间有请求过期）
                current_time = time.time()
                while request_times and current_time - request_times[0] >= window_seconds:
                    request_times.popleft()

        # 3. 记录当前请求时间戳，加入滑动窗口队列
        request_times.append(current_time)
        logging.getLogger().info(f"API请求时间戳已记录，当前{window_seconds}秒窗口内请求数：{len(request_times)}")

    # 步骤3方法2
    def _summarize_image(self, image_path: str, root_folder: str, image_content: Tuple[str, str]) -> str:

        # 1 llm模型工具

        # 2 调用模型

        # 3 处理返回摘要信息

        return "图片描述"

if __name__ == "__main__":
    setup_logging()

    init_state = {
        "md_path": "E:\output\B530\hybrid_auto\B530.md",
        "md_content": None
    }

    node = NodeMDImg()
    result = node(init_state)

    # 打印结果
    dumps = json.dumps(result)
    print(dumps)
