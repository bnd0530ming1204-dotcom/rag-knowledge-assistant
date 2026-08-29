"""Run one-variable dense, sparse, or weighted-hybrid retrieval experiments."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

ROOT=Path(__file__).resolve().parents[2]; EVAL=ROOT/'evaluation_v2'
sys.path.insert(0,str(ROOT))
from evaluation_v2.runners.baseline_runner import entity, metrics, printable
from utils.embedding_utils import generate_embeddings
from utils.milvus_utils import create_hybrid_search_requests, get_milvus_client, hybrid_search

class VectorDatabaseUnavailable(RuntimeError): pass
class RetrievalFailed(RuntimeError): pass

def pct(v,p):
 v=sorted(v); x=(len(v)-1)*p; lo=int(x); hi=min(lo+1,len(v)-1); return round(v[lo]*(hi-x)+v[hi]*(x-lo),3)

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--mode',choices=['dense','sparse','hybrid'],required=True); ap.add_argument('--collection',required=True); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--limit',type=int,default=5); ap.add_argument('--dataset',type=Path,default=EVAL/'dataset/dataset_v2_frozen.json'); a=ap.parse_args()
 raw_dataset=a.dataset.read_bytes(); ds=json.loads(raw_dataset); mf=json.loads((EVAL/'artifacts/manifest_frozen.json').read_text(encoding='utf-8'))
 client=get_milvus_client()
 try: client.load_collection(a.collection)
 except Exception as exc: raise VectorDatabaseUnavailable(f'cannot load {a.collection}: {exc}') from exc
 rows=[]; lat=[]
 for c in ds['cases']:
  t=time.perf_counter(); emb=generate_embeddings([c['query']]); embed_ms=(time.perf_counter()-t)*1000; s=time.perf_counter()
  if a.mode=='hybrid':
   req=create_hybrid_search_requests(emb['dense'][0],emb['sparse'][0],limit=a.limit); raw=hybrid_search(client,a.collection,req,ranker_weights=(.8,.2),limit=a.limit,output_fields=['chunk_id','content','title','file_title','parent_title'])
  else:
   field='dense_vector' if a.mode=='dense' else 'sparse_vector'; metric='COSINE' if a.mode=='dense' else 'IP'; vector=emb[a.mode][0]
   raw=client.search(collection_name=a.collection,data=[vector],anns_field=field,limit=a.limit,search_params={'metric_type':metric},output_fields=['chunk_id','content','title','file_title','parent_title'])
  if raw is None: raise RetrievalFailed(f'{a.mode} retrieval returned error sentinel, not NO_RESULT')
  search_ms=(time.perf_counter()-s)*1000; docs=[entity(x) for x in (raw[0] if raw else [])]; total=embed_ms+search_ms; lat.append(total)
  rows.append({'query_id':c['query_id'],'query':c['query'],'category':c['category'],'tags':c.get('tags',[]),'answerable':c['answerable'],'relevant_documents':c['relevant_documents'],'relevant_locators':c['relevant_locators'],'results':printable(docs),'metrics':metrics(docs,c['relevant_locators']) if c['answerable'] else None,'latency_ms':{'embedding':round(embed_ms,3),'search':round(search_ms,3),'total':round(total,3)}})
 ans=[r for r in rows if r['answerable']]; names=['recall@1','recall@3','recall@5','mrr@5']; agg={n:sum(r['metrics'][n] for r in ans)/len(ans) for n in names}; by={}
 for cat in sorted({r['category'] for r in ans}):
  z=[r for r in ans if r['category']==cat]; by[cat]={'query_count':len(z),**{n:sum(r['metrics'][n] for r in z)/len(z) for n in names}}
 artifact={'run_id':f"ablation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}",'experiment':'ordinary_'+a.mode,'dataset_status':ds.get('status'),'dataset_sha256':hashlib.sha256(raw_dataset).hexdigest(),'corpus_manifest_sha256':mf['corpus_manifest_sha256'],'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'collection':a.collection,'config':{'mode':a.mode,'limit':a.limit,'weights':[.8,.2] if a.mode=='hybrid' else None},'metrics':agg,'metrics_by_category':by,'latency':{'p50_ms':pct(lat,.5),'p95_ms':pct(lat,.95),'mean_ms':round(mean(lat),3)},'queries':rows}
 a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'output':str(a.output),'metrics':agg,'latency':artifact['latency']},indent=2))
if __name__=='__main__': main()
