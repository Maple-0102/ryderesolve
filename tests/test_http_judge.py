"""Exercise the actual urllib POST transport against a loopback stub, never a provider."""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ryde_resolve.agents import HTTPJudge, ModelConfig
from ryde_resolve.mock_agents import review_ruling
from ryde_resolve.orchestrator import RydeOrchestrator


class ModelTransportTests(unittest.TestCase):
    def call(self, redirect=False):
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append((self.path, self.headers.get('Authorization'), body))
                if redirect:
                    self.send_response(307)
                    self.send_header('Location', '/must-not-follow')
                    self.end_headers()
                    return
                case=json.loads(body['messages'][1]['content'])
                content=review_ruling(case, ['Policy clock needs clarification.'])
                data=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(content)}}]}).encode()
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(data)))
                self.end_headers();self.wfile.write(data)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            config=ModelConfig(f'http://127.0.0.1:{server.server_port}/chat/completions','stub-model','stub-token')
            result=RydeOrchestrator(judge_runner=HTTPJudge(config)).run()
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)
        return result, requests

    def test_real_http_post_and_json_response(self):
        r,requests=self.call()
        self.assertFalse(r['validation_errors'])
        self.assertEqual(len(requests),1)
        self.assertEqual(requests[0][0],'/chat/completions')
        self.assertEqual(requests[0][1],'Bearer stub-token')
        self.assertEqual(requests[0][2]['model'],'stub-model')
        self.assertEqual(r['ruling']['decision'],'escalate')
        self.assertNotIn('stub-token',json.dumps(r))

    def test_redirect_is_not_followed(self):
        r,requests=self.call(redirect=True)
        self.assertEqual(len(requests),1)
        self.assertIn('MODEL_HTTP_307',r['validation_errors'])
        self.assertEqual(r['ruling']['decision'],'escalate')
