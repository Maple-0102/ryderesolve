"""Local workbench with preview-first supplementation and explicit paid actions."""
import argparse
from dataclasses import replace
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import tempfile
from urllib.parse import urlsplit
from .agents import AgentError
from .case_workspace import CaseWorkspace
from .execution import RunLimits
from .orchestrator import RydeOrchestrator
from .ui import render_html,esc
from ryderesolve_evidence.core import assert_json_value

MAX_BODY=4*1024*1024


def make_server(workspace,port=0):
    nonce=secrets.token_urlsafe(24)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def reply(self,code,body,kind='application/json; charset=utf-8'):
            data=body.encode('utf-8') if isinstance(body,str) else json.dumps(body,ensure_ascii=False,allow_nan=False).encode('utf-8')
            self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',f"default-src 'self'; script-src 'nonce-{nonce}'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers();self.wfile.write(data)
        def allowed_host(self):return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'
        def do_GET(self):
            if not self.allowed_host():return self.reply(403,{'error':'HOST_REJECTED'})
            path=urlsplit(self.path).path
            try:
                if path=='/':
                    text=Path(__file__).with_name('workbench.html').read_text(encoding='utf-8').replace('__NONCE__',nonce).replace('__PAID__',json.dumps(workspace.paid))
                    return self.reply(200,text,'text/html; charset=utf-8')
                if path=='/api/runs':return self.reply(200,workspace.list_runs())
                parts=path.strip('/').split('/')
                if len(parts)==4 and parts[:2]==['api','runs']:
                    run=workspace.load_run(parts[2])
                    if parts[3]=='raw':return self.reply(200,run['snapshot']['raw'])
                    if parts[3]=='refs':
                        pack=run['snapshot']['evidence_pack']
                        return self.reply(200,{'evidence':[{'id':f['evidence_id'],'text':f['fact']} for f in pack['facts']],
                            'policy':[{'id':p['policy_id'],'text':p['rule']} for p in pack['policy']]})
                    if parts[3]=='human':
                        items=[json.loads(p.read_text()) for p in (workspace.directory/'human-decisions'/parts[2]).glob('*.json')]
                        return self.reply(200,sorted(items,key=lambda x:x['recorded_at']))
                if len(parts)==2 and parts[0]=='runs':
                    run=workspace.load_run(parts[1])
                    if not run.get('ruling'):return self.reply(200,'<p>正在执行，请返回工作台查看真实进度。</p>','text/html; charset=utf-8')
                    with tempfile.TemporaryDirectory() as d:
                        text=render_html(run,Path(d)/'view.html').read_text()
                    # Static report's original inline script gets this response nonce.
                    text=text.replace('<script>','<script nonce="'+nonce+'">')
                    return self.reply(200,text,'text/html; charset=utf-8')
                self.reply(404,{'error':'NOT_FOUND'})
            except (AgentError,ValueError,KeyError,TypeError,OSError) as exc:self.reply(400,{'error':str(exc) if isinstance(exc,AgentError) else 'WORKSPACE_INPUT_INVALID'})
        def do_POST(self):
            origin=f'http://127.0.0.1:{self.server.server_port}'
            if not self.allowed_host() or self.headers.get('Origin')!=origin or not secrets.compare_digest(self.headers.get('X-Workspace-Token',''),nonce):return self.reply(403,{'error':'REQUEST_ORIGIN_REJECTED'})
            try:
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise AgentError('JSON_BODY_REQUIRED')
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=MAX_BODY:raise AgentError('REQUEST_BODY_LIMIT')
                data=json.loads(self.rfile.read(length));assert_json_value(data)
                if not isinstance(data,dict):raise AgentError('JSON_OBJECT_REQUIRED')
                path=urlsplit(self.path).path
                if path=='/api/start':out={'run_id':workspace.start(data.get('case_id'),confirmed=data.get('confirm_model_calls'))}
                elif path=='/api/supplement/preview':out=workspace.preview(data.get('parent_run_id'),data.get('raw'),data.get('source_note'),data.get('source_kind'))
                elif path=='/api/supplement/commit':out={'run_id':workspace.commit(data.get('preview_id'),confirmed=data.get('confirm_model_calls'))}
                elif path=='/api/human':out=workspace.human_decision(data.get('run_id'),data.get('record'))
                else:return self.reply(404,{'error':'NOT_FOUND'})
                self.reply(200,out)
            except (AgentError,ValueError,KeyError,TypeError,OSError):
                # Return safe typed codes only; raw input, paths and provider bodies stay private.
                import sys
                exc=sys.exception();self.reply(400,{'error':str(exc) if isinstance(exc,AgentError) else 'WORKSPACE_INPUT_INVALID'})
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=Path('outputs/local-workbench'));p.add_argument('--port',type=int,default=8765)
    p.add_argument('--live',action='store_true',help='Enable paid Vertex actions; each action also requires confirmation in the UI.')
    p.add_argument('--import-run',type=Path,action='append',default=[])
    p.add_argument('--parallel-advocates',action='store_true',help='Use isolated concurrent Advocate pairs.')
    a=p.parse_args();workspace=CaseWorkspace(a.directory,paid=a.live)
    if a.parallel_advocates and not a.live:
        from .mock_agents import OfflineAdvocate
        workspace.runner_factory=lambda:RydeOrchestrator(checkpoint_store=workspace.checkpoints,parallel_advocates=True,advocate_factory=OfflineAdvocate)
    if a.live:
        from .vertex import VertexJudge,VertexConfig
        from .teammate_advocate import TeammateAdvocate
        from .reviewer import InferenceReviewer
        config=replace(VertexConfig.from_env(),thinking_level='LOW')
        workspace.runner_factory=lambda:RydeOrchestrator(advocate_runner=TeammateAdvocate(VertexJudge(config)),judge_runner=VertexJudge(config),
            reviewer_runner=InferenceReviewer(VertexJudge(config)),checkpoint_store=workspace.checkpoints,
            limits=RunLimits(max_calls=7,transient_retries=0,judge_repairs=1),issue_guidance=True,parallel_advocates=a.parallel_advocates,advocate_factory=lambda:TeammateAdvocate(VertexJudge(config)))
    for path in a.import_run:workspace.import_run(json.loads(path.read_text()))
    server=make_server(workspace,a.port)
    print(f'Local workbench: http://127.0.0.1:{server.server_port} | paid actions enabled: {a.live}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
