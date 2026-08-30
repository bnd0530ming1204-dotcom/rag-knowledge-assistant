"""Real qwen-flash generation over recorded production-default contexts."""
from __future__ import annotations
import argparse, json, statistics, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))

def pct(v,p): return sorted(v)[int((len(v)-1)*p)] if v else 0.0
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--retrieval',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--workers',type=int,default=4); args=ap.parse_args()
    from evaluation_v3.generation_metrics import evaluate_generation
    from evaluation_v3.failure_analysis import classify
    from processor.query_processor.prompt.answer_prompt import ANSWER_PROMPT
    from utils.context_builder import build_fixed_context
    from utils.llm_utils import get_llm_client
    ds=json.loads((ROOT/'evaluation_v2/dataset/dataset_v2_frozen.json').read_text(encoding='utf-8')); cases={c['query_id']:c for c in ds['cases']}; source=json.loads(args.retrieval.read_text(encoding='utf-8'))
    def run(item):
        c=cases[item['query_id']]; ctx=build_fixed_context(item['selected_contexts'],3000,5); prompt=ANSWER_PROMPT.format(context=ctx.text or '无参考内容',history='暂无历史对话',item_names='无指定商品',question=c['query'])
        started=time.perf_counter(); error=None
        try: answer=str(get_llm_client().invoke(prompt).content).strip()
        except Exception as exc: answer=''; error={'type':type(exc).__name__,'message':str(exc)}
        latency=(time.perf_counter()-started)*1000; citations=[{'chunk_id':d.get('chunk_id')} for d in ctx.documents]
        row=evaluate_generation({'query_id':c['query_id'],'query':c['query'],'category':c['category'],'answerable':c['answerable'],'reference_answer':c.get('reference_answer',''),'relevant_locators':c.get('relevant_locators',[]),'answer':answer,'selected_contexts':ctx.documents,'citations':citations,'llm_latency_ms':round(latency,3),'error':error}); row['failures']=classify(row); return row
    rows=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(run,x):x['query_id'] for x in source['queries']}
        for f in as_completed(futures): rows.append(f.result())
    rows.sort(key=lambda x:x['query_id']); valid=[r for r in rows if not r['error']]; answerable=[r for r in valid if r['answerable']]; na=[r for r in valid if not r['answerable']]; lat=[r['llm_latency_ms'] for r in valid]
    out={'status':'REAL_QWEN_FLASH_GENERATION_V3','metric_warning':'deterministic/reference-based proxy metrics, not human accuracy or RAGAS gold-standard','metrics':{k:statistics.mean(r[k] for r in answerable) for k in ('answer_correctness','faithfulness','citation_correctness','context_relevance')},'no_answer':{k:sum(r['no_answer_behavior']==k for r in na) for k in ('SUPPORTED_REFUSAL','UNSUPPORTED_FACTUAL_CLAIM','UNCERTAIN_NEEDS_REVIEW')},'latency':{'p50_ms':statistics.median(lat),'p95_ms':pct(lat,.95)},'errors':len(rows)-len(valid),'queries':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__': main()
