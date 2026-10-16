"""Two explicitly paid development probes; no claim of independent model accuracy."""
from copy import deepcopy
from dataclasses import replace
import argparse
import json
from pathlib import Path
from ryde_resolve.agents import AgentError, ROOT
from ryde_resolve.contracts import check_judge
from ryde_resolve.reviewer import InferenceReviewer, validate_review
from ryde_resolve.vertex import VertexConfig, VertexJudge


def run_probes():
    source = json.loads((ROOT/'outputs/policy-v21-2026-10-15/fare-replayed-advocates/DISP-003.run.json').read_text())
    snapshot, arguments = source['snapshot'], source['arguments']
    good = source['judge_proposal']
    bad = deepcopy(good)
    bad['findings'][0]['finding'] = 'System notification records confirm the rider was notified of the increased surge before pickup.'
    reviewer = InferenceReviewer(VertexJudge(replace(VertexConfig.from_env(), thinking_level='LOW')))
    report = {'kind': 'two live inference-reviewer development probes', 'model_quality_measured': True,
              'boundary': 'One supplied Fare case and a team-seeded inference fault. Same provider/model, not independent ground truth or an accuracy benchmark.',
              'model': reviewer.model.config.model, 'thinking_level': 'LOW', 'results': []}
    for label, proposal, expected in [('saved_valid_proposal',good,True),('seeded_false_notice_inference',bad,False)]:
        errors = check_judge(snapshot,proposal,arguments)[0]
        row = {'probe':label,'expected_review_pass':expected,'candidate_contract_errors':errors,
               'candidate':proposal,'review':None,'review_pass':None,'error':None}
        if errors:
            row['error']='PROBE_CANDIDATE_PRECHECK_FAILED'
        else:
            try:
                row['review']=reviewer(snapshot,arguments,source['calculations'],proposal)
                row['review_pass']=validate_review(snapshot,arguments,proposal,row['review'])
            except AgentError as exc:row['error']=str(exc)
            row['transport']=deepcopy(reviewer.last_metadata)
        row['matched']=row['error'] is None and row['review_pass']==expected
        report['results'].append(row)
        print(json.dumps({'probe':label,'review_pass':row['review_pass'],'error':row['error'],'matched':row['matched']},ensure_ascii=False),flush=True)
    report['all_matched']=all(row['matched'] for row in report['results'])
    report['attempted_model_calls']=sum('transport' in row for row in report['results'])
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    report=run_probes()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return 0 if report['all_matched'] else 1

if __name__=='__main__':raise SystemExit(main())
