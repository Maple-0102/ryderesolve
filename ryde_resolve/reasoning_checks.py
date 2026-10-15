"""Typed support checks, not a natural-language entailment or truth oracle."""
from pathlib import Path
from jsonschema import Draft202012Validator
from ryderesolve_evidence.core import read_json, pointer
from .review_policy import review_plan

ANALYSIS_VALIDATOR = Draft202012Validator(read_json(Path(__file__).resolve().parents[1] / 'schemas/judge-analysis.schema.json'))
TYPES = {'statement', 'observation', 'calculation', 'inference', 'context'}
TOPICS = {'presence', 'contact_attempt', 'wait_duration', 'route_justification',
          'fare_difference', 'responsibility', 'other'}


def evidence_categories(snapshot, refs):
    categories = set()
    for ref in refs:
        item = snapshot['source_index']['evidence'].get(ref)
        if not item:
            continue
        kind = item['kind']
        paths = item['source_refs']
        if kind == 'historical_context':
            categories.add('history')
        elif kind == 'party_statement':
            categories.add('statement')
        elif kind == 'communication_record':
            values = [pointer(snapshot['raw'], p) for p in paths]
            # Call metadata documents attempted contact. Message content stays a party statement.
            categories.add('contact_record' if any(isinstance(v, dict) and v.get('type') == 'call' for v in values) else 'statement')
        elif kind == 'derived_metric' or any(p.startswith(('/fare_breakdown', '/reference_route', '/gps_telemetry')) for p in paths):
            categories.add('measurement')
        elif kind in ('record', 'event_record', 'trip_context', 'traffic_record'):
            categories.add('record')
        else:
            categories.add('context')
    return categories


def verified_route_records(snapshot, refs):
    """Accept only explicit structured verification records, never a trip-start event.

    'Verified' means asserted by this case's data provider. This function does not
    independently authenticate a traffic service. Ordinary chat cannot use this path.
    """
    values = []
    for ref in refs:
        ix = snapshot['source_index']['evidence'].get(ref, {})
        if ix.get('kind') != 'event_record':
            continue
        for path in ix.get('source_refs', []):
            row = pointer(snapshot['raw'], path)
            if (isinstance(row, dict) and row.get('event_type') == 'route_context_verification'
                and type(row.get('justification_verified')) is bool
                and type(row.get('extra_charge_verified')) is bool
                and isinstance(row.get('verification_source'), str) and row['verification_source'].strip()):
                values.append(row)
    return values


def check_finding_support(snapshot, output):
    errors, warnings = [], []
    final = output['decision'] != 'escalate'
    for i, finding in enumerate(output['findings']):
        label = f'findings/{i}'
        ft, topic = finding.get('finding_type'), finding.get('topic')
        if ft is None and topic is None and not final:
            warnings.append({'code': 'UNTYPED_FINDING', 'message': label + ' has no typed-support check'})
            continue
        if not isinstance(ft, str) or not isinstance(topic, str) or ft not in TYPES or topic not in TOPICS:
            errors.append('INVALID_FINDING_CLASSIFICATION: ' + label)
            continue
        kinds = evidence_categories(snapshot, finding['evidence_refs'])
        if ft in {'observation', 'calculation', 'inference'} and not (kinds - {'history', 'statement', 'context'}):
            errors.append('FACT_FROM_STATEMENT_OR_HISTORY_ONLY: ' + label)
        if topic == 'responsibility' and ft != 'statement':
            if not kinds or kinds <= {'history', 'context'}:
                errors.append('RESPONSIBILITY_FROM_HISTORY: ' + label)
            elif kinds <= {'measurement', 'history', 'context'}:
                errors.append('RESPONSIBILITY_FROM_ARITHMETIC: ' + label)
        if topic == 'route_justification' and ft in {'observation', 'inference'}:
            from .policy_v21 import application
            policy = application(snapshot)
            expected = next((c for c in policy['conditions'] if c['condition_id']=='route_justification'),None) if policy else None
            source_bound = expected and expected['status']=='met' and set(finding['evidence_refs']) & set(expected['evidence_refs'])
            if not source_bound and not verified_route_records(snapshot, finding['evidence_refs']):
                errors.append('ROUTE_CONTEXT_NOT_VERIFIED: ' + label)
    if final and not any(f.get('finding_type') == 'inference' and f.get('topic') == 'responsibility'
                         for f in output['findings']):
        errors.append('NO_DECISION_INFERENCE')
    warnings.append({'code': 'SEMANTIC_CHECK_LIMITATION', 'message':
                     'Typed checks cannot prove free-text entailment, evidence authenticity or LLM fairness.'})
    return errors, warnings


def argument_paths(arguments, side):
    return {f'/{rnd}/{side}/{field}/{i}'
            for rnd in ('opening', 'response') for field in ('claims', 'counterpoints')
            for i, _ in enumerate(arguments.get(rnd, {}).get(side, {}).get(field, []))}


def check_case_analysis(snapshot, output, arguments=None):
    errors, warnings = [], []
    analysis = output.get('case_analysis')
    if analysis is None:
        if output['decision'] != 'escalate':
            return ['CASE_ANALYSIS_REQUIRED'], []
        return [], [{'code': 'ANALYSIS_NOT_AVAILABLE', 'message': 'Escalation has no accepted structured analysis.'}]
    problems = list(ANALYSIS_VALIDATOR.iter_errors(analysis))
    if problems:
        return ['INVALID_CASE_ANALYSIS: /' + '/'.join(map(str, p.path)) for p in problems], []
    evidence = snapshot['source_index']['evidence']; policies = snapshot['source_index']['policy']
    records = list(analysis['sides'].values()) + analysis['disputed_points'] + analysis['review_responses']
    for record in records:
        if any(ref not in evidence for ref in record['evidence_refs']):
            errors.append('ANALYSIS_UNKNOWN_EVIDENCE')
        if any(ref not in policies for ref in record['policy_refs']):
            errors.append('ANALYSIS_UNKNOWN_POLICY')
    if arguments is None:
        errors.append('ANALYSIS_ARGUMENTS_UNAVAILABLE')
    else:
        for side, assessment in analysis['sides'].items():
            expected = argument_paths(arguments, side)
            refs = set(assessment['argument_refs'])
            if refs - expected: errors.append('ANALYSIS_UNKNOWN_ARGUMENT: ' + side)
            if expected - refs: errors.append('UNADDRESSED_ARGUMENT: ' + side)
            if assessment['assessment'] != 'unresolved' and not expected:
                errors.append('SIDE_ASSESSED_WITHOUT_ARGUMENT: ' + side)
            if assessment['assessment'] in {'accepted', 'partly_supported', 'contradicted'} and not assessment['evidence_refs']:
                errors.append('UNSUPPORTED_SIDE_ASSESSMENT: ' + side)
            if assessment['assessment'] in {'accepted', 'partly_supported'}:
                kinds = evidence_categories(snapshot, assessment['evidence_refs'])
                if not (kinds - {'history', 'statement', 'context'}):
                    errors.append('SIDE_SUPPORTED_BY_STATEMENT_OR_HISTORY_ONLY: ' + side)
    if arguments is not None:
        from .deliberation import check_deliberation
        errors.extend(check_deliberation(snapshot, output, arguments))
    issues = {i['code']: i for i in review_plan(snapshot)['items'] if i['category'] != 'informational'}
    codes = [r['issue_code'] for r in analysis['review_responses']]
    if len(codes) != len(set(codes)): errors.append('DUPLICATE_REVIEW_RESPONSE')
    if set(codes) - set(issues): errors.append('UNKNOWN_REVIEW_RESPONSE')
    if set(issues) - set(codes): errors.append('UNADDRESSED_REVIEW_ISSUE')
    for response in analysis['review_responses']:
        issue = issues.get(response['issue_code'])
        if not issue or response['status'] != 'resolved': continue
        if issue['category'] == 'requires_clarification':
            errors.append('CANNOT_SELF_RESOLVE_POLICY_OR_DATA: ' + issue['code'])
            continue
        from .policy_v21 import application,policy_refs
        applied=application(snapshot)
        if applied:
            required_sections=['1.3','1.4'] if snapshot['evidence_pack']['dispute_type']=='route_deviation' else ['3.2','3.3']
            needed=policy_refs(snapshot,required_sections)
            if not set(needed)<=set(response['policy_refs']):
                errors.append('POLICY_REVIEW_RESPONSE_BASIS_MISSING')
            relevant=[c for c in applied['conditions'] if c['condition_id'] in applied['material_condition_ids']]
            if (applied['permitted_decision'] is None or any(c['status']=='unknown' or not set(response['evidence_refs']) & set(c['evidence_refs']) for c in relevant)):
                errors.append('POLICY_REVIEW_CANNOT_CLEAR_MATERIAL_GAP')
            continue
        rows = verified_route_records(snapshot, response['evidence_refs'])
        # Both context and refund rules must be considered; arbitrary P IDs are not enough.
        paths = {p for ref in response['policy_refs'] if ref in policies for p in policies[ref]['source_refs']}
        if not {'/route_policy/context_rule', '/route_policy/refund_rule'} <= paths:
            errors.append('ROUTE_RESOLUTION_POLICY_MISSING')
        if not rows:
            errors.append('ROUTE_RESOLUTION_CONTEXT_MISSING')
        elif len({(r['justification_verified'], r['extra_charge_verified']) for r in verified_route_records(snapshot, list(evidence))}) != 1:
            errors.append('CONFLICTING_ROUTE_VERIFICATION')
        elif output['decision'] == 'uphold_charge' and not all(r['justification_verified'] and r['extra_charge_verified'] for r in rows):
            errors.append('ROUTE_RESOLUTION_DECISION_CONFLICT')
        elif output['decision'] in {'refund_full', 'refund_partial'}:
            if not all(not r['extra_charge_verified'] for r in rows):
                errors.append('ROUTE_RESOLUTION_DECISION_CONFLICT')
    if output['decision'] in {'refund_full', 'refund_partial'} and snapshot['evidence_pack']['dispute_type'] == 'route_deviation':
        from decimal import Decimal
        diff = snapshot['audit']['metrics'].get('fare_difference', {}).get('difference_cents')
        amount = output.get('refund_amount')
        if type(amount) in (int, float) and diff is not None:
            if Decimal(str(amount)) > max(Decimal(str(diff)) / 100, Decimal(0)):
                errors.append('REFUND_EXCEEDS_SUPPORTED_ROUTE_EXCESS')
    if output['decision'] != 'escalate':
        if analysis['missing_information']:
            errors.append('UNRESOLVED_MATERIAL_INFORMATION')
        if any(s['assessment'] == 'unresolved' for s in analysis['sides'].values()):
            errors.append('UNRESOLVED_SIDE_ASSESSMENT')
    return errors, warnings
