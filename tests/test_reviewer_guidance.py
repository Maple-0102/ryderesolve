"""Optional reviewer and symmetric issue guidance, with grounded injected faults."""
from copy import deepcopy
import json
import unittest
from ryde_resolve.agents import AgentError
from ryde_resolve.evidence import EvidenceGateway
from ryde_resolve.orchestrator import RydeOrchestrator
from ryde_resolve.reviewer import CHECKS,validate_review
from ryde_resolve.teammate_advocate import TeammateAdvocate
from ryde_resolve.mock_agents import OfflineAdvocate
from test_policy_v21 import completed,arguments
from test_teammate_advocate import FakeClient
from test_execution import Judge,Advocate


def review_output(s,status='clear'):
    checks=[{'check_id':c,'status':'clear','explanation':'No seeded test fault in this check.',
             'finding_indices':[],'argument_refs':[],'evidence_refs':[],'policy_refs':[],'source_quotes':[]} for c in CHECKS]
    if status!='clear':
        ref,index=next((k,v) for k,v in s['source_index']['evidence'].items() if '/surge_pricing_log' in v['source_refs'])
        checks[0].update(status=status,explanation='Candidate says a notice occurred, but source records rider_notified=false.',finding_indices=[0],
            evidence_refs=[ref],source_quotes=[{'evidence_ref':ref,'source_ref':'/surge_pricing_log','quote':'false'}])
    return {'case_id':s['case_id'],'snapshot_id':s['snapshot_id'],'outcome':'pass' if status=='clear' else 'needs_human','checks':checks}


class Reviewer:
    mode='test_reviewer'
    def __init__(self):self.calls=0;self.status='clear';self.mutate=None
    def __call__(self,s,a,c,p):
        self.calls+=1;out=review_output(s,self.status)
        if self.mutate:self.mutate(out)
        return out


class ReviewTests(unittest.TestCase):
    def setUp(self):self.s=EvidenceGateway().prepare('DISP-003');self.a=arguments(self.s)

    def test_reviewer_prompt_contains_exact_raw_quote_catalogue_without_fact_prefix(self):
        from ryde_resolve.reviewer import InferenceReviewer
        from ryde_resolve.rule_engine import calculate_rules
        from ryderesolve_evidence.policies import source_value
        class Client:
            def generate(client,system,user,**kwargs):
                client.payload=json.loads(user)
                return review_output(self.s)
        client=Client()
        InferenceReviewer(client)(self.s,self.a,calculate_rules(self.s),completed(self.s,self.a))
        rows=client.payload['source_quote_catalogue']
        self.assertTrue(rows)
        for row in rows:
            index=self.s['source_index']['evidence'][row['evidence_ref']]
            self.assertIn(row['source_ref'],index['source_refs'])
            raw=source_value(self.s['raw'],self.s.get('policy_documents',{}),index,row['source_ref'])
            expected=raw if isinstance(raw,str) else json.dumps(raw,ensure_ascii=False,sort_keys=True)
            self.assertEqual(row['source_text'],expected)

    def test_pass_retains_candidate_and_blocks_cannot_award_money(self):
        reviewer=Reviewer();r=RydeOrchestrator(advocate_runner=Advocate(),judge_runner=Judge(),reviewer_runner=reviewer).run('DISP-003')
        self.assertEqual(r['ruling']['refund_amount'],4.5);self.assertFalse(r['validation_errors'])
        reviewer.status='issue'
        r=RydeOrchestrator(advocate_runner=Advocate(),judge_runner=Judge(),reviewer_runner=reviewer).run('DISP-003')
        self.assertFalse(r['validation_errors']);self.assertTrue(r['reviewer_blocked'])
        self.assertEqual(r['ruling']['decision'],'escalate');self.assertIsNone(r['ruling']['refund_amount'])
        self.assertEqual(r['judge_proposal']['refund_amount'],4.5)
        self.assertIn('inference_review',r['review_reason_types'])

    def test_wrong_quote_wrong_snapshot_and_unreferenced_target_rejected(self):
        out=review_output(self.s,'issue');p=completed(self.s,self.a)
        self.assertFalse(validate_review(self.s,self.a,p,out))
        for mutate in (lambda o:o.update(snapshot_id='old'),
                       lambda o:o['checks'][0]['source_quotes'][0].update(quote='a made-up excerpt'),
                       lambda o:o['checks'][0].update(finding_indices=[999]),
                       lambda o:o.update(outcome='pass'),
                       lambda o:o['checks'][0].update(policy_refs=['P-FAKE'])):
            bad=deepcopy(out);mutate(bad)
            with self.assertRaises(AgentError):validate_review(self.s,self.a,p,bad)

    def test_invalid_reviewer_not_treated_as_business_ruling(self):
        reviewer=Reviewer();reviewer.mutate=lambda o:o.update(refund_amount=100)
        r=RydeOrchestrator(advocate_runner=Advocate(),judge_runner=Judge(),reviewer_runner=reviewer).run('DISP-003')
        self.assertEqual(r['execution_status'],'failed');self.assertEqual(r['business_decision_status'],'unavailable')
        self.assertIn('REVIEWER_INVALID_SCHEMA',r['validation_errors'])

    def test_no_reviewer_call_on_policy_human_cases_or_invalid_judge(self):
        reviewer=Reviewer()
        for case in ('DISP-001','DISP-002'):
            RydeOrchestrator(reviewer_runner=reviewer).run(case)
        judge=Judge();judge.failure=AgentError('VERTEX_HTTP_400')
        RydeOrchestrator(advocate_runner=Advocate(),judge_runner=judge,reviewer_runner=reviewer).run('DISP-003')
        self.assertEqual(reviewer.calls,0)

    def test_guidance_is_symmetric_response_only_and_does_not_add_calls(self):
        client=FakeClient();advocate=TeammateAdvocate(client)
        r=RydeOrchestrator(advocate_runner=advocate,issue_guidance=True).run('DISP-003')
        self.assertEqual(len(client.inputs),4);self.assertFalse(r['validation_errors'])
        self.assertTrue(all('round_guidance' not in c for _,c,_ in client.inputs[:2]))
        first=client.inputs[2][1]['round_guidance'];second=client.inputs[3][1]['round_guidance']
        self.assertEqual(first['issues'],second['issues']);self.assertEqual((first['side'],second['side']),('rider','driver'))
        self.assertIn('issue_progress',r)
        # Reusing the adapter on a new ordinary opening cannot leak the last side/context.
        advocate(self.s,'rider','opening')
        self.assertNotIn('round_guidance',client.inputs[-1][1])
        self.assertIsNone(advocate._round_guidance)

    def test_coordinator_pairs_existing_paths_without_resolving_unknown_sources(self):
        from ryde_resolve.issue_guidance import coordinate_openings,response_guidance
        ledger={'issues':[{'issue_id':'notice','record_status':'unknown','question':'Missing notice',
            'evidence_refs':['E-001'],'policy_refs':['P-001']}],'boundary':'source only'}
        openings={side:{'claims':[{'claim':'Agents agree notice was provided','evidence_refs':['E-001','E-UNLINKED']}]} for side in ('rider','driver')}
        out=coordinate_openings(ledger,openings)
        self.assertEqual(ledger['issues'][0]['record_status'],'unknown')
        issue=out['issues'][0]
        self.assertEqual(issue['coordination_action'],'preserve_source_gap')
        self.assertEqual(issue['record_status'],'unknown')
        for side in ('rider','driver'):
            row=issue['opening_claims'][side][0]
            self.assertEqual(row['argument_ref'],f'/opening/{side}/claims/0')
            self.assertEqual(row['shared_evidence_refs'],['E-001'])
        self.assertEqual(response_guidance(out,'rider')['issues'],response_guidance(out,'driver')['issues'])
        self.assertEqual(out['termination']['remaining_response_rounds'],1)

    def test_guidance_failure_clears_context(self):
        client=FakeClient();client.mutate=lambda out:out.update(side='wrong')
        advocate=TeammateAdvocate(client)
        with self.assertRaises(AgentError):advocate.run_guided(self.s,'rider','response',{'snapshot_id':self.s['snapshot_id']}, {'side':'rider','issues':[]})
        self.assertIsNone(advocate._round_guidance)
