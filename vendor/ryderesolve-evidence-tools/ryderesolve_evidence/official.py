"""Record adapters and deterministic arithmetic for the organizer's route/fare formats."""
from decimal import Decimal
import json


def cents(value, ref):
    from .core import number, InputError
    number(value, ref)
    amount = Decimal(str(value)) * 100
    if amount != amount.to_integral_value() or abs(amount) > 9007199254740991:
        raise InputError(f'Money must have at most two decimals and safe integer cents: {ref}')
    return int(amount)


def validate_extensions(raw):
    from .core import number, timestamp, InputError
    for key in ('optimal_route', 'surge_pricing_log', 'fare_policy'):
        if key in raw and not isinstance(raw[key], dict):
            raise InputError(f'{key} must be an object')
    route = raw.get('optimal_route', {})
    points = route.get('waypoints', [])
    if not isinstance(points, list):
        raise InputError('optimal_route.waypoints must be an array')
    for i, point in enumerate(points):
        if not isinstance(point, dict):
            raise InputError('Route waypoint must be an object')
        number(point.get('lat'), f'/optimal_route/waypoints/{i}/lat', -90, 90)
        number(point.get('lng'), f'/optimal_route/waypoints/{i}/lng', -180, 180)
    if 'estimated_distance_km' in route:
        number(route['estimated_distance_km'], '/optimal_route/estimated_distance_km', 0)
    traffic = raw.get('traffic_conditions', [])
    if not isinstance(traffic, list):
        raise InputError('traffic_conditions must be an array')
    for i, record in enumerate(traffic):
        if not isinstance(record, dict):
            raise InputError('Traffic record must be an object')
        start = timestamp(record.get('timestamp'), f'/traffic_conditions/{i}/timestamp')
        if record.get('clear_time') is not None and timestamp(record['clear_time'], f'/traffic_conditions/{i}/clear_time') < start:
            raise InputError('Traffic clearance precedes incident')
    surge = raw.get('surge_pricing_log', {})
    if 'rider_notified' in surge and type(surge['rider_notified']) is not bool:
        raise InputError('surge_pricing_log.rider_notified must be boolean')
    if 'free_cancellation_offered' in surge and type(surge['free_cancellation_offered']) is not bool:
        raise InputError('surge_pricing_log.free_cancellation_offered must be boolean')
    if surge.get('notification_method') is not None and not isinstance(surge['notification_method'], str):
        raise InputError('surge_pricing_log.notification_method must be text or null')
    for key in ('surge_activated_at', 'notification_timestamp'):
        if surge.get(key) is not None:
            timestamp(surge[key], f'/surge_pricing_log/{key}')
    for key in ('quote_time_surge', 'trip_start_surge', 'notified_multiplier', 'revised_estimated_fare'):
        if key in surge:
            number(surge[key], f'/surge_pricing_log/{key}', 0)
    fare = raw.get('fare_breakdown', {})
    for name in ('estimated', 'actual', 'delta', 'upfront_quote', 'actual_fare', 'comparison'):
        if name not in fare:
            continue
        if not isinstance(fare[name], dict):
            raise InputError(f'fare_breakdown.{name} must be an object')
        for key in ('total', 'surge_amount', 'surgeable_subtotal', 'total_difference', 'surge_amount_difference'):
            if key in fare[name]:
                cents(fare[name][key], f'/fare_breakdown/{name}/{key}')
                if key in ('total', 'surgeable_subtotal'):
                    number(fare[name][key], f'/fare_breakdown/{name}/{key}', 0)
        if 'surge_multiplier' in fare[name]:
            number(fare[name]['surge_multiplier'], f'/fare_breakdown/{name}/surge_multiplier', 0)
    for key in ('excess_distance_fare', 'excess_tolls'):
        if key in fare:
            cents(fare[key], f'/fare_breakdown/{key}')
    for key in ('actual_fare', 'estimated_fare', 'upfront_quote', 'fare_difference', 'excess_fare', 'cancellation_fee'):
        if key in raw['trip_data']:
            cents(raw['trip_data'][key], f'/trip_data/{key}')
    for role in ('rider', 'driver'):
        flags = raw.get(role + '_profile', {}).get('fraud_flags')
        if flags is not None and (type(flags) is not int or flags < 0):
            raise InputError('fraud_flags must be a nonnegative integer count')


def enrich_official(raw, metrics, add, issue):
    trip = raw['trip_data']
    kind = raw['dispute_ticket']['dispute_type']
    for key in ('start_time', 'end_time', 'estimated_duration_min', 'actual_duration_min',
                'estimated_distance_km', 'actual_distance_km', 'excess_distance_km',
                'estimated_fare', 'actual_fare', 'upfront_quote', 'fare_difference', 'excess_fare'):
        if key in trip:
            add(f'Trip record {key}: {trip[key]}.', 'trip_data', [f'/trip_data/{key}'])
    if 'optimal_route' in raw:
        add('Organizer-supplied recommended route: ' + json.dumps(raw['optimal_route'], ensure_ascii=False, sort_keys=True),
            'optimal_route', ['/optimal_route'])
    for i, record in enumerate(raw.get('traffic_conditions', [])):
        add('Organizer-supplied traffic record (not a live or independently authenticated API response): ' +
            json.dumps(record, ensure_ascii=False, sort_keys=True), 'traffic_conditions', [f'/traffic_conditions/{i}'], 'traffic_record')
    if 'surge_pricing_log' in raw:
        add('Surge/notification system record: ' + json.dumps(raw['surge_pricing_log'], ensure_ascii=False, sort_keys=True),
            'surge_pricing_log', ['/surge_pricing_log'], 'event_record')
    if kind == 'route_deviation' and 'optimal_route' in raw:
        ref = raw['optimal_route'].get('estimated_distance_km')
        actual = trip.get('actual_distance_km')
        if ref is not None and actual is not None:
            excess = Decimal(str(actual)) - Decimal(str(ref))
            refs = ['/trip_data/actual_distance_km', '/optimal_route/estimated_distance_km']
            metrics['reported_route_distance'] = {'actual_km': actual, 'recommended_km': ref, 'excess_km': float(excess),
                'source_refs': refs, 'method': 'Decimal subtraction of reported road-route distances',
                'limitation': 'Reported route distances are distinct from sampled GPS polyline lengths; no responsibility inferred.'}
            add(f'Reported distance difference: {actual} - {ref} = {excess} km. This is not the sampled-polyline difference.',
                'derived.reported_route_distance', refs, 'derived_metric')
            if ('estimated_distance_km' in trip and Decimal(str(trip['estimated_distance_km'])) != Decimal(str(ref))) or ('excess_distance_km' in trip and Decimal(str(trip['excess_distance_km'])) != excess):
                issue('ROUTE_DISTANCE_RECORD_CONFLICT', 'Reported trip and recommended-route distances disagree.', ['/trip_data', '/optimal_route'])
        else:
            issue('REPORTED_ROUTE_DISTANCE_MISSING', 'Reported actual and recommended distances are required for the policy km thresholds.', ['/trip_data', '/optimal_route'])
        issue('TRAFFIC_API_PROVENANCE_MISSING', 'Traffic records are supplied by the sample. Historical traffic API provider/response provenance required by section 1.4 is not supplied.', ['/traffic_conditions'] if 'traffic_conditions' in raw else [])
        issue('VERBAL_ROUTE_NOTICE_RECORD_MISSING', 'The supplied chat is available; no trip call recording is supplied to check a verbal route notification or rider acknowledgment. Do not infer that no verbal notice occurred.', ['/chat_logs'] if 'chat_logs' in raw else [])
    quoted_key = 'upfront_quote' if kind == 'fare_dispute' else 'estimated_fare'
    if kind in ('route_deviation', 'fare_dispute') and 'actual_fare' in trip and quoted_key in trip:
        charged = cents(trip['actual_fare'], '/trip_data/actual_fare')
        quoted = cents(trip[quoted_key], f'/trip_data/{quoted_key}')
        refs = ['/trip_data/actual_fare', f'/trip_data/{quoted_key}']
        metrics['fare_difference'] = {'currency': trip.get('currency', 'SGD'),
            'currency_basis': 'trip field' if 'currency' in trip else 'Singapore sample context; currency not explicitly encoded in fare fields',
            'charged_cents': charged, 'quoted_cents': quoted, 'difference_cents': charged - quoted,
            'source_refs': refs, 'limitation': 'Arithmetic difference, not an awarded refund.'}
        add(f'Recorded fare difference is {charged - quoted} cents ({charged} charged minus {quoted} quoted); this is not a refund award.', 'derived.fare_difference', refs, 'derived_metric')
        fare = raw.get('fare_breakdown', {})
        quoted_section = 'upfront_quote' if kind == 'fare_dispute' else 'estimated'
        actual_section = 'actual_fare' if kind == 'fare_dispute' else 'actual'
        for section, expected in ((quoted_section, quoted), (actual_section, charged)):
            if 'total' in fare.get(section, {}) and cents(fare[section]['total'], f'/fare_breakdown/{section}/total') != expected:
                issue('FARE_TOTAL_RECORD_CONFLICT', 'Trip and breakdown totals disagree; do not select one silently.', refs + [f'/fare_breakdown/{section}/total'])
        for key in ('fare_difference', 'excess_fare'):
            if key in trip and cents(trip[key], f'/trip_data/{key}') != charged - quoted:
                issue('FARE_DIFFERENCE_RECORD_CONFLICT', 'Recorded fare difference disagrees with charged minus quoted.', refs + [f'/trip_data/{key}'])
        if kind == 'route_deviation' and 'excess_distance_fare' in fare:
            metrics['reported_excess_distance_fare'] = {'amount_cents': cents(fare['excess_distance_fare'], '/fare_breakdown/excess_distance_fare'),
                'currency': 'SGD', 'source_refs': ['/fare_breakdown/excess_distance_fare'],
                'limitation': 'Organizer-recorded excess distance fare; not an awarded refund or a verified per-km tariff.'}
    elif kind == 'fare_dispute':
        issue('INCOMPLETE_FARE_COMPARISON', 'Charged and upfront quote totals are missing.', ['/trip_data'])
    if kind == 'fare_dispute':
        enrich_surge(raw, metrics, add, issue)


def enrich_surge(raw, metrics, add, issue):
    from .core import timestamp
    fare = raw.get('fare_breakdown', {})
    quote, actual = fare.get('upfront_quote', {}), fare.get('actual_fare', {})
    required = {'surge_multiplier', 'surgeable_subtotal', 'surge_amount', 'total'}
    if required <= quote.keys() and required <= actual.keys():
        refs = ['/fare_breakdown/upfront_quote', '/fare_breakdown/actual_fare']
        qsub, asub = Decimal(str(quote['surgeable_subtotal'])), Decimal(str(actual['surgeable_subtotal']))
        qm, am = Decimal(str(quote['surge_multiplier'])), Decimal(str(actual['surge_multiplier']))
        qs, act = cents(quote['surge_amount'], refs[0]), cents(actual['surge_amount'], refs[1])
        qt, at = cents(quote['total'], refs[0]), cents(actual['total'], refs[1])
        qres = Decimal(qt) / 100 - qsub * qm
        ares = Decimal(at) / 100 - asub * am
        consistent = (qsub == asub and qres == ares and qres >= 0 and
                      qsub * (qm - 1) * 100 == qs and asub * (am - 1) * 100 == act and at - qt == act - qs)
        metrics['surge_comparison'] = {'quote_multiplier': float(qm), 'actual_multiplier': float(am),
            'difference_cents': at - qt, 'surge_amount_difference_cents': act - qs,
            'breakdown_consistent_with_surge_only_change': consistent,
            'source_refs': refs, 'limitation': 'Arithmetic consistency of supplied records, not independent tariff verification or a refund award.'}
        add(f'Supplied fare breakdown difference is {at - qt} cents; surge amount difference is {act - qs} cents; consistent with surge-only change: {consistent}.', 'derived.surge_comparison', refs, 'derived_metric')
        if not consistent:
            issue('SURGE_COMPONENTS_INCONSISTENT', 'Cannot attribute the total difference solely to surge using the supplied breakdown.', refs)
        comparison = fare.get('comparison', {})
        for key, computed in (('total_difference', at - qt), ('surge_amount_difference', act - qs)):
            if key in comparison and cents(comparison[key], '/fare_breakdown/comparison/' + key) != computed:
                issue('SURGE_COMPARISON_RECORD_CONFLICT', 'Provided comparison disagrees with component arithmetic.', ['/fare_breakdown/comparison'] + refs)
    else:
        issue('SURGE_COMPONENTS_MISSING', 'Quote and actual surge components are incomplete.', ['/fare_breakdown'] if 'fare_breakdown' in raw else [])
    log = raw.get('surge_pricing_log', {})
    if 'rider_notified' not in log:
        issue('SURGE_NOTIFICATION_STATUS_MISSING', 'Notification status was not supplied. Missing log is not proof that no notification occurred.', ['/surge_pricing_log'] if 'surge_pricing_log' in raw else [])
    elif log['rider_notified']:
        needed = ('notification_timestamp', 'notification_method', 'notified_multiplier', 'revised_estimated_fare', 'free_cancellation_offered')
        if any(log.get(key) is None for key in needed):
            issue('SURGE_NOTICE_DETAILS_MISSING', 'A notified flag alone does not demonstrate timely in-app notice of the new multiplier, revised fare and penalty-free cancellation option.', ['/surge_pricing_log'])
        if log.get('notification_timestamp') and raw['trip_data'].get('start_time') and timestamp(log['notification_timestamp'], 'notice') > timestamp(raw['trip_data']['start_time'], 'start'):
            issue('SURGE_NOTICE_AFTER_PICKUP', 'Notification is recorded after trip start.', ['/surge_pricing_log/notification_timestamp', '/trip_data/start_time'])
    elif log.get('notification_timestamp') is not None or log.get('notification_method') is not None:
        issue('SURGE_NOTIFICATION_RECORD_CONFLICT', 'Notified=false conflicts with supplied notification metadata.', ['/surge_pricing_log'])
    for key, section in (('quote_time_surge', quote), ('trip_start_surge', actual)):
        if key in log and 'surge_multiplier' in section and Decimal(str(log[key])) != Decimal(str(section['surge_multiplier'])):
            issue('SURGE_MULTIPLIER_RECORD_CONFLICT', 'Surge log and fare breakdown multipliers disagree.', ['/surge_pricing_log', '/fare_breakdown'])
    if log.get('surge_activated_at') and raw['trip_data'].get('start_time') and timestamp(log['surge_activated_at'], 'activation') > timestamp(raw['trip_data']['start_time'], 'start'):
        issue('SURGE_ACTIVATED_AFTER_START', 'Activation timestamp does not support a change before pickup.', ['/surge_pricing_log/surge_activated_at', '/trip_data/start_time'])
