"""Version-bound two-round workflow with durable stage outputs and explicit failures."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
from .agents import AgentError
from .contracts import check_advocate, check_judge
from .evidence import EvidenceGateway, verify_snapshot
from .mock_agents import OfflineAdvocate, OfflineJudge, review_ruling
from .rule_engine import calculate_rules
from .execution import CheckpointStore, ExecutionSession, RunLimits, repairable


class RydeOrchestrator:
    def __init__(self, evidence_gateway=None, advocate_runner=None, judge_runner=None,
                 *, checkpoint_store=None, limits=None, clock=None, wait=None, reviewer_runner=None, issue_guidance=False, parallel_advocates=False, advocate_factory=None):
        self.evidence = evidence_gateway or EvidenceGateway()
        self.advocate = advocate_runner or OfflineAdvocate()
        self.judge = judge_runner or OfflineJudge()
        self.reviewer=reviewer_runner; self.issue_guidance=issue_guidance
        self.parallel_advocates=parallel_advocates;self.advocate_factory=advocate_factory
        if parallel_advocates and advocate_factory is None:raise AgentError('PARALLEL_ADVOCATE_FACTORY_REQUIRED')
        self.store = checkpoint_store
        self.limits = limits or RunLimits()
        self.clock = clock; self.wait = wait
        self.events = []

    def run(self, case_id='DISP-002', *, resume=None, run_id=None):
        self.events = []
        if resume and run_id and resume!=run_id:raise AgentError('RUN_ID_RESUME_MISMATCH')
        run_id = resume or run_id or str(uuid4())
        if self.store:self.store.path(run_id)
        modes = {'advocate': getattr(self.advocate, 'mode', 'custom_adapter'),
                 'judge': getattr(self.judge, 'mode', 'custom_adapter')}
        result = {'run_id': run_id, 'case_id': case_id, 'modes': modes,
                  'snapshot': None, 'calculations': {},
                  'arguments': {'opening': {}, 'response': {}},
                  'ruling': None, 'judge_proposal': None, 'judge_adjustments': [],
                  'judge_raw_validation_errors': [], 'judge_final_validation_errors': [],
                  'repair_history': [], 'validation_errors': [], 'validation_warnings': [],
                  'execution_status': 'running', 'business_decision_status': 'pending',
                  'review_reason_types': [], 'communication_log': self.events,
                  'workflow_options':{'issue_guidance':self.issue_guidance,'reviewer':self.reviewer is not None,'parallel_advocates':self.parallel_advocates}}
        kwargs={k:v for k,v in [('clock',self.clock),('wait',self.wait)] if v is not None}
        session=ExecutionSession(run_id,result,self.store,resume,self.limits,**kwargs)

        def step(name,agent,inputs,fn,*,runner=None,key=None):
            def event_factory():
                event={'sequence':len(self.events)+1,'step':name,'agent':agent,
                       'started_at':datetime.now(timezone.utc).isoformat(),
                       'input':deepcopy(inputs),'status':'running'}
                self.events.append(event);return event
            return session.invoke(key or name,inputs,runner,fn,event_factory)

        def finish():
            from .execution_status import annotate_execution
            annotate_execution(result)
            from .handoff import build_handoff
            result['human_handoff']=build_handoff(result)
            session.save()
            return result

        parallel_runners={}
        if self.parallel_advocates:
            parallel_runners={rnd+':'+side:self.advocate_factory() for rnd in ('opening','response') for side in ('rider','driver')}
            instances=list(parallel_runners.values())
            models=[r.model for r in instances if getattr(r,'model',None) is not None]
            if len({id(r) for r in instances})!=4 or len({id(m) for m in models})!=len(models):raise AgentError('PARALLEL_RUNNER_MUST_BE_ISOLATED')

        snapshot={'case_id':case_id}
        try:
            snapshot=step('prepare_case','EvidenceTools',{'case_id':case_id},lambda:self.evidence.prepare(case_id))
            verify_snapshot(snapshot)
            if snapshot['case_id']!=case_id:raise AgentError('EVIDENCE_CASE_MISMATCH')
            result['snapshot']=deepcopy(snapshot)
            runners={'advocate':self.advocate,'judge':self.judge}
            runners.update(parallel_runners)
            if self.reviewer:runners['reviewer']=self.reviewer
            session.bind(snapshot,runners,{'issue_guidance':self.issue_guidance,'reviewer_enabled':self.reviewer is not None,'parallel_advocates':self.parallel_advocates})
            result['calculations']=step('calculate_rules','Audited calculations',{'snapshot_id':snapshot['snapshot_id']},
                                        lambda:calculate_rules(snapshot))
            policy=result['calculations'].get('policy_application')
            if policy and policy['evidence_only']:
                result['execution_policy']='evidence_only';result['providers_skipped']=True
                result['ruling']=review_ruling(snapshot,['SAFETY_EVIDENCE_ONLY: policy sections 5.1-5.2 require human adjudication.'])
                step('safety_gate','Policy v2.1',{'snapshot_id':snapshot['snapshot_id']},
                     lambda:{'action':'human_review','agents_called':False,'policy_refs':['P-RYDE-2.1-S5.1','P-RYDE-2.1-S5.2']})
                return finish()
            if self.issue_guidance:
                from .issue_guidance import build_issue_ledger
                result['issue_ledger']=build_issue_ledger(result['calculations'])
            for round_name in ('opening','response'):
                if self.issue_guidance and round_name=='response':
                    from .issue_guidance import coordinate_openings
                    result['issue_ledger']=coordinate_openings(result['issue_ledger'],result['arguments']['opening'])
                def accept(side,output):
                    errors,warnings=check_advocate(snapshot,output,side)
                    result['validation_warnings'].extend(warnings)
                    if errors:
                        result['validation_errors'].extend(errors)
                        raise AgentError('INVALID_ADVOCATE_OUTPUT')
                    result['arguments'][round_name][side]=output
                    session.save()
                tasks=[]
                for side in ('rider','driver'):
                    runner=parallel_runners.get(round_name+':'+side,self.advocate)
                    other='driver' if side=='rider' else 'rider'
                    opponent=deepcopy(result['arguments']['opening'].get(other)) if round_name=='response' else None
                    inputs={'snapshot_id':snapshot['snapshot_id'],'opponent_opening':opponent,
                            'evidence_refs':[f['evidence_id'] for f in snapshot['evidence_pack']['facts']]}
                    guided=self.issue_guidance and round_name=='response' and callable(getattr(runner,'run_guided',None))
                    if guided:
                        from .issue_guidance import response_guidance
                        inputs['round_guidance']=response_guidance(result['issue_ledger'],side)
                    def invoke(runner=runner,side=side,opponent=opponent,inputs=inputs,guided=guided):
                        return runner.run_guided(deepcopy(snapshot),side,round_name,deepcopy(opponent),deepcopy(inputs['round_guidance'])) if guided else runner(deepcopy(snapshot),side,round_name,deepcopy(opponent))
                    def event_factory(side=side,inputs=inputs):
                        event={'sequence':len(self.events)+1,'step':round_name,'agent':side+' Advocate',
                            'started_at':datetime.now(timezone.utc).isoformat(),'input':deepcopy(inputs),'status':'running'}
                        self.events.append(event);return event
                    task={'key':round_name+':'+side,'inputs':inputs,'runner':runner,'fn':invoke,'event_factory':event_factory}
                    if self.parallel_advocates:tasks.append(task)
                    else:
                        output=step(round_name,side+' Advocate',inputs,invoke,runner=runner,key=task['key'])
                        accept(side,output)
                if self.parallel_advocates:
                    outputs=session.invoke_batch(tasks)
                    # Barrier: validate both openings before either response, and both responses before Judge.
                    for side,output in zip(('rider','driver'),outputs):accept(side,output)
            if self.issue_guidance:
                from .issue_guidance import citation_progress
                result['issue_progress']=citation_progress(result['arguments'])
            judge_inputs={'snapshot_id':snapshot['snapshot_id'],'arguments':result['arguments'],
                          'calculations':result['calculations']}
            try:
                proposal=step('judge','Judge ('+modes['judge']+')',judge_inputs,
                    lambda:self.judge(deepcopy(snapshot),deepcopy(result['arguments']),deepcopy(result['calculations'])),runner=self.judge)
                errors,warnings=check_judge(snapshot,proposal,result['arguments'])
            except AgentError as exc:
                if not repairable([str(exc)]) or not self.limits.judge_repairs or not callable(getattr(self.judge,'repair',None)):
                    raise
                proposal=None;errors=[str(exc)];warnings=[]
            result['judge_initial_proposal']=deepcopy(proposal)
            result['judge_raw_validation_errors']=list(errors)
            adopted=proposal
            if errors and proposal is not None:
                from .statement_gate import downgrade_statement_only_review
                candidate,adjustments=downgrade_statement_only_review(snapshot,proposal)
                if adjustments:
                    candidate_errors,candidate_warnings=check_judge(snapshot,candidate,result['arguments'])
                    if not candidate_errors:
                        adopted=candidate;errors=candidate_errors;warnings=candidate_warnings
                        result['judge_adjustments']=adjustments
                        warnings=list(warnings)+[{'code':'STATEMENT_ONLY_REVIEW_DOWNGRADE','path':a['argument_ref'],
                            'message':'Program downgraded a statement-only support label; inspect the retained original Judge proposal.'} for a in adjustments]
            if errors and repairable(errors) and self.limits.judge_repairs and callable(getattr(self.judge,'repair',None)):
                original_errors=list(errors)
                result['repair_history'].append({'attempt':1,'original_proposal':deepcopy(proposal),'original_errors':original_errors})
                fixed=step('judge_repair','Judge structural repair',{**judge_inputs,'previous':proposal,'errors':original_errors},
                    lambda:self.judge.repair(deepcopy(snapshot),deepcopy(result['arguments']),deepcopy(result['calculations']),
                                            deepcopy(proposal),list(original_errors)),runner=self.judge)
                errors,warnings=check_judge(snapshot,fixed,result['arguments'])
                if proposal is not None and any(fixed.get(k)!=proposal.get(k) for k in ('case_id','decision','refund_amount','currency','amount_unit','escalate_to_human')):
                    errors.append('STRUCTURAL_REPAIR_CHANGED_BUSINESS_DECISION')
                result['repair_history'][-1].update(repaired_proposal=deepcopy(fixed),errors=list(errors),accepted=not errors)
                adopted=fixed
            result['judge_transport']=deepcopy(next((e.get('transport',{}) for e in reversed(self.events) if e['step'] in ('judge','judge_repair') and e['status'] in ('success','reused')),{}))
            if not errors and self.reviewer and adopted['decision']!='escalate':
                from .reviewer import validate_review
                candidate=deepcopy(adopted)
                review=step('inference_review','Inference Reviewer',{**judge_inputs,'proposal':candidate},
                    lambda:self.reviewer(deepcopy(snapshot),deepcopy(result['arguments']),deepcopy(result['calculations']),deepcopy(candidate)),runner=self.reviewer)
                result['inference_review']=deepcopy(review)
                if not validate_review(snapshot,result['arguments'],candidate,review):
                    result['reviewer_blocked']=True
                    adopted=review_ruling(snapshot,['INFERENCE_REVIEW_REQUIRES_HUMAN']+[c['explanation'] for c in review['checks'] if c['status']!='clear'])
            result['judge_final_validation_errors']=list(errors)
            result['validation_errors'].extend(errors);result['validation_warnings'].extend(warnings)
            result['judge_proposal']=deepcopy(proposal) if not errors else None
            result['ruling']=review_ruling(snapshot,['JUDGE_OUTPUT_REJECTED']+errors) if errors else deepcopy(adopted)
            step('validate_and_gate','Orchestrator',{'snapshot_id':snapshot['snapshot_id'],'proposal':adopted,'errors':errors},
                lambda:{'accepted':not errors,'errors':errors,'warnings':warnings,'effective_decision':result['ruling']['decision'],
                        'raw_model_errors':result['judge_raw_validation_errors'],'program_adjustments':result['judge_adjustments']})
        except AgentError as exc:
            result['validation_errors'].append(str(exc))
            result['ruling']=review_ruling(snapshot,[str(exc)]+result['validation_errors'])
        except (KeyboardInterrupt,SystemExit):
            result['execution_status']='interrupted';result['business_decision_status']='unavailable'
            session.save();raise
        return finish()

    def rerun_with_supplement(self, previous, new_snapshot, *, source_note, run_id=None):
        """One explicit, traceable supplement; rebuild all arguments against the new snapshot.

        This consumes supplied evidence only. It neither retrieves nor authenticates it.
        No earlier verdict is inserted into the Judge input.
        """
        if previous.get('ruling', {}).get('decision') != 'escalate':
            raise AgentError('SUPPLEMENT_REQUIRES_REVIEW_CASE')
        if previous.get('supplement_lineage'):
            raise AgentError('SUPPLEMENT_ROUND_LIMIT')
        if not isinstance(source_note, str) or not source_note.strip() or len(source_note) > 2000:
            raise AgentError('SUPPLEMENT_SOURCE_NOTE_REQUIRED')
        old = previous.get('snapshot')
        if not old: raise AgentError('SUPPLEMENT_PREVIOUS_SNAPSHOT_REQUIRED')
        verify_snapshot(old); verify_snapshot(new_snapshot)
        if new_snapshot['case_id'] != previous['case_id']:
            raise AgentError('SUPPLEMENT_CASE_MISMATCH')
        if (old['source_sha256'] == new_snapshot['source_sha256'] and
                old.get('policy_documents', {}) == new_snapshot.get('policy_documents', {})):
            raise AgentError('SUPPLEMENT_NO_SOURCE_CHANGE')
        captured = deepcopy(new_snapshot)
        class CapturedEvidence:
            def prepare(self, case_id):
                return deepcopy(captured)
        rerunner = RydeOrchestrator(evidence_gateway=CapturedEvidence(),
                                   advocate_runner=self.advocate, judge_runner=self.judge, checkpoint_store=self.store, limits=self.limits, reviewer_runner=self.reviewer, issue_guidance=self.issue_guidance, clock=self.clock, wait=self.wait, parallel_advocates=self.parallel_advocates, advocate_factory=self.advocate_factory)
        result = rerunner.run(previous['case_id'],run_id=run_id)
        result['supplement_lineage'] = {
            'round': 1, 'parent_run_id': previous['run_id'],
            'old_snapshot_id': old['snapshot_id'], 'new_snapshot_id': captured['snapshot_id'],
            'source_note': source_note.strip(),
            'data_origin': captured['audit'].get('data_origin'),
            'policy_origin': captured['audit'].get('policy_origin'),
            'old_decision': previous['ruling']['decision'], 'new_decision': result['ruling']['decision'],
            'boundary': 'Supplied source note is not independent authentication. All advocates regenerated; previous verdict excluded from model input.'}
        return result
