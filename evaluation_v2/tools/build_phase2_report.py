"""Derive single-variable stage ablations from immutable Phase 1/2 artifacts."""
from __future__ import annotations
import json, hashlib, subprocess
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2]; E=ROOT/'evaluation_v2'
def load(n): return json.loads((E/'artifacts'/n).read_text(encoding='utf-8'))
def locs(rows): return [{*sum((x.get('locators',[]) for x in rows[:k]),[])} for k in (1,3,5)]
def met(rows,rel):
 rel=set(rel); f=locs(rows); ranks=[x['rank'] for x in rows[:5] if rel&set(x.get('locators',[]))]
 return {'recall@1':len(f[0]&rel)/len(rel),'recall@3':len(f[1]&rel)/len(rel),'recall@5':len(f[2]&rel)/len(rel),'mrr@5':1/min(ranks) if ranks else 0}
def aggregate(base,stage):
 qs=[]
 for q in base['queries']:
  if q['answerable']:
   m=met(q['stages'][stage],q['relevant_locators']); qs.append((q,m))
 names=['recall@1','recall@3','recall@5','mrr@5']; overall={n:sum(m[n] for _,m in qs)/len(qs) for n in names}; by={}
 for c in sorted({q['category'] for q,_ in qs}):
  z=[m for q,m in qs if q['category']==c]; by[c]={n:sum(m[n] for m in z)/len(z) for n in names}
 return {'metrics':overall,'metrics_by_category':by,'per_query':{q['query_id']:m for q,m in qs}}
def rank(stage,rel): return next((x['rank'] for x in stage if set(x.get('locators',[]))&set(rel)),None)
def pct(v,p): v=sorted(v); x=(len(v)-1)*p; a=int(x); b=min(a+1,len(v)-1); return round(v[a]*(b-x)+v[b]*(x-a),3)
def lat(base,names):
 vals=[]
 for q in base['queries']:
  d={t['stage']:t['latency_ms'] for t in q['trace']}; vals.append(sum(d.get(n,0) for n in names))
 return {'p50_ms':pct(vals,.5),'p95_ms':pct(vals,.95)}
def main():
 b=load('baseline_current_production.json'); out={'dataset_sha256':b['dataset_manifest']['dataset_sha256'],'corpus_manifest_sha256':b['dataset_manifest']['corpus_manifest_sha256'],'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}
 out['hyde_off']=aggregate(b,'ordinary_retrieval'); out['hyde_on_rrf']=aggregate(b,'rrf_result'); out['hyde_off']['latency']=lat(b,['ordinary_total']); out['hyde_on_rrf']['latency']=lat(b,['ordinary_total','hyde_generation','hyde_retrieval_total','rrf'])
 c0=out['hyde_off']['per_query']; c1=out['hyde_on_rrf']['per_query']; out['hyde_decision']={'improved':sum(c1[k]['mrr@5']>v['mrr@5'] for k,v in c0.items()),'degraded':sum(c1[k]['mrr@5']<v['mrr@5'] for k,v in c0.items()),'unchanged':sum(c1[k]['mrr@5']==v['mrr@5'] for k,v in c0.items()),'no_answer_assertive_hyde':'20/20 corpus-unsupported assertions observed; retrieval causality not asserted'}
 out['rerank_off']=aggregate(b,'rrf_result'); out['rerank_on_no_cutoff']=aggregate(b,'post_rerank_result'); out['cutoff_on']=aggregate(b,'final_retrieval'); out['cutoff_off']=out['rerank_on_no_cutoff']
 moves=Counter(); removed=[]
 for q in b['queries']:
  if not q['answerable']: continue
  a=rank(q['stages']['pre_rerank_result'],q['relevant_locators']); z=rank(q['stages']['post_rerank_result'],q['relevant_locators'])
  if a is None and z is not None: moves['improved']+=1
  elif a is not None and z is None: moves['removed']+=1; removed.append(q['query_id'])
  elif a is None: moves['unchanged_missing']+=1
  elif z<a: moves['improved']+=1
  elif z>a: moves['degraded']+=1
  else: moves['unchanged']+=1
 out['rerank_rank_movement']={**moves,'relevant_removed':removed}
 cut_removed=[]; reduced=0
 for q in b['queries']:
  pre=q['stages']['post_rerank_result']; fin=q['stages']['final_retrieval']; reduced+=len(pre)-len(fin)
  if q['answerable']:
   before=set(sum((x['locators'] for x in pre),[])); after=set(sum((x['locators'] for x in fin),[])); lost=(before-after)&set(q['relevant_locators'])
   if lost: cut_removed.append({'query_id':q['query_id'],'locators':sorted(lost)})
 out['cutoff_effect']={'chunks_removed':reduced,'relevant_locator_cases_removed':cut_removed}
 tabs={}
 A={n:load(n) for n in ['ablation_a1_dense.json','ablation_a2_sparse.json','ablation_a3_hybrid.json']}
 for qid in ['v2q081','v2q082','v2q088']:
  qb=next(q for q in b['queries'] if q['query_id']==qid); tabs[qid]={'relevant':qb['relevant_locators'],'dense_rank':rank(next(q for q in A['ablation_a1_dense.json']['queries'] if q['query_id']==qid)['results'],qb['relevant_locators']),'sparse_rank':rank(next(q for q in A['ablation_a2_sparse.json']['queries'] if q['query_id']==qid)['results'],qb['relevant_locators']),'hybrid_rank':rank(next(q for q in A['ablation_a3_hybrid.json']['queries'] if q['query_id']==qid)['results'],qb['relevant_locators']),'hyde_rank':rank(qb['stages']['hyde_retrieval'],qb['relevant_locators']),'rrf_rank':rank(qb['stages']['rrf_result'],qb['relevant_locators']),'rerank_rank':rank(qb['stages']['post_rerank_result'],qb['relevant_locators']),'final_rank':rank(qb['stages']['final_retrieval'],qb['relevant_locators']),'chunk_preview':next((x['content_preview'] for s in qb['stages'].values() if isinstance(s,list) for x in s if set(x.get('locators',[]))&set(qb['relevant_locators'])),None)}
 out['table_failures']=tabs
 (E/'artifacts/phase2_derived_analysis.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({k:v for k,v in out.items() if k not in ['hyde_off','hyde_on_rrf','rerank_off','rerank_on_no_cutoff','cutoff_on','cutoff_off']},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
