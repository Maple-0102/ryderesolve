"""Audited conservative downgrades for review-only proposals; never grant entitlement."""
from copy import deepcopy
from .reasoning_checks import ANALYSIS_VALIDATOR, evidence_categories


def downgrade_statement_only_review(snapshot, proposal):
    """Correct unsupported support labels, retaining original statements elsewhere.

    No malformed shape, unknown ID or decisive proposal can be repaired here. Only
    the incident-ledger status and its attributed citations/gap are affected; the
    decision, amounts, policy, conditions and source evidence remain unchanged.
    The orchestrator must revalidate the ENTIRE candidate before adopting it.
    """
    candidate = deepcopy(proposal)
    if not isinstance(candidate, dict) or candidate.get('decision') != 'escalate':
        return candidate, []
    analysis = candidate.get('case_analysis')
    if not isinstance(analysis, dict) or list(ANALYSIS_VALIDATOR.iter_errors(analysis)):
        return candidate, []
    changes = []
    index = snapshot['source_index']['evidence']
    for row in analysis['argument_assessments']:
        from .policy_v21 import bound
        if bound(snapshot) and row.get('assessment_scope') == 'communication_act':
            continue
        if row['assessment'] not in ('supported', 'partly_supported'):
            continue
        refs = row['supporting_evidence_refs']
        if not refs or set(refs) - set(index):
            continue
        if evidence_categories(snapshot, refs) - {'history', 'statement', 'context'}:
            continue
        # Presence of genuine opposing citations still needs substantive adjudication.
        if row['opposing_evidence_refs']:
            continue
        before = deepcopy(row)
        row['assessment'] = 'insufficient_evidence'
        row['supporting_evidence_refs'] = []
        gap = 'No cited independent incident record corroborates this assertion; attributed speech alone is insufficient.'
        if gap not in row['missing_information']:
            row['missing_information'].append(gap)
        changes.append({'argument_ref': row['argument_ref'], 'rule': 'statement_only_review_downgrade',
                        'original': before, 'adjusted': deepcopy(row),
                        'boundary': 'Support rating reduced; original model proposal retained. No charge/refund or factual verification is created.'})
    return candidate, changes


def reconcile_independent_fare_analysis(snapshot, proposal, arguments):
    """Conservative ledger corrections only when a fare ruling has independent grounds.

    No generated evidence, restored allegation support, changed decision or amount.
    All original findings/conditions must pass and exclude the downgraded sources.
    The full production validator must accept the final candidate unchanged elsewhere.
    """
    from .contracts import check_judge
    from .policy_v21 import application, check_application
    from .review_policy import unresolved_issues
    if not isinstance(proposal,dict) or proposal.get('decision') not in ('uphold_charge','refund_full','refund_partial'):
        return deepcopy(proposal),[]
    if snapshot['evidence_pack']['dispute_type']!='fare_dispute':return deepcopy(proposal),[]
    app=application(snapshot)
    if (not app or app['evidence_only'] or app['mandatory_human_review']
        or app['permitted_decision'] is None or check_application(snapshot,proposal)):
        return deepcopy(proposal),[]
    errors,_=check_judge(snapshot,proposal,arguments)
    allowed={'ARGUMENT_ASSESSMENT_WITHOUT_RECORD_SUPPORT','SIDE_LEDGER_CONFLICT','UNRESOLVED_DATA_OR_POLICY_REVIEW'}
    if not errors or any(error.split(':',1)[0] not in allowed for error in errors):return deepcopy(proposal),[]
    analysis=proposal['case_analysis']
    if unresolved_issues(snapshot,analysis):return deepcopy(proposal),[]
    bad_paths={error.split(': ',1)[1] for error in errors if error.startswith('ARGUMENT_ASSESSMENT_WITHOUT_RECORD_SUPPORT: ')}
    material_refs={ref for finding in proposal['findings'] for ref in finding['evidence_refs']}
    material_refs.update(ref for condition in analysis['decision_conditions'] for ref in condition['evidence_refs'])
    rows={row['argument_ref']:row for row in analysis['argument_assessments']}
    index=snapshot['source_index']['evidence']
    for path in bad_paths:
        row=rows.get(path)
        if not row:return deepcopy(proposal),[]
        refs=row['supporting_evidence_refs']
        if (row.get('assessment_scope')!='incident_fact' or row['assessment'] not in ('supported','partly_supported')
            or not refs or set(refs)-set(index) or row['opposing_evidence_refs']
            or set(refs)&material_refs or evidence_categories(snapshot,refs)-{'history','statement','context'}):
            return deepcopy(proposal),[]
    candidate=deepcopy(proposal);changes=[]
    for row in candidate['case_analysis']['argument_assessments']:
        if row['argument_ref'] not in bad_paths:continue
        before=deepcopy(row)
        row.update(assessment='insufficient_evidence',supporting_evidence_refs=[],
            reason='Program source check: the cited attribution/background does not independently establish the incident in this argument. The original model rationale is retained in the adjustment audit.')
        row['missing_information'].append('Independent incident support for this argument is absent from its citations; no missing material fare condition is inferred by this correction.')
        changes.append({'argument_ref':row['argument_ref'],'rule':'independent_fare_argument_downgrade',
            'original':before,'adjusted':deepcopy(row),
            'boundary':'Only argument support reduced. Existing independently checked fare conditions/findings and decision/amount preserved.'})
    from .reasoning_checks import argument_paths
    remaining_errors=check_judge(snapshot,candidate,arguments)[0]
    conflicting_sides={error.split(': ',1)[1] for error in remaining_errors if error.startswith('SIDE_LEDGER_CONFLICT: ')}
    for side,summary in candidate['case_analysis']['sides'].items():
        if side not in conflicting_sides:continue
        statuses={row['assessment'] for row in candidate['case_analysis']['argument_assessments']
                  if row['argument_ref'] in argument_paths(arguments,side) and row['assessment']!='not_factual_claim'}
        desired=('unresolved' if summary['assessment'] not in ('accepted','partly_supported') or not statuses
                 else 'unsupported' if statuses=={'insufficient_evidence'} else 'contradicted' if statuses=={'contradicted'}
                 else 'partly_supported' if statuses&{'supported','partly_supported'} else 'unresolved')
        if summary['assessment']==desired:continue
        before=deepcopy(summary)
        summary.update(assessment=desired,reason='Program summary of the retained per-argument assessments; see each original argument and its evidence. The original model summary is retained in the adjustment audit.')
        changes.append({'side':side,'rule':'independent_fare_side_summary',
            'original':before,'adjusted':deepcopy(summary),
            'boundary':'Mechanical summary consistency only; no evidence, entitlement or payment created.'})
    if not changes or check_judge(snapshot,candidate,arguments)[0]:return deepcopy(proposal),[]
    return candidate,changes
