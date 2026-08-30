"""Targeted, read-only HyDE promotion evaluation against Frozen V2."""
from __future__ import annotations
import argparse, json, os, statistics, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
DATASET=ROOT/"evaluation_v2/dataset/dataset_v2_frozen.json"

def pct(values,p): return sorted(values)[int((len(values)-1)*p)] if values else 0.0

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--baseline',type=Path,required=True); ap.add_argument('--collection',required=True); ap.add_argument('--output',type=Path,required=True); args=ap.parse_args()
    os.environ.update({'ENABLE_HYDE':'false','ENABLE_RERANK':'false','ENABLE_RRF':'false','CONTEXT_SELECTOR_MODE':'fixed'})
    from config.settings import reset_settings_cache; reset_settings_cache()
    from config.milvus_config import milvus_config; object.__setattr__(milvus_config,'chunks_collection',args.collection)
    from evaluation_v2.runners.baseline_runner import metrics
    from processor.query_processor.nodes.b_node_search_embedding import NodeSearchEmbedding
    from processor.query_processor.prompt.search_embedding_hyde import HYDE_PROMPT
    from utils.llm_utils import get_llm_client
    ds=json.loads(DATASET.read_text(encoding='utf-8')); base=json.loads(args.baseline.read_text(encoding='utf-8'))
    bm={q['query_id']:q for q in base['queries']}; selected=[c for c in ds['cases'] if c['category']=='paraphrase_colloquial' or not c['answerable']]
    rows=[]
    for case in selected:
        started=time.perf_counter(); error=None; hypothesis=''
        try:
            hs=time.perf_counter(); hypothesis=str(get_llm_client().invoke(HYDE_PROMPT.format(rewritten_query=case['query'])).content).strip(); hlat=(time.perf_counter()-hs)*1000
            result=NodeSearchEmbedding().process({'rewritten_query':case['query']+' '+hypothesis,'request_id':'hyde-'+case['query_id']})
            docs=result['reranked_docs']; total=(time.perf_counter()-started)*1000
        except Exception as exc:
            docs=[]; hlat=0; total=(time.perf_counter()-started)*1000; error={'type':type(exc).__name__,'message':str(exc)}
        normal=bm[case['query_id']].get('retrieval_metrics'); hm=metrics(docs,case['relevant_locators']) if case['answerable'] and not error else None
        drift=bool((not case['answerable']) and hypothesis and (any(ch.isdigit() for ch in hypothesis) or any(x in hypothesis for x in ('支持','必须','是','为','可以'))))
        rows.append({'query_id':case['query_id'],'query':case['query'],'category':case['category'],'answerable':case['answerable'],'hypothesis':hypothesis,'normal_metrics':normal,'hyde_metrics':hm,'hyde_latency_ms':round(hlat,3),'total_latency_ms':round(total,3),'unsupported_assertion_proxy':drift,'error':error})
    comparable=[r for r in rows if r['hyde_metrics']]
    def avg(kind,key): return sum(r[kind][key] for r in comparable)/len(comparable)
    changes={'improved':0,'degraded':0,'unchanged':0}
    for r in comparable:
        d=r['hyde_metrics']['mrr@5']-r['normal_metrics']['mrr@5']; changes['improved' if d>0 else 'degraded' if d<0 else 'unchanged']+=1
    out={'scope':'paraphrase_colloquial plus all frozen no-answer','query_count':len(rows),'answerable_count':len(comparable),'no_answer_count':sum(not r['answerable'] for r in rows),'normal_metrics':{k:avg('normal_metrics',k) for k in ('recall@1','recall@3','recall@5','mrr@5')},'hyde_metrics':{k:avg('hyde_metrics',k) for k in ('recall@1','recall@3','recall@5','mrr@5')},'changes':changes,'latency':{'hyde_generation_p50_ms':statistics.median([r['hyde_latency_ms'] for r in rows]),'hyde_generation_p95_ms':pct([r['hyde_latency_ms'] for r in rows],.95),'total_p50_ms':statistics.median([r['total_latency_ms'] for r in rows]),'total_p95_ms':pct([r['total_latency_ms'] for r in rows],.95)},'no_answer_unsupported_assertion_proxy_count':sum(r['unsupported_assertion_proxy'] for r in rows if not r['answerable']),'metric_warning':'unsupported assertion is a lexical review proxy, not final-answer hallucination','queries':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__': main()
