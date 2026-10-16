"""Offline replay of saved live outputs; never constructs a provider or calls a model."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import argparse
import json
from .run_statement_regressions import CapturedEvidence,CapturedAdvocates
from ryde_resolve.execution import implementation_digest
from ryde_resolve.orchestrator import RydeOrchestrator
from ryde_resolve.ui import render_html


class SavedJudge:
    mode='teammate_json'
    def __init__(self,proposal):self.proposal=deepcopy(proposal)
    def __call__(self,*_):return deepcopy(self.proposal)


def revalidate(source,output):
    source=Path(source);output=Path(output)
    if (output/'revalidation.json').exists():raise ValueError('Choose a new output directory; retain previous attempts.')
    data=json.loads(source.read_text());output.mkdir(parents=True,exist_ok=True)
    results=[]
    for row in data['results']:
        old=row['run'];s=old['snapshot'];args=old['arguments']
        if not isinstance(old.get('judge_initial_proposal'),dict):raise ValueError('No saved Judge proposal for '+row['exercise_id'])
        run=RydeOrchestrator(CapturedEvidence(s),CapturedAdvocates(s,args),SavedJudge(old['judge_initial_proposal']),issue_guidance=True).run(s['case_id'])
        expected=deepcopy(row['expected'])
        results.append({'exercise_id':row['exercise_id'],'expected':expected,'source_run_id':old['run_id'],
            'valid_expected_result':not run['validation_errors'] and run['ruling']['decision']==expected['decision'] and run['ruling']['refund_amount']==expected['refund_amount'],'run':run})
    report={'kind':'offline revalidation of retained live model outputs under conservative source/summary corrections',
        'runtime_implementation':implementation_digest(),'source_sha256':sha256(source.read_bytes()).hexdigest(),
        'boundary':'No fresh model calls. All Advocate and Judge outputs are replayed. Formal acceptance after conservative program corrections is not raw-model success or semantic proof. The final code has not been freshly sampled end to end.',
        'summary':{'cases':len(results),'valid_expected_results':sum(r['valid_expected_result'] for r in results),
            'provider_calls':sum(r['run']['execution_usage']['provider_calls'] for r in results)},'results':results}
    (output/'revalidation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    html=render_html([r['run'] for r in results],output/'ryde-evaluation.html')
    text=html.read_text().replace('<body>','<body><p style="padding:16px;background:#fff3cd;color:#332701"><b>离线复验报告：</b>沿用本轮已保存的真实模型输出，展示程序保守修正后的检查结果；本报告未重新调用模型，不代表新版本全流程已重新跑通。</p>',1)
    html.write_text(text)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();report=revalidate(args.source,args.output)
    print(json.dumps(report['summary']))
    return 0 if all(r['valid_expected_result'] for r in report['results']) else 1


if __name__=='__main__':raise SystemExit(main())
