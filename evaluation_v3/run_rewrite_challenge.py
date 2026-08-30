import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.rewrite_decision import decide_rewrite

ROOT=Path(__file__).parent
def main():
    data=json.loads((ROOT/"rewrite_challenge.json").read_text(encoding="utf-8")); rows=[]
    for case in data["cases"]:
        result=decide_rewrite(case["query"],case["history"],"conditional")
        rows.append({**case,"predicted":result.required,"reason":result.reason,"correct":result.required==case["rewrite_required"]})
    required=[x for x in rows if x["rewrite_required"]]; unnecessary=[x for x in rows if not x["rewrite_required"] and x["predicted"]]
    print(json.dumps({"rewrite_required_accuracy":sum(x["correct"] for x in required)/len(required),
                      "unnecessary_rewrite_rate":len(unnecessary)/sum(not x["rewrite_required"] for x in rows),
                      "rewrite_drift_cases":unnecessary,"rows":rows},ensure_ascii=False,indent=2))
if __name__=="__main__": main()
