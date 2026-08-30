"""Evaluate recorded production-compatible generation rows without changing V2."""
import argparse, json, statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation_v3.failure_analysis import classify
from evaluation_v3.generation_metrics import evaluate_generation


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--input",type=Path,required=True); parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(); source=json.loads(args.input.read_text(encoding="utf-8"))
    rows=[]
    for item in source.get("queries", source if isinstance(source,list) else []):
        row=evaluate_generation(item); row["failures"]=classify(row); rows.append(row)
    valid=[r for r in rows if not r.get('error')]; answerable=[r for r in valid if r.get('answerable')]; no_answer=[r for r in valid if not r.get('answerable')]
    artifact={"status":"GENERATION_EVALUATION_V3_RESCored_NO_NEW_LLM_CALLS",
              "metric_warning":"deterministic/reference-based diagnostic proxies; not human accuracy, semantic accuracy, or RAGAS gold-standard",
              "metrics":{k:statistics.mean(r[k] for r in answerable) for k in ('answer_correctness','faithfulness','citation_correctness','context_relevance')},
              "no_answer":{k:sum(r['no_answer_behavior']==k for r in no_answer) for k in ('SUPPORTED_REFUSAL','UNSUPPORTED_FACTUAL_CLAIM','UNCERTAIN_NEEDS_REVIEW')},
              "queries":rows}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__": main()
