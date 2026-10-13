"""Integration invariants for the real teammate module, with local fake transport."""
import copy
import json
import unittest
from ryde_resolve.agents import AgentError
from ryde_resolve.evidence import EvidenceGateway
from ryde_resolve.orchestrator import RydeOrchestrator
from ryde_resolve.teammate_advocate import TeammateAdvocate
from evaluation.fixtures import with_verification


class FakeClient:
    def __init__(self): self.inputs=[]; self.last_metadata={}; self.mutate=None
    def generate(self, system, user, max_output_tokens):
        context=json.loads(user); self.inputs.append((system,context,max_output_tokens))
        pack=context['evidence_pack']; side='rider' if 'SIDE = rider.' in system else 'driver'
        out={'case_id':pack['case_id'],'side':side,'position':'request_review',
             'claims':[{'claim':'A test-provider argument; no model was called.',
                        'evidence_refs':[pack['facts'][0]['evidence_id']], 'policy_refs':[]}],
             'counterpoints':[],'missing_information':['Test provider only.']}
        self.last_metadata={'provider':'local_test', 'usage':{'totalTokenCount':0}}
        if self.mutate: self.mutate(out)
        return out


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.s=EvidenceGateway().prepare('DISP-002');self.client=FakeClient();self.a=TeammateAdvocate(self.client)

    def test_two_symmetric_rounds_and_safe_transport_log(self):
        r=RydeOrchestrator(advocate_runner=self.a).run('DISP-002')
        self.assertFalse(r['validation_errors'],r['validation_errors']);self.assertEqual(len(self.client.inputs),4)
        self.assertEqual(r['modes']['advocate'],'teammate_custom_provider')
        for _,c,cap in self.client.inputs[:2]:
            self.assertNotIn('opponent_output',c);self.assertEqual(cap,8192)
        self.assertEqual(self.client.inputs[2][1]['opponent_output']['side'],'driver')
        self.assertEqual(self.client.inputs[3][1]['opponent_output']['side'],'rider')
        self.assertTrue(all(x['transport']['provider']=='local_test' for x in r['communication_log'] if x['step'] in ('opening','response')))
        self.assertTrue(all(o['snapshot_id']==self.s['snapshot_id'] for rnd in r['arguments'].values() for o in rnd.values()))

    def test_inputs_are_unchanged_and_scoring_labels_absent(self):
        before=copy.deepcopy(self.s);self.a(self.s,'rider','opening')
        self.assertEqual(self.s,before)
        text=json.dumps(self.client.inputs[0][1]);self.assertNotIn('expected',text);self.assertNotIn('exercise_id',text)

    def test_wrong_reference_or_role_is_rejected(self):
        for mutation in (lambda o:o.update(side='customer'), lambda o:o['claims'][0].update(evidence_refs=['E-FAKE'])):
            self.client.mutate=mutation
            with self.assertRaisesRegex(AgentError,'TEAM_CONTRACT'):self.a(self.s,'rider','opening')

    def test_missing_or_stale_opponent_is_rejected_before_call(self):
        for opponent in (None, {'snapshot_id':'old'}):
            with self.assertRaises(AgentError):self.a(self.s,'rider','response',opponent)
        self.assertFalse(self.client.inputs)

    def test_initial_round_cannot_see_opponent(self):
        with self.assertRaisesRegex(AgentError,'INDEPENDENT'):self.a(self.s,'rider','opening',{})
        self.assertFalse(self.client.inputs)

    def test_both_cases_use_current_evidence_without_copying_fixture_pack(self):
        for case in ('DISP-002','SYN-ROUTE-001'):
            r=RydeOrchestrator(advocate_runner=self.a).run(case)
            self.assertFalse(r['validation_errors'],r['validation_errors'])
            self.assertEqual(r['snapshot']['snapshot_id'],r['arguments']['opening']['rider']['snapshot_id'])

    def test_teammate_advocates_regenerate_after_new_evidence_snapshot(self):
        o=RydeOrchestrator(advocate_runner=self.a);old=o.run('SYN-ROUTE-001')
        new=o.rerun_with_supplement(old,with_verification(old['snapshot']),source_note='Synthetic integration test')
        self.assertFalse(new['validation_errors']);self.assertEqual(len(self.client.inputs),8)
        self.assertNotEqual(old['arguments']['opening']['rider']['snapshot_id'],new['arguments']['opening']['rider']['snapshot_id'])


if __name__ == '__main__': unittest.main()
