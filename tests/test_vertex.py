"""Credential-safe Gemini transport and CLI integration checks; no external calls."""
import io
import json
import tempfile
import subprocess
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from ryde_resolve.agents import AgentError
from ryde_resolve.vertex import VertexConfig, VertexJudge, MAX_RESPONSE, adc_token
from ryde_resolve.evidence import EvidenceGateway
from ryde_resolve.mock_agents import OfflineJudge, OfflineAdvocate
from ryde_resolve.rule_engine import calculate_rules


class Opener:
    def __init__(self, obj): self.raw=json.dumps(obj).encode(); self.requests=[]
    def open(self, request, timeout): self.requests.append(request); return io.BytesIO(self.raw)


def response(text='{"confidence":0.5}', reason='STOP'):
    return {'candidates':[{'finishReason':reason,'content':{'parts':[{'text':text}]}}],
            'modelVersion':'gemini-3.8-flash', 'usageMetadata':{'promptTokenCount':12, 'totalTokenCount':20}}


class VertexTests(unittest.TestCase):
    def judge(self, obj=None):
        op=Opener(response() if obj is None else obj)
        return VertexJudge(VertexConfig('sample-project'), opener=op, token_provider=lambda c:'fake-secret'),op

    def test_only_google_endpoint_and_path_safe_config(self):
        for kw in [{'project':'x/../../other'},{'model':'gemini-a?key=x'},{'location':'evil.com'},{'timeout':float('nan')}]:
            with self.assertRaises(AgentError): VertexConfig(**({'project':'sample-project'}|kw))
        self.assertTrue(VertexConfig('sample-project').endpoint.startswith('https://aiplatform.googleapis.com/'))

    def test_request_and_metadata_exclude_token_and_no_tools(self):
        judge,op=self.judge();self.assertEqual(judge.generate('rules','data'),{'confidence':0.5})
        req=op.requests[0];body=json.loads(req.data)
        self.assertEqual(req.get_header('Authorization'),'Bearer fake-secret')
        self.assertEqual(req.get_header('X-goog-user-project'),'sample-project')
        self.assertEqual(body['systemInstruction']['parts'][0]['text'],'rules')
        self.assertNotIn('tools',body)
        self.assertNotIn('fake-secret',json.dumps(judge.last_metadata))
        self.assertEqual(judge.last_metadata['usage']['totalTokenCount'],20)

    def test_truncation_block_and_function_call_rejected(self):
        cases=[response(reason='MAX_TOKENS'),{'promptFeedback':{'blockReason':'SAFETY'}},
               {'candidates':[{'finishReason':'STOP','content':{'parts':[{'functionCall':{'name':'x'}}]}}]}]
        for obj in cases:
            judge,_=self.judge(obj)
            with self.assertRaises(AgentError): judge.generate('rules','data')

    def test_truncated_response_retains_safe_diagnostics(self):
        judge,_=self.judge(response(reason='MAX_TOKENS'))
        with self.assertRaisesRegex(AgentError,'MAX_TOKENS'):judge.generate('rules','data')
        self.assertEqual(judge.last_metadata['finish_reason'],'MAX_TOKENS')
        self.assertEqual(judge.last_metadata['usage']['totalTokenCount'],20)

    def test_thought_content_not_parsed_as_answer(self):
        obj=response();obj['candidates'][0]['content']['parts'].insert(0,{'thought':True,'text':'not json'})
        judge,_=self.judge(obj);self.assertEqual(judge.generate('rules','data')['confidence'],0.5)

    def test_malformed_json_and_non_objects_rejected(self):
        for text in ['nope','[]','{"confidence":NaN}','```json\n{}\n```']:
            judge,_=self.judge(response(text))
            with self.assertRaises(AgentError): judge.generate('rules','data')

    def test_oversize_error_safe_and_metadata_cleared(self):
        judge,op=self.judge();judge.generate('rules','data')
        op.raw=b'x'*(MAX_RESPONSE+1)
        with self.assertRaisesRegex(AgentError,'TOO_LARGE'):judge.generate('rules','data')
        self.assertEqual(judge.last_metadata,{})
        with patch.object(op,'open',side_effect=HTTPError('https://secret',403,'fake-secret',{},io.BytesIO(b'fake-secret'))):
            with self.assertRaises(AgentError) as ctx:judge.generate('rules','data')
            self.assertEqual(str(ctx.exception),'VERTEX_HTTP_403')

    def test_actual_judge_payload_and_required_confidence(self):
        snap=EvidenceGateway().prepare('DISP-002');calc=calculate_rules(snap)
        args={rnd:{side:OfflineAdvocate()(snap,side,rnd) for side in ('rider','driver')} for rnd in ('opening','response')}
        for confidence in [None,True,-1,2]:
            judge,_=self.judge(response(json.dumps({'confidence':confidence})))
            with self.assertRaisesRegex(AgentError,'CONFIDENCE'):judge(snap,args,calc)
        out=OfflineJudge()(snap,args,calc);out['confidence']=0.5
        judge,op=self.judge(response(json.dumps(out)));self.assertEqual(judge(snap,args,calc),out)
        payload=json.loads(json.loads(op.requests[0].data)['contents'][0]['parts'][0]['text'])
        self.assertEqual(payload['case_id'],'DISP-002');self.assertNotIn('expected',payload)

    def test_cli_constructs_vertex_and_preserves_offline_default(self):
        from ryde_resolve.run_demo import main
        with patch('ryde_resolve.run_demo.VertexConfig.from_env',side_effect=AgentError('VERTEX_ADC_MISSING_OR_INVALID')) as config:
            self.assertEqual(main(['--judge','vertex','--case','DISP-002']),2);config.assert_called_once()


class ADCCredentialTests(unittest.TestCase):
    def test_missing_credentials_do_not_start_process(self):
        with tempfile.TemporaryDirectory() as temp, patch('ryde_resolve.vertex.ROOT',Path(temp)), patch('ryde_resolve.vertex.subprocess.run') as run:
            with self.assertRaisesRegex(AgentError,'ADC_MISSING'):adc_token(VertexConfig('sample-project'))
            run.assert_not_called()

    def test_quota_mismatch_and_public_file_rejected(self):
        with tempfile.TemporaryDirectory() as temp, patch('ryde_resolve.vertex.ROOT',Path(temp)), patch('ryde_resolve.vertex.subprocess.run') as run:
            p=Path(temp)/'.local/gcloud/application_default_credentials.json';p.parent.mkdir(parents=True)
            p.write_text(json.dumps({'quota_project_id':'another-project'}));p.chmod(0o600)
            with self.assertRaisesRegex(AgentError,'QUOTA_PROJECT_MISMATCH'):adc_token(VertexConfig('sample-project'))
            p.chmod(0o644)
            with self.assertRaisesRegex(AgentError,'UNSAFE_FILE'):adc_token(VertexConfig('sample-project'))
            run.assert_not_called()

    def test_token_captured_not_in_command_and_errors_redacted(self):
        with tempfile.TemporaryDirectory() as temp, patch('ryde_resolve.vertex.ROOT',Path(temp)), patch('ryde_resolve.vertex.subprocess.run') as run:
            p=Path(temp)/'.local/gcloud/application_default_credentials.json';p.parent.mkdir(parents=True)
            p.write_text(json.dumps({'quota_project_id':'sample-project'}));p.chmod(0o600)
            run.return_value=subprocess.CompletedProcess([],0,'fake-secret\n','')
            self.assertEqual(adc_token(VertexConfig('sample-project')),'fake-secret')
            self.assertNotIn('fake-secret',str(run.call_args.args))
            self.assertEqual(run.call_args.kwargs['env']['CLOUDSDK_CONFIG'],str(p.parent))
            run.return_value=subprocess.CompletedProcess([],1,'','secret-credential-detail')
            with self.assertRaises(AgentError) as e:adc_token(VertexConfig('sample-project'))
            self.assertEqual(str(e.exception),'VERTEX_ADC_REFRESH_FAILED')

class ThinkingLevelTests(unittest.TestCase):
    def test_explicit_supported_level_sent_and_recorded(self):
        op=Opener(response())
        judge=VertexJudge(VertexConfig('sample-project', thinking_level='LOW'), opener=op, token_provider=lambda c:'fake-secret')
        judge.generate('rules','data')
        body=json.loads(op.requests[0].data)
        self.assertEqual(body['generationConfig']['thinkingConfig'],{'thinkingLevel':'LOW'})
        self.assertNotIn('thinkingBudget',body['generationConfig']['thinkingConfig'])
        self.assertEqual(judge.last_metadata['thinking_level'],'LOW')

    def test_unspecified_level_preserves_provider_default(self):
        op=Opener(response());judge=VertexJudge(VertexConfig('sample-project'),opener=op,token_provider=lambda c:'fake-secret')
        judge.generate('rules','data')
        self.assertNotIn('thinkingConfig',json.loads(op.requests[0].data)['generationConfig'])
        self.assertEqual(judge.last_metadata['thinking_level'],'provider_default')

    def test_unknown_level_or_older_model_rejected_before_request(self):
        for kw in ({'thinking_level':'UNBOUNDED'}, {'model':'gemini-2.5-flash','thinking_level':'LOW'}):
            with self.assertRaisesRegex(AgentError,'THINKING_LEVEL'): VertexConfig('sample-project',**kw)
