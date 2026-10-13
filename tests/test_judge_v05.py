"""Concrete v0.5 regressions and evaluation harness tests; no model/network calls."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch
from test_reasoning import args_for, analysed_route
from evaluation.fixtures import with_verification
from evaluation.judge_suite import build_exercises
from evaluation.run_judge_suite import evaluate, main as evaluate_main
from ryde_resolve.evidence import EvidenceGateway
from ryde_resolve.contracts import check_judge
from ryde_resolve.mock_agents import OfflineJudge, review_ruling
from ryde_resolve.orchestrator import RydeOrchestrator
from ryde_resolve.agents import AgentError
from ryde_resolve.rule_engine import calculate_rules
from ryde_resolve.ui import render_html


class JudgeV05Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = with_verification(EvidenceGateway().prepare('SYN-ROUTE-001'))
        cls.args = args_for(cls.s)

    def proposal(self): return analysed_route(self.s, self.args)
    def errors(self, out): return check_judge(self.s, out, self.args)[0]

    def test_material_uncertainty_cannot_coexist_with_final_decision(self):
        out = self.proposal(); out['uncertainties'] = ['Route justification remains unverified.']
        self.assertIn('FINAL_WITH_UNRESOLVED_UNCERTAINTIES', self.errors(out))
        out['uncertainties'] = []; out['notes'] = ['Records are from a synthetic exercise.']
        self.assertFalse(self.errors(out))
        out['notes'] = {'material': 'hide uncertainty'}
        self.assertIn('INVALID_NON_MATERIAL_NOTES', self.errors(out))

    def test_unknown_or_inverted_decisive_condition_blocks_ruling(self):
        for status in ('unknown', 'not_met'):
            out = self.proposal(); out['case_analysis']['decision_conditions'][1]['status'] = status
            self.assertTrue(self.errors(out), status)

    def test_duplicate_unknown_and_missing_conditions_block_ruling(self):
        for mutation in ('duplicate', 'unknown', 'missing'):
            out = self.proposal(); rows = out['case_analysis']['decision_conditions']
            if mutation == 'duplicate': rows.append(copy.deepcopy(rows[0]))
            if mutation == 'unknown': rows[0]['condition_id'] = 'model_invented'
            if mutation == 'missing': rows.pop()
            self.assertIn('DECISION_CONDITION_COVERAGE', self.errors(out))

    def test_unrelated_record_cannot_launder_responsibility(self):
        out = self.proposal(); out['findings'][0].update(
            finding='Trip started; therefore driver bears no responsibility.', evidence_refs=['E-016'])
        self.assertIn('FINDING_CONDITION_BASIS_MISMATCH', self.errors(out))

    def test_unknown_and_malformed_condition_refs_fail_cleanly(self):
        for refs in ([], ['made_up'], [{}], [True], 'extra_charge', None):
            out = self.proposal(); out['findings'][0]['condition_refs'] = refs
            self.assertTrue(self.errors(out), repr(refs))

    def test_insufficient_evidence_requires_gap_not_counterevidence(self):
        out = self.proposal(); a = out['case_analysis']
        a['sides']['rider'].update(assessment='unsupported', evidence_refs=[],
            reason='The allegation is not supported; no contrary fact has been established.')
        for row in a['argument_assessments']:
            if '/rider/' in row['argument_ref']:
                row.update(assessment='insufficient_evidence', supporting_evidence_refs=[], opposing_evidence_refs=[],
                           missing_information=['A contemporaneous record supporting this allegation.'])
        self.assertFalse(self.errors(out), self.errors(out))
        a['argument_assessments'][next(i for i,x in enumerate(a['argument_assessments']) if '/rider/' in x['argument_ref'])]['missing_information'] = []
        self.assertTrue(any('ARGUMENT_MISSING_GAP_EXPLANATION' in e for e in self.errors(out)))

    def test_contradicted_requires_opposing_evidence_not_just_support(self):
        out = self.proposal(); a = out['case_analysis']
        for row in a['argument_assessments']:
            if '/rider/' in row['argument_ref']: row['assessment'] = 'contradicted'
        a['sides']['rider']['assessment'] = 'contradicted'
        self.assertTrue(any('WITHOUT_RECORD_SUPPORT' in e for e in self.errors(out)))
        for row in a['argument_assessments']:
            if '/rider/' in row['argument_ref']:
                row['opposing_evidence_refs'] = row['supporting_evidence_refs']; row['supporting_evidence_refs'] = []
        self.assertFalse(self.errors(out))

    def test_unsupported_party_does_not_establish_charge(self):
        out = self.proposal(); out['case_analysis']['sides']['rider']['assessment'] = 'unsupported'
        for row in out['case_analysis']['argument_assessments']:
            if '/rider/' in row['argument_ref']:
                row.update(assessment='insufficient_evidence', supporting_evidence_refs=[],
                           missing_information=['Missing direct records.'])
        for c in out['case_analysis']['decision_conditions']: c['status'] = 'unknown'
        self.assertTrue(any('UNRESOLVED_DECISION_CONDITION' in e for e in self.errors(out)))

    def test_every_argument_requires_one_assessment(self):
        for mutation in ('missing', 'duplicate', 'wrong_side', 'malformed'):
            out = self.proposal(); rows = out['case_analysis']['argument_assessments']
            if mutation == 'missing': rows.pop()
            if mutation == 'duplicate': rows.append(copy.deepcopy(rows[0]))
            if mutation == 'wrong_side': rows[0]['argument_ref'] = '/opening/driver/claims/999'
            if mutation == 'malformed': rows[0]['supporting_evidence_refs'] = {}
            self.assertTrue(self.errors(out), mutation)

    def test_ledger_references_and_summary_consistency(self):
        for mutation in ('unknown_evidence', 'unknown_policy', 'same_both', 'false_summary'):
            out = self.proposal(); a = out['case_analysis']; row = a['argument_assessments'][0]
            if mutation == 'unknown_evidence': row['supporting_evidence_refs'] = ['E-999']
            if mutation == 'unknown_policy': row['policy_refs'] = ['P-999']
            if mutation == 'same_both': row['opposing_evidence_refs'] = row['supporting_evidence_refs'][:]
            if mutation == 'false_summary': a['sides']['rider']['assessment'] = 'accepted'
            self.assertTrue(self.errors(out), mutation)

    def test_disputed_point_cannot_be_unsupported_final_assertion(self):
        out = self.proposal(); out['case_analysis']['disputed_points'][0].update(
            reasoning='The driver wins.', evidence_refs=[], policy_refs=[])
        self.assertIn('DISPUTED_POINT_BASIS_MISSING', self.errors(out))

    def test_no_show_policy_condition_cannot_be_self_resolved(self):
        s = EvidenceGateway().prepare('DISP-002'); args = args_for(s)
        out = OfflineJudge()(s, args, calculate_rules(s))
        out['case_analysis']['decision_conditions'][0].update(status='met', evidence_refs=['E-001'], policy_refs=['P-004'])
        self.assertIn('CONDITION_CANNOT_CLEAR_POLICY_AMBIGUITY', check_judge(s, out, args)[0])

    def test_handoff_is_actionable_for_offline_and_failed_pipeline(self):
        r = RydeOrchestrator().run('DISP-002')
        self.assertTrue(r['human_handoff'])
        for item in r['human_handoff']:
            for key in ('requested_information', 'suggested_owner', 'decision_impact', 'next_action'):
                self.assertTrue(item[key])
        self.assertIn('OFFLINE_JUDGE', {x['issue_code'] for x in r['human_handoff']})
        def fail(*args): raise AgentError('MODEL_CONNECTION_OR_TIMEOUT')
        failed = RydeOrchestrator(judge_runner=fail).run()
        self.assertIn('PIPELINE_OUTPUT_REJECTED', {x['issue_code'] for x in failed['human_handoff']})

    def test_definitive_ruling_has_no_handoff(self):
        snapshot = self.s
        class Gateway:
            def prepare(self, case_id): return copy.deepcopy(snapshot)
        r = RydeOrchestrator(evidence_gateway=Gateway(), judge_runner=lambda s,a,c: analysed_route(s,a)).run(snapshot['case_id'])
        self.assertFalse(r['validation_errors']); self.assertEqual(r['human_handoff'], [])

    def test_new_ui_text_is_escaped_and_sections_present(self):
        r = RydeOrchestrator().run()
        r['human_handoff'][0]['requested_information'] = '<img src=x onerror=alert(1)>'
        r['ruling']['case_analysis']['argument_assessments'][0]['reason'] = '<script>injected()</script>'
        with tempfile.TemporaryDirectory() as d: page = render_html(r, Path(d)/'review.html').read_text()
        self.assertNotIn('<img src=x', page); self.assertNotIn('<script>injected', page)
        for text in ('人工交接单', '裁决关键条件', '逐条论点评估', '&lt;img', '&lt;script&gt;'): self.assertIn(text,page)


class EvaluationTests(unittest.TestCase):
    def test_always_review_cannot_score_as_good_on_resolvable_cases(self):
        r = evaluate(OfflineJudge(), build_exercises())
        self.assertEqual(r['summary']['required_review'], {'matched':5, 'total':5})
        self.assertEqual(r['summary']['resolvable_cases'], {'matched':0, 'total':4})
        self.assertFalse(r['model_quality_measured'])
        self.assertFalse(r['summary']['order_pairs']['argument_order']['both_correct'])

    def test_scoring_accepts_complete_supported_test_output(self):
        exercises = [x for x in build_exercises() if x['exercise_id']=='ROUTE-JUSTIFIED']
        r = evaluate(lambda s,a,c: analysed_route(s,a), exercises)
        self.assertTrue(r['results'][0]['behaviour_match'], r['results'][0]['errors'])

    def test_gate_rejection_cannot_be_counted_as_correct_model_review(self):
        r = evaluate(lambda s,a,c: {'decision':'uphold_charge'}, build_exercises()[:1])
        row=r['results'][0]
        self.assertEqual(row['effective_decision'],'escalate')
        self.assertFalse(row['behaviour_match']); self.assertFalse(row['shared_contract_pass'])

    def test_legacy_escalation_without_analysis_does_not_pass_exercise(self):
        r = evaluate(lambda s,a,c: review_ruling(s, ['Manual review required.']), build_exercises()[:1])
        self.assertIn('EVALUATION_REQUIRES_STRUCTURED_ANALYSIS', r['results'][0]['errors'])
        self.assertFalse(r['results'][0]['behaviour_match'])

    def test_expected_answers_never_reach_judge_inputs(self):
        x=build_exercises()[0]; x['expected']['sentinel']='SECRET_ANSWER_KEY'
        def judge(s,a,c):
            text=json.dumps([s,a,c])
            self.assertNotIn('SECRET_ANSWER_KEY',text); self.assertNotIn('exercise_id',text)
            return OfflineJudge()(s,a,c)
        evaluate(judge,[x])

    def test_cli_default_never_constructs_remote_judge(self):
        with tempfile.TemporaryDirectory() as d, patch('evaluation.run_judge_suite.HTTPJudge') as remote, redirect_stdout(StringIO()):
            exit_code=evaluate_main(['--output',str(Path(d)/'score.json')])
            remote.assert_not_called(); self.assertEqual(exit_code,1)
            self.assertEqual(json.loads((Path(d)/'score.json').read_text())['mode'],'offline_review')

    def test_order_pair_has_identical_case_and_claim_multisets(self):
        a,b=[x for x in build_exercises() if x['order_pair']]
        self.assertEqual(a['snapshot'],b['snapshot'])
        for rnd in ('opening','response'):
            for side in ('rider','driver'):
                self.assertEqual(sorted(json.dumps(c,sort_keys=True) for c in a['arguments'][rnd][side]['claims']),
                                 sorted(json.dumps(c,sort_keys=True) for c in b['arguments'][rnd][side]['claims']))
