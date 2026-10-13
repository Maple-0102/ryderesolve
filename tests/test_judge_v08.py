"""Protect provenance, scorer isolation, fee generalization and failed-output scoring."""
import copy
import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from evaluation.export_dataset import export_dataset
from evaluation.judge_suite import build_exercises
from evaluation.run_judge_suite import evaluate
from ryde_resolve.agents import build_judge_messages
from ryde_resolve.evidence import EvidenceGateway, verify_snapshot
from ryde_resolve.policy_provenance import policy_provenance
from ryde_resolve.rule_engine import calculate_rules
from ryde_resolve.mock_agents import OfflineJudge
from test_reasoning import analysed_route


class JudgeV08Tests(unittest.TestCase):
    def test_prompt_has_no_case_specific_values_or_names(self):
        x = build_exercises()[0]
        prompt = build_judge_messages(x['snapshot'], x['arguments'], calculate_rules(x['snapshot']))[0]['content']
        for hint in ('DISP-002', 'SYN-ROUTE-001', '480/470/360'):
            self.assertNotIn(hint, prompt)
        # Case values still arrive through audited data, rather than being discarded.
        payload = build_judge_messages(x['snapshot'], x['arguments'], calculate_rules(x['snapshot']))[1]['content']
        self.assertIn('DISP-002', payload)

    def test_policy_origin_retained_without_mutating_case_or_registry(self):
        for case in ('DISP-002', 'SYN-ROUTE-001'):
            s = EvidenceGateway().prepare(case); original = copy.deepcopy(s)
            result = policy_provenance(s)
            self.assertEqual({r['origin'] for r in result['dataset_policy']}, {s['audit']['policy_origin']})
            self.assertTrue(all(r['source_refs'] for r in result['dataset_policy']))
            result['local_safeguards'][0]['origin'] = 'invented_official'
            self.assertEqual(policy_provenance(s)['local_safeguards'][0]['origin'], 'team_implementation')
            self.assertEqual(s, original)

    def test_export_separates_answers_and_is_reproducible(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            self.assertEqual(export_dataset(a), 15); export_dataset(b)
            manifest = json.loads((Path(a)/'manifest.json').read_text())
            for row in manifest['cases']:
                data = (Path(a)/row['file']).read_bytes()
                self.assertEqual(data, (Path(b)/row['file']).read_bytes())
                self.assertEqual(row['sha256'], sha256(data).hexdigest())
                user = json.loads(json.loads(data)[1]['content'])
                self.assertNotIn('expected', user); self.assertNotIn('exercise_id', user)
            labels = json.loads((Path(a)/'scorer-only-labels.json').read_text())
            self.assertEqual(len(labels), 15)
            self.assertEqual(sum(r['split']=='holdout_candidate' for r in labels.values()), 6)

    def test_fee_variants_can_pass_existing_validators_at_correct_amount(self):
        examples = [x for x in build_exercises('holdout') if x['exercise_id'].endswith('-UNSUPPORTED')]
        for x in examples:
            verify_snapshot(x['snapshot'])
            def judge(s, a, c):
                out = analysed_route(s, a, decision='refund_partial')
                out['refund_amount'] = x['expected']['refund_amount']
                return out
            row = evaluate(judge, [x])['results'][0]
            self.assertTrue(row['behaviour_match'], row['errors'])

    def test_memorized_five_dollar_refund_fails_changed_fee_cases(self):
        x = next(x for x in build_exercises('holdout') if x['exercise_id']=='FEE-800-UNSUPPORTED')
        r = evaluate(lambda s,a,c: analysed_route(s,a,decision='refund_partial'), [x])
        self.assertFalse(r['results'][0]['behaviour_match'])
        self.assertEqual(r['metrics']['refund_amount_mismatches'], 1)

    def test_invalid_output_retained_but_not_counted_as_correct_escalation(self):
        x = build_exercises()[0]
        r = evaluate(lambda s,a,c: {'decision': 'escalate'}, [x])
        self.assertEqual(r['results'][0]['rejected_output'], {'decision':'escalate'})
        self.assertEqual(r['metrics']['confusion']['escalate'], {'invalid_output':1})
        self.assertEqual(r['metrics']['by_expected_decision']['escalate']['matched'], 0)

    def test_malformed_output_can_be_saved_without_nan_or_non_json_values(self):
        x = build_exercises()[0]
        for out in ({'decision': 'escalate', 'confidence': float('nan')}, {'decision': 'escalate', 'findings': {1,2}}):
            r = evaluate(lambda s,a,c: out, [x])
            json.dumps(r, allow_nan=False)
            self.assertEqual(r['results'][0]['rejected_output'], {'omitted': 'rejected non-JSON model output'})
            self.assertFalse(r['results'][0]['behaviour_match'])

    def test_checkpoint_callback_preserves_completed_rows(self):
        saves = []
        evaluate(OfflineJudge(), build_exercises()[:2], on_result=saves.append)
        self.assertEqual([len(s) for s in saves], [1,2])
        saves[0][0]['expected']['decision'] = 'changed'
        self.assertEqual(saves[1][0]['expected']['decision'], 'escalate')

    def test_no_full_refund_coverage_not_silently_reported_as_pass(self):
        r = evaluate(OfflineJudge(), build_exercises())
        self.assertEqual(r['metrics']['by_expected_decision']['refund_full'], {'matched':0,'total':0})
        self.assertFalse(r['metrics']['usage_complete'])


if __name__ == '__main__': unittest.main()

class SupplementTests(unittest.TestCase):
    def test_new_snapshot_rebuilds_advocates_without_leaking_prior_verdict(self):
        from ryde_resolve.orchestrator import RydeOrchestrator
        from evaluation.fixtures import with_verification
        orchestrator = RydeOrchestrator()
        previous = orchestrator.run('SYN-ROUTE-001'); saved = copy.deepcopy(previous)
        previous['ruling']['notes'] = ['PRIOR_VERDICT_SENTINEL']
        newer = with_verification(previous['snapshot'])
        result = orchestrator.rerun_with_supplement(previous, newer, source_note='Synthetic test verification, not operational evidence.')
        self.assertNotIn('PRIOR_VERDICT_SENTINEL', json.dumps(result['communication_log']))
        self.assertEqual(result['snapshot']['snapshot_id'], newer['snapshot_id'])
        self.assertEqual(result['supplement_lineage']['round'], 1)
        from ryde_resolve.ui import render_html
        result['supplement_lineage']['source_note'] = '<script>untrusted-source()</script>'
        with tempfile.TemporaryDirectory() as d:
            page = render_html(result, Path(d)/'supplement.html').read_text()
        self.assertIn('规则来源', page); self.assertIn('补材料后重新分析', page)
        self.assertNotIn('<script>untrusted-source()', page)
        self.assertIn('&lt;script&gt;untrusted-source()', page)
        self.assertFalse(result['validation_errors'])
        self.assertEqual(previous['snapshot'], saved['snapshot'])
        for event in result['communication_log']:
            if event['step'] in ('opening', 'response'):
                self.assertEqual(event['input']['snapshot_id'], newer['snapshot_id'])

    def test_same_source_or_second_round_is_blocked(self):
        from ryde_resolve.orchestrator import RydeOrchestrator
        from ryde_resolve.agents import AgentError
        from evaluation.fixtures import with_verification
        o = RydeOrchestrator(); previous = o.run('SYN-ROUTE-001')
        with self.assertRaisesRegex(AgentError, 'NO_SOURCE_CHANGE'):
            o.rerun_with_supplement(previous, previous['snapshot'], source_note='No actual new material')
        result = o.rerun_with_supplement(previous, with_verification(previous['snapshot']), source_note='Synthetic test material')
        with self.assertRaisesRegex(AgentError, 'ROUND_LIMIT'):
            o.rerun_with_supplement(result, result['snapshot'], source_note='Another request')

    def test_old_file_advocate_is_rejected_after_supplement(self):
        from ryde_resolve.orchestrator import RydeOrchestrator
        from ryde_resolve.agents import FileAdvocate
        from evaluation.fixtures import with_verification
        old = RydeOrchestrator().run('SYN-ROUTE-001')
        doc = {'case_id': old['case_id'], 'snapshot_id': old['snapshot']['snapshot_id'], **old['arguments']}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'old-arguments.json'; p.write_text(json.dumps(doc))
            result = RydeOrchestrator(advocate_runner=FileAdvocate(p)).rerun_with_supplement(
                old, with_verification(old['snapshot']), source_note='Synthetic test verification')
        self.assertIn('ADVOCATE_SNAPSHOT_MISMATCH', result['validation_errors'])
        self.assertEqual(result['ruling']['decision'], 'escalate')

class ArgumentKindTests(unittest.TestCase):
    def proposal(self):
        x = next(x for x in build_exercises() if x['exercise_id']=='ROUTE-JUSTIFIED')
        out = analysed_route(x['snapshot'], x['arguments'])
        for row in out['case_analysis']['argument_assessments']:
            if row['argument_ref'].endswith('/1'):
                row.update(assessment='not_factual_claim', supporting_evidence_refs=[], opposing_evidence_refs=[],
                           reason='Procedural request, not an incident assertion.')
        return x,out

    def test_procedural_requests_do_not_require_invented_support(self):
        from ryde_resolve.contracts import check_judge
        x,out = self.proposal()
        self.assertFalse(check_judge(x['snapshot'],out,x['arguments'])[0])

    def test_non_factual_label_cannot_carry_fake_record_support(self):
        from ryde_resolve.contracts import check_judge
        x,out = self.proposal()
        row = next(r for r in out['case_analysis']['argument_assessments'] if r['assessment']=='not_factual_claim')
        row['supporting_evidence_refs'] = ['E-001']
        self.assertTrue(any(e.startswith('NON_FACTUAL_ARGUMENT_WITH_EVIDENCE') for e in check_judge(x['snapshot'],out,x['arguments'])[0]))

    def test_all_non_factual_rows_cannot_establish_a_supported_side(self):
        from ryde_resolve.contracts import check_judge
        x,out = self.proposal()
        for row in out['case_analysis']['argument_assessments']:
            if '/driver/' in row['argument_ref']:
                row.update(assessment='not_factual_claim', supporting_evidence_refs=[], opposing_evidence_refs=[])
        self.assertIn('SIDE_WITHOUT_FACTUAL_ARGUMENTS: driver',check_judge(x['snapshot'],out,x['arguments'])[0])
