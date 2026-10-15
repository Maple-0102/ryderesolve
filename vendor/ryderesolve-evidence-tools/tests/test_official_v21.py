"""Official import, policy isolation and counterfactual data checks; no model calls."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest

from ryderesolve_evidence import EvidenceTools, CaseRepository, InputError
from ryderesolve_evidence.core import build_bundle, source_hash, pointer
from ryderesolve_evidence.policies import DOCUMENT_ID, policy_id, source_value

ROOT = Path(__file__).resolve().parents[1]


class OfficialV21Tests(unittest.TestCase):
    def setUp(self):
        self.tools = EvidenceTools()
        self.snapshots = {case: self.tools.prepare_case(case) for case in ('DISP-001', 'DISP-002', 'DISP-003')}

    def rebuild(self, case, raw, with_policy=True):
        snapshot = self.snapshots[case]
        return build_bundle(raw, {key: snapshot['audit'].get(key) for key in ('data_origin', 'policy_origin', 'source_url')},
                            snapshot['policy_documents'] if with_policy else None)

    def codes(self, bundle):
        return {row['code'] for row in bundle.audit['issues']}

    def test_catalog_has_three_official_cases_and_retains_synthetic(self):
        rows = {row['case_id']: row for row in self.tools.list_cases()}
        self.assertEqual(set(rows), {'DISP-001', 'DISP-002', 'DISP-003', 'SYN-ROUTE-001'})
        self.assertEqual(rows['SYN-ROUTE-001']['data_origin'], 'synthetic')
        self.assertEqual(self.tools.prepare_case('SYN-ROUTE-001')['policy_documents'], {})

    def test_archive_bytes_and_projection_are_reproducible(self):
        manifest = json.loads((ROOT / 'sources/official/2026-10-15/manifest.json').read_text(encoding='utf-8'))
        for case, item in manifest['files'].items():
            content = (ROOT / item['archive_path']).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), item['file_sha256'])
            if case == 'policy':
                continue
            original = json.loads(re.search(r'```json\s*\n(.*?)```', content.decode('utf-8-sig'), re.S)[1])
            self.assertEqual(source_hash(original), item['original_json_sha256'])
            projected = copy.deepcopy(original)
            for ref in item['excluded_pointers']:
                parts = ref.strip('/').split('/')
                parent = projected
                for token in parts[:-1]:
                    parent = parent[int(token)] if isinstance(parent, list) else parent[token]
                del parent[parts[-1]]
            self.assertEqual(projected, self.snapshots[case]['raw'])
            self.assertEqual(source_hash(projected), item['runtime_json_sha256'])

    def test_importer_reproduces_manifest_from_archived_attachments(self):
        spec = importlib.util.spec_from_file_location('import_official', ROOT / 'scripts/import_official.py')
        importer = importlib.util.module_from_spec(spec); spec.loader.exec_module(importer)
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp); inputs = temp / 'inputs'; inputs.mkdir()
            for case, filename in importer.FILES.items():
                name = 'policy-v2.1' if case == 'policy' else case
                (inputs / filename).write_bytes((ROOT / f'sources/official/2026-10-15/{name}.md').read_bytes())
            package = temp / 'package'; data = package / 'ryderesolve_evidence/data'; data.mkdir(parents=True)
            (data / 'catalog.json').write_text('{"cases":[]}', encoding='utf-8')
            importer.ROOT = package
            importer.import_files(inputs)
            result = json.loads((package / 'sources/official/2026-10-15/manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(result, json.loads((ROOT / 'sources/official/2026-10-15/manifest.json').read_text(encoding='utf-8')))
            changed = inputs / importer.FILES['DISP-001']
            original_bytes = changed.read_bytes()
            changed.write_bytes(original_bytes + b'\nChanged attachment')
            with self.assertRaisesRegex(ValueError, 'Archived source changed'):
                importer.import_files(inputs)
            self.assertEqual((package / 'sources/official/2026-10-15/DISP-001.md').read_bytes(), original_bytes)

    def test_nested_answers_and_editorial_ruling_rejected(self):
        for key in ('expected_ruling', 'recommended_ruling', 'expected_refund_amount', 'ruling_rationale'):
            raw = copy.deepcopy(self.snapshots['DISP-001']['raw'])
            raw['case_metadata'] = {key: 'answer'}
            with self.subTest(key=key), self.assertRaises(InputError):
                build_bundle(raw)

    def test_all_runtime_snapshots_exclude_current_case_answers(self):
        for snapshot in self.snapshots.values():
            text = json.dumps(snapshot)
            for key in ('expected_ruling', 'recommended_ruling', 'expected_refund_amount', 'chat_log_analysis', 'traffic_analysis', 'evidence_summary'):
                self.assertNotIn('"' + key + '"', text)

    def test_every_policy_excerpt_resolves_in_correct_source(self):
        for case, snapshot in self.snapshots.items():
            for row in snapshot['evidence_pack']['policy']:
                resolved = self.tools.get_policy(case, row['policy_id'], expected_snapshot_id=snapshot['snapshot_id'])
                for excerpt in resolved['excerpts']:
                    self.assertEqual(excerpt['value'], source_value(snapshot['raw'], snapshot['policy_documents'], resolved, excerpt['source_ref']))
        old = self.tools.get_policy('DISP-002', 'P-004')
        self.assertEqual(old['excerpts'][0]['value'], 8)
        new = self.tools.get_policy('DISP-002', policy_id('2.1'))
        self.assertIn('from the scheduled pickup time', new['excerpts'][0]['value']['text'])
        self.assertEqual(new['source_document_id'], DOCUMENT_ID)

    def test_policy_tampering_or_removal_invalidates_snapshot(self):
        s = self.snapshots['DISP-002']
        docs = copy.deepcopy(s['policy_documents'])
        docs[DOCUMENT_ID]['sections']['2.1']['text'] = 'Start at driver arrival.'
        with self.assertRaises(InputError):
            build_bundle(s['raw'], policy_documents=docs)
        legacy = self.rebuild('DISP-002', s['raw'], False)
        self.assertNotEqual(legacy.audit['snapshot_id'], s['snapshot_id'])
        self.assertEqual(legacy.audit['source_sha256'], s['source_sha256'])

    def test_policy_missing_leaves_clock_missing(self):
        bundle = self.rebuild('DISP-002', self.snapshots['DISP-002']['raw'], False)
        self.assertIn('POLICY_CLOCK_BASIS_UNSPECIFIED', self.codes(bundle))
        self.assertNotIn('policy_context', bundle.audit)

    def test_no_show_free_clock_is_explicit_but_threshold_remains_unresolved(self):
        s = self.snapshots['DISP-002']; audit = s['audit']
        self.assertEqual(s['source_sha256'], '6712c5be3edf06bf27fccdaabb7b46ecf9936dba56758b7db5e74e40599579ca')
        self.assertEqual([audit['metrics'][key]['seconds'] for key in ('trip_wait', 'app_wait_5', 'scheduled_pickup_to_cancellation')], [480, 470, 360])
        clock = audit['policy_context']['free_wait_clock']
        self.assertEqual(clock['basis'], 'scheduled_time')
        self.assertEqual(clock['ends_at'], '2026-09-13T08:50:00+08:00')
        codes = {row['code'] for row in audit['issues'] if row['severity'] == 'review'}
        self.assertEqual(codes, {'NO_SHOW_THRESHOLD_CLOCK_UNSPECIFIED', 'POLICY_SOURCE_CONFLICT'})
        self.assertEqual(audit['policy_context']['confidence_requirement']['minimum'], .95)

    def test_missing_scheduled_time_does_not_fall_back_to_driver_arrival(self):
        raw = copy.deepcopy(self.snapshots['DISP-002']['raw']); del raw['trip_data']['scheduled_time']
        bundle = self.rebuild('DISP-002', raw)
        self.assertIn('POLICY_APPLICABILITY_UNCONFIRMED', self.codes(bundle))
        self.assertNotIn('free_wait_clock', bundle.audit['policy_context'])

    def test_route_reported_km_not_sampled_polyline_is_used_for_policy(self):
        s = self.snapshots['DISP-001']; metrics = s['audit']['metrics']
        self.assertEqual(metrics['reported_route_distance']['excess_km'], 4.3)
        self.assertNotEqual(metrics['route_comparison']['sampled_excess_m'], 4300)
        self.assertEqual(metrics['fare_difference']['difference_cents'], 650)
        self.assertEqual(metrics['reported_excess_distance_fare']['amount_cents'], 344)
        self.assertIn('ROUTE_DISTANCE_REQUIRES_HUMAN_REVIEW', {i['code'] for i in s['audit']['issues']})
        self.assertTrue(metrics['route_comparison']['trip_window_boundaries_observed'])
        self.assertNotIn('INCOMPLETE_COMMUNICATION_RECORD', {i['code'] for i in s['audit']['issues']})

    def test_official_route_filters_out_of_window_gps_with_original_refs(self):
        raw = copy.deepcopy(self.snapshots['DISP-001']['raw'])
        raw['gps_telemetry'].insert(0, {'timestamp':'2026-09-12T12:00:00+08:00', 'lat':0, 'lng':0, 'speed_kmh':0})
        bundle = self.rebuild('DISP-001', raw)
        metric = bundle.audit['metrics']['route_comparison']
        self.assertEqual(metric['excluded_gps_indices'], [0])
        self.assertEqual(metric['actual_sampled_length_m'], self.snapshots['DISP-001']['audit']['metrics']['route_comparison']['actual_sampled_length_m'])
        self.assertIn('/gps_telemetry/1', metric['source_refs'])

    def test_surge_diff_decimal_arithmetic_and_message_alias(self):
        s = self.snapshots['DISP-003']; metrics = s['audit']['metrics']
        self.assertEqual(metrics['fare_difference']['difference_cents'], 450)
        self.assertTrue(metrics['surge_comparison']['breakdown_consistent_with_surge_only_change'])
        facts = '\n'.join(row['fact'] for row in s['evidence_pack']['facts'])
        self.assertIn('Just noticed the fare is $16.50', facts)
        self.assertIn('"rider_notified": false', facts)
        self.assertFalse(s['audit']['requires_policy_or_data_review'])
        self.assertNotIn('decision', s['evidence_pack'])

    def test_missing_notification_is_unknown_not_recorded_false(self):
        raw = copy.deepcopy(self.snapshots['DISP-003']['raw']); del raw['surge_pricing_log']
        self.assertIn('SURGE_NOTIFICATION_STATUS_MISSING', self.codes(self.rebuild('DISP-003', raw)))

    def test_positive_notice_flag_requires_content_and_timeliness(self):
        raw = copy.deepcopy(self.snapshots['DISP-003']['raw'])
        raw['surge_pricing_log'].update(rider_notified=True, notification_timestamp='2026-09-14T21:06:00+08:00')
        codes = self.codes(self.rebuild('DISP-003', raw))
        self.assertTrue({'SURGE_NOTICE_DETAILS_MISSING', 'SURGE_NOTICE_AFTER_PICKUP'} <= codes)

    def test_inconsistent_amount_and_surge_fields_are_flagged(self):
        for change, expected in ((lambda r: r['fare_breakdown']['actual_fare'].update(total=17), 'FARE_TOTAL_RECORD_CONFLICT'),
                                 (lambda r: r['surge_pricing_log'].update(trip_start_surge=2), 'SURGE_MULTIPLIER_RECORD_CONFLICT'),
                                 (lambda r: r['fare_breakdown']['actual_fare'].update(surgeable_subtotal=10), 'SURGE_COMPONENTS_INCONSISTENT')):
            raw = copy.deepcopy(self.snapshots['DISP-003']['raw']); change(raw)
            self.assertIn(expected, self.codes(self.rebuild('DISP-003', raw)))

    def test_invalid_new_field_types_rejected(self):
        for change in (lambda r: r.update(optimal_route=[]), lambda r: r.update(surge_pricing_log=[]),
                       lambda r: r['surge_pricing_log'].update(rider_notified='false'),
                       lambda r: r['fare_breakdown']['actual_fare'].update(total=True),
                       lambda r: r['fare_breakdown']['actual_fare'].update(total=-1),
                       lambda r: r['surge_pricing_log'].update(free_cancellation_offered='false'),
                       lambda r: r['fare_breakdown']['actual_fare'].update(total=16.501)):
            raw = copy.deepcopy(self.snapshots['DISP-003']['raw']); change(raw)
            with self.assertRaises(InputError):
                self.rebuild('DISP-003', raw)

    def test_surge_decrease_remains_a_signed_difference(self):
        raw = copy.deepcopy(self.snapshots['DISP-003']['raw'])
        raw['trip_data'].update(upfront_quote=16.5, actual_fare=12, fare_difference=-4.5)
        quote = raw['fare_breakdown']['upfront_quote']
        actual = raw['fare_breakdown']['actual_fare']
        quote.update(surge_multiplier=1.5, surge_amount=4.5, total=16.5)
        actual.update(surge_multiplier=1, surge_amount=0, total=12)
        raw['fare_breakdown']['comparison'].update(total_difference=-4.5, surge_amount_difference=-4.5)
        raw['surge_pricing_log'].update(quote_time_surge=1.5, trip_start_surge=1)
        bundle = self.rebuild('DISP-003', raw)
        self.assertEqual(bundle.audit['metrics']['fare_difference']['difference_cents'], -450)
        self.assertTrue(bundle.audit['metrics']['surge_comparison']['breakdown_consistent_with_surge_only_change'])
        self.assertFalse({'FARE_DIFFERENCE_RECORD_CONFLICT', 'SURGE_COMPARISON_RECORD_CONFLICT'} & self.codes(bundle))

    def test_safety_flag_and_fraud_do_not_suppress_large_value_escalation(self):
        raw = copy.deepcopy(self.snapshots['DISP-003']['raw'])
        raw['trip_data']['actual_fare'] = 100
        raw['rider_profile']['fraud_flags'] = 1
        raw['dispute_ticket']['description'] = 'The driver threatened me and I felt unsafe.'
        bundle = self.rebuild('DISP-003', raw)
        self.assertTrue({'SAFETY_INDICATOR_REQUIRES_HUMAN_REVIEW', 'DISPUTE_VALUE_REQUIRES_HUMAN_REVIEW'} <= self.codes(bundle))
        self.assertEqual(bundle.audit['policy_context']['confidence_requirement']['minimum'], .95)
        self.assertTrue(bundle.audit['policy_context']['evidence_only'])


if __name__ == '__main__':
    unittest.main()
