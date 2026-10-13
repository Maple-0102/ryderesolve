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
