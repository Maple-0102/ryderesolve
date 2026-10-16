"""Opt-in compaction retains source content and changes resume identity, not facts."""
from dataclasses import replace
import json
import unittest
from ryde_resolve.agents import AgentError, build_judge_messages
from ryde_resolve.evidence import EvidenceGateway
from ryde_resolve.execution import runner_identity
from ryde_resolve.mock_agents import OfflineAdvocate
from ryde_resolve.rule_engine import calculate_rules
from ryde_resolve.vertex import VertexConfig, VertexJudge, compact_json_context
from test_vertex import Opener, response


class ContextCompactionTests(unittest.TestCase):
    def test_all_official_contexts_preserve_every_field_and_literal(self):
        for case_id in ('DISP-001','DISP-002','DISP-003'):
            s=EvidenceGateway().prepare(case_id)
            args={rnd:{side:OfflineAdvocate()(s,side,rnd) for side in ('rider','driver')} for rnd in ('opening','response')}
            original=build_judge_messages(s,args,calculate_rules(s))[1]['content']
            compact=compact_json_context(original)
            self.assertEqual(json.loads(compact),json.loads(original))
            self.assertLess(len(compact.encode()),len(original.encode()))
        text=' { "n": -0.00e+01, "dup":1, "dup":2, "quote": "a  b \\" c\\n d" } '
        compact=compact_json_context(text)
        self.assertEqual(compact,'{"n":-0.00e+01,"dup":1,"dup":2,"quote":"a  b \\" c\\n d"}')
        for invalid in ('not JSON','{"x":NaN}','```json\n{}\n```'):
            self.assertEqual(compact_json_context(invalid),invalid)

    def test_request_defaults_preserve_bytes_and_opt_in_is_audited_and_version_bound(self):
        original=' { "record": "someone said  two spaces", "n": -0.00e+01 } '
        base=VertexConfig('sample-project')
        op=Opener(response());normal=VertexJudge(base,opener=op,token_provider=lambda _: 'fake-secret')
        normal.generate('same rules',original)
        self.assertEqual(json.loads(op.requests[0].data)['contents'][0]['parts'][0]['text'],original)
        config=replace(base,compact_context=True)
        op2=Opener(response());compact=VertexJudge(config,opener=op2,token_provider=lambda _: 'fake-secret')
        compact.generate('same rules',original)
        body=json.loads(op2.requests[0].data)
        self.assertEqual(body['systemInstruction']['parts'][0]['text'],'same rules')
        self.assertEqual(json.loads(body['contents'][0]['parts'][0]['text']),json.loads(original))
        self.assertEqual(compact.last_metadata['context_encoding'],'minified_json')
        sizes=compact.last_metadata['context_bytes'];self.assertLess(sizes['sent'],sizes['input'])
        self.assertNotEqual(runner_identity(normal),runner_identity(compact))
        self.assertNotIn('fake-secret',json.dumps(compact.last_metadata))
        with self.assertRaisesRegex(AgentError,'INVALID_COMPACT_CONTEXT'):
            replace(base,compact_context='true')
