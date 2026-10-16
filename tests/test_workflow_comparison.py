from copy import deepcopy
import json
import unittest
from jsonschema import Draft202012Validator
from evaluation.compare_workflows import baseline_schema,common_checks,score,baseline
from ryde_resolve.evidence import EvidenceGateway
from test_policy_v21 import completed,arguments
from ryde_resolve.orchestrator import RydeOrchestrator
from test_execution import RecoverableJudge,Advocate,Judge


class ComparisonTests(unittest.TestCase):
    def setUp(self):self.s=EvidenceGateway().prepare('DISP-003');self.a=arguments(self.s)
    def test_baseline_has_no_artificial_argument_coverage_requirement(self):
        p=completed(self.s,self.a)
        p['case_analysis']={k:v for k,v in p['case_analysis'].items() if k in ('decision_conditions','precedent_analysis')}
        self.assertFalse(list(Draft202012Validator(baseline_schema()).iter_errors(p)))
        self.assertFalse(common_checks(self.s,p))
    def test_wrong_money_and_invalid_output_cannot_score_as_correct_escalation(self):
        p=completed(self.s,self.a);p['refund_amount']=9
        self.assertTrue(common_checks(self.s,p))
        self.assertFalse(score({'decision':'escalate','refund_amount':None},['CALL_FAILED'],{'decision':'escalate','refund_amount':None})['expectation_match'])
    def test_baseline_inputs_exclude_scorer_labels_and_invented_advocates(self):
        test=self
        class Client:
            def generate(self,system,user,**kw):
                self.data=json.loads(user)
                test.assertNotIn('arguments',self.data)
                test.assertNotIn('expected',self.data)
                test.assertNotIn('exercise_id',self.data)
        client=Client();baseline(client,self.s)
        self.assertEqual(client.data['raw'],self.s['raw'])
    def test_duplicate_citation_role_is_repaired_once_without_relaxing_validator(self):
        class DuplicateRole(RecoverableJudge):
            def __call__(self,s,a,c):
                p=Judge.__call__(self,s,a,c)
                row=p['case_analysis']['argument_assessments'][0]
                row['opposing_evidence_refs']=row['supporting_evidence_refs'][:1]
                return p
        j=DuplicateRole();r=RydeOrchestrator(advocate_runner=Advocate(),judge_runner=j).run('DISP-003')
        self.assertFalse(r['validation_errors'],r['validation_errors']);self.assertEqual(j.repairs,1)
        self.assertTrue(any(e.startswith('ARGUMENT_CONFLICTING_REFERENCE_ROLE') for e in r['judge_raw_validation_errors']))
        self.assertFalse(r['first_pass_valid'])
