"""Failure injection: paid-provider-shaped fakes, never a network or model call."""
from copy import deepcopy
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from ryde_resolve.agents import AgentError
from ryde_resolve.evidence import EvidenceGateway
from ryde_resolve.execution import CheckpointStore,RunLimits
from ryde_resolve.orchestrator import RydeOrchestrator
from ryde_resolve.mock_agents import OfflineAdvocate,OfflineJudge
from ryde_resolve.ui import render_html
from test_policy_v21 import completed,arguments,variant


class Advocate:
    mode='test_provider'
    def __init__(self):self.calls=0;self.last_metadata={}
    def __call__(self,*args):
        self.calls+=1;self.last_metadata={'usage':{'totalTokenCount':10}}
        return OfflineAdvocate()(*args)


class Judge:
    mode='test_provider'
    def __init__(self):self.calls=0;self.failure=None;self.last_metadata={}
    def __call__(self,s,args,c):
        self.calls+=1
        if self.failure:raise self.failure
        self.last_metadata={'usage':{'totalTokenCount':20}}
        return completed(s,args)


class RecoverableJudge(Judge):
    def __init__(self):super().__init__();self.repairs=0;self.semantic=False;self.change_decision=False
    def __call__(self,s,args,c):
        out=super().__call__(s,args,c)
        if self.semantic:out['refund_amount']=9
        else:out['case_analysis']['sides']['rider']['argument_refs']=out['case_analysis']['sides']['rider']['argument_refs'][:1]
        return out
    def repair(self,s,args,c,previous,errors):
        self.repairs+=1
        out=completed(s,args)
        if self.change_decision:out.update(decision='escalate',refund_amount=None,escalate_to_human=True,uncertainties=['Repair changed decision.'])
        return out


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=CheckpointStore(self.temp.name);self.a=Advocate();self.j=Judge()
    def runner(self,**kw):
        return RydeOrchestrator(advocate_runner=self.a,judge_runner=self.j,checkpoint_store=self.store,wait=lambda _:None,**kw)

    def test_failed_judge_resumes_without_regenerating_four_advocates(self):
        self.j.failure=AgentError('VERTEX_HTTP_400')
        first=self.runner().run('DISP-003')
        self.assertEqual(first['execution_status'],'failed');self.assertEqual(self.a.calls,4)
        self.assertEqual(first['review_reason_types'],['transport_error'])
        self.j.failure=None
        restored=self.runner().run('DISP-003',resume=first['run_id'])
        self.assertEqual(restored['execution_status'],'completed',restored['validation_errors'])
        self.assertEqual((self.a.calls,self.j.calls),(4,2))
        self.assertEqual(restored['ruling']['refund_amount'],4.5)
        self.assertEqual(restored['execution_usage']['provider_calls'],6)
        self.assertEqual(restored['execution_usage']['unknown_usage_calls'],1)
        self.assertTrue(any(e.get('reused_from_checkpoint') for e in restored['communication_log']))
        self.assertTrue(any(e.get('error')=='VERTEX_HTTP_400' for e in restored['communication_log']))

    def test_missing_finding_condition_citations_get_one_validated_repair(self):
        class CitationJudge(RecoverableJudge):
            def __call__(judge,s,args,c):
                out=Judge.__call__(judge,s,args,c)
                out['findings'][0]['evidence_refs']=[r for r in out['findings'][0]['evidence_refs'] if r!='E-018']
                return out
        judge=CitationJudge()
        r=RydeOrchestrator(advocate_runner=self.a,judge_runner=judge).run('DISP-003')
        self.assertFalse(r['validation_errors'],r['validation_errors'])
        self.assertEqual(judge.repairs,1)
        self.assertIn('FINDING_CONDITION_BASIS_MISMATCH',r['judge_raw_validation_errors'])
        self.assertEqual(r['ruling']['refund_amount'],4.5)
        self.assertFalse(r['first_pass_valid'])

    def test_completed_resume_calls_no_provider_and_revalidates_candidates(self):
        r=self.runner().run('DISP-003');old=(self.a.calls,self.j.calls)
        again=self.runner().run('DISP-003',resume=r['run_id'])
        self.assertFalse(again['validation_errors']);self.assertEqual(old,(self.a.calls,self.j.calls))
        self.assertEqual(again['execution_usage']['provider_calls'],5)
        text=render_html([again],Path(self.temp.name)/'resumed.html').read_text()
        self.assertIn('reused',text)

    def test_interruption_is_persisted_and_four_completed_calls_survive(self):
        self.j.failure=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.runner().run('DISP-003')
        paths=list(Path(self.temp.name).glob('*.json'));self.assertEqual(len(paths),1)
        stored=self.store.load(paths[0].stem)
        self.assertEqual(stored['result']['execution_status'],'interrupted')
        self.j.failure=None
        r=self.runner().run('DISP-003',resume=paths[0].stem)
        self.assertEqual(self.a.calls,4);self.assertFalse(r['validation_errors'])
        self.assertEqual(r['execution_usage']['unknown_usage_calls'],1)

    def test_snapshot_and_code_and_model_changes_reject_before_provider(self):
        first=self.runner().run('DISP-003');calls=(self.a.calls,self.j.calls)
        changed=variant(first['snapshot'],lambda raw:raw['dispute_ticket'].update(description='Changed case record'))
        class Gateway:
            def prepare(self,_):return deepcopy(changed)
        r=self.runner(evidence_gateway=Gateway()).run('DISP-003',resume=first['run_id'])
        self.assertIn('CHECKPOINT_INPUT_OR_VERSION_MISMATCH',r['validation_errors'])
        with patch('ryde_resolve.execution.implementation_digest',return_value='different prompt/schema/code'):
            r=self.runner().run('DISP-003',resume=first['run_id'])
        self.assertIn('CHECKPOINT_INPUT_OR_VERSION_MISMATCH',r['validation_errors'])
        self.j.cache_identity='new model config'
        r=self.runner().run('DISP-003',resume=first['run_id'])
        self.assertIn('CHECKPOINT_INPUT_OR_VERSION_MISMATCH',r['validation_errors'])
        self.assertEqual(calls,(self.a.calls,self.j.calls))

    def test_limits_cover_all_prior_calls_after_resume(self):
        r=self.runner(limits=RunLimits(max_calls=4)).run('DISP-003')
        self.assertIn('RUN_CALL_BUDGET_EXHAUSTED',r['validation_errors']);self.assertEqual(self.j.calls,0)
        r=self.runner(limits=RunLimits(max_calls=4)).run('DISP-003',resume=r['run_id'])
        self.assertEqual((self.a.calls,self.j.calls),(4,0))
        self.assertIn('RUN_CALL_BUDGET_EXHAUSTED',r['validation_errors'])

    def test_token_and_time_admission(self):
        r=self.runner(limits=RunLimits(max_recorded_tokens=15)).run('DISP-003')
        self.assertIn('RUN_TOKEN_BUDGET_EXHAUSTED',r['validation_errors']);self.assertEqual(self.a.calls,2)
        ticks=[0]
        def clock():ticks[0]+=1;return ticks[0]
        r=self.runner(clock=clock,limits=RunLimits(max_seconds=1)).run('DISP-003')
        self.assertIn('RUN_TIME_BUDGET_EXHAUSTED',r['validation_errors'])

    def test_http_400_and_timeout_not_retried_but_503_is_bounded(self):
        for code,expected in [('VERTEX_HTTP_400',1),('VERTEX_CONNECTION_OR_TIMEOUT',1),('VERTEX_HTTP_503',2)]:
            with self.subTest(code=code):
                self.j.calls=0;self.j.failure=AgentError(code)
                r=self.runner().run('DISP-003');self.assertEqual(self.j.calls,expected)
                self.assertEqual(r['execution_status'],'failed')

    def test_single_coverage_repair_preserves_first_failure(self):
        self.j=RecoverableJudge();r=self.runner().run('DISP-003')
        self.assertFalse(r['validation_errors'],r['validation_errors']);self.assertEqual(self.j.repairs,1)
        self.assertFalse(r['first_pass_valid']);self.assertTrue(r['judge_raw_validation_errors'])
        self.assertTrue(r['repair_history'][0]['accepted']);self.assertEqual(r['ruling']['refund_amount'],4.5)

    def test_semantic_error_is_not_sent_to_structural_repair(self):
        self.j=RecoverableJudge();self.j.semantic=True;r=self.runner().run('DISP-003')
        self.assertEqual(self.j.repairs,0);self.assertEqual(r['business_decision_status'],'unavailable')
        self.assertTrue(r['judge_initial_proposal']);self.assertIsNone(r['judge_proposal'])

    def test_structural_repair_cannot_change_business_decision(self):
        self.j=RecoverableJudge();self.j.change_decision=True;r=self.runner().run('DISP-003')
        self.assertIn('STRUCTURAL_REPAIR_CHANGED_BUSINESS_DECISION',r['validation_errors'])
        self.assertEqual(r['execution_status'],'failed')

    def test_corrupt_checkpoint_does_not_trigger_model_calls(self):
        r=self.runner().run('DISP-003');path=self.store.path(r['run_id'])
        data=json.loads(path.read_text());data['payload']['usage']['provider_calls']=0;path.write_text(json.dumps(data))
        calls=(self.a.calls,self.j.calls)
        with self.assertRaisesRegex(AgentError,'INTEGRITY'):self.runner().run('DISP-003',resume=r['run_id'])
        self.assertEqual(calls,(self.a.calls,self.j.calls))
        with self.assertRaises(AgentError):self.store.path('../escape')

    def test_business_human_review_different_from_technical_failure_in_ui(self):
        r=RydeOrchestrator().run('DISP-001')
        self.assertEqual(r['execution_status'],'completed');self.assertIn('policy_gate',r['review_reason_types'])
        self.j.failure=AgentError('VERTEX_HTTP_400');failed=self.runner().run('DISP-003')
        text=render_html([r,failed],Path(self.temp.name)/'view.html').read_text()
        self.assertIn('政策要求人工裁决',text);self.assertIn('流程失败／待恢复',text)
        self.assertEqual(failed['business_decision_status'],'unavailable')

    def test_checkpoint_private_permissions(self):
        r=self.runner().run('DISP-003')
        import os
        if os.name!='nt':self.assertEqual(self.store.path(r['run_id']).stat().st_mode & 0o777,0o600)
