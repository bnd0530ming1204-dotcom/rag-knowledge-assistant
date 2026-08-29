"""Build the project-owned structured trace from final frozen retrieval + locked gate."""
import json, uuid
from difflib import SequenceMatcher
from pathlib import Path
E=Path(__file__).resolve().parents[1]
def main():
 r=json.loads((E/'artifacts/phase3_candidate10_noextras.json').read_text(encoding='utf-8')); g=json.loads((E/'artifacts/phase3_frozen_gate_once.json').read_text(encoding='utf-8')); gd={x['query_id']:x for x in g['rows']}; run='phase3-final-'+uuid.uuid4().hex[:10]; rows=[]
 for q in r['queries']:
  gate=gd[q['query_id']]; rows.append({'run_id':run,'query_id':q['query_id'],'retrieval_config':{'embedding':'BAAI/bge-m3','hybrid_weights':[.8,.2],'candidate_budget':10,'final_top_k':5,'hyde':False,'rerank':False,'cutoff':False,'parent_heading_compatible':True},'embedding_latency_ms':q['latency_ms']['embedding'],'milvus_latency_ms':q['latency_ms']['search'],'candidate_count':len(q['results']),'top_document':gate['top_document'],'top_score':gate['top_score'],'evidence_gate_result':gate['evidence_gate_result'],'total_retrieval_latency_ms':q['latency_ms']['total'],'hyde_used':False,'hyde_latency_ms':None,'error':None,'fallback':False})
 (E/'artifacts/phase3_structured_trace.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf-8')
 cal=json.loads((E/'calibration/calibration_v1.json').read_text(encoding='utf-8')); frozen=json.loads((E/'dataset/dataset_v2_frozen.json').read_text(encoding='utf-8')); pairs=[]
 for c in cal['cases']:
  best=max((SequenceMatcher(None,c['query'],f['query']).ratio(),f['query_id']) for f in frozen['cases']); pairs.append({'calibration_query_id':c['query_id'],'max_character_similarity':round(best[0],4),'closest_frozen_query_id':best[1]})
 leak={'exact_duplicates':sum(c['query'] in {f['query'] for f in frozen['cases']} for c in cal['cases']),'max_similarity':max(x['max_character_similarity'] for x in pairs),'pairs':pairs,'manual_design_note':'Calibration questions target distinct facts or unsupported attributes and were created without retrieval outputs.'}
 (E/'artifacts/phase3_calibration_leakage_audit.json').write_text(json.dumps(leak,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'trace_rows':len(rows),'leakage':{k:v for k,v in leak.items() if k!='pairs'}},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
