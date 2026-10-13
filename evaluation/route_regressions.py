"""Small, labelled development regressions; no training or official answer claims."""
from copy import deepcopy
from ryde_resolve.evidence import EvidenceGateway
from ryde_resolve.rule_engine import refs_for_paths
from .fixtures import with_verification
from .judge_suite import exercise_arguments


def build_route_regressions():
    base = EvidenceGateway().prepare('SYN-ROUTE-001')
    mixed = with_verification(base, justified=True, charged=False)
    cases = []
    def add(name, snapshot, decision, amount, purpose, claim=None):
        arguments = exercise_arguments(snapshot)
        if claim:
            arguments['response']['driver']['claims'].append({
                'claim': claim, 'evidence_refs': refs_for_paths(snapshot, ['/gps_telemetry', '/chat_logs']),
                'policy_refs': refs_for_paths(snapshot, ['/route_policy/context_rule', '/route_policy/refund_rule'], 'policy')})
        cases.append({'exercise_id': name, 'snapshot': deepcopy(snapshot), 'arguments': arguments,
                      'expected': {'decision': decision, 'refund_amount': amount}, 'purpose': purpose,
                      'order_pair': None, 'split': 'targeted_development',
                      'provenance': 'Team-reviewed regression assumptions, not official ground truth.'})
    add('ROUTE-SAMPLED-SPEED', base, 'escalate', None,
        'Reject the full-trip speed inference while retaining the measured samples.',
        'The sampled speeds prove the vehicle maintained 24 km/h throughout the entire trip.')
    add('ROUTE-UNVERIFIED-NOT-FALSE', base, 'escalate', None,
        'Absent traffic verification is not affirmative proof of an unjustified charge.',
        'No independent traffic feed is supplied, so the driver traffic explanation is false and the extra charge must be refunded.')
    add('ROUTE-JUSTIFIED-CHARGE-INVALID', mixed, 'refund_partial', 5,
        'A verified justified route does not authorize a separately verified unjustified extra charge.',
        'The detour is verified as justified, therefore the extra fare must also be valid.')
    return cases
