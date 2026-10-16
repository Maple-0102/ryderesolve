"""Protected review states cannot be cleared or launder an invalid ruling."""
from copy import deepcopy
from pathlib import Path
import json
import unittest
from ryde_resolve.review_contract import program_review_contract,lock_review_statuses
from ryde_resolve.contracts import check_judge
from ryde_resolve.output_schema import judge_output_schema,vertex_response_schema
from ryde_resolve.agents import build_judge_messages
from ryde_resolve.rule_engine import calculate_rules
from ryde_resolve.orchestrator import RydeOrchestrator
from evaluation.run_statement_regressions import CapturedEvidence,CapturedAdvocates

ROOT=Path(__file__).resolve().parents[1]


class ReviewContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=json.loads((ROOT/'outputs/latest-flow-2026-10-16/final-live-official/fresh-pipeline.json').read_text())['results']

    def saved(self,index=0):
        run=deepcopy(self.rows[index]['run'])
        return run['snapshot'],run['arguments'],run['judge_initial_proposal']

    def execute(self,s,args,proposal):
        class Judge:
            mode='teammate_json'
            def __call__(self,*_):return deepcopy(proposal)
        return RydeOrchestrator(CapturedEvidence(s),CapturedAdvocates(s,args),Judge()).run(s['case_id'])

    def test_identified_referral_stays_unresolved_without_rewriting_correct_explanation(self):
        s,args,raw=self.saved();before=deepcopy((s,args,raw))
        code='ROUTE_DISTANCE_REQUIRES_HUMAN_REVIEW'
        self.assertIn(code,{row['issue_code'] for row in program_review_contract(s)['fixed_review_statuses']})
        candidate,changes=lock_review_statuses(s,raw)
        self.assertEqual(len(changes),1)
        original=next(r for r in raw['case_analysis']['review_responses'] if r['issue_code']==code)
        adjusted=next(r for r in candidate['case_analysis']['review_responses'] if r['issue_code']==code)
        self.assertEqual(adjusted,dict(original,status='unresolved'))
        for field in ('decision','refund_amount','findings','uncertainties','confidence'):
            self.assertEqual(candidate[field],raw[field])
        for field in ('argument_assessments','decision_conditions','sides'):
            self.assertEqual(candidate['case_analysis'][field],raw['case_analysis'][field])
        self.assertTrue(any(e.startswith('ARGUMENT_ASSESSMENT_WITHOUT_RECORD_SUPPORT') for e in check_judge(s,candidate,args)[0]))
        self.assertEqual((s,args,raw),before)

    def test_combined_pipeline_passes_full_unchanged_validator_and_keeps_all_raw_errors(self):
        s,args,raw=self.saved();run=self.execute(s,args,raw)
        self.assertEqual(run['validation_errors'],[])
        self.assertEqual(run['ruling']['decision'],'escalate');self.assertIsNone(run['ruling']['refund_amount'])
        self.assertFalse(check_judge(s,run['ruling'],args)[0])
        self.assertFalse(run['first_pass_valid'])
        self.assertEqual(run['judge_initial_proposal'],raw)
        self.assertEqual(run['judge_raw_validation_errors'],check_judge(s,raw,args)[0])
        self.assertEqual(len(run['judge_adjustments']),5)
        self.assertIn('program_review_status_lock',{r['rule'] for r in run['judge_adjustments']})
        self.assertEqual(run['execution_usage']['provider_calls'],0)
        self.assertEqual(run['execution_status'],'completed')
        self.assertEqual(run['business_decision_status'],'awaiting_human')

    def test_decisive_money_malformed_unknown_and_duplicate_outputs_cannot_be_approved(self):
        for failure in ('decisive','amount','unknown_ref','unknown_code','duplicate','coverage'):
            s,args,raw=self.saved()
            if failure=='decisive':raw.update(decision='uphold_charge',refund_amount=0,escalate_to_human=False)
            elif failure=='amount':raw['refund_amount']=3.44
            elif failure=='unknown_ref':raw['case_analysis']['review_responses'][0]['evidence_refs']=['E-INVENTED']
            elif failure=='unknown_code':raw['case_analysis']['review_responses'][0]['issue_code']='INVENTED_GATE'
            elif failure=='duplicate':raw['case_analysis']['review_responses'].append(deepcopy(raw['case_analysis']['review_responses'][0]))
            else:raw['case_analysis']['argument_assessments'].pop()
            run=self.execute(s,args,raw)
            self.assertTrue(run['validation_errors'],failure)
            self.assertFalse(run['judge_adjustments'],failure)
            self.assertEqual(run['ruling']['decision'],'escalate',failure)
            self.assertIsNone(run['ruling']['refund_amount'],failure)
            self.assertEqual(run['judge_initial_proposal'],raw,failure)

    def test_request_contract_and_generation_constraints_derive_from_snapshot_not_answers(self):
        for i in range(3):
            s,args,raw=self.saved(i)
            payload=json.loads(build_judge_messages(s,args,calculate_rules(s))[1]['content'])
            contract=program_review_contract(s)
            self.assertEqual(payload['program_review_contract'],contract)
            self.assertNotIn('expected',payload);self.assertNotIn('exercise_id',payload)
            schema=judge_output_schema(policy_bound=True,arguments=args,snapshot=s)
            generated=vertex_response_schema(schema)
            self.assertEqual(generated['properties']['decision']['enum'],['escalate'] if contract['required_decision'] else ['uphold_charge','refund_full','refund_partial','escalate'])
            if i==1:
                self.assertEqual(generated['properties']['case_analysis']['properties']['review_responses']['items']['properties']['status']['enum'],['unresolved'])
        s,args,raw=self.saved(2)
        self.assertEqual(lock_review_statuses(s,raw),(raw,[]))
