"""Explicitly versioned policy sources. Case records are never overwritten by policy text."""
from datetime import timedelta
import re

DOCUMENT_ID = 'RYDE-POLICY-V2.1'
DOCUMENT_SHA256 = '2a90f8974e09e417c60300b2cb05a616d2cc12bdea893eba6456ca686d1c244f'


def policy_id(section):
    return 'P-RYDE-2.1-S' + section


def validate_documents(documents):
    from .core import InputError, source_hash
    if not isinstance(documents, dict):
        raise InputError('policy_documents must be an object')
    for key, document in documents.items():
        if key != DOCUMENT_ID or source_hash(document) != DOCUMENT_SHA256:
            raise InputError('Unknown or changed policy source; explicit revision support required')


def append_policies(documents, dispute_type, pack, policy_index):
    if not documents:
        return
    document = documents[DOCUMENT_ID]
    chapter = {'route_deviation': '1', 'no_show_charge': '2', 'fare_dispute': '3'}[dispute_type]
    precedent = {'route_deviation': '7.1', 'no_show_charge': '7.3', 'fare_dispute': '7.2'}[dispute_type]
    for section, value in document['sections'].items():
        if section.split('.')[0] not in (chapter, '5', '6') and section != precedent:
            continue
        ref = policy_id(section)
        pack['policy'].append({'policy_id': ref, 'rule': f"Section {section}: {value['title']}\n{value['text']}",
                               'source': f'Ryde Dispute Resolution Policy v2.1 §{section}'})
        policy_index[ref] = {'source_document_id': DOCUMENT_ID, 'source_refs': [f'/sections/{section}'],
                             'policy_origin': 'organizer_policy_document', 'document_sha256': DOCUMENT_SHA256,
                             'version': '2.1', 'effective_date': document['effective_date']}


def source_value(raw, documents, index_entry, ref):
    """Resolve a pointer in its declared document; legacy pointers still address raw."""
    from .core import pointer, InputError
    document_id = index_entry.get('source_document_id')
    if document_id is None:
        return pointer(raw, ref)
    if document_id not in documents:
        raise InputError('Policy source document missing from snapshot')
    return pointer(documents[document_id], ref)


def apply_policy_context(raw, documents, metrics, issues, add, issue):
    if not documents:
        return {}
    from .core import timestamp
    context = {'document_id': DOCUMENT_ID, 'version': '2.1',
               'precedence': 'No organizer statement resolves conflicts between embedded case policy and the standalone policy. Preserve both.'}
    trip = raw['trip_data']
    kind = raw['dispute_ticket']['dispute_type']
    # The effective date is explicit. A missing date must not imply applicability.
    date_key = next((key for key in ('scheduled_time', 'start_time', 'trip_start_time') if key in trip), None)
    if date_key is None or timestamp(trip[date_key], date_key).date().isoformat() < documents[DOCUMENT_ID]['effective_date']:
        issue('POLICY_APPLICABILITY_UNCONFIRMED', 'Trip date is missing or predates policy v2.1 effective date.', ['/trip_data'])
        return context
    if kind == 'no_show_charge':
        # Section 2.1 defines the FREE wait only. It does not define the embedded 8-minute clock.
        issues[:] = [i for i in issues if i['code'] not in ('POLICY_CLOCK_BASIS_UNSPECIFIED', 'INCOMPLETE_NO_SHOW_POLICY')]
        for item in issues:
            if item['code'] in ('WAIT_START_DISAGREEMENT', 'WAIT_START_BEFORE_SCHEDULED_PICKUP'):
                item['severity'] = 'info'
                item['message'] += ' Section 2.1 explicitly starts the free wait at scheduled pickup; the logged timers remain separate records.'
                item['policy_refs'] = [policy_id('2.1')]
        scheduled = trip.get('scheduled_time')
        context['free_wait_clock'] = {'basis': 'scheduled_time', 'minutes': 5,
                                     'policy_refs': [policy_id('2.1')], 'source_refs': ['/trip_data/scheduled_time'] if scheduled else []}
        if scheduled:
            end = timestamp(scheduled, 'scheduled_time') + timedelta(minutes=5)
            context['free_wait_clock']['ends_at'] = end.isoformat()
            refs = ['/trip_data/scheduled_time']
            elapsed = metrics.get('scheduled_pickup_to_cancellation', {}).get('seconds')
            if elapsed is not None:
                refs.append('/trip_data/cancellation_time')
            add(f'Under supplied policy v2.1 section 2.1, free wait starts at scheduled pickup {scheduled} and ends at {end.isoformat()}. Recorded cancellation elapsed from scheduled pickup: {elapsed} seconds. This does not resolve the embedded no-show threshold or establish fee entitlement.',
                'derived.free_wait_policy', refs, 'derived_metric')
        else:
            issue('SCHEDULED_PICKUP_MISSING', 'Section 2.1 supplies a free-wait basis but scheduled pickup is absent.', ['/trip_data'], policy_refs=[policy_id('2.1')])
        policy = raw.get('cancellation_policy', {})
        conflicts = [key for key, expected in (('free_wait_time_min', 5), ('cancellation_fee_after_wait', 5))
                     if key in policy and policy[key] != expected]
        if 'no_show_threshold_min' in policy:
            issue('NO_SHOW_THRESHOLD_CLOCK_UNSPECIFIED', 'The embedded no-show threshold has no defined start event. Section 2.1 defines free wait from scheduled pickup but does not define this separate threshold clock.', ['/cancellation_policy/no_show_threshold_min'], policy_refs=[policy_id('2.1')])
            if policy['no_show_threshold_min'] != 5:
                conflicts.append('no_show_threshold_min')
        if conflicts:
            issue('POLICY_SOURCE_CONFLICT', 'Embedded cancellation thresholds/fee differ from standalone v2.1 sections 2.1-2.2 (cancel after 5 free minutes from scheduled pickup; $5 fee). Source precedence is not supplied. Do not treat 5+8 as 13 or choose the favorable clock.',
                  ['/cancellation_policy/' + key for key in conflicts], policy_refs=[policy_id('2.1'), policy_id('2.2')])
        if policy.get('wait_clock_basis'):
            issue('EMBEDDED_CLOCK_REQUIRES_RECONCILIATION', 'A case-specific clock statement must be reconciled with section 2.1; no source precedence is supplied.', ['/cancellation_policy/wait_clock_basis'], policy_refs=[policy_id('2.1')])
    route = metrics.get('reported_route_distance')
    if kind == 'route_deviation' and route and route['excess_km'] > 2:
        issue('ROUTE_DISTANCE_REQUIRES_HUMAN_REVIEW', 'Section 6.2 requires human review when reported route deviation exceeds 2 km, regardless of a possible refund rationale.', route['source_refs'], policy_refs=[policy_id('6.2')])
    if kind == 'route_deviation' and not route:
        issue('ROUTE_POLICY_DISTANCE_UNAVAILABLE', 'Policy uses reported road-route km; sampled polyline distance cannot substitute for that quantity.', [], policy_refs=[policy_id('1.4'), policy_id('6.2')])
    flags = [f'/{role}_profile/fraud_flags' for role in ('rider', 'driver') if raw.get(role + '_profile', {}).get('fraud_flags', 0) >= 1]
    if flags:
        context['confidence_requirement'] = {'minimum': 0.95, 'policy_refs': [policy_id('6.3')], 'source_refs': flags,
            'limitation': 'Policy confidence gate only; the history flag does not establish responsibility.'}
        issue('FRAUD_FLAG_CONFIDENCE_REQUIREMENT', 'Section 6.3 raises the required confidence to 95%. This is not proof of present fault and no confidence value is fabricated.', flags, 'info', [policy_id('6.3')])
    elif kind == 'route_deviation':
        context['confidence_requirement'] = {'minimum': 0.8, 'policy_refs': [policy_id('6.2')], 'source_refs': []}
    if kind == 'fare_dispute' and 'fare_difference' in metrics:
        value = abs(metrics['fare_difference']['difference_cents'])
        context['dispute_value'] = {'cents': value, 'basis': 'disputed fare difference, not entire trip fare',
                                    'source_refs': metrics['fare_difference']['source_refs']}
        if value > 5000:
            issue('DISPUTE_VALUE_REQUIRES_HUMAN_REVIEW', 'Sections 6.1-6.2 require human review for a dispute value above $50.', metrics['fare_difference']['source_refs'], policy_refs=[policy_id('6.1'), policy_id('6.2')])
        elif value >= 1000 and not flags:
            context['confidence_requirement'] = {'minimum': 0.8, 'policy_refs': [policy_id('6.1'), policy_id('6.2')], 'source_refs': metrics['fare_difference']['source_refs']}
    # Inspect reported incident text, never policy text or a traffic report about another road.
    candidates = [('/dispute_ticket/description', raw['dispute_ticket'].get('description', ''))]
    candidates += [(f'/chat_logs/{i}/' + ('content' if 'content' in row else 'message'),
                    row.get('content', row.get('message', ''))) for i, row in enumerate(raw.get('chat_logs', []))]
    safety_refs = [ref for ref, text in candidates if re.search(r'\b(unsafe|harass\w*|assault\w*|reckless\w*|threaten\w*|dangerous driving|traffic accident)\b', text, re.I)]
    if raw['dispute_ticket'].get('safety_related') is True:
        safety_refs.append('/dispute_ticket/safety_related')
    if safety_refs:
        issue('SAFETY_INDICATOR_REQUIRES_HUMAN_REVIEW', 'Reported safety indicators require human review under sections 5.1-5.2; keyword screening is not a safety classifier or a finding of fault. Agents may prepare evidence only.', safety_refs, policy_refs=[policy_id('5.1'), policy_id('5.2')])
        context['evidence_only'] = True
    return context
