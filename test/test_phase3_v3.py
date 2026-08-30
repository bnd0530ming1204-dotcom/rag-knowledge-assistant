import json
import unittest
from pathlib import Path

from evaluation_v3.generation_metrics import context_relevance, no_answer_behavior

ROOT = Path(__file__).resolve().parents[1]


class Phase3EvaluationTests(unittest.TestCase):
    def test_locator_comment_is_used_for_context_relevance(self):
        docs = [{"content": "<!-- locator: FACT-1 -->\nevidence"}]
        self.assertEqual(context_relevance(docs, ["FACT-1"]), 1.0)

    def test_explicit_missing_information_is_refusal(self):
        self.assertEqual(no_answer_behavior("参考内容未提及该信息，无法确定。", False), "SUPPORTED_REFUSAL")

    def test_real_artifacts_are_complete(self):
        expected = {"experiment_B_real.json": 110, "experiment_D_targeted.json": 38,
                    "generation_real.json": 110, "generation_rescored.json": 110}
        for name, count in expected.items():
            data = json.loads((ROOT / "evaluation_v3/artifacts" / name).read_text(encoding="utf-8"))
            self.assertEqual(len(data["queries"]), count, name)

    def test_frozen_hash_manifest_is_unchanged(self):
        import hashlib
        raw = (ROOT / "evaluation_v2/dataset/dataset_v2_frozen.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         "6c99b11ffaa35142bc6dd3f7fd483a04fe090cfbb3210772f0db8b5cd5cd7634")


if __name__ == "__main__":
    unittest.main()
