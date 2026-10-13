import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from ryderesolve_advocate import AdvocateSystem, CallableProvider, ContractError, validate_output
from ryderesolve_advocate.providers import GeminiProvider, ProviderError

ROOT = Path(__file__).resolve().parents[1]


def fixture(pack, side):
    return {"case_id": pack['case_id'], "side": side, "position": "request_review",
            "claims": [{"claim": "Recorded evidence requires assessment.",
                        "evidence_refs": [pack['facts'][0]['evidence_id']],
                        "policy_refs": [pack['policy'][0]['policy_id']]}],
            "counterpoints": [], "missing_information": []}


class Tests(unittest.TestCase):
    def setUp(self):
        self.pack = json.loads((ROOT / 'examples/input/DISP-002.evidence_pack.json').read_text(encoding="utf-8"))

    def test_two_case_contracts(self):
        for case in ('DISP-002', 'SYN-ROUTE-001'):
            pack = json.loads((ROOT / f'examples/input/{case}.evidence_pack.json').read_text(encoding="utf-8"))
            for side in ('rider', 'driver'):
                self.assertTrue(validate_output(fixture(pack, side), pack, side)['structurally_valid'])

    def test_unknown_evidence(self):
        output = fixture(self.pack, 'rider')
        output['claims'][0]['evidence_refs'] = ['E-FAKE']
        self.assertFalse(validate_output(output, self.pack, 'rider')['structurally_valid'])

    def test_unknown_policy(self):
        output = fixture(self.pack, 'rider')
        output['claims'][0]['policy_refs'] = ['P-FAKE']
        self.assertFalse(validate_output(output, self.pack, 'rider')['structurally_valid'])

    def test_wrong_side_and_case(self):
        output = fixture(self.pack, 'driver')
        output['case_id'] = 'OTHER'
        self.assertFalse(validate_output(output, self.pack, 'rider')['structurally_valid'])

    def test_empty_refs_warning(self):
        output = fixture(self.pack, 'rider')
        output['claims'][0]['evidence_refs'] = []
        self.assertEqual(validate_output(output, self.pack, 'rider')['warnings'][0]['code'], 'UNSUPPORTED_STATEMENT')

    def test_bad_nested_schema(self):
        output = fixture(self.pack, 'rider')
        output['counterpoints'] = ['invalid']
        self.assertFalse(validate_output(output, self.pack, 'rider')['structurally_valid'])

    def test_duplicate_input_id(self):
        pack = copy.deepcopy(self.pack)
        pack['facts'].append(pack['facts'][0])
        with self.assertRaises(ContractError):
            validate_output(fixture(pack, 'rider'), pack, 'rider')

    def test_invalid_model_json(self):
        agent = AdvocateSystem(CallableProvider(lambda s, u: 'not json'))
        with self.assertRaises(ContractError):
            agent.run_advocate(self.pack)

    def test_nan_rejected(self):
        output = fixture(self.pack, 'rider')
        output['extra'] = float('nan')
        self.assertFalse(validate_output(output, self.pack, 'rider')['structurally_valid'])

    def test_symmetric_rounds(self):
        seen = []
        def call(system, user):
            context = json.loads(user)
            side = 'rider' if 'SIDE = rider.' in system else 'driver'
            seen.append((side, context))
            return fixture(context['evidence_pack'], side)
        pair = AdvocateSystem(CallableProvider(call)).run_pair(self.pack, rebuttal=True)
        self.assertEqual(pair['rounds'], 2)
        self.assertEqual(len(seen), 4)
        self.assertNotIn('opponent_output', seen[0][1])
        self.assertNotIn('opponent_output', seen[1][1])
        self.assertEqual(seen[2][1]['opponent_output']['side'], 'driver')
        self.assertEqual(seen[3][1]['opponent_output']['side'], 'rider')

    def test_input_not_mutated_and_no_answer_key(self):
        original = copy.deepcopy(self.pack)
        seen = []
        def call(system, user):
            seen.append(user)
            return fixture(self.pack, 'rider')
        AdvocateSystem(CallableProvider(call)).run_advocate(self.pack)
        self.assertEqual(self.pack, original)
        self.assertNotIn('Expected ruling', seen[0])

    def test_no_credentials(self):
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(ProviderError):
                GeminiProvider.from_env()

    def test_model_path_rejected_before_network(self):
        with self.assertRaises(ProviderError):
            GeminiProvider('secret', '../bad').generate('system', 'user')

    def test_provider_failure_no_fallback(self):
        def fail(s, u):
            raise ProviderError('test failure')
        with self.assertRaises(ProviderError):
            AdvocateSystem(CallableProvider(fail)).run_advocate(self.pack)

    def test_gemini_request_and_response_offline(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self):
                return json.dumps({'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': '{}'}]}}]}).encode()
        with patch('urllib.request.OpenerDirector.open', return_value=Response()) as opened:
            self.assertEqual(GeminiProvider('test-secret', 'test-model').generate('s', 'u'), '{}')
            request = opened.call_args.args[0]
            self.assertEqual(request.get_header('X-goog-api-key'), 'test-secret')
            self.assertEqual(json.loads(request.data)['generationConfig']['responseMimeType'], 'application/json')


if __name__ == '__main__':
    unittest.main()
