"""Local, version-bound checkpoints and bounded execution; no provider side effects."""
from copy import deepcopy
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import tempfile
from time import monotonic, sleep
import re

from .agents import AgentError, ROOT


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def implementation_digest():
    paths = [*ROOT.joinpath('ryde_resolve').glob('*.py'), *ROOT.joinpath('prompts').glob('*.md'),
             *ROOT.joinpath('schemas').glob('*.json')]
    for module in ('ryderesolve-advocate-system/ryderesolve_advocate','ryderesolve-evidence-tools/ryderesolve_evidence'):
        paths.extend(ROOT.joinpath('vendor',module).rglob('*.py'))
    return digest({str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in sorted(paths)})


def runner_identity(runner):
    identity = {'mode': getattr(runner, 'mode', 'custom_adapter'),
                'class': type(runner).__module__ + '.' + type(runner).__qualname__}
    if hasattr(runner, '__code__'):
        identity['function'] = digest({'module': runner.__module__, 'name': runner.__qualname__,
                                      'code': runner.__code__.co_code.hex()})
    config = getattr(runner, 'config', None)
    identity['config'] = {k: getattr(config, k) for k in ('project', 'model', 'location', 'thinking_level', 'timeout')
                          if hasattr(config, k)}
    if hasattr(config, 'endpoint'):
        identity['endpoint_hash'] = digest(config.endpoint)
    if hasattr(runner, 'model'):
        identity['model_client'] = runner_identity(runner.model)
    if hasattr(runner, 'document'):
        identity['document_hash'] = digest(runner.document)
    identity['adapter_revision'] = getattr(runner, 'cache_identity', None)
    return identity


@dataclass(frozen=True)
class RunLimits:
    max_calls: int = 7
    max_seconds: float = 900
    max_recorded_tokens: int = 300000
    transient_retries: int = 1
    judge_repairs: int = 1

    def __post_init__(self):
        if any(type(getattr(self,k)) is not int or getattr(self,k)<0 for k in
               ('max_calls','max_recorded_tokens','transient_retries','judge_repairs')):
            raise AgentError('INVALID_EXECUTION_LIMITS')
        if not self.max_calls or not self.max_recorded_tokens or type(self.max_seconds) not in (int,float) or not math.isfinite(self.max_seconds) or self.max_seconds<=0:
            raise AgentError('INVALID_EXECUTION_LIMITS')
        if self.transient_retries>2 or self.judge_repairs>1:
            raise AgentError('INVALID_EXECUTION_LIMITS')


class CheckpointStore:
    """Checksummed atomic files, scoped by UUID. Checksums detect corruption, not forgery."""
    def __init__(self, directory):
        self.directory = Path(directory)

    def path(self, run_id):
        if not isinstance(run_id,str) or not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',run_id):
            raise AgentError('INVALID_CHECKPOINT_ID')
        return self.directory / (run_id+'.json')

    def load(self, run_id):
        try:
            path=self.path(run_id)
            if path.is_symlink() or path.stat().st_size>32*1024*1024:
                raise AgentError('CHECKPOINT_UNSAFE_OR_TOO_LARGE')
            data=json.loads(path.read_text(encoding='utf-8'))
            payload=data['payload']
            if data['sha256']!=digest(payload) or payload['version']!=1 or payload['run_id']!=run_id:
                raise AgentError('CHECKPOINT_INTEGRITY_FAILED')
            if not isinstance(payload.get('manifest'),dict) or not isinstance(payload.get('entries'),dict) or not isinstance(payload.get('result',{}).get('communication_log'),list):
                raise AgentError('CHECKPOINT_INVALID_STATE')
            if any(type(payload.get('usage',{}).get(k)) is not int or payload['usage'][k]<0 for k in ('provider_calls','calls_with_usage','recorded_tokens','unknown_usage_calls')):
                raise AgentError('CHECKPOINT_INVALID_STATE')
            if type(payload.get('active_seconds')) not in (int,float) or not math.isfinite(payload['active_seconds']) or payload['active_seconds']<0:
                raise AgentError('CHECKPOINT_INVALID_STATE')
            return payload
        except (OSError,ValueError,KeyError,TypeError):
            raise AgentError('CHECKPOINT_UNREADABLE') from None

    def save(self, run_id, payload):
        path=self.path(run_id)
        self.directory.mkdir(parents=True,exist_ok=True)
        if path.is_symlink():raise AgentError('CHECKPOINT_UNSAFE_PATH')
        text=json.dumps({'payload':payload,'sha256':digest(payload)},ensure_ascii=False,indent=2,allow_nan=False)
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=self.directory,delete=False) as f:
                temporary=f.name;os.chmod(f.name,0o600);f.write(text);f.flush();os.fsync(f.fileno())
            os.replace(temporary,path);temporary=None
        finally:
            if temporary:Path(temporary).unlink(missing_ok=True)


def provider_call(runner):
    return getattr(runner,'mode','custom_adapter') not in ('offline_review','offline_placeholder','teammate_json')


def retryable(code):
    return bool(re.fullmatch(r'(VERTEX|ADP|MODEL)_HTTP_(429|502|503|504)',code))


REPAIRABLE = {'FINDING_CONDITION_BASIS_MISMATCH','ARGUMENT_ASSESSMENT_COVERAGE','SIDE_ARGUMENT_COVERAGE','DUPLICATE_ARGUMENT_ASSESSMENT',
              'UNADDRESSED_ARGUMENT','ANALYSIS_SIDE_MISSING_ARGUMENT','CASE_ANALYSIS_REQUIRED','VERTEX_INVALID_RESPONSE','VERTEX_INVALID_JSON_OBJECT'}


def repairable(errors):
    codes={e.split(':',1)[0] for e in errors}
    return bool(codes & REPAIRABLE) and codes <= REPAIRABLE | {'UNRESOLVED_DATA_OR_POLICY_REVIEW'}


class ExecutionSession:
    def __init__(self,run_id,result,store=None,resume=None,limits=None,clock=monotonic,wait=sleep):
        self.run_id=run_id;self.result=result;self.store=store;self.old=store.load(resume) if resume and store else None
        if resume and not store:raise AgentError('RESUME_REQUIRES_CHECKPOINT_STORE')
        self.limits=limits or RunLimits();self.clock=clock;self.wait=wait;self.started=clock()
        self.manifest=None;self.entries={};self.prior_seconds=0
        self.usage={'provider_calls':0,'calls_with_usage':0,'recorded_tokens':0,'unknown_usage_calls':0}
        self.reused=0

    def bind(self,snapshot,runners,options=None):
        manifest={'case_id':snapshot['case_id'],'snapshot_id':snapshot['snapshot_id'],
                  'implementation':implementation_digest(),'runners':{k:runner_identity(v) for k,v in runners.items()},
                  'limits':asdict(self.limits),'options':options or {}}
        if self.old:
            if self.old['manifest']!=manifest:raise AgentError('CHECKPOINT_INPUT_OR_VERSION_MISMATCH')
            self.entries=deepcopy(self.old['entries']);self.usage=deepcopy(self.old['usage'])
            self.prior_seconds=self.old['active_seconds']
            previous=deepcopy(self.old['result']['communication_log'])
            for event in previous:
                if event.get('status') == 'running':
                    # A hard process stop bypasses invoke()'s finally block. The
                    # external request may have completed, so retain unknown usage.
                    event.update(status='interrupted', error='PREVIOUS_ATTEMPT_NOT_COMPLETED',
                                 duration_ms=None, finished_at=None)
            self.result['communication_log'][:0]=previous
            for i,event in enumerate(self.result['communication_log'],1):event['sequence']=i
            self.result['resumed_from_run_id']=self.run_id
        self.manifest=manifest;self.save()

    def seconds(self):return self.prior_seconds+self.clock()-self.started

    def save(self):
        self.result['execution_usage']={**self.usage,'active_seconds':round(self.seconds(),3),
            'reused_steps':self.reused,'limits':asdict(self.limits),
            'boundary':'Recorded usage only, not billed cost. Missing/timeout usage is unknown. Time/token admission is checked between calls; an in-flight request may exceed these bounds.'}
        if self.store and self.manifest:
            self.store.save(self.run_id,{'version':1,'run_id':self.run_id,'manifest':self.manifest,
                'entries':self.entries,'usage':self.usage,'active_seconds':self.seconds(),'result':self.result})

    def admit(self):
        if self.seconds()>=self.limits.max_seconds:raise AgentError('RUN_TIME_BUDGET_EXHAUSTED')
        if self.usage['provider_calls']>=self.limits.max_calls:raise AgentError('RUN_CALL_BUDGET_EXHAUSTED')
        if self.usage['recorded_tokens']>=self.limits.max_recorded_tokens:raise AgentError('RUN_TOKEN_BUDGET_EXHAUSTED')

    def invoke(self,key,inputs,runner,fn,event_factory):
        fingerprint=digest({'inputs':inputs,'runner':runner_identity(runner) if runner else None})
        prior=self.entries.get(key)
        if prior and prior['fingerprint']==fingerprint:
            event=event_factory();event.update(status='reused',output=deepcopy(prior['output']),
                transport=deepcopy(prior.get('transport',{})),reused_from_checkpoint=True,usage_charged_this_attempt=False,
                duration_ms=0.0,finished_at=event['started_at'])
            self.reused+=1;self.save();return deepcopy(prior['output'])
        retries=self.limits.transient_retries if runner and provider_call(runner) else 0
        for attempt in range(retries+1):
            paid=runner is not None and provider_call(runner)
            if paid:self.admit()
            event=event_factory();event['attempt']=attempt+1
            if paid:
                self.usage['provider_calls']+=1
                # Unknown until a response reports usage, including crash/interrupt windows.
                self.usage['unknown_usage_calls']+=1
            if runner is not None and hasattr(runner,'last_metadata'):runner.last_metadata={}
            self.save();start=self.clock()
            try:
                output=fn()
                from ryderesolve_evidence.core import assert_json_value
                assert_json_value(output)
                event.update(status='success',output=deepcopy(output))
            except BaseException as exc:
                code=str(exc) if isinstance(exc,AgentError) else 'STEP_FAILED_'+type(exc).__name__
                event.update(status='interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed',error=code)
                if isinstance(exc,(KeyboardInterrupt,SystemExit)):raise
                if not isinstance(exc,Exception):raise
                if attempt<retries and retryable(code):
                    event['retry_scheduled']=True
                else:raise AgentError(code) from None
            finally:
                transport=deepcopy(getattr(runner,'last_metadata',{})) if runner else {}
                if transport:event['transport']=transport
                usage=transport.get('usage')
                if paid and isinstance(usage,dict) and type(usage.get('totalTokenCount')) is int and usage['totalTokenCount']>=0:
                    self.usage['calls_with_usage']+=1;self.usage['unknown_usage_calls']-=1
                    self.usage['recorded_tokens']+=usage['totalTokenCount']
                event['duration_ms']=round((self.clock()-start)*1000,2)
                from datetime import datetime,timezone
                event['finished_at']=datetime.now(timezone.utc).isoformat()
                if event['status']=='success':
                    self.entries[key]={'fingerprint':fingerprint,'output':deepcopy(output),'transport':transport,
                        'boundary':'Provider candidate retained; business validators are run again on resume.'}
                self.save()
            if event['status']=='success':return output
            delay=min(2**attempt,4)
            if self.seconds()+delay>=self.limits.max_seconds:raise AgentError('RUN_TIME_BUDGET_EXHAUSTED')
            self.wait(delay)
