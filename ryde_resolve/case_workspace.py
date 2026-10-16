"""Local case actions. Inputs and human outcomes never overwrite official sources."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import tempfile
from threading import Lock, Thread
from uuid import uuid4
from .agents import AgentError
from .evidence import EvidenceGateway, verify_snapshot
from .execution import CheckpointStore
from .orchestrator import RydeOrchestrator
from .rule_engine import charged_amount
from ryderesolve_evidence.core import build_bundle, assert_json_value


def atomic_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,delete=False) as f:
            temporary=f.name;os.chmod(temporary,0o600)
            json.dump(data,f,ensure_ascii=False,allow_nan=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(temporary,path);temporary=None
    finally:
        if temporary:Path(temporary).unlink(missing_ok=True)


def source_diff(old,new,path=''):
    """Literal data changes only, never a determination of evidential truth."""
    rows=[]
    if isinstance(old,dict) and isinstance(new,dict):
        for key in sorted(old.keys() | new.keys()):
            ptr=path+'/'+str(key).replace('~','~0').replace('/','~1')
            if key not in old:rows.append({'pointer':ptr,'change':'added','after':new[key]})
            elif key not in new:rows.append({'pointer':ptr,'change':'removed','before':old[key]})
            else:rows.extend(source_diff(old[key],new[key],ptr))
    elif old!=new or type(old)!=type(new):rows.append({'pointer':path or '/','change':'changed','before':old,'after':new})
    return rows


class CaseWorkspace:
    def __init__(self,directory,runner_factory=None,*,paid=False):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.checkpoints=CheckpointStore(self.directory/'checkpoints')
        self.runner_factory=runner_factory or (lambda:RydeOrchestrator(checkpoint_store=self.checkpoints))
        self.paid=paid;self.lock=Lock();self.jobs={}

    def _path(self,folder,identifier):
        self.checkpoints.path(identifier)
        return self.directory/folder/(identifier+'.json')

    def _read(self,folder,identifier):
        path=self._path(folder,identifier)
        if path.is_symlink() or not path.is_file() or path.stat().st_size>32*1024*1024:raise AgentError('WORKSPACE_RECORD_UNAVAILABLE')
        try:return json.loads(path.read_text(encoding='utf-8'))
        except (ValueError,OSError):raise AgentError('WORKSPACE_RECORD_UNREADABLE') from None

    def load_run(self,run_id):
        path=self._path('runs',run_id)
        if path.exists():return self._read('runs',run_id)
        if self.checkpoints.path(run_id).exists():return self.checkpoints.load(run_id)['result']
        raise AgentError('WORKSPACE_RUN_NOT_FOUND')

    def import_run(self,result):
        """Import a source-bound report as a local artifact; no provider calls."""
        assert_json_value(result);verify_snapshot(result['snapshot'])
        if result['case_id']!=result['snapshot']['case_id']:raise AgentError('WORKSPACE_CASE_MISMATCH')
        path=self._path('runs',result['run_id'])
        if path.exists():raise AgentError('WORKSPACE_RUN_ALREADY_EXISTS')
        atomic_json(path,result)
        return result['run_id']

    def preview(self,parent_id,raw,source_note,source_kind):
        previous=self.load_run(parent_id)
        if previous.get('execution_status')!='completed' or previous.get('ruling',{}).get('decision')!='escalate':raise AgentError('SUPPLEMENT_REQUIRES_BUSINESS_REVIEW')
        if previous.get('supplement_lineage') or self._path('supplement-links',parent_id).exists():raise AgentError('SUPPLEMENT_ROUND_LIMIT')
        if not isinstance(source_note,str) or not source_note.strip() or len(source_note)>2000:raise AgentError('SUPPLEMENT_SOURCE_NOTE_REQUIRED')
        if source_kind not in ('synthetic','unverified_input'):raise AgentError('SUPPLEMENT_SOURCE_KIND_INVALID')
        if not isinstance(raw,dict):raise AgentError('SUPPLEMENT_RAW_OBJECT_REQUIRED')
        old=previous['snapshot']
        if raw==old['raw']:raise AgentError('SUPPLEMENT_NO_SOURCE_CHANGE')
        # Organizer policy is pinned to the old version; this UI cannot amend it.
        b=build_bundle(deepcopy(raw),{'data_origin':source_kind,'policy_origin':old['audit']['policy_origin'],'source_url':None},old.get('policy_documents'))
        snapshot={'case_id':b.pack['case_id'],'snapshot_id':b.audit['snapshot_id'],'source_sha256':b.audit['source_sha256'],
            'normalizer_version':b.audit['normalizer_version'],'raw':b.raw,'audit':b.audit,'evidence_pack':b.pack,
            'source_index':{'evidence':b.evidence_index,'policy':b.policy_index},'policy_documents':b.policy_documents}
        verify_snapshot(snapshot)
        if snapshot['case_id']!=previous['case_id']:raise AgentError('SUPPLEMENT_CASE_MISMATCH')
        from .policy_v21 import application
        preview_id=str(uuid4());changes=source_diff(old['raw'],snapshot['raw'])
        item={'preview_id':preview_id,'parent_run_id':parent_id,'parent_snapshot_id':old['snapshot_id'],
            'snapshot':snapshot,'source_note':source_note.strip(),'source_kind':source_kind,'changes':changes[:200],
            'change_count':len(changes),'changes_truncated':len(changes)>200,'before_policy':application(old),'after_policy':application(snapshot),
            'boundary':'Source declarations are not authentication. Changes are literal differences; they do not clear policy gates or prove a fact.'}
        atomic_json(self._path('previews',preview_id),item)
        return {k:v for k,v in item.items() if k!='snapshot'} | {'new_snapshot_id':snapshot['snapshot_id']}

    def _launch(self,worker,*,confirmed=False,run_id=None,reserve=None):
        if self.paid and confirmed is not True:raise AgentError('MODEL_CALL_CONFIRMATION_REQUIRED')
        if not self.lock.acquire(blocking=False):raise AgentError('WORKSPACE_BUSY')
        identifier=run_id or str(uuid4())
        try:
            self.checkpoints.path(identifier)
            if reserve:reserve(identifier)
            self.jobs[identifier]={'run_id':identifier,'execution_status':'queued','paid':self.paid}
            def work():
                try:
                    self.jobs[identifier]['execution_status']='running'
                    result=worker(identifier)
                    atomic_json(self._path('runs',identifier),result)
                    self.jobs[identifier].update(execution_status=result['execution_status'])
                except BaseException as exc:
                    code=str(exc) if isinstance(exc,AgentError) else 'WORKSPACE_ACTION_FAILED_'+type(exc).__name__
                    self.jobs[identifier].update(execution_status='failed',error=code)
                    atomic_json(self._path('action-errors',identifier),self.jobs[identifier])
                finally:self.lock.release()
            Thread(target=work,daemon=True).start()
            return identifier
        except BaseException:
            self.lock.release();raise

    def start(self,case_id,*,confirmed=False):
        # Validate the selection before starting any provider.
        EvidenceGateway().prepare(case_id)
        return self._launch(lambda identifier:self.runner_factory().run(case_id,run_id=identifier),confirmed=confirmed)

    def commit(self,preview_id,*,confirmed=False):
        item=self._read('previews',preview_id);previous=self.load_run(item['parent_run_id'])
        if previous['snapshot']['snapshot_id']!=item['parent_snapshot_id']:raise AgentError('SUPPLEMENT_PARENT_CHANGED')
        if previous.get('supplement_lineage') or previous.get('execution_status')!='completed' or previous['ruling']['decision']!='escalate':raise AgentError('SUPPLEMENT_REQUIRES_BUSINESS_REVIEW')
        def reserve(identifier):
            link=self._path('supplement-links',previous['run_id']);link.parent.mkdir(parents=True,exist_ok=True)
            data={'parent_run_id':previous['run_id'],'child_run_id':identifier,'preview_id':preview_id}
            try:
                with link.open('x',encoding='utf-8') as f:os.chmod(link,0o600);json.dump(data,f)
            except FileExistsError:raise AgentError('SUPPLEMENT_ROUND_LIMIT') from None
        def work(identifier):
            result=self.runner_factory().rerun_with_supplement(previous,item['snapshot'],source_note=item['source_note'],run_id=identifier)
            result['supplement_changes']={'changes':item['changes'],'change_count':item['change_count'],'changes_truncated':item['changes_truncated'],
                'source_kind':item['source_kind'],'source_note':item['source_note'],'boundary':item['boundary']}
            return result
        return self._launch(work,confirmed=confirmed,reserve=reserve)

    def human_decision(self,run_id,record):
        run=self.load_run(run_id)
        if run.get('execution_status')!='completed' or run.get('ruling',{}).get('decision')!='escalate':raise AgentError('HUMAN_DECISION_REQUIRES_REVIEW')
        if not isinstance(record,dict):raise AgentError('HUMAN_RECORD_INVALID')
        for key in ('reviewer','reason'):
            if not isinstance(record.get(key),str) or not record[key].strip() or len(record[key])>2000:raise AgentError('HUMAN_RECORD_REASON_AND_NAME_REQUIRED')
        s=run['snapshot'];decision=record.get('decision');amount=record.get('refund_amount')
        if decision not in ('uphold_charge','refund_full','refund_partial') or type(amount) not in (int,float):raise AgentError('HUMAN_DECISION_INVALID')
        money=Decimal(str(amount));charged=charged_amount(s)
        if not money.is_finite() or money.as_tuple().exponent < -2 or charged is None or not 0<=money<=charged:raise AgentError('HUMAN_AMOUNT_INVALID')
        if (decision=='uphold_charge' and money!=0) or (decision=='refund_full' and money!=charged) or (decision=='refund_partial' and not 0<money<charged):raise AgentError('HUMAN_AMOUNT_INVALID')
        for key,kind in (('evidence_refs','evidence'),('policy_refs','policy')):
            refs=record.get(key)
            if not isinstance(refs,list) or not refs or any(not isinstance(r,str) or r not in s['source_index'][kind] for r in refs):raise AgentError('HUMAN_REFERENCE_INVALID')
        identifier=str(uuid4());out={k:deepcopy(record[k]) for k in ('reviewer','reason','decision','refund_amount','evidence_refs','policy_refs')}
        out.update(record_id=identifier,run_id=run_id,case_id=run['case_id'],snapshot_id=s['snapshot_id'],currency='SGD',amount_unit='major',
            recorded_at=datetime.now(timezone.utc).isoformat(),origin='local_human_entry',
            boundary='Self-declared local reviewer, not independently authenticated. Records a human outcome only; no refund executed, AI proposal overwritten or policy/precedent updated.')
        atomic_json(self.directory/'human-decisions'/run_id/(identifier+'.json'),out)
        return out

    def summary(self,identifier):
        error_path=self._path('action-errors',identifier)
        error=self._read('action-errors',identifier) if error_path.exists() else None
        try:r=self.load_run(identifier)
        except AgentError:
            if error:return error
            if identifier in self.jobs:return deepcopy(self.jobs[identifier])
            raise
        from .workflow_view import timeline
        human=list((self.directory/'human-decisions'/identifier).glob('*.json'))
        status=r.get('execution_status','running')
        # A process failure may leave a valid checkpoint at its last running stage.
        # After restart, no worker owns it: show interrupted rather than live progress.
        if error:status='failed'
        elif status in ('running','queued') and identifier not in self.jobs:status='interrupted'
        out={'run_id':identifier,'case_id':r['case_id'],'execution_status':status,
            'business_decision_status':r.get('business_decision_status','pending') if status not in ('failed','interrupted') else 'unavailable',
            'decision':(r.get('ruling') or {}).get('decision'),
            'refund_amount':(r.get('ruling') or {}).get('refund_amount'),'timeline':timeline(r),'human_record_count':len(human),
            'human_review_status':'human_finalized' if human else None,'validation_errors':r.get('validation_errors',[]),
            'can_supplement':status=='completed' and (r.get('ruling') or {}).get('decision')=='escalate' and not r.get('supplement_lineage') and not self._path('supplement-links',identifier).exists()}
        if status in ('failed','interrupted'):
            for row in out['timeline']:
                if row['status']=='running':row.update(status='interrupted',error='WORKER_NOT_RUNNING')
        if error:out['error']=error.get('error')
        if status=='interrupted':out['error']='WORKER_NOT_RUNNING_RESTART_REQUIRED'
        return out

    def list_runs(self):
        identifiers=set(self.jobs)
        for folder in ('runs','checkpoints','action-errors'):
            identifiers.update(p.stem for p in (self.directory/folder).glob('*.json'))
        return [self.summary(i) for i in sorted(identifiers)]
