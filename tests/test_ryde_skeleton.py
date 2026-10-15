"""Integration/regression checks; no paid model calls and no organizer data mutation."""
import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from ryde_resolve.agents import (AgentError, FileAdvocate, HTTPJudge, ModelConfig,
                                 build_judge_messages)
from ryde_resolve.contracts import check_advocate, check_judge
from ryde_resolve.evidence import EvidenceGateway, verify_snapshot
from ryde_resolve.mock_agents import OfflineAdvocate, review_ruling
from ryde_resolve.orchestrator import RydeOrchestrator
from ryde_resolve.rule_engine import calculate_rules, refs_for_paths
from ryde_resolve.run_demo import main
from ryde_resolve.ui import render_html


class FakeResponse(io.BytesIO):
    pass


class FakeTransport:
    def __init__(self, body=None, error=None):
        self.body, self.error, self.requests = body, error, []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if self.error:
            raise self.error
        return FakeResponse(self.body)


def completion(output, reason='stop'):
    return json.dumps({'choices': [{'finish_reason': reason,
                      'message': {'content': json.dumps(output)}}]}).encode()


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = EvidenceGateway().prepare('DISP-002')

    def test_both_real_evidence_cases_run_with_explicit_mock_modes(self):
        for case, origin, count in [('DISP-002', 'organizer_sample', 39),
                                    ('SYN-ROUTE-001', 'synthetic', 24)]:
            with self.subTest(case=case):
                r = RydeOrchestrator().run(case)
                self.assertEqual(r['snapshot']['audit']['data_origin'], origin)
                self.assertEqual(len(r['snapshot']['evidence_pack']['facts']), count)
                self.assertEqual(r['ruling']['decision'], 'escalate')
                self.assertIsNone(r['ruling']['refund_amount'])
                self.assertNotIn('confidence', r['ruling'])
                self.assertFalse(r['validation_errors'])
                self.assertEqual(r['modes']['judge'], 'offline_review')
                self.assertEqual(set(r['arguments']['response']), {'rider', 'driver'})

    def test_all_clock_candidates_preserved_without_fee_ruling(self):
        c = calculate_rules(self.s)
        self.assertEqual({m['seconds'] for m in c['calculations'] if 'seconds' in m}, {480, 470, 360})
        self.assertIsNone(c['selected_clock'])
        self.assertIsNone(c['fee_applicable'])
        self.assertEqual(c['status'], 'review_required')

    def test_correct_current_refs_not_old_mock_meanings(self):
        policy = refs_for_paths(self.s, ['/cancellation_policy/no_show_threshold_min'], 'policy')
        self.assertEqual(policy, ['P-004'])
        fact = next(f for f in self.s['evidence_pack']['facts'] if f['evidence_id'] == 'E-002')
        self.assertEqual(fact['source'], 'dispute_ticket.description')

    def test_route_arithmetic_is_not_refund(self):
        s = EvidenceGateway().prepare('SYN-ROUTE-001')
        metrics = {x['name']: x for x in calculate_rules(s)['calculations']}
        self.assertEqual(metrics['fare_difference']['difference_cents'], 500)
        self.assertAlmostEqual(metrics['route_comparison']['actual_sampled_length_m'], 4447.226)
        self.assertIsNone(calculate_rules(s)['fee_applicable'])

    def test_snapshot_tampering_rejected(self):
        for key in ['raw', 'evidence_pack', 'source_index', 'audit']:
            s = copy.deepcopy(self.s)
            s[key]['tampered'] = True
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_snapshot(s)

    def test_teammate_optional_fields_accepted_and_role_case_checked(self):
        out = {'case_id': 'DISP-002', 'side': 'rider', 'claims': []}
        self.assertFalse(check_advocate(self.s, out, 'rider')[0])
        self.assertTrue(check_advocate(self.s, out, 'driver')[0])
        out['case_id'] = 'ANOTHER-CASE'
        self.assertTrue(check_advocate(self.s, out, 'rider')[0])

    def test_bad_advocate_stops_before_judge(self):
        called = []
        def bad(s, side, round_name, opponent):
            return {'case_id': s['case_id'], 'side': side,
                    'claims': [{'claim': 'invented', 'evidence_refs': ['E-999']} ]}
        r = RydeOrchestrator(advocate_runner=bad, judge_runner=lambda *args: called.append(1)).run()
        self.assertEqual(called, [])
        self.assertEqual(r['ruling']['decision'], 'escalate')
        self.assertIn('INVALID_ADVOCATE_OUTPUT', r['validation_errors'])

    def test_one_round_response_receives_other_opening_symmetrically(self):
        received = []
        def recorder(s, side, round_name, opponent):
            received.append((side, round_name, copy.deepcopy(opponent)))
            return {'case_id': s['case_id'], 'side': side, 'claims': []}
        RydeOrchestrator(advocate_runner=recorder).run()
        self.assertEqual([x[2] for x in received[:2]], [None, None])
        self.assertEqual(received[2][2]['side'], 'driver')
        self.assertEqual(received[3][2]['side'], 'rider')

    def test_repeat_runs_do_not_mix_logs_or_cases(self):
        runner = RydeOrchestrator()
        a, b = runner.run(), runner.run('SYN-ROUTE-001')
        self.assertNotEqual(a['run_id'], b['run_id'])
        self.assertEqual(len(a['communication_log']), 8)
        self.assertEqual(len(b['communication_log']), 8)
        self.assertIsNot(a['communication_log'], b['communication_log'])
        for e in b['communication_log']:
            self.assertIn('started_at', e)
            self.assertIn('finished_at', e)
            self.assertGreaterEqual(e['duration_ms'], 0)

    def test_invalid_judge_proposal_never_remains_effective(self):
        def wrong(s, *args):
            r = review_ruling(s, ['missing'])
            r['case_id'] = 'WRONG'
            return r
        r = RydeOrchestrator(judge_runner=wrong).run()
        self.assertEqual(r['ruling']['case_id'], 'DISP-002')
        self.assertIsNone(r['judge_proposal'])
        self.assertTrue(r['validation_errors'])

    def test_unsupported_uphold_rejected_by_audit_gate(self):
        def overconfident(s, *args):
            return {'case_id': s['case_id'], 'decision': 'uphold_charge', 'refund_amount': 0,
                    'currency': 'SGD', 'amount_unit': 'major', 'uncertainties': [],
                    'escalate_to_human': False, 'confidence': 1,
                    'findings': [{'finding': '8 minutes therefore charge',
                                  'evidence_refs': ['E-001'], 'policy_refs': ['P-004']}]}
        r = RydeOrchestrator(judge_runner=overconfident).run()
        self.assertEqual(r['ruling']['decision'], 'escalate')
        self.assertIn('UNRESOLVED_DATA_OR_POLICY_REVIEW', r['validation_errors'])

    def test_bad_money_and_nan_bool_unknown_decision_rejected(self):
        base = review_ruling(self.s, ['review'])
        for key, val in [('confidence', float('nan')), ('confidence', True),
                         ('refund_amount', float('inf')), ('decision', 'pay_driver'),
                         ('currency', 'USD'), ('refund_amount', 0)]:
            obj = copy.deepcopy(base); obj[key] = val
            with self.subTest(key=key, val=val):
                self.assertTrue(check_judge(self.s, obj)[0])
        obj = copy.deepcopy(base)
        obj.update(decision='refund_partial', refund_amount=500, escalate_to_human=False)
        self.assertIn('REFUND_EXCEEDS_CHARGE_OR_CHARGE_UNKNOWN', check_judge(self.s, obj)[0])

    def test_large_finite_refund_cannot_crash_validation(self):
        out = review_ruling(self.s, ['review'])
        out.update(decision='refund_partial', refund_amount=1e308, escalate_to_human=False)
        self.assertIn('REFUND_EXCEEDS_CHARGE_OR_CHARGE_UNKNOWN', check_judge(self.s, out)[0])

    def test_model_config_repr_does_not_disclose_key(self):
        cfg = ModelConfig('https://example.test/chat/completions', 'm', 'secret-marker')
        self.assertNotIn('secret-marker', repr(cfg))

    def test_empty_escalation_findings_accepted(self):
        self.assertFalse(check_judge(self.s, review_ruling(self.s, ['Missing evidence']))[0])

    def test_unknown_policy_and_counterpoint_refs_rejected(self):
        out = {'case_id': 'DISP-002', 'side': 'driver', 'claims': [],
               'counterpoints': [{'claim': 'bad ref', 'evidence_refs': ['E-999']}]}
        self.assertTrue(check_advocate(self.s, out, 'driver')[0])
        judge = review_ruling(self.s, ['review'])
        judge['findings'] = [{'finding': 'a', 'evidence_refs': ['E-001'], 'policy_refs': ['P-999']}]
        self.assertTrue(check_judge(self.s, judge)[0])

    def test_nan_custom_output_is_not_written_to_logs(self):
        def bad(s, *args):
            r = review_ruling(s, ['review']); r['confidence'] = float('nan'); return r
        r = RydeOrchestrator(judge_runner=bad).run()
        json.dumps(r, allow_nan=False)
        self.assertTrue(r['validation_errors'])

    def test_model_context_separates_prompt_and_has_no_answer_key(self):
        messages = build_judge_messages(self.s, {}, calculate_rules(self.s))
        self.assertEqual([m['role'] for m in messages], ['system', 'user'])
        payload = json.loads(messages[1]['content'])
        self.assertEqual(payload['snapshot_id'], self.s['snapshot_id'])
        for forbidden in ['Expected ruling', 'expected_ruling', 'official_expected', 'Evidence Summary']:
            self.assertNotIn(forbidden, messages[1]['content'])
        self.assertIn('UNTRUSTED CASE DATA', messages[0]['content'])

    def test_remote_request_and_response_transport(self):
        transport = FakeTransport(completion(review_ruling(self.s, ['review'])))
        judge = HTTPJudge(ModelConfig('https://example.test/chat/completions', 'test-model', 'fake-key'), transport)
        r = RydeOrchestrator(judge_runner=judge).run()
        self.assertEqual(r['modes']['judge'], 'remote_llm')
        self.assertFalse(r['validation_errors'])
        req, timeout = transport.requests[0]
        self.assertEqual(req.get_header('Authorization'), 'Bearer fake-key')
        self.assertEqual(timeout, 45)
        body = json.loads(req.data)
        self.assertEqual(body['response_format'], {'type': 'json_object'})
        self.assertFalse(body['stream'])
        self.assertNotIn('fake-key', json.dumps(r))

    def test_remote_failures_turn_into_review_without_leaking_body_or_key(self):
        cases = [FakeTransport(b'not JSON'), FakeTransport(completion({}, 'length')),
                 FakeTransport(error=TimeoutError('fake-key')),
                 FakeTransport(error=HTTPError('secret-url', 401, 'fake-key', {}, io.BytesIO(b'fake-key')))]
        for transport in cases:
            judge = HTTPJudge(ModelConfig('https://example.test/chat/completions', 'm', 'fake-key'), transport)
            r = RydeOrchestrator(judge_runner=judge).run()
            self.assertEqual(r['ruling']['decision'], 'escalate')
            self.assertTrue(r['validation_errors'])
            self.assertNotIn('fake-key', json.dumps(r))
            self.assertNotIn('secret-url', json.dumps(r))

    def test_remote_config_explicit_and_https_required(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(AgentError):
            ModelConfig.from_env()
        with self.assertRaises(AgentError):
            ModelConfig('http://example.com/chat', 'm', 'k')
        with self.assertRaises(AgentError):
            ModelConfig('https://example.com/chat?key=x', 'm', 'k')

    def test_teammate_json_envelope_and_stale_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            doc = {'case_id': self.s['case_id'], 'snapshot_id': self.s['snapshot_id']}
            runner = OfflineAdvocate()
            for name in ('opening', 'response'):
                doc[name] = {side: runner(self.s, side, name) for side in ('rider', 'driver')}
            path = Path(d) / 'advocate.json'; path.write_text(json.dumps(doc))
            r = RydeOrchestrator(advocate_runner=FileAdvocate(path)).run()
            self.assertFalse(r['validation_errors'])
            self.assertEqual(r['modes']['advocate'], 'teammate_json')
            doc['snapshot_id'] = '0' * 64; path.write_text(json.dumps(doc))
            r = RydeOrchestrator(advocate_runner=FileAdvocate(path)).run()
            self.assertIn('ADVOCATE_SNAPSHOT_MISMATCH', r['validation_errors'])

    def test_cli_produces_two_cases_and_missing_remote_config_fails(self):
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--output-dir', d]), 0)
            for name in ['DISP-002.run.json', 'SYN-ROUTE-001.run.json', 'ryde-evaluation.html']:
                self.assertTrue((Path(d) / name).is_file())
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(main(['--judge', 'remote', '--output-dir', d]), 2)

    def test_ui_refs_resolve_and_case_text_is_escaped(self):
        class Tags(HTMLParser):
            def __init__(self): super().__init__(); self.ids=[]; self.targets=[]; self.panels=0
            def handle_starttag(self, tag, attrs):
                a=dict(attrs)
                if 'id' in a:self.ids.append(a['id'])
                if tag=='a' and a.get('href','').startswith('#'):self.targets.append(a['href'][1:])
                if a.get('role')=='tabpanel':self.panels+=1
        results=[RydeOrchestrator().run(c) for c in ['DISP-002', 'SYN-ROUTE-001']]
        results[0]['ruling']['uncertainties'].append('<script>alert("x")</script>')
        results[0]['ruling']['case_analysis']['sides']['rider']['reason'] = '<img src=x onerror=alert(1)>'
        results[0]['ruling']['case_analysis']['disputed_points'][0]['reasoning'] = '<script>alert("x")</script>'
        with tempfile.TemporaryDirectory() as d:
            page=render_html(results, Path(d)/'ui.html').read_text()
        parser=Tags();parser.feed(page)
        self.assertEqual(parser.panels,2)
        self.assertEqual(len(parser.ids),len(set(parser.ids)))
        self.assertTrue(set(parser.targets).issubset(parser.ids))
        self.assertNotIn('<script>alert(',page)
        self.assertIn('&lt;script&gt;',page)
        self.assertIn('offline_placeholder',page)
        self.assertIn('团队合成案例',page)
        self.assertIn('Judge 如何看双方观点', page)
        self.assertIn('必须补充政策或数据', page)
        self.assertIn('需 Judge 分析', page)
        self.assertIn('仅供提示', page)
        self.assertIn('当前是离线分析骨架', page)
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', page)
        self.assertNotIn('<img src=x', page)
        self.assertTrue(any('argument-opening-rider-claims-' in x for x in parser.targets))


if __name__ == '__main__':
    unittest.main()
