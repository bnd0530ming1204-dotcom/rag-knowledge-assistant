import os
import time
import unittest
from unittest.mock import patch, MagicMock

from config.settings import AppSettings
from evaluation_v3.failure_analysis import classify
from evaluation_v3.generation_metrics import (answer_correctness, citation_correctness,
    context_relevance, evaluate_generation, faithfulness, no_answer_behavior)
from utils.context_builder import select_context
from utils.fusion import reciprocal_rank_fusion
from utils.observability import create_trace, get_trace
from utils.rerank_stage import optional_rerank
from utils.retrieval_strategy import HYDE_HYBRID, NORMAL_HYBRID, route_strategy
from utils.rewrite_decision import decide_rewrite


def hit(cid, score=.8, content=None):
    return {"distance":score,"entity":{"chunk_id":cid,"file_title":"doc","title":"t"+cid,
            "parent_title":"p","content":content or "content "+cid}}


class RewriteDecisionTests(unittest.TestCase):
    def test_standalone_with_history(self):
        result=decide_rewrite("什么是 RRF？",[{"role":"user","text":"A100"}],"conditional")
        self.assertFalse(result.required); self.assertEqual(result.reason,"standalone_query")
    def test_pronoun_rewrite(self):
        self.assertTrue(decide_rewrite("它支持多久？",[{"role":"user","text":"A100"}],"conditional").required)
    def test_ellipsis_rewrite(self):
        self.assertTrue(decide_rewrite("那第二个呢？",[{"role":"user","text":"两个型号"}],"conditional").required)
    def test_topic_switch_no_rewrite(self):
        self.assertFalse(decide_rewrite("A200 需要多少带宽？",[{"role":"user","text":"午饭"}],"conditional").required)
    def test_history_mode_preserves_production_default(self):
        self.assertTrue(decide_rewrite("什么是 RRF？",[{"role":"user","text":"A100"}],"history").required)


class RouterFusionTests(unittest.TestCase):
    def test_router_normal_for_fact(self):
        self.assertEqual(route_strategy("保修多久？",True).strategy,NORMAL_HYBRID)
    def test_router_hyde_for_descriptive(self):
        self.assertEqual(route_strategy("请解释混合检索为什么可能改善语义召回",True).strategy,HYDE_HYBRID)
    def test_router_disabled_is_normal(self):
        self.assertEqual(route_strategy("请解释系统原理",False).strategy,NORMAL_HYBRID)
    def test_explicit_dense_sparse_rrf(self):
        result=reciprocal_rank_fusion([hit("a"),hit("b")],[hit("b"),hit("c")],k=60,top_n=3)
        self.assertEqual(result[0]["chunk_id"],"b"); self.assertEqual({x["chunk_id"] for x in result},{"a","b","c"})

    @patch("processor.query_processor.nodes.b_node_search_embedding.hybrid_search",return_value=[[hit("a")]])
    @patch("processor.query_processor.nodes.b_node_search_embedding.get_milvus_client")
    @patch("processor.query_processor.nodes.b_node_search_embedding.generate_embeddings",return_value={"dense":[[.1]],"sparse":[{1:.2}]})
    @patch("processor.query_processor.nodes.b_node_search_embedding.NodeSearchEmbedding._generate_hyde",side_effect=TimeoutError())
    @patch.dict(os.environ,{"ENABLE_HYDE":"true"})
    def test_hyde_failure_fallback(self, *_):
        from config.settings import reset_settings_cache; reset_settings_cache()
        from processor.query_processor.nodes.b_node_search_embedding import NodeSearchEmbedding
        create_trace("hyde","s","q",.8,.2)
        result=NodeSearchEmbedding().process({"request_id":"hyde","rewritten_query":"请解释混合检索为什么改善召回"})
        self.assertEqual(len(result["reranked_docs"]),1)
        self.assertTrue(get_trace("hyde").hyde_fallback)
        reset_settings_cache()


class RerankSelectorTests(unittest.TestCase):
    @patch("utils.rerank_stage.rerank_documents",return_value=[.1,.9])
    def test_rerank_success(self,_):
        result=optional_rerank("q",[{"content":"a"},{"content":"b"}],True,2,1)
        self.assertEqual(result.documents[0]["content"],"b"); self.assertFalse(result.fallback)
    @patch("utils.rerank_stage.rerank_documents",side_effect=RuntimeError("down"))
    def test_rerank_failure_fallback(self,_):
        docs=[{"content":"a"}]; result=optional_rerank("q",docs,True,1,1)
        self.assertEqual(result.documents,docs); self.assertTrue(result.fallback)
    @patch("utils.rerank_stage.rerank_documents",side_effect=lambda *_:(time.sleep(.05),[.9])[1])
    def test_rerank_timeout_fallback(self,_):
        result=optional_rerank("q",[{"content":"a"}],True,1,.005)
        self.assertTrue(result.fallback)
    def docs(self):
        return [{"chunk_id":str(i),"file_title":"d","title":str(i),"parent_title":"p"+str(i),"content":str(i)+"x"*10,"score":score}
                for i,score in enumerate([.9,.85,.4,.39],1)]
    def test_fixed_selector(self):
        self.assertEqual(len(select_context(self.docs(),"fixed",500,3,1,4,.25,None).documents),3)
    def test_dynamic_selector_gap(self):
        result=select_context(self.docs(),"dynamic",500,5,1,5,.25,None)
        self.assertEqual(len(result.documents),2); self.assertEqual(result.selection_reason,"dynamic_score_gap")
    def test_dynamic_minimum_protection(self):
        result=select_context(self.docs(),"dynamic",500,5,2,5,.01,.95)
        self.assertGreaterEqual(len(result.documents),2)
    def test_dynamic_token_budget(self):
        result=select_context(self.docs(),"dynamic",35,5,1,5,1,None)
        self.assertLessEqual(result.token_count,35)


class GenerationEvaluationTests(unittest.TestCase):
    def test_deterministic_metrics(self):
        self.assertEqual(answer_correctness("uses 12 V 3 A adapter",["12 V 3 A adapter"]),1)
        self.assertEqual(faithfulness("uses 12 V 3 A adapter",[{"content":"device uses 12 V 3 A adapter"}]),1)
    def test_citation_correctness(self):
        contexts=[{"chunk_id":"c1","locators":["L1"],"content":"x"}]
        self.assertEqual(citation_correctness([{"chunk_id":"c1"}],contexts,["L1"]),1)
        self.assertEqual(citation_correctness([{"chunk_id":"fake"}],contexts,["L1"]),0)
    def test_context_relevance(self):
        self.assertEqual(context_relevance([{"locators":["L1"]},{"locators":["X"]}],["L1"]),.5)
    def test_no_answer_false_claim(self):
        self.assertEqual(no_answer_behavior("该设备保修 5 年。",False),"UNSUPPORTED_FACTUAL_CLAIM")
    def test_generation_row_and_failure_taxonomy(self):
        row=evaluate_generation({"query_id":"q","answer":"wrong 99","answerable":False,"reference_answer":"",
            "selected_contexts":[],"citations":[],"relevant_locators":[]})
        failures=classify(row)
        self.assertTrue(any(x["failure_type"] in {"CITATION_MISMATCH","NO_ANSWER_FALSE_CLAIM"} for x in failures))


class ConfigTraceDefaultTests(unittest.TestCase):
    def test_strategy_config_override(self):
        with patch.dict(os.environ,{"FUSION_MODE":"explicit_rrf","CONTEXT_SELECTOR_MODE":"dynamic","ENABLE_RRF":"true"}):
            value=AppSettings(_env_file=None)
        self.assertEqual(value.fusion_mode,"explicit_rrf"); self.assertEqual(value.context_selector_mode,"dynamic")
    def test_production_defaults_unchanged(self):
        value=AppSettings(_env_file=None)
        self.assertEqual((value.dense_weight,value.sparse_weight,value.hybrid_candidate_top_n,value.final_context_top_k),(.8,.2,10,5))
        self.assertFalse(value.enable_hyde); self.assertFalse(value.enable_rrf); self.assertFalse(value.enable_rerank)
        self.assertEqual(value.context_selector_mode,"fixed"); self.assertEqual(value.rewrite_decision_mode,"history")
    def test_trace_strategy_fields(self):
        trace=create_trace("fields","s","q",.8,.2).public_dict()
        for key in ("retrieval_strategy","fusion_mode","hyde_used","rerank_used","context_selector_mode","selection_reason"):
            self.assertIn(key,trace)

if __name__=="__main__": unittest.main()
