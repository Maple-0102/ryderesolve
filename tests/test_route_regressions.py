"""Protect real failure handling, provider constraints and separate charging conditions."""
from copy import deepcopy
import io
import json
from pathlib import Path
import unittest
import tempfile
import subprocess
from jsonschema import Draft202012Validator
from evaluation.route_regressions import build_route_regressions
from ryde_resolve.agents import build_judge_messages
from ryde_resolve.contracts import check_judge
from ryde_resolve.evidence import EvidenceGateway
from ryde_resolve.mock_agents import OfflineJudge
from ryde_resolve.output_schema import judge_output_schema, vertex_response_schema
from ryde_resolve.rule_engine import calculate_rules
from ryde_resolve.vertex import VertexConfig, VertexJudge
from test_reasoning import analysed_route
from test_teammate_advocate import FakeClient
from ryde_resolve.teammate_advocate import TeammateAdvocate
from ryde_resolve.statement_gate import downgrade_statement_only_review
from ryde_resolve.orchestrator import RydeOrchestrator


class Recorder:
    def __init__(self, output): self.output = output; self.requests = []
    def open(self, request, timeout):
        self.requests.append(json.loads(request.data))
        return io.BytesIO(json.dumps({'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(self.output)}]}}]}).encode())


class RouteRegressions(unittest.TestCase):
    def test_credential_directory_links_are_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'credential-store').mkdir()
            try:
                (root/'.local').symlink_to(root/'credential-store',target_is_directory=True)
            except OSError:
                self.skipTest('Directory symlinks require local OS support')
            ignore=Path(__file__).resolve().parents[1]/'.gitignore'
            (root/'.gitignore').write_text(ignore.read_text())
            subprocess.run(['git','init','-q'],cwd=root,check=True,capture_output=True)
            result=subprocess.run(['git','check-ignore','.local'],cwd=root,capture_output=True,text=True)
            self.assertEqual(result.returncode,0)

    def test_recorded_missing_fields_remain_a_rejected_output(self):
        doc = json.loads((Path(__file__).parent/'fixtures/route-baseline-rejected.json').read_text())
        original = deepcopy(doc['judge_output']); s = EvidenceGateway().prepare('SYN-ROUTE-001')
        self.assertEqual(doc['judge_output']['case_id'], s['case_id'])  # Retain the original normalizer's historical ID.
        failures = list(Draft202012Validator(judge_output_schema()).iter_errors(original))
        self.assertEqual({tuple(e.path) for e in failures}, {('case_analysis','argument_assessments',i) for i in range(19,24)})
        errors, _ = check_judge(s, original, doc['arguments'])
        self.assertEqual(sum('INVALID_CASE_ANALYSIS' in e for e in errors), 5)
        self.assertEqual(original, doc['judge_output'])  # No silent repair of the historical failure.

    def test_vertex_judge_sends_required_nested_fields_to_provider(self):
        x = build_route_regressions()[0]
        output = OfflineJudge()(x['snapshot'], x['arguments'], calculate_rules(x['snapshot'])); output['confidence'] = .5
        op = Recorder(output); j = VertexJudge(VertexConfig('sample-project'), op, lambda c:'fake-token')
        self.assertEqual(j(x['snapshot'], x['arguments'], calculate_rules(x['snapshot'])), output)
        schema = op.requests[0]['generationConfig']['responseSchema']
        ledger = schema['properties']['case_analysis']['properties']['argument_assessments']['items']
        self.assertIn('opposing_evidence_refs', ledger['required'])
        self.assertIn('missing_information', ledger['required'])
        self.assertEqual(ledger['properties']['opposing_evidence_refs']['type'], 'ARRAY')
        self.assertTrue(schema['properties']['refund_amount']['nullable'])
        self.assertEqual(schema['properties']['case_analysis']['properties']['sides']['required'], ['rider','driver'])
        self.assertTrue(j.last_metadata['response_schema_sha256'])
        payload = json.loads(op.requests[0]['contents'][0]['parts'][0]['text'])
        self.assertNotIn('expected', payload)

    def test_schema_conversion_keeps_all_required_shapes_and_order(self):
        source = judge_output_schema(); before = deepcopy(source); compiled = vertex_response_schema(source)
        def compare(a,b):
            self.assertEqual(a.get('required',[]), b.get('required',[]))
            if 'properties' in a:
                self.assertEqual(list(a['properties']), b['propertyOrdering'])
                for name,v in a['properties'].items(): compare(v,b['properties'][name])
            if 'items' in a: compare(a['items'],b['items'])
        compare(source,compiled);self.assertEqual(source,before)
        self.assertNotIn('uniqueItems',json.dumps(compiled))

    def test_guidance_reaches_both_roles_without_modifying_evidence(self):
        s = EvidenceGateway().prepare('SYN-ROUTE-001'); before = deepcopy(s)
        client=FakeClient();a=TeammateAdvocate(client)
        a(s,'rider','opening');a(s,'driver','opening')
        x=build_route_regressions()[0]
        prompt=build_judge_messages(s,x['arguments'],calculate_rules(s))[0]['content']
        for text in [prompt]+[p[0] for p in client.inputs]:
            for rule in ['SAMPLED VERSUS CONTINUOUS','UNVERIFIED VERSUS DISPROVED','ROUTE VERSUS CHARGE','POLICY ORIGIN']:
                self.assertIn(rule,text)
        self.assertEqual(s,before)
        self.assertFalse(any('responseSchema' in json.dumps(c[1]) for c in client.inputs))

    def test_justified_route_can_refund_invalid_charge(self):
        x=build_route_regressions()[2];s=x['snapshot'];a=x['arguments']
        out=analysed_route(s,a,decision='refund_partial')
        next(c for c in out['case_analysis']['decision_conditions'] if c['condition_id']=='route_justification')['status']='met'
        errors,_=check_judge(s,out,a);self.assertFalse(errors,errors)
        wrongly_upheld=deepcopy(out);wrongly_upheld.update(decision='uphold_charge',refund_amount=0)
        self.assertTrue(any('DECISION_CONDITION_CONFLICT' in e for e in check_judge(s,wrongly_upheld,a)[0]))

    def test_missing_traffic_evidence_cannot_become_refund_entitlement(self):
        x=build_route_regressions()[1]
        out=analysed_route(x['snapshot'],x['arguments'],decision='refund_partial')
        self.assertTrue(check_judge(x['snapshot'],out,x['arguments'])[0])

    def statement_fixture(self):
        return json.loads((Path(__file__).parent/'fixtures/route-statement-only-rejected.json').read_text())

    def test_statement_downgrade_retains_raw_proposal_and_all_material_conditions(self):
        doc=self.statement_fixture();s=EvidenceGateway().prepare('SYN-ROUTE-001')
        before=deepcopy(doc['judge_output']);candidate,changes=downgrade_statement_only_review(s,before)
        self.assertEqual(len(changes),2);self.assertEqual(before,doc['judge_output'])
        for key in ['decision','refund_amount','uncertainties','escalate_to_human']:
            self.assertEqual(candidate[key],before[key])
        self.assertEqual(candidate['case_analysis']['decision_conditions'],before['case_analysis']['decision_conditions'])
        self.assertFalse(check_judge(s,candidate,doc['arguments'])[0])
        self.assertTrue(check_judge(s,before,doc['arguments'])[0])

    def test_statement_gate_never_repairs_decisive_or_malformed_or_unknown_refs(self):
        doc=self.statement_fixture();s=EvidenceGateway().prepare('SYN-ROUTE-001')
        decisive=deepcopy(doc['judge_output']);decisive['decision']='refund_partial'
        self.assertEqual(downgrade_statement_only_review(s,decisive),(decisive,[]))
        malformed=deepcopy(doc['judge_output']);del malformed['case_analysis']['argument_assessments'][0]['opposing_evidence_refs']
        self.assertEqual(downgrade_statement_only_review(s,malformed),(malformed,[]))
        unknown=deepcopy(doc['judge_output'])
        for row in unknown['case_analysis']['argument_assessments']:row['supporting_evidence_refs']=['E-NOT-IN-CASE']
        self.assertEqual(downgrade_statement_only_review(s,unknown),(unknown,[]))

    def test_orchestrator_applies_only_fully_revalidated_review_corrections(self):
        doc=self.statement_fixture()
        def advocate(s,side,rnd,opponent):return deepcopy(doc['arguments'][rnd][side])
        def judge(s,a,c):return deepcopy(doc['judge_output'])
        run=RydeOrchestrator(advocate_runner=advocate,judge_runner=judge).run('SYN-ROUTE-001')
        self.assertFalse(run['validation_errors']);self.assertEqual(len(run['judge_raw_validation_errors']),2)
        self.assertEqual(run['judge_proposal'],doc['judge_output']);self.assertEqual(len(run['judge_adjustments']),2)
        self.assertEqual(run['ruling']['decision'],'escalate')
        self.assertTrue(any(w['code']=='STATEMENT_ONLY_REVIEW_DOWNGRADE' for w in run['validation_warnings']))
        from ryde_resolve.ui import render_html
        with tempfile.TemporaryDirectory() as temp:
            page=render_html([run],Path(temp)/'review.html').read_text()
            self.assertIn('程序保守修正',page)
            self.assertIn('原始模型检查错误',page)
            self.assertIn('原始 Judge 建议',page)


    def test_unrelated_fault_still_blocks_after_a_statement_downgrade(self):
        doc=self.statement_fixture();bad=deepcopy(doc['judge_output'])
        bad['case_analysis']['decision_conditions'][0]['evidence_refs']=['E-NOT-IN-CASE']
        def advocate(s,side,rnd,opponent):return deepcopy(doc['arguments'][rnd][side])
        run=RydeOrchestrator(advocate_runner=advocate,judge_runner=lambda s,a,c:deepcopy(bad)).run('SYN-ROUTE-001')
        self.assertTrue(run['validation_errors']);self.assertEqual(run['judge_adjustments'],[])
        self.assertIsNone(run['judge_proposal'])

    def test_scoring_targets_are_not_model_inputs(self):
        for x in build_route_regressions():
            x['expected']['sentinel']='SCORER_ONLY_ROUTE_FIX'
            payload=build_judge_messages(x['snapshot'],x['arguments'],calculate_rules(x['snapshot']))
            self.assertNotIn('SCORER_ONLY_ROUTE_FIX',json.dumps(payload))


if __name__ == '__main__': unittest.main()
