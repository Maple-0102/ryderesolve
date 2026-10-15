"""Capture one snapshot, run two balanced rounds, validate, and gate the result."""
from copy import deepcopy
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from .agents import AgentError
from .contracts import check_advocate, check_judge
from .evidence import EvidenceGateway, verify_snapshot
from .mock_agents import OfflineAdvocate, OfflineJudge, review_ruling
from .rule_engine import calculate_rules


class RydeOrchestrator:
    def __init__(self, evidence_gateway=None, advocate_runner=None, judge_runner=None):
        self.evidence = evidence_gateway or EvidenceGateway()
        self.advocate = advocate_runner or OfflineAdvocate()
        self.judge = judge_runner or OfflineJudge()
        self.events = []

    def run(self, case_id='DISP-002'):
        self.events = []  # New run must never inherit another case's transcript.
        run_id = str(uuid4())
        modes = {'advocate': getattr(self.advocate, 'mode', 'custom_adapter'),
                 'judge': getattr(self.judge, 'mode', 'custom_adapter')}
        result = {'run_id': run_id, 'case_id': case_id, 'modes': modes,
                  'snapshot': None, 'calculations': {},
                  'arguments': {'opening': {}, 'response': {}},
                  'ruling': None, 'judge_proposal': None, 'judge_adjustments': [],
                  'judge_raw_validation_errors': [], 'validation_errors': [],
                  'validation_warnings': [], 'communication_log': self.events}

        def step(name, agent, inputs, fn):
            event = {'sequence': len(self.events) + 1, 'step': name, 'agent': agent,
                     'started_at': datetime.now(timezone.utc).isoformat(),
                     'input': deepcopy(inputs), 'status': 'running'}
            self.events.append(event)
            start = perf_counter()
            try:
                out = fn()
                event.update(status='success', output=deepcopy(out))
                return out
            except Exception as exc:
                code = str(exc) if isinstance(exc, AgentError) else 'STEP_FAILED_' + type(exc).__name__
                event.update(status='failed', error=code)
                raise AgentError(code) from None
            finally:
                event['finished_at'] = datetime.now(timezone.utc).isoformat()
                event['duration_ms'] = round((perf_counter() - start) * 1000, 2)

        snapshot = {'case_id': case_id}
        try:
            def prepare():
                s = self.evidence.prepare(case_id)
                verify_snapshot(s)
                if s['case_id'] != case_id:
                    raise AgentError('EVIDENCE_CASE_MISMATCH')
                return s
            snapshot = step('prepare_case', 'EvidenceTools', {'case_id': case_id}, prepare)
            result['snapshot'] = deepcopy(snapshot)
            result['calculations'] = step('calculate_rules', 'Audited calculations',
                                          {'snapshot_id': snapshot['snapshot_id']},
                                          lambda: calculate_rules(snapshot))
            policy = result['calculations'].get('policy_application')
            if policy and policy['evidence_only']:
                result['execution_policy'] = 'evidence_only'
                result['providers_skipped'] = True
                result['ruling'] = review_ruling(snapshot, ['SAFETY_EVIDENCE_ONLY: policy sections 5.1-5.2 require human adjudication.'])
                step('safety_gate', 'Policy v2.1', {'snapshot_id':snapshot['snapshot_id']},
                     lambda: {'action':'human_review','agents_called':False,'policy_refs': ['P-RYDE-2.1-S5.1','P-RYDE-2.1-S5.2']})
                from .handoff import build_handoff
                result['human_handoff'] = build_handoff(result)
                return result
            for round_name in ('opening', 'response'):
                for side in ('rider', 'driver'):
                    other = 'driver' if side == 'rider' else 'rider'
                    opponent = deepcopy(result['arguments']['opening'].get(other)) if round_name == 'response' else None
                    def run_advocate():
                        try:
                            out = self.advocate(deepcopy(snapshot), side, round_name, deepcopy(opponent))
                        finally:
                            from .teammate_advocate import TeammateAdvocate
                            if isinstance(self.advocate, TeammateAdvocate):
                                self.events[-1]['transport'] = deepcopy(self.advocate.last_metadata)
                        errors, warnings = check_advocate(snapshot, out, side)
                        result['validation_warnings'].extend(warnings)
                        if errors:
                            result['validation_errors'].extend(errors)
                            raise AgentError('INVALID_ADVOCATE_OUTPUT')
                        return out
                    result['arguments'][round_name][side] = step(
                        round_name, side + ' Advocate',
                        {'snapshot_id': snapshot['snapshot_id'], 'opponent_opening': opponent,
                         'evidence_refs': [f['evidence_id'] for f in snapshot['evidence_pack']['facts']]}, run_advocate)
            proposal = step('judge', 'Judge (' + modes['judge'] + ')',
                            {'snapshot_id': snapshot['snapshot_id'], 'arguments': result['arguments'],
                             'calculations': result['calculations']},
                            lambda: self.judge(deepcopy(snapshot), deepcopy(result['arguments']),
                                               deepcopy(result['calculations'])))
            from .adp import ADPJudge
            from .vertex import VertexJudge
            if isinstance(self.judge, (ADPJudge, VertexJudge)):
                result['judge_transport'] = deepcopy(self.judge.last_metadata)
            # validate() rejects NaN and non-JSON values; do not serialize rejected proposals.
            errors, warnings = check_judge(snapshot, proposal, result['arguments'])
            result['judge_raw_validation_errors'] = list(errors)
            adopted = proposal
            if errors:
                from .statement_gate import downgrade_statement_only_review
                candidate, adjustments = downgrade_statement_only_review(snapshot, proposal)
                if adjustments:
                    candidate_errors, candidate_warnings = check_judge(snapshot, candidate, result['arguments'])
                    if not candidate_errors:
                        adopted = candidate
                        errors, warnings = candidate_errors, candidate_warnings
                        result['judge_adjustments'] = adjustments
                        warnings = list(warnings) + [
                            {'code': 'STATEMENT_ONLY_REVIEW_DOWNGRADE', 'path': a['argument_ref'],
                             'message': 'Program downgraded a statement-only support label; inspect the retained original Judge proposal.'}
                            for a in adjustments]
            result['validation_errors'].extend(errors)
            result['validation_warnings'].extend(warnings)
            if errors:
                result['ruling'] = review_ruling(snapshot, ['JUDGE_OUTPUT_REJECTED'] + errors)
            else:
                result['judge_proposal'] = deepcopy(proposal)
                result['ruling'] = deepcopy(adopted)
            step('validate_and_gate', 'Orchestrator', {'snapshot_id': snapshot['snapshot_id']},
                 lambda: {'accepted': not errors, 'errors': errors, 'warnings': warnings,
                          'effective_decision': result['ruling']['decision'],
                          'raw_model_errors': result['judge_raw_validation_errors'],
                          'program_adjustments': result['judge_adjustments']})
        except AgentError as exc:
            from .vertex import VertexJudge
            if isinstance(self.judge, VertexJudge):
                result['judge_transport'] = deepcopy(self.judge.last_metadata)
            result['validation_errors'].append(str(exc))
            result['ruling'] = review_ruling(snapshot, [str(exc)] + result['validation_errors'])
        # Remove any malformed output from logs (e.g. NaN from a custom adapter).
        from ryderesolve_evidence.core import assert_json_value
        for event in self.events:
            if 'output' in event:
                try:
                    assert_json_value(event['output'])
                except (ValueError, TypeError):
                    event['output'] = {'omitted': 'invalid JSON output'}
        from .handoff import build_handoff
        result['human_handoff'] = build_handoff(result)
        return result

    def rerun_with_supplement(self, previous, new_snapshot, *, source_note):
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
                                   advocate_runner=self.advocate, judge_runner=self.judge)
        result = rerunner.run(previous['case_id'])
        result['supplement_lineage'] = {
            'round': 1, 'parent_run_id': previous['run_id'],
            'old_snapshot_id': old['snapshot_id'], 'new_snapshot_id': captured['snapshot_id'],
            'source_note': source_note.strip(),
            'data_origin': captured['audit'].get('data_origin'),
            'policy_origin': captured['audit'].get('policy_origin'),
            'old_decision': previous['ruling']['decision'], 'new_decision': result['ruling']['decision'],
            'boundary': 'Supplied source note is not independent authentication. All advocates regenerated; previous verdict excluded from model input.'}
        return result
