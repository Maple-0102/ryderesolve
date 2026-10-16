"""ADP transport, stream boundaries and local setup. Only a loopback test uses sockets."""
import copy
import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ryde_resolve.adp import ADPConfig, ADPJudge, read_sse, ENDPOINT
from ryde_resolve.adp_setup import save_key, prepare_console
from ryde_resolve.agents import AgentError
from ryde_resolve.evidence import EvidenceGateway
from ryde_resolve.mock_agents import OfflineJudge, OfflineAdvocate
from ryde_resolve.rule_engine import calculate_rules
from ryde_resolve.orchestrator import RydeOrchestrator
from ryde_resolve.run_demo import main


def frame(kind, payload, wrapper=None):
    body = {'Type':kind, **payload} if wrapper is None else {'Type':kind, wrapper:payload}
    return ('event: '+kind+'\r\ndata: '+json.dumps(body,ensure_ascii=False)+'\r\n\r\n').encode()


DONE = b'event: done\ndata: [DONE]\n\n'


def completed(output, wrapper=None):
    return frame('response.completed', {'Response': {'Messages':[{'Contents':[{'Type':'text','Text':json.dumps(output,ensure_ascii=False)}]}],
                        'StatInfo':{'InputTokens':12,'OutputTokens':10,'TotalTokens':22,'TotalCost':0.01}}}, wrapper)


class FakeResponse(io.BytesIO):
    headers = {'Content-Type':'text/event-stream; charset=utf-8'}


class FakeOpener:
    def __init__(self, data=None, error=None): self.data=data; self.error=error; self.requests=[]
    def open(self, req, timeout):
        self.requests.append(req)
        if self.error: raise self.error
        return FakeResponse(self.data)


class ADPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = EvidenceGateway().prepare('DISP-002')
        cls.args = {rnd:{side:OfflineAdvocate()(cls.s,side,rnd) for side in ('rider','driver')} for rnd in ('opening','response')}
        cls.calc = calculate_rules(cls.s)
        cls.out = OfflineJudge()(cls.s,cls.args,cls.calc); cls.out['confidence']=0.4

    def test_top_level_and_wrapped_completed_frames(self):
        for wrapper in (None,'Payload','Data'):
            out,meta=read_sse(FakeResponse(completed(self.out,wrapper)+DONE),120)
            self.assertEqual(out,self.out); self.assertEqual(meta['usage']['total_tokens'],22)

    def test_completed_answer_supersedes_stream_draft(self):
        raw=frame('text.delta',{'Text':'wrong draft'})+completed(self.out)+DONE
        self.assertEqual(read_sse(FakeResponse(raw),120)[0],self.out)

    def test_incremental_replace_and_done_without_completed(self):
        text=json.dumps(self.out,ensure_ascii=False)
        raw=frame('text.delta',{'Text':'draft'})+frame('text.replace',{'Text':text[:20]})+frame('text.delta',{'Text':text[20:]})+DONE
        out,meta=read_sse(FakeResponse(raw),120)
        self.assertEqual(out,self.out); self.assertFalse(meta['completion_event'])

    def test_truncated_stream_cannot_pass_even_with_valid_json(self):
        for raw in (completed(self.out), frame('text.delta',{'Text':json.dumps(self.out)})):
            with self.assertRaisesRegex(AgentError,'INCOMPLETE_STREAM'): read_sse(FakeResponse(raw),120)

    def test_error_after_partial_answer_does_not_leak_secrets(self):
        raw=completed(self.out)+frame('error',{'Code':'secret-app-key','Message':'secret-app-key'})+DONE
        with self.assertRaises(AgentError) as e: read_sse(FakeResponse(raw),120)
        self.assertEqual(str(e.exception),'ADP_SERVICE_ERROR')

    def test_malformed_empty_and_oversized_streams(self):
        cases=[(b'data: nope\n\n'+DONE,'INVALID_SSE_JSON'),(DONE,'EMPTY_RESPONSE'),
               (b'data: \xff\n\n'+DONE,'INVALID_SSE_ENCODING'),(b'x'*1_000_001,'RESPONSE_TOO_LARGE'),
               (frame('text.delta',{'Text':'not JSON'})+DONE,'INVALID_JUDGE_JSON')]
        for raw,code in cases:
            with self.subTest(code=code),self.assertRaisesRegex(AgentError,code): read_sse(FakeResponse(raw),120)

    def test_comment_multiline_and_final_line_without_blank(self):
        text=json.dumps(self.out)
        raw=b': keepalive\n\nevent: text.delta\ndata: {"Text":\ndata: '+json.dumps(text).encode()+b'}\n\nevent: done\ndata: [DONE]'
        self.assertEqual(read_sse(FakeResponse(raw),120)[0],self.out)

    def test_fences_allowed_but_surrounding_prose_rejected(self):
        text=json.dumps(self.out)
        good=frame('text.delta',{'Text':'```json\n'+text+'\n```'})+DONE
        self.assertEqual(read_sse(FakeResponse(good),120)[0],self.out)
        with self.assertRaisesRegex(AgentError,'INVALID_JUDGE_JSON'):
            read_sse(FakeResponse(frame('text.delta',{'Text':'Result: '+text})+DONE),120)

    def test_fresh_ids_request_shape_and_metadata(self):
        fake=FakeOpener(completed(self.out)+DONE); judge=ADPJudge(ADPConfig('test-app-key'),fake)
        for _ in range(2): self.assertEqual(judge(self.s,self.args,self.calc),self.out)
        bodies=[json.loads(r.data) for r in fake.requests]
        self.assertEqual(bodies[0]['AppKey'],'test-app-key')
        self.assertEqual(bodies[0]['Stream'],'enable'); self.assertIs(bodies[0]['Incremental'],True)
        for key in ('RequestId','ConversationId','VisitorId'): self.assertNotEqual(bodies[0][key],bodies[1][key])
        self.assertNotIn('test-app-key',bodies[0]['Contents'][0]['Text'])
        self.assertNotIn('test-app-key',json.dumps(judge.last_metadata))
        self.assertNotIn('test-app-key',repr(judge.config))
        self.assertNotIn('evaluation/',bodies[0]['Contents'][0]['Text'])

    def test_http_and_network_errors_are_sanitized(self):
        for error in (HTTPError('secret',401,'secret',{},io.BytesIO(b'secret')),URLError('secret')):
            judge=ADPJudge(ADPConfig('test-app-key'),FakeOpener(error=error))
            with self.assertRaises(AgentError) as e: judge(self.s,self.args,self.calc)
            self.assertNotIn('secret',str(e.exception));self.assertEqual(judge.last_metadata,{})

    def test_missing_bad_confidence_and_content_type(self):
        for score in (None,True,1.5,-0.1):
            out=copy.deepcopy(self.out);out['confidence']=score
            judge=ADPJudge(ADPConfig('test-app-key'),FakeOpener(completed(out)+DONE))
            with self.assertRaisesRegex(AgentError,'CONFIDENCE_REQUIRED'): judge(self.s,self.args,self.calc)
        with patch.object(FakeResponse,'headers',{'Content-Type':'text/html'}):
            judge=ADPJudge(ADPConfig('test-app-key'),FakeOpener(completed(self.out)+DONE))
            with self.assertRaisesRegex(AgentError,'UNEXPECTED_CONTENT_TYPE'): judge(self.s,self.args,self.calc)

    def test_endpoint_and_timeout_validation(self):
        for url in ('https://unrelated.example/adp','http://wss.lke.tencentcloud.com/adp/v2/chat',ENDPOINT+'?key=x'):
            with self.assertRaises(AgentError): ADPConfig('test-key',url)
        for timeout in (float('nan'),0,301):
            with self.assertRaises(AgentError): ADPConfig('test-key',timeout=timeout)

    @unittest.skipIf(os.name == 'nt', 'POSIX fchmod/0600; run in Linux CI or WSL')
    def test_local_key_private_and_env_precedence(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{},clear=True):
            p=Path(d)/'.local/key';save_key('private-test-key',p)
            self.assertEqual(p.stat().st_mode & 0o777,0o600)
            with patch('ryde_resolve.adp.KEY_FILE',p):
                self.assertEqual(ADPConfig.from_env().app_key,'private-test-key')
                with patch.dict(os.environ,{'ADP_APP_KEY':'environment-test-key'}):
                    self.assertEqual(ADPConfig.from_env().app_key,'environment-test-key')
                p.chmod(0o644)
                with self.assertRaisesRegex(AgentError,'PERMISSIONS'): ADPConfig.from_env()

    def test_symlink_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            original=Path(d)/'existing';original.write_text('keep')
            link=Path(d)/'link'
            try:
                link.symlink_to(original)
            except OSError as exc:
                if os.name == 'nt' and getattr(exc, 'winerror', None) == 1314:
                    self.skipTest('Windows symlink privilege unavailable; exercised in Linux CI')
                raise
            with self.assertRaisesRegex(AgentError,'UNSAFE'): save_key('new-test-key',link)
            self.assertEqual(original.read_text(),'keep')

    def test_prepare_console_is_offline_and_contains_no_answer_key(self):
        with tempfile.TemporaryDirectory() as d:
            prepare_console(d)
            prompt=(Path(d)/'judge-system-prompt.txt').read_text()
            data=(Path(d)/'judge-debug-input.txt').read_text()
            self.assertIn('confidence',prompt)
            self.assertIn('UNTRUSTED CASE DATA',data)
            self.assertNotIn('expected_ruling',data);self.assertNotIn('AppKey',data)
            self.assertEqual(json.loads((Path(d)/'setup-manifest.json').read_text())['cloud_status'],'not_configured_by_this_command')

    def test_adp_cli_missing_configuration_fails_without_mock_fallback(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{},clear=True),patch('ryde_resolve.adp.KEY_FILE',Path(d)/'absent'),patch('sys.stderr',new_callable=io.StringIO):
            self.assertEqual(main(['--judge','adp','--case','DISP-002','--output-dir',d]),2)
            self.assertFalse((Path(d)/'DISP-002.run.json').exists())

    def test_failed_call_does_not_reuse_metadata(self):
        fake=FakeOpener(completed(self.out)+DONE);judge=ADPJudge(ADPConfig('test-key'),fake)
        judge(self.s,self.args,self.calc);self.assertTrue(judge.last_metadata)
        fake.data=b''
        with self.assertRaises(AgentError): judge(self.s,self.args,self.calc)
        self.assertEqual(judge.last_metadata,{})


class ADPLoopbackTests(unittest.TestCase):
    def run_transport(self, redirect=False):
        requests=[];s=EvidenceGateway().prepare('DISP-002')
        args={rnd:{side:OfflineAdvocate()(s,side,rnd) for side in ('rider','driver')} for rnd in ('opening','response')}
        output=OfflineJudge()(s,args,calculate_rules(s));output['confidence']=0.4
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*a): pass
            def do_POST(self):
                requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                if redirect:
                    self.send_response(307);self.send_header('Location','/blocked');self.end_headers();return
                data=completed(output)+DONE
                self.send_response(200);self.send_header('Content-Type','text/event-stream')
                self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            judge=ADPJudge(ADPConfig('local-stub-key',f'http://127.0.0.1:{server.server_port}/adp/v2/chat'))
            result=RydeOrchestrator(judge_runner=judge).run()
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)
        return result,requests

    def test_real_sse_http_transport_and_key_not_in_logs(self):
        result,requests=self.run_transport()
        self.assertFalse(result['validation_errors']);self.assertEqual(len(requests),1)
        self.assertEqual(requests[0]['AppKey'],'local-stub-key')
        self.assertEqual(result['modes']['judge'],'tencent_adp')
        self.assertEqual(result['judge_transport']['usage']['total_tokens'],22)
        self.assertNotIn('local-stub-key',json.dumps(result))

    def test_redirect_cannot_forward_appkey(self):
        result,requests=self.run_transport(redirect=True)
        self.assertEqual(len(requests),1);self.assertIn('ADP_HTTP_307',result['validation_errors'])
        self.assertEqual(result['ruling']['decision'],'escalate')
