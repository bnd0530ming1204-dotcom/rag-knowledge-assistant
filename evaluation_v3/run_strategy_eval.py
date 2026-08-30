"""Run one production-compatible retrieval/context strategy against Frozen V2 read-only data."""
from __future__ import annotations
import argparse, json, os, statistics, time, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
DATASET=ROOT/"evaluation_v2/dataset/dataset_v2_frozen.json"

MODES={
 "A":{"ENABLE_HYDE":"false","ENABLE_RRF":"false","FUSION_MODE":"weighted_hybrid","ENABLE_RERANK":"false","CONTEXT_SELECTOR_MODE":"fixed"},
 "B":{"ENABLE_HYDE":"false","ENABLE_RRF":"false","FUSION_MODE":"weighted_hybrid","ENABLE_RERANK":"true","CONTEXT_SELECTOR_MODE":"fixed"},
 "C":{"ENABLE_HYDE":"false","ENABLE_RRF":"false","FUSION_MODE":"weighted_hybrid","ENABLE_RERANK":"false","CONTEXT_SELECTOR_MODE":"dynamic"},
 "D":{"ENABLE_HYDE":"true","ENABLE_RRF":"false","FUSION_MODE":"weighted_hybrid","ENABLE_RERANK":"false","CONTEXT_SELECTOR_MODE":"fixed"},
 "E":{"ENABLE_HYDE":"false","ENABLE_RRF":"true","FUSION_MODE":"explicit_rrf","ENABLE_RERANK":"false","CONTEXT_SELECTOR_MODE":"fixed"},
 "F":{"ENABLE_HYDE":"false","ENABLE_RRF":"true","FUSION_MODE":"explicit_rrf","ENABLE_RERANK":"true","CONTEXT_SELECTOR_MODE":"fixed"},
}

def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--mode",choices=MODES,required=True); ap.add_argument("--collection",required=True); ap.add_argument("--output",type=Path,required=True); args=ap.parse_args()
 os.environ.update(MODES[args.mode])
 from config.settings import reset_settings_cache; reset_settings_cache()
 from config.milvus_config import milvus_config; object.__setattr__(milvus_config,"chunks_collection",args.collection)
 from evaluation_v2.runners.baseline_runner import metrics
 from processor.query_processor.nodes.b_node_search_embedding import NodeSearchEmbedding
 from utils.context_builder import select_context
 from config.settings import get_settings
 ds=json.loads(DATASET.read_text(encoding="utf-8")); rows=[]; lat=[]; settings=get_settings()
 for case in ds["cases"]:
  started=time.perf_counter(); error=None
  try:
   result=NodeSearchEmbedding().process({"rewritten_query":case["query"],"request_id":case["query_id"]})
   candidates=result["reranked_docs"]
   selected=select_context(candidates,settings.context_selector_mode,settings.max_context_tokens,
                           settings.final_context_top_k,settings.min_contexts,settings.max_contexts,
                           settings.dynamic_score_gap,settings.dynamic_min_score)
  except Exception as exc:
   candidates=[]; selected=None; error={"type":type(exc).__name__,"message":"strategy execution failed"}
  elapsed=round((time.perf_counter()-started)*1000,3); lat.append(elapsed)
  rows.append({"query_id":case["query_id"],"query":case["query"],"category":case["category"],"answerable":case["answerable"],
               "relevant_locators":case["relevant_locators"],"retrieval_metrics":metrics(candidates,case["relevant_locators"]) if case["answerable"] and not error else None,
               "selected_contexts":selected.documents if selected else [],"context_count":len(selected.documents) if selected else 0,
               "context_tokens":selected.token_count if selected else 0,"total_retrieval_context_latency_ms":elapsed,"error":error})
 answerable=[r for r in rows if r["retrieval_metrics"]]
 by_category={}
 for category in sorted({r["category"] for r in answerable}):
  subset=[r for r in answerable if r["category"]==category]
  by_category[category]={name:sum(r["retrieval_metrics"][name] for r in subset)/len(subset) for name in ("recall@1","recall@3","recall@5","mrr@5")}
 relevance=[]
 for row in rows:
  if row["selected_contexts"]:
   relevant=set(row["relevant_locators"])
   relevance.append(sum(bool(relevant & set(map(str,doc.get("locators") or []))) for doc in row["selected_contexts"])/len(row["selected_contexts"]))
 artifact={"mode":args.mode,"config":MODES[args.mode],"frozen_dataset_read_only":True,
           "metrics":{name:sum(r["retrieval_metrics"][name] for r in answerable)/len(answerable) for name in ("recall@1","recall@3","recall@5","mrr@5")} if answerable else {},
           "metrics_by_category":by_category,"avg_context_relevance":statistics.mean(relevance) if relevance else 0.0,
           "avg_context_count":statistics.mean(r["context_count"] for r in rows),"avg_context_tokens":statistics.mean(r["context_tokens"] for r in rows),
           "latency":{"p50_ms":statistics.median(lat),"p95_ms":sorted(lat)[int((len(lat)-1)*.95)]},"queries":rows}
 args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__": main()
