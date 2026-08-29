"""Evaluate the pre-locked calibration rule; never searches thresholds on Frozen Test."""
import argparse, hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from evaluation_v2.reliability.evidence_gate import RULE_VERSION, THRESHOLD, evaluate
def assess(artifact):
 rows=[]; tp=fp=tn=fn=0
 for q in artifact['queries']:
  dec=evaluate(q['results']); actual=q['answerable']
  tp+=actual and dec.accepted; fn+=actual and not dec.accepted; fp+=(not actual) and dec.accepted; tn+=(not actual) and not dec.accepted
  rows.append({'query_id':q['query_id'],'answerable':actual,'top_score':dec.top_score,'evidence_gate_result':dec.status,'answer':dec.answer,'top_document':q['results'][0]['document_id'] if q['results'] else None,'candidate_count':len(q['results']),'error':None,'fallback':False})
 return {'rule_version':RULE_VERSION,'threshold':THRESHOLD,'confusion':{'true_accept':tp,'false_accept':fp,'true_reject':tn,'false_reject':fn},'accept_precision':tp/(tp+fp) if tp+fp else 0,'answerable_accept_recall':tp/(tp+fn) if tp+fn else 0,'no_answer_rejection_rate':tn/(tn+fp) if tn+fp else 0,'rows':rows}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--input',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--role',choices=['calibration','frozen_test'],required=True); a=ap.parse_args(); raw=a.input.read_bytes(); d=json.loads(raw); out=assess(d); out['role']=a.role; out['input_sha256']=hashlib.sha256(raw).hexdigest(); out['threshold_search_performed']=False; a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({k:v for k,v in out.items() if k!='rows'},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
