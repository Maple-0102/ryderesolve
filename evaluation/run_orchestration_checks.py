"""Reproducible scripted failure/recovery comparison, explicitly not an LLM benchmark."""
from copy import deepcopy
import argparse
import json
from pathlib import Path
import tempfile
from ryde_resolve.agents import AgentError,ROOT
from ryde_resolve.execution import CheckpointStore
from ryde_resolve.orchestrator import RydeOrchestrator
from ryde_resolve.evidence import EvidenceGateway
from ryde_resolve.contracts import check_judge
from .robustness_suite import build_robustness_exercises
from ryde_resolve.policy_v21 import application

SOURCE=ROOT/'outputs/policy-v21-2026-10-15/fare-replayed-advocates/DISP-003.run.json'


def run_checks():
    source=json.loads(SOURCE.read_text(encoding='utf-8'))
    class Advocate:
        mode='scripted_provider'
        def __init__(self):self.calls=0
        def __call__(self,s,side,rnd,opponent):
            self.calls+=1;return deepcopy(source['arguments'][rnd][side])
    class Judge:
        mode='scripted_provider'
        def __init__(self):self.calls=0
        def __call__(self,s,a,c):
            self.calls+=1
            if self.calls==1:raise AgentError('VERTEX_HTTP_400')
            return deepcopy(source['judge_proposal'])
    outcomes=[]
    for durable in (False,True):
        a,j=Advocate(),Judge()
        with tempfile.TemporaryDirectory() as d:
            kwargs={'advocate_runner':a,'judge_runner':j}
            if durable:kwargs['checkpoint_store']=CheckpointStore(d)
            runner=RydeOrchestrator(**kwargs)
            failed=runner.run('DISP-003')
            recovered=runner.run('DISP-003',**({'resume':failed['run_id']} if durable else {}))
            assert failed['execution_status']=='failed' and not recovered['validation_errors']
            assert recovered['ruling']['refund_amount']==4.5
            outcomes.append({'strategy':'durable_resume' if durable else 'restart_entire_case',
                'scripted_advocate_calls':a.calls,'scripted_judge_calls':j.calls,'total_scripted_calls':a.calls+j.calls,
                'first_status':failed['execution_status'],'final_status':recovered['execution_status'],
                'reused_steps':recovered['execution_usage']['reused_steps'],
                'original_failure_retained':any(e.get('error')=='VERTEX_HTTP_400' for e in recovered['communication_log'])})
    cases=[]
    for x in build_robustness_exercises():
        app=application(x['snapshot']);actual={'decision':app['permitted_decision'] or 'escalate',
            'refund_amount':app['refundable_amount_cents']/100 if app['refundable_amount_cents'] is not None else None}
        cases.append({'exercise_id':x['exercise_id'],'snapshot_id':x['snapshot']['snapshot_id'],
                      'expected':x['expected'],'actual_policy_application':actual,'matched':actual==x['expected']})
    return {'kind':'scripted failure injection and deterministic policy regression','model_calls':0,
        'model_quality_measured':False,'comparison':outcomes,'policy_regression':cases,
        'policy_regression_matches':sum(x['matched'] for x in cases),
        'boundary':'Scripted call savings are not measured cloud cost savings. Policy expectations are team-written development checks, not official gold or independent accuracy. Other fault paths are covered by tests/test_execution.py.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    report=run_checks();args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'comparison':report['comparison'],'policy_regression_matches':report['policy_regression_matches'],'total':len(report['policy_regression'])},ensure_ascii=False))
    return 0 if all(x['matched'] for x in report['policy_regression']) else 1

if __name__=='__main__':raise SystemExit(main())
