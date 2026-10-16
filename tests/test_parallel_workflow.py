"""Real concurrency and failure injection with provider-shaped fakes, no network."""
from copy import deepcopy
import tempfile
from threading import Barrier, Lock
from pathlib import Path
import unittest
from ryde_resolve.agents import AgentError
from ryde_resolve.execution import CheckpointStore,RunLimits
from ryde_resolve.mock_agents import OfflineAdvocate
from ryde_resolve.orchestrator import RydeOrchestrator
from test_execution import Judge


class Context:
    def __init__(self):
        self.barriers={r:Barrier(2,timeout=3) for r in ('opening','response')}
        self.calls=[];self.lock=Lock();self.fail_side=None;self.malformed=None;self.retry_once=False
        self.barrier_enabled=True;self.instances=[]
    def factory(self):
        runner=ConcurrentAdvocate(self);self.instances.append(runner);return runner


class ConcurrentAdvocate:
    mode='test_provider'
    def __init__(self,ctx):self.ctx=ctx;self.last_metadata={};self.used=[]
    def __call__(self,s,side,rnd,opponent=None):
        self.used.append((side,rnd));self.last_metadata={}
        with self.ctx.lock:
            self.ctx.calls.append((side,rnd,deepcopy(opponent)))
        if self.ctx.barrier_enabled:self.ctx.barriers[rnd].wait()
        if self.ctx.fail_side==side and rnd=='opening':
            if self.ctx.retry_once:
                self.ctx.retry_once=False
                raise AgentError('VERTEX_HTTP_503')
            raise AgentError('VERTEX_HTTP_400')
        self.last_metadata={'usage':{'totalTokenCount':11},'role':side}
        out=OfflineAdvocate()(s,side,rnd,opponent)
        if self.ctx.malformed==side and rnd=='opening':out['side']='wrong'
        return out


class ParallelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=CheckpointStore(self.tmp.name);self.ctx=Context();self.j=Judge()
    def run_case(self,**kwargs):
        options={'advocate_runner':OfflineAdvocate(),'judge_runner':self.j,'checkpoint_store':self.store,
            'parallel_advocates':True,'advocate_factory':self.ctx.factory,'limits':RunLimits(transient_retries=0)}
        options.update(kwargs)
        return RydeOrchestrator(**options).run('DISP-003')
    def test_pairs_actually_overlap_and_have_independent_context_and_barriers(self):
        r=self.run_case()
        self.assertFalse(r['validation_errors'],r['validation_errors'])
        self.assertEqual(len(self.ctx.calls),4);self.assertEqual(self.j.calls,1)
        self.assertTrue(all(opponent is None for _,rnd,opponent in self.ctx.calls if rnd=='opening'))
        for side,rnd,opponent in self.ctx.calls:
            if rnd=='response':self.assertNotEqual(opponent['side'],side)
        self.assertTrue(all(len(x.used)==1 for x in self.ctx.instances))
        self.assertEqual(r['execution_usage']['provider_calls'],5)
        self.assertEqual(r['execution_usage']['recorded_tokens'],64)
        self.assertEqual(r['execution_usage']['unknown_usage_calls'],0)
        events=[e for e in r['communication_log'] if e['step'] in ('opening','response')]
        self.assertTrue(all(e['parallel_batch'] for e in events))
        self.assertTrue(all(e['transport']['role'] in e['agent'] for e in events))
    def test_failure_drains_other_branch_and_resume_reuses_successful_half(self):
        self.ctx.fail_side='rider';first=self.run_case()
        self.assertEqual(first['execution_status'],'failed');self.assertEqual(len(self.ctx.calls),2)
        self.assertEqual(first['execution_usage']['provider_calls'],2)
        self.assertEqual(first['execution_usage']['unknown_usage_calls'],1)
        self.assertIn('opening:driver',self.store.load(first['run_id'])['entries'])
        self.ctx.fail_side=None;self.ctx.barrier_enabled=False
        runner=RydeOrchestrator(advocate_runner=OfflineAdvocate(),judge_runner=self.j,checkpoint_store=self.store,
            parallel_advocates=True,advocate_factory=self.ctx.factory,limits=RunLimits(transient_retries=0))
        restored=runner.run('DISP-003',resume=first['run_id'])
        self.assertFalse(restored['validation_errors'],restored['validation_errors'])
        self.assertEqual(restored['execution_usage']['provider_calls'],6)
        self.assertEqual(len([1 for side,rnd,_ in self.ctx.calls if side=='driver' and rnd=='opening']),1)
        self.assertEqual(restored['execution_usage']['unknown_usage_calls'],1)
        again=runner.run('DISP-003',resume=first['run_id'])
        self.assertEqual(again['execution_usage']['provider_calls'],6)
    def test_budget_reserves_entire_pair_before_dispatch(self):
        r=self.run_case(limits=RunLimits(max_calls=1,transient_retries=0))
        self.assertEqual(r['execution_usage']['provider_calls'],0);self.assertEqual(self.ctx.calls,[])
        self.assertIn('RUN_CALL_BUDGET_EXHAUSTED',r['validation_errors'])
    def test_token_budget_blocks_next_pair_after_current_pair_drains(self):
        r=self.run_case(limits=RunLimits(max_recorded_tokens=1,transient_retries=0))
        self.assertEqual(len(self.ctx.calls),2)
        self.assertEqual(r['execution_usage']['recorded_tokens'],22)
        self.assertIn('RUN_TOKEN_BUDGET_EXHAUSTED',r['validation_errors']);self.assertEqual(self.j.calls,0)
    def test_invalid_opening_never_reaches_response_or_judge(self):
        self.ctx.malformed='rider';r=self.run_case()
        self.assertEqual(len(self.ctx.calls),2);self.assertEqual(self.j.calls,0)
        self.assertIn('INVALID_ADVOCATE_OUTPUT',r['validation_errors'])
    def test_only_failed_branch_retried_within_same_budget(self):
        self.ctx.fail_side='rider';self.ctx.retry_once=True
        # Disable the barriers here: a retry intentionally has only one branch.
        self.ctx.barrier_enabled=False
        original=self.ctx.factory
        def factory():
            runner=original();fn=runner.__call__
            # Clear the injected permanent failure after the first transient failure.
            class RetryAdvocate:
                mode='test_provider'
                last_metadata={}
                def __call__(adapter,*args):
                    try:return fn(*args)
                    except AgentError:
                        self.ctx.fail_side=None;raise
                    finally:adapter.last_metadata=deepcopy(runner.last_metadata)
            return RetryAdvocate()
        r=self.run_case(advocate_factory=factory,limits=RunLimits(max_calls=6,transient_retries=1),wait=lambda _:None)
        self.assertFalse(r['validation_errors'],r['validation_errors'])
        self.assertEqual(r['execution_usage']['provider_calls'],6)
        self.assertEqual(len([x for x in self.ctx.calls if x[:2]==('driver','opening')]),1)
    def test_shared_adapter_or_model_rejected_before_calls(self):
        same=self.ctx.factory()
        with self.assertRaisesRegex(AgentError,'ISOLATED'):self.run_case(advocate_factory=lambda:same)
        self.assertFalse(self.ctx.calls)
