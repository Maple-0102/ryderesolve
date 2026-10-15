"""Three official cases traverse the existing team contracts without external models."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from ryde_resolve.agents import build_judge_messages
from ryde_resolve.contracts import check_judge
from ryde_resolve.deliberation import condition_specs
from ryde_resolve.evidence import EvidenceGateway, verify_snapshot
from ryde_resolve.mock_agents import review_ruling
from ryde_resolve.orchestrator import RydeOrchestrator
from ryde_resolve.rule_engine import calculate_rules, charged_amount
from ryde_resolve.teammate_advocate import TeammateAdvocate
from ryde_resolve.ui import render_html
from ryderesolve_evidence.core import build_bundle


class CapturingModel:
    def __init__(self):
        self.calls = []

    def generate(self, system, user, **kwargs):
        self.calls.append((system, json.loads(user)))
        pack = json.loads(user)['evidence_pack']
        side = 'rider' if 'SIDE = rider.' in system else 'driver'
        return {'case_id': pack['case_id'], 'side': side, 'position': 'request_review',
                'claims': [{'claim': 'Recorded data requires assessment.', 'evidence_refs': [pack['facts'][0]['evidence_id']],
                            'policy_refs': [pack['policy'][0]['policy_id']]}],
                'counterpoints': [], 'missing_information': ['Test provider, not model advocacy.']}


class OfficialIntegrationTests(unittest.TestCase):
    def test_official_cases_run_all_stages_with_teammate_contract(self):
        for case in ('DISP-001', 'DISP-002', 'DISP-003'):
            model = CapturingModel()
            result = RydeOrchestrator(advocate_runner=TeammateAdvocate(model)).run(case)
            with self.subTest(case=case):
                self.assertFalse(result['validation_errors'], result['validation_errors'])
                self.assertEqual(len(model.calls), 4)
                self.assertEqual(len(result['communication_log']), 8)
                self.assertTrue(all(e['status'] == 'success' for e in result['communication_log']))
                self.assertEqual(result['ruling']['decision'], 'escalate')  # Offline Judge, not a claimed model verdict.
                policy = model.calls[0][1]['evidence_pack']['policy']
                self.assertTrue(any(p['policy_id'].startswith('P-RYDE-2.1-') for p in policy))
                self.assertIn('five-minute FREE wait at scheduled pickup', model.calls[0][0])
                self.assertIn('SURGE DIFFERENTIAL', model.calls[0][0])
                self.assertNotIn('recommended_ruling', json.dumps(model.calls))

    def test_official_policy_and_data_rebuild_and_tamper_detection(self):
        s = EvidenceGateway().prepare('DISP-003')
        verify_snapshot(s)
        for key in ('policy_documents', 'raw', 'source_index', 'audit'):
            mutated = copy.deepcopy(s); mutated[key]['tampered'] = True
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_snapshot(mutated)
        mutated = copy.deepcopy(s); del mutated['policy_documents']
        with self.assertRaises(ValueError): verify_snapshot(mutated)

    def test_charge_bounds_and_fare_condition_are_not_no_show_defaults(self):
        route = EvidenceGateway().prepare('DISP-001'); fare = EvidenceGateway().prepare('DISP-003')
        self.assertEqual(float(charged_amount(route)), 35)
        self.assertEqual(float(charged_amount(fare)), 16.5)
        self.assertEqual(condition_specs(fare)[0]['condition_id'], 'fare_charge')
        output = review_ruling(fare, ['test'])
        output.update(decision='refund_full', refund_amount=16.5, escalate_to_human=False, uncertainties=[])
        self.assertIn('REFUND_EXCEEDS_DISPUTED_FARE_DIFFERENCE', check_judge(fare, output)[0])

    def test_fraud_policy_requires_95_confidence_before_final_ruling(self):
        s = EvidenceGateway().prepare('DISP-002')
        output = review_ruling(s, ['test'])
        output.update(decision='uphold_charge', refund_amount=0, escalate_to_human=False, uncertainties=[], confidence=.94)
        self.assertIn('POLICY_CONFIDENCE_REQUIREMENT_NOT_MET', check_judge(s, output)[0])
        output['confidence'] = .95
        errors = check_judge(s, output)[0]
        self.assertNotIn('POLICY_CONFIDENCE_REQUIREMENT_NOT_MET', errors)
        self.assertIn('UNRESOLVED_DATA_OR_POLICY_REVIEW', errors)  # Confidence cannot waive a conflict.

    def test_ui_policy_sources_render_for_all_cases(self):
        results = [RydeOrchestrator().run(case) for case in ('DISP-001', 'DISP-002', 'DISP-003')]
        with tempfile.TemporaryDirectory() as directory:
            page = render_html(results, Path(directory) / 'review.html').read_text(encoding='utf-8')
        for section in ('1.4', '2.1', '3.3'):
            self.assertIn('P-RYDE-2.1-S' + section, page)
        self.assertIn('source_document_id', page)
        self.assertIn('from the scheduled pickup time', page)
        self.assertIn('报告道路距离 24.8 km / 参考 20.5 km / 差额 4.3 km', page)
        self.assertIn('原记录金额 3.44 SGD', page)
        self.assertIn('政策免费等待', page)
        self.assertIn('政策要求人工裁决', page)
        route_handoff = next(x for x in results[0]['human_handoff'] if x['issue_code'] == 'ROUTE_DISTANCE_REQUIRES_HUMAN_REVIEW')
        self.assertEqual(route_handoff['suggested_owner'], '人工复核负责人')
        self.assertIn('不能免除', route_handoff['decision_impact'])

    def test_judge_context_has_traceable_policy_and_no_case_answers(self):
        s = EvidenceGateway().prepare('DISP-001')
        payload = json.loads(build_judge_messages(s, {}, calculate_rules(s))[1]['content'])
        self.assertIn('P-RYDE-2.1-S6.2', payload['source_index']['policy'])
        for field in ('expected_ruling', 'recommended_ruling', 'evidence_summary'):
            self.assertNotIn(field, json.dumps(payload))

    def test_policy_only_supplement_can_rerun_unchanged_raw_case(self):
        current = EvidenceGateway().prepare('DISP-002')
        bundle = build_bundle(current['raw'], {key: current['audit'].get(key) for key in ('data_origin', 'policy_origin', 'source_url')})
        legacy = {'case_id': 'DISP-002', 'snapshot_id': bundle.audit['snapshot_id'],
                  'source_sha256': bundle.audit['source_sha256'], 'normalizer_version': bundle.audit['normalizer_version'],
                  'evidence_pack': bundle.pack, 'raw': bundle.raw, 'audit': bundle.audit,
                  'source_index': {'evidence': bundle.evidence_index, 'policy': bundle.policy_index}, 'policy_documents': {}}
        class LegacyGateway:
            def prepare(self, case_id): return copy.deepcopy(legacy)
        runner = RydeOrchestrator(evidence_gateway=LegacyGateway())
        previous = runner.run('DISP-002')
        result = runner.rerun_with_supplement(previous, current, source_note='Organizer policy v2.1 supplied separately.')
        self.assertFalse(result['validation_errors'])
        self.assertEqual(result['snapshot']['source_sha256'], previous['snapshot']['source_sha256'])
        self.assertNotEqual(result['snapshot']['snapshot_id'], previous['snapshot']['snapshot_id'])
        self.assertIn('POLICY_SOURCE_CONFLICT', str(result['ruling']['uncertainties']))


if __name__ == '__main__':
    unittest.main()
