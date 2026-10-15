"""Expose audited arithmetic. Never select an unspecified policy clock."""
from copy import deepcopy
from decimal import Decimal
from .review_policy import review_plan
from .deliberation import condition_specs
from .policy_provenance import policy_provenance
from .policy_v21 import application


def refs_for_paths(snapshot, paths, kind='evidence'):
    wanted = set(paths)
    return [ref for ref, item in snapshot['source_index'][kind].items()
            if any(w == p or w.startswith(p + '/') for w in wanted for p in item['source_refs'])]


def calculate_rules(snapshot):
    audit = snapshot['audit']
    policy = application(snapshot)
    calculations = []
    for name, metric in audit['metrics'].items():
        if name == 'gps_sampling':
            continue
        entry = deepcopy(metric)
        entry.update(name=name, evidence_refs=refs_for_paths(snapshot, metric['source_refs']))
        if 'seconds' in metric:
            entry['minutes'] = metric['seconds'] / 60
        calculations.append(entry)
    return {
        'status': 'review_required' if audit['requires_policy_or_data_review'] else 'calculated',
        'selected_clock': None,
        'free_wait_clock': deepcopy(audit.get('policy_context', {}).get('free_wait_clock')),
        'policy_context': deepcopy(audit.get('policy_context', {})),
        'policy_application': policy,
        'fee_applicable': None,
        'calculations': calculations,
        'issues': deepcopy(audit['issues']),
        'review_plan': review_plan(snapshot),
        'decision_requirements': condition_specs(snapshot),
        'policy_provenance': policy_provenance(snapshot),
        'decision_amount_rules': {
            'currency': 'SGD', 'amount_unit': 'major',
            'recorded_charge': float(charged_amount(snapshot)) if charged_amount(snapshot) is not None else None,
            'supported_route_excess_limit': (audit['metrics'].get('reported_excess_distance_fare', {}).get('amount_cents', 0) / 100
                                            if policy and snapshot['evidence_pack']['dispute_type']=='route_deviation' else
                                            max(audit['metrics']['fare_difference']['difference_cents'] / 100, 0) if 'fare_difference' in audit['metrics'] else None),
            'full_refund_basis': 'Entire recorded charge; refunding only the extra fare is partial.',
            'boundary': 'These bounds validate amount labels; they do not establish entitlement.'},
        'limitation': 'Arithmetic is not a ruling; no policy clock or refund entitlement is inferred.',
    }


def charged_amount(snapshot):
    raw = snapshot['raw']
    if 'charged_total_cents' in raw.get('fare_breakdown', {}):
        return Decimal(str(raw['fare_breakdown']['charged_total_cents'])) / 100
    if 'actual_fare' in raw.get('trip_data', {}):
        return Decimal(str(raw['trip_data']['actual_fare']))
    amount = raw.get('trip_data', {}).get('cancellation_fee')
    return Decimal(str(amount)) if amount is not None else None
