"""Five fresh full-pipeline development cases, with expectations kept outside agent inputs."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import argparse
import json
from .robustness_suite import build_robustness_exercises
from .run_statement_regressions import CapturedEvidence
from ryde_resolve.execution import CheckpointStore, RunLimits, implementation_digest
from ryde_resolve.orchestrator import RydeOrchestrator
from ryde_resolve.teammate_advocate import TeammateAdvocate
from ryde_resolve.ui import render_html
from ryde_resolve.vertex import VertexConfig, VertexJudge

ROOT=Path(__file__).resolve().parents[1]
SELECTED=('R21-ROUTE-ORIGINAL','R21-NOSHOW-ORIGINAL','R21-FARE-ORIGINAL',
          'R21-FARE-NOTIFIED','R21-FARE-NOTICE-MISSING')


def selected_exercises():
    rows={r['exercise_id']:r for r in build_robustness_exercises()}
    return [rows[k] for k in SELECTED]


def run_fresh(output, advocate_factory, judge_factory, *, exercises=None):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    target=output/'fresh-pipeline.json'
    if target.exists():raise ValueError('Choose a new output directory; retain previous attempts.')
    runtime=[*ROOT.joinpath('ryde_resolve').glob('*.py'),*ROOT.joinpath('prompts').glob('*.md'),*ROOT.joinpath('schemas').glob('*.json')]
    for package in ('ryderesolve-advocate-system','ryderesolve-evidence-tools'):
        runtime.extend(p for p in (ROOT/'vendor'/package).rglob('*') if p.suffix in ('.py','.txt','.json') and '__pycache__' not in p.parts)
    report={'kind':'fresh five-case full-pipeline development evaluation',
        'runtime_implementation':implementation_digest(),
        'runtime_files':{str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in sorted(runtime)},
        'settings':{'max_calls_per_case':5,'max_recorded_tokens_per_case':180000,'thinking_level':'LOW for live CLI',
                    'transient_retries':0,'judge_repairs':0,'reviewer':False,'issue_guidance':True,'parallel_advocates':False},
        'boundary':'Three organizer samples and two existing synthetic notification counterfactuals. All four Advocate calls and Judge are fresh. No held-out accuracy, training, independent gold, or semantic-correctness claim. Expected labels and handwritten Advocate fixtures are never passed to agents.',
        'results':[]}
    rows=selected_exercises() if exercises is None else exercises
    for row in rows:
        exercise=row['exercise_id'];snapshot=deepcopy(row['snapshot'])
        print(json.dumps({'event':'case_started','exercise_id':exercise}),flush=True)
        run=RydeOrchestrator(CapturedEvidence(snapshot),advocate_factory(),judge_factory(),
            checkpoint_store=CheckpointStore(output/'checkpoints'),issue_guidance=True,
            limits=RunLimits(max_calls=5,max_seconds=900,max_recorded_tokens=180000,transient_retries=0,judge_repairs=0)).run(snapshot['case_id'])
        actual=run['ruling'];expected=deepcopy(row['expected'])
        result={'exercise_id':exercise,'source_origin':snapshot['audit']['data_origin'],'expected':expected,
            'valid_expected_result':not run['validation_errors'] and actual['decision']==expected['decision'] and actual['refund_amount']==expected['refund_amount'],
            'run':run}
        report['results'].append(result)
        report['summary']={'cases':len(report['results']),
            'valid_expected_results':sum(r['valid_expected_result'] for r in report['results']),
            'provider_calls':sum(r['run']['execution_usage']['provider_calls'] for r in report['results']),
            'recorded_tokens':sum(r['run']['execution_usage']['recorded_tokens'] for r in report['results'])}
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        render_html([r['run'] for r in report['results']],output/'ryde-evaluation.html')
        print(json.dumps({'event':'case_finished','exercise_id':exercise,'passed':result['valid_expected_result'],
            'decision':actual['decision'],'amount':actual['refund_amount'],'errors':run['validation_errors'],
            'usage':run['execution_usage']},ensure_ascii=False),flush=True)
        systemic=('VERTEX_ADC_','VERTEX_INVALID_CONFIG','VERTEX_HTTP_401','VERTEX_HTTP_403','VERTEX_HTTP_404','VERTEX_HTTP_429')
        if any(any(code in error for code in systemic) for error in run['validation_errors']):
            report['stopped_early']='provider authentication/configuration/access/quota failure; remaining cases not attempted'
            target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            break
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    if not args.live:parser.error('Explicit --live required; at most 25 fresh model calls, no retries or repairs.')
    config=replace(VertexConfig.from_env(),thinking_level='LOW')
    class ProgressClient(VertexJudge):
        def generate(self,*args,**kwargs):
            print(json.dumps({'event':'provider_call_started'}),flush=True)
            try:return super().generate(*args,**kwargs)
            finally:print(json.dumps({'event':'provider_call_finished','usage':self.last_metadata.get('usage',{})}),flush=True)
    report=run_fresh(args.output,lambda:TeammateAdvocate(ProgressClient(config)),lambda:ProgressClient(config))
    print(json.dumps({'event':'evaluation_finished','summary':report['summary']},ensure_ascii=False),flush=True)
    return 0 if len(report['results'])==len(SELECTED) and all(r['valid_expected_result'] for r in report['results']) else 1


if __name__=='__main__':raise SystemExit(main())
