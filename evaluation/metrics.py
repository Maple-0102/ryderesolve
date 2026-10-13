"""Small-suite descriptive metrics; no population accuracy or calibrated confidence."""
from collections import Counter
from math import ceil
from statistics import median


def summarize_metrics(rows):
    decisions = ('uphold_charge', 'refund_full', 'refund_partial', 'escalate')
    by_decision = {}
    for decision in decisions:
        group = [r for r in rows if r['expected']['decision'] == decision]
        by_decision[decision] = {'matched': sum(r['behaviour_match'] for r in group), 'total': len(group)}
    confusion = {d: {} for d in decisions}
    for row in rows:
        actual = row['model_decision'] if row['all_checks_pass'] else 'invalid_output'
        actual = actual or 'no_output'
        bucket = confusion[row['expected']['decision']]
        bucket[actual] = bucket.get(actual, 0) + 1
    times = sorted(r['duration_ms'] for r in rows)
    errors = Counter(e.split(':', 1)[0] for r in rows for e in r['errors'])
    usage = Counter(); recorded_calls = 0
    for row in rows:
        tokens = row.get('transport', {}).get('usage', {})
        if tokens: recorded_calls += 1
        usage.update(tokens)
    valid = [r for r in rows if r['all_checks_pass']]
    return {'by_expected_decision': by_decision, 'confusion': confusion,
            'invalid_outputs': len(rows) - len(valid),
            'false_escalations': sum(r['all_checks_pass'] and r['model_decision'] == 'escalate' and r['expected']['decision'] != 'escalate' for r in rows),
            'unsafe_decisive_recommendations': sum(r['all_checks_pass'] and r['model_decision'] != 'escalate' and r['expected']['decision'] == 'escalate' for r in rows),
            'refund_amount_mismatches': sum(r['all_checks_pass'] and r['model_decision'] == r['expected']['decision'] and not r['behaviour_match'] for r in rows),
            'error_counts': dict(errors),
            'latency_ms': {'median': median(times) if times else None, 'p95_sample': times[max(0, ceil(.95*len(times))-1)] if times else None},
            'recorded_token_usage': dict(usage), 'calls_with_recorded_usage': recorded_calls,
            'usage_complete': recorded_calls == len(rows) and bool(rows),
            'boundary': 'Descriptive results on this small shared-seed suite only. Invalid outputs fail scoring; they are not correct escalations. Token sums are not billed costs.'}
