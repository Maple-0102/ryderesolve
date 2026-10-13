"""Bounded cross-field checks. Evidence meaning still requires model/human evaluation."""
from .review_policy import review_plan


def condition_specs(snapshot):
    if snapshot['evidence_pack']['dispute_type'] == 'route_deviation':
        return [
            {'condition_id': 'route_justification', 'question': 'Is the route change justified by verified context?'},
            {'condition_id': 'extra_charge', 'question': 'Is the extra charge supported by verified records and policy?'},
        ]
    return [{'condition_id': 'no_show_charge', 'question': 'Do the authoritative waiting clock, presence/contact records and policy establish this no-show charge?'}]


def check_deliberation(snapshot, output, arguments):
    """Called only after case_analysis schema validation, with validated Advocate outputs."""
    from .reasoning_checks import argument_paths, evidence_categories, verified_route_records
    a = output['case_analysis']; errors = []
    final = output['decision'] != 'escalate'
    expected = set().union(*(argument_paths(arguments, side) for side in ('rider', 'driver')))
    ledger = a['argument_assessments']
    paths = [x['argument_ref'] for x in ledger]
    if len(paths) != len(set(paths)): errors.append('DUPLICATE_ARGUMENT_ASSESSMENT')
    if set(paths) != expected: errors.append('ARGUMENT_ASSESSMENT_COVERAGE')
    evidence = snapshot['source_index']['evidence']; policies = snapshot['source_index']['policy']
    for item in ledger:
        label = item['argument_ref']; status = item['assessment']
        support, opposition = set(item['supporting_evidence_refs']), set(item['opposing_evidence_refs'])
        if (support | opposition) - set(evidence): errors.append('ARGUMENT_UNKNOWN_EVIDENCE: ' + label)
        if set(item['policy_refs']) - set(policies): errors.append('ARGUMENT_UNKNOWN_POLICY: ' + label)
        if support & opposition: errors.append('ARGUMENT_CONFLICTING_REFERENCE_ROLE: ' + label)
        required = support if status in ('supported', 'partly_supported') else opposition if status == 'contradicted' else None
        if required is not None:
            if not (evidence_categories(snapshot, required) - {'history', 'statement', 'context'}):
                errors.append('ARGUMENT_ASSESSMENT_WITHOUT_RECORD_SUPPORT: ' + label)
        if status == 'insufficient_evidence' and not item['missing_information']:
            errors.append('ARGUMENT_MISSING_GAP_EXPLANATION: ' + label)
        if status == 'unresolved' and final: errors.append('UNRESOLVED_ARGUMENT: ' + label)
        if status == 'not_factual_claim' and (support or opposition):
            errors.append('NON_FACTUAL_ARGUMENT_WITH_EVIDENCE: ' + label)
    # Side summaries cannot contradict their own per-argument statuses.
    for side, summary in a['sides'].items():
        statuses = {x['assessment'] for x in ledger if x['argument_ref'] in argument_paths(arguments, side) and x['assessment'] != 'not_factual_claim'}
        if not statuses and summary['assessment'] != 'unresolved':
            errors.append('SIDE_WITHOUT_FACTUAL_ARGUMENTS: ' + side)
        allowed = {'accepted': {'supported'}, 'partly_supported': {'supported', 'partly_supported'},
                   'unsupported': {'insufficient_evidence'}, 'contradicted': {'contradicted'}}
        if summary['assessment'] == 'accepted' and statuses != {'supported'}:
            errors.append('SIDE_LEDGER_CONFLICT: ' + side)
        elif summary['assessment'] in allowed and summary['assessment'] != 'accepted' and not (statuses & allowed[summary['assessment']]):
            errors.append('SIDE_LEDGER_CONFLICT: ' + side)
        if summary['assessment'] == 'unsupported' and statuses - {'insufficient_evidence'}:
            errors.append('SIDE_LEDGER_CONFLICT: ' + side)
        if summary['assessment'] == 'contradicted' and statuses - {'contradicted'}:
            errors.append('SIDE_LEDGER_CONFLICT: ' + side)
    conditions = {c['condition_id']: c for c in a['decision_conditions']}
    required_ids = {c['condition_id'] for c in condition_specs(snapshot)}
    if len(conditions) != len(a['decision_conditions']) or set(conditions) != required_ids:
        errors.append('DECISION_CONDITION_COVERAGE')
    for c in a['decision_conditions']:
        if set(c['evidence_refs']) - set(evidence): errors.append('CONDITION_UNKNOWN_EVIDENCE')
        if set(c['policy_refs']) - set(policies): errors.append('CONDITION_UNKNOWN_POLICY')
        if c['status'] != 'unknown' and (not c['evidence_refs'] or not c['policy_refs']):
            errors.append('CONDITION_BASIS_MISSING: ' + c['condition_id'])
        if final and c['status'] == 'unknown': errors.append('UNRESOLVED_DECISION_CONDITION: ' + c['condition_id'])
        if c['status'] == 'unknown': continue
        if c['condition_id'] in ('route_justification', 'extra_charge'):
            rows = verified_route_records(snapshot, c['evidence_refs'])
            key = 'justification_verified' if c['condition_id'] == 'route_justification' else 'extra_charge_verified'
            all_rows = verified_route_records(snapshot, list(evidence))
            values = {r[key] for r in all_rows}
            if not rows or len(values) != 1 or (c['status'] == 'met') != next(iter(values), None):
                errors.append('CONDITION_RECORD_CONFLICT: ' + c['condition_id'])
            wanted = '/route_policy/context_rule' if key == 'justification_verified' else '/route_policy/refund_rule'
            policy_paths = {p for ref in c['policy_refs'] if ref in policies for p in policies[ref]['source_refs']}
            if wanted not in policy_paths: errors.append('CONDITION_POLICY_MISSING: ' + c['condition_id'])
        elif c['condition_id'] == 'no_show_charge' and any(i['category'] == 'requires_clarification' for i in review_plan(snapshot)['items']):
            errors.append('CONDITION_CANNOT_CLEAR_POLICY_AMBIGUITY')
    if final:
        for point in a['disputed_points']:
            if not point['evidence_refs'] or not point['policy_refs']:
                errors.append('DISPUTED_POINT_BASIS_MISSING')
        if set(conditions) == required_ids:
            uphold = output['decision'] == 'uphold_charge'
            decisive = 'extra_charge' if 'extra_charge' in conditions else 'no_show_charge'
            if conditions[decisive]['status'] != ('met' if uphold else 'not_met'):
                errors.append('DECISION_CONDITION_CONFLICT')
            if uphold and any(c['status'] != 'met' for c in conditions.values()):
                errors.append('DECISION_CONDITION_CONFLICT')
        for finding in output['findings']:
            if finding.get('topic') != 'responsibility' or finding.get('finding_type') != 'inference': continue
            refs = finding.get('condition_refs')
            if not isinstance(refs, list) or any(not isinstance(r, str) for r in refs):
                errors.append('INVALID_FINDING_CONDITION_REFS'); continue
            if set(refs) != required_ids or len(refs) != len(set(refs)):
                errors.append('FINDING_CONDITION_COVERAGE'); continue
            # A relevant verified condition elsewhere cannot launder an unrelated finding citation.
            if set(conditions) == required_ids:
                evidence_needed = {r for c in conditions.values() for r in c['evidence_refs']}
                policies_needed = {r for c in conditions.values() for r in c['policy_refs']}
                if not evidence_needed <= set(finding['evidence_refs']) or not policies_needed <= set(finding['policy_refs']):
                    errors.append('FINDING_CONDITION_BASIS_MISMATCH')
    return errors
