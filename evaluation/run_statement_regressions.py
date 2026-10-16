"""Fresh Judge calls on retained Advocate transcripts, never a fresh multi-agent run."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import argparse
import json
from ryde_resolve.execution import CheckpointStore,RunLimits,implementation_digest,digest
from ryde_resolve.orchestrator import RydeOrchestrator
from ryde_resolve.vertex import VertexConfig,VertexJudge

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_SOURCE=ROOT/'outputs/workflow-followups-2026-10-16/comparison/comparison.json'


class CapturedEvidence:
    def __init__(self,snapshot):self.snapshot=deepcopy(snapshot)
    def prepare(self,case_id):return deepcopy(self.snapshot)


class CapturedAdvocates:
    mode='teammate_json'
    def __init__(self,snapshot,arguments):
        self.document={'snapshot_id':snapshot['snapshot_id'],'case_id':snapshot['case_id'],**deepcopy(arguments)}
    def __call__(self,snapshot,side,rnd,opponent=None):
        from ryde_resolve.agents import AgentError
        if self.document['snapshot_id']!=snapshot['snapshot_id']:raise AgentError('ADVOCATE_SNAPSHOT_MISMATCH')
        return deepcopy(self.document[rnd][side])


def run_regressions(source,output,judge_factory):
    source=Path(source);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    target=output/'judge-regressions.json'
    if target.exists():raise ValueError('Choose a new output directory; retain previous attempts.')
    original=json.loads(source.read_text());report={'kind':'same-transcript Judge development regressions',
        'runtime_implementation':implementation_digest(),'source_report_sha256':digest(original),'results':[],
        'boundary':'Retained development cases. Four Advocate outputs replayed per case; only Judge calls are fresh. No retries, repairs, extra reviewer, training or held-out accuracy claim. Original failed records remain unchanged.'}
    for row in original['results']:
        old=row['run'] if 'run' in row else row['variants']['debate_judge']['run'];snapshot=old['snapshot']
        run=RydeOrchestrator(CapturedEvidence(snapshot),CapturedAdvocates(snapshot,old['arguments']),judge_factory(),
            checkpoint_store=CheckpointStore(output/'checkpoints'),limits=RunLimits(max_calls=1,transient_retries=0,judge_repairs=0)).run(snapshot['case_id'])
        expected=row['expected'];actual=run['ruling']
        report['results'].append({'exercise_id':row['exercise_id'],'snapshot_id':snapshot['snapshot_id'],
            'before_errors':old['validation_errors'],'expected':expected,
            'valid_expected_result':not run['validation_errors'] and actual['decision']==expected['decision'] and actual['refund_amount']==expected['refund_amount'],
            'run':run})
        report['summary']={'cases':len(report['results']),'valid_expected_results':sum(r['valid_expected_result'] for r in report['results']),
            'provider_calls':sum(r['run']['execution_usage']['provider_calls'] for r in report['results']),
            'recorded_tokens':sum(r['run']['execution_usage']['recorded_tokens'] for r in report['results'])}
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'case':row['exercise_id'],'passed':report['results'][-1]['valid_expected_result'],
            'decision':actual['decision'],'errors':run['validation_errors']},ensure_ascii=False),flush=True)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--live',action='store_true');p.add_argument('--source',type=Path,default=DEFAULT_SOURCE);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not a.live:p.error('Explicit --live required; one Judge call per retained case, replayed Advocates, no retries or repairs.')
    config=replace(VertexConfig.from_env(),thinking_level='LOW');r=run_regressions(a.source,a.output,lambda:VertexJudge(config))
    return 0 if all(x['valid_expected_result'] for x in r['results']) else 1

if __name__=='__main__':raise SystemExit(main())
