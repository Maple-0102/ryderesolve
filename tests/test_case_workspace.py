from copy import deepcopy
import json
from pathlib import Path
import re
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from ryde_resolve.agents import AgentError
from ryde_resolve.case_workspace import CaseWorkspace
from ryde_resolve.orchestrator import RydeOrchestrator
from ryde_resolve.workbench import make_server
from evaluation.fixtures import with_verification


def wait(workspace,identifier):
    deadline=time.monotonic()+5
    while workspace.jobs[identifier]['execution_status'] in ('queued','running') and time.monotonic()<deadline:time.sleep(.01)
    if workspace.jobs[identifier]['execution_status'] in ('queued','running'):raise AssertionError('worker did not finish')
    return workspace.load_run(identifier)


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.w=CaseWorkspace(self.temp.name)
        self.old=RydeOrchestrator().run('SYN-ROUTE-001');self.w.import_run(self.old)
    def preview(self):
        return self.w.preview(self.old['run_id'],with_verification(self.old['snapshot'])['raw'],'Team synthetic verification, not organizer evidence.','synthetic')
    def test_preview_is_read_only_and_commit_preserves_source_lineage(self):
        before=deepcopy(self.old);p=self.preview()
        self.assertNotEqual(p['new_snapshot_id'],p['parent_snapshot_id']);self.assertGreater(p['change_count'],0)
        self.assertEqual(self.w.load_run(self.old['run_id']),before);self.assertFalse(self.w.jobs)
        identifier=self.w.commit(p['preview_id']);child=wait(self.w,identifier)
        self.assertFalse(child['validation_errors'],child['validation_errors'])
        self.assertEqual(child['supplement_lineage']['parent_run_id'],self.old['run_id'])
        self.assertEqual(child['snapshot']['snapshot_id'],p['new_snapshot_id'])
        self.assertEqual(self.w.load_run(self.old['run_id']),before)
        self.assertTrue(self.w.checkpoints.path(identifier).exists())
        self.assertTrue(all(a['case_id']==self.old['case_id'] for rnd in child['arguments'].values() for a in rnd.values()))
        with self.assertRaisesRegex(AgentError,'ROUND_LIMIT'):self.w.commit(p['preview_id'])
        with self.assertRaisesRegex(AgentError,'ROUND_LIMIT'):self.w.preview(identifier,with_verification(child['snapshot'])['raw'],'again','synthetic')
    def test_unchanged_source_missing_note_and_forged_official_origin_rejected(self):
        for raw,note,kind in [(self.old['snapshot']['raw'],'note','synthetic'),(with_verification(self.old['snapshot'])['raw'],'','synthetic'),(with_verification(self.old['snapshot'])['raw'],'note','organizer_sample')]:
            with self.assertRaises(AgentError):self.w.preview(self.old['run_id'],raw,note,kind)
    def test_wrong_case_rejected_and_policy_is_pinned(self):
        p=self.preview();stored=self.w._read('previews',p['preview_id'])
        self.assertEqual(stored['snapshot'].get('policy_documents',{}),self.old['snapshot'].get('policy_documents',{}))
        raw=deepcopy(self.old['snapshot']['raw']);raw['trip_data']['trip_id']='OTHER-TRIP'
        # Case ID is controlled by the dispute ticket, not a pathname supplied by the user.
        raw['dispute_ticket']['dispute_id']='DIFFERENT-CASE'
        with self.assertRaises((AgentError,ValueError)):self.w.preview(self.old['run_id'],raw,'note','synthetic')
    def test_human_outcome_does_not_modify_ai_or_policy_and_is_append_only(self):
        e=next(iter(self.old['snapshot']['source_index']['evidence']));p=next(iter(self.old['snapshot']['source_index']['policy']))
        record={'reviewer':'Demo reviewer','reason':'Manual review of synthetic source only.','decision':'refund_partial','refund_amount':1.5,'evidence_refs':[e],'policy_refs':[p]}
        first=self.w.human_decision(self.old['run_id'],record);second=self.w.human_decision(self.old['run_id'],record)
        self.assertNotEqual(first['record_id'],second['record_id'])
        self.assertEqual(self.w.load_run(self.old['run_id']),self.old)
        self.assertEqual(self.w.summary(self.old['run_id'])['human_review_status'],'human_finalized')
        self.assertEqual(self.w.summary(self.old['run_id'])['human_record_count'],2)
        for change in ({'refund_amount':float('nan')},{'refund_amount':1.001},{'evidence_refs':['E-FAKE']},{'reason':''}):
            with self.assertRaises(AgentError):self.w.human_decision(self.old['run_id'],record|change)
    def test_paid_run_requires_explicit_confirmation_and_path_is_uuid_only(self):
        paid=CaseWorkspace(Path(self.temp.name)/'paid',paid=True)
        with self.assertRaisesRegex(AgentError,'CONFIRMATION'):paid.start('DISP-003')
        self.assertFalse(paid.jobs)
        with self.assertRaises(AgentError):self.w.load_run('../escape')
    def test_new_material_cannot_remove_mandatory_policy_gate(self):
        original=RydeOrchestrator().run('DISP-001');self.w.import_run(original)
        raw=deepcopy(original['snapshot']['raw']);raw['dispute_ticket']['description']+=' Synthetic additional statement.'
        p=self.w.preview(original['run_id'],raw,'Synthetic statement, not official clarification.','synthetic')
        self.assertTrue(any(g['code']=='ROUTE_DISTANCE_REQUIRES_HUMAN_REVIEW' for g in p['after_policy']['mandatory_human_review']))

    def test_failed_worker_and_abandoned_checkpoint_are_not_shown_as_running(self):
        from ryde_resolve.case_workspace import atomic_json
        r=deepcopy(self.old);r['execution_status']='running';r['ruling']=None
        # A last-running artifact can survive an application restart.
        atomic_json(self.w._path('runs',r['run_id']),r)
        self.assertEqual(self.w.summary(r['run_id'])['execution_status'],'interrupted')
        atomic_json(self.w._path('action-errors',r['run_id']),{'run_id':r['run_id'],'error':'WORKER_FAILED','execution_status':'failed'})
        summary=self.w.summary(r['run_id'])
        self.assertEqual(summary['execution_status'],'failed')
        self.assertEqual(summary['error'],'WORKER_FAILED')
        self.assertFalse(summary['can_supplement'])


class WorkbenchHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.w=CaseWorkspace(cls.temp.name);cls.old=RydeOrchestrator().run('SYN-ROUTE-001');cls.w.import_run(cls.old)
        cls.server=make_server(cls.w);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base='http://127.0.0.1:'+str(cls.server.server_port)
        cls.page=urlopen(cls.base).read().decode();cls.token=re.search("const token='([^']+)'",cls.page)[1]
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.temp.cleanup()
    def test_get_routes_are_read_only_and_have_real_refs(self):
        self.assertIn('离线演示模式',self.page)
        rows=json.load(urlopen(self.base+'/api/runs'));self.assertEqual(rows[0]['case_id'],'SYN-ROUTE-001')
        refs=json.load(urlopen(self.base+'/api/runs/'+self.old['run_id']+'/refs'));self.assertTrue(refs['evidence']);self.assertTrue(refs['policy'])
        self.assertIn('流程进度',urlopen(self.base+'/runs/'+self.old['run_id']).read().decode())
        self.assertFalse(self.w.jobs)
    def test_foreign_origin_missing_token_and_rebinding_host_rejected(self):
        for headers in ({'Origin':'https://example.com','X-Workspace-Token':self.token},{'Origin':self.base}, {'Origin':self.base,'X-Workspace-Token':self.token,'Host':'evil.example'}):
            req=Request(self.base+'/api/start',data=b'{}',headers=headers|{'Content-Type':'application/json'})
            with self.assertRaises(HTTPError) as error:urlopen(req)
            self.assertEqual(error.exception.code,403)
        self.assertFalse(self.w.jobs)
    def test_same_origin_preview_does_not_start_a_job(self):
        body={'parent_run_id':self.old['run_id'],'raw':with_verification(self.old['snapshot'])['raw'],'source_note':'Synthetic HTTP test','source_kind':'synthetic'}
        req=Request(self.base+'/api/supplement/preview',data=json.dumps(body).encode(),headers={'Origin':self.base,'X-Workspace-Token':self.token,'Content-Type':'application/json'})
        p=json.load(urlopen(req));self.assertNotEqual(p['new_snapshot_id'],p['parent_snapshot_id']);self.assertFalse(self.w.jobs)
