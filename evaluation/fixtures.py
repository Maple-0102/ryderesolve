"""Synthetic in-memory case variants; source files are never rewritten."""
from copy import deepcopy
from ryderesolve_evidence.core import build_bundle


def with_verification(base, *, justified=True, charged=True, contradiction=False):
    raw = deepcopy(base['raw'])
    event = {'timestamp': '2026-10-01T10:15:00+08:00', 'event_type': 'route_context_verification',
             'details': 'Synthetic Judge exercise only; not an operational verification service.',
             'verification_source': 'internal-test-fixture', 'justification_verified': justified,
             'extra_charge_verified': charged}
    raw['app_events'].append(event)
    if contradiction:
        raw['app_events'].append({**event, 'timestamp': '2026-10-01T10:15:01+08:00',
                                  'extra_charge_verified': not charged})
    b = build_bundle(raw, {'data_origin': 'synthetic', 'policy_origin': 'team_authored_synthetic', 'source_url': None})
    return {'case_id': b.pack['case_id'], 'snapshot_id': b.audit['snapshot_id'],
            'source_sha256': b.audit['source_sha256'], 'normalizer_version': b.audit['normalizer_version'],
            'raw': b.raw, 'audit': b.audit, 'evidence_pack': b.pack,
            'source_index': {'evidence': b.evidence_index, 'policy': b.policy_index}}


def with_fee(base, *, excess_cents):
    """Counterfactual pricing variant; keep the narrative and source data consistent."""
    if type(excess_cents) is not int or excess_cents <= 0:
        raise ValueError('excess_cents must be a positive integer')
    raw = deepcopy(base['raw'])
    fare = raw['fare_breakdown']
    fare['charged_total_cents'] = fare['reference_quote_cents'] + excess_cents
    raw['dispute_ticket']['description'] = (
        f"The original quote was SGD {fare['reference_quote_cents']/100:.2f} but I was charged "
        f"SGD {fare['charged_total_cents']/100:.2f}. Please review whether the extra charge is justified.")
    b = build_bundle(raw, {'data_origin': 'synthetic', 'policy_origin': 'team_authored_synthetic', 'source_url': None})
    return {'case_id': b.pack['case_id'], 'snapshot_id': b.audit['snapshot_id'],
            'source_sha256': b.audit['source_sha256'], 'normalizer_version': b.audit['normalizer_version'],
            'raw': b.raw, 'audit': b.audit, 'evidence_pack': b.pack,
            'source_index': {'evidence': b.evidence_index, 'policy': b.policy_index}}
