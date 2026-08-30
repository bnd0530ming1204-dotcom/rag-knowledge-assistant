import unittest
from unittest.mock import patch
from pathlib import Path

from config.retrieval_config import retrieval_config
from config.settings import get_settings
from processor.import_processor.parent_context import assign_parent_titles, build_embedding_text
from processor.import_processor.nodes.f_node_bge_embedding import NodeBGEEmbedding


class ParentContextTests(unittest.TestCase):
    def test_markdown_hierarchy_and_adjacent_parents(self):
        chunks = [
            {"title": "# 平台手册", "content": "root"},
            {"title": "## 站点管理", "content": "site"},
            {"title": "### 创建站点", "content": "create"},
            {"title": "## 许可证管理", "content": "license"},
            {"title": "### 离线激活", "content": "offline"},
        ]
        original_contents = [chunk["content"] for chunk in chunks]

        result = assign_parent_titles(chunks)

        self.assertEqual(
            [chunk["parent_title"] for chunk in result],
            ["", "# 平台手册", "## 站点管理", "# 平台手册", "## 许可证管理"],
        )
        self.assertEqual([chunk["content"] for chunk in result], original_contents)
        self.assertTrue(all("parent_title" not in chunk for chunk in chunks))

    def test_numbered_fallback_uses_existing_title(self):
        chunks = [
            {"title": "## 2 许可证", "content": "chapter"},
            {"title": "## 2.4 离线激活", "content": "section"},
            {"title": "## 2.4.3 参数规则", "content": "rules"},
        ]

        result = assign_parent_titles(chunks)

        self.assertEqual(result[1]["parent_title"], "## 2 许可证")
        self.assertEqual(result[2]["parent_title"], "## 2.4 离线激活")

    def test_non_numbered_headings_use_markdown_levels(self):
        result = assign_parent_titles([
            {"title": "# 附录", "content": "appendix"},
            {"title": "## 故障代码", "content": "errors"},
        ])
        self.assertEqual(result[1]["parent_title"], "# 附录")

    def test_missing_or_irregular_heading_has_safe_empty_parent(self):
        result = assign_parent_titles([
            {"title": "普通文本标题", "content": "plain"},
            {"title": "### 孤立小节", "content": "orphan"},
        ])
        self.assertEqual(result[0]["parent_title"], "")
        self.assertEqual(result[1]["parent_title"], "")

    def test_long_fragment_keeps_real_source_heading(self):
        result = assign_parent_titles([
            {
                "title": "## 安装步骤 - 1",
                "parent_title": "## 安装步骤",
                "part": 1,
                "content": "first fragment",
            },
            {"title": "### 注意事项", "content": "warning"},
        ])
        self.assertEqual(result[0]["parent_title"], "## 安装步骤")
        self.assertEqual(result[1]["parent_title"], "## 安装步骤")

    def test_embedding_text_preserves_original_semantics_without_parent(self):
        chunk = {"item_name": "控制器", "content": "原始正文", "parent_title": ""}
        self.assertEqual(build_embedding_text(chunk), "控制器\n原始正文")
        self.assertEqual(chunk["content"], "原始正文")

    @patch("processor.import_processor.nodes.f_node_bge_embedding.generate_embeddings")
    def test_dense_and_sparse_share_parent_enhanced_input(self, generate_embeddings):
        captured = []

        def fake_generate(texts):
            captured.extend(texts)
            return {"dense": [[1.0] for _ in texts], "sparse": [{0: 1.0} for _ in texts]}

        generate_embeddings.side_effect = fake_generate
        chunks = [{
            "title": "### 参数规则",
            "parent_title": "## 离线激活",
            "content": "原始正文",
        }]

        result = NodeBGEEmbedding()._step_generate_embeddings(chunks)

        self.assertEqual(captured, ["## 离线激活\n\n原始正文"])
        self.assertEqual(result[0]["content"], "原始正文")
        self.assertEqual(result[0]["dense_vector"], [1.0])
        self.assertEqual(result[0]["sparse_vector"], {0: 1.0})

    def test_retrieval_budget_matches_promoted_candidate10_config(self):
        settings = get_settings()
        self.assertEqual(retrieval_config.initial_candidate_limit, settings.hybrid_candidate_top_n)
        self.assertEqual(retrieval_config.final_output_limit, settings.final_context_top_k)
        self.assertEqual(settings.hybrid_candidate_top_n, 10)
        self.assertEqual(settings.final_context_top_k, 5)

    def test_downstream_nodes_still_consume_original_content(self):
        project_root = Path(__file__).resolve().parents[1]
        reranker_source = (project_root / "processor/query_processor/nodes/f_node_rerank.py").read_text(
            encoding="utf-8"
        )
        context_source = (project_root / "utils/context_builder.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('contents = [doc.get("content") for doc in merged_multi_docs]', reranker_source)
        self.assertIn('doc["content"]', context_source)
        self.assertNotIn("embedding_text", reranker_source)
        self.assertNotIn("embedding_text", context_source)


if __name__ == "__main__":
    unittest.main()
