"""Source-bound v2.1 policy checks. Calculations, not model-authored verification."""
from datetime import datetime, timedelta
from decimal import Decimal
import re
from ryderesolve_evidence.core import pointer

DOCUMENT = 'RYDE-POLICY-V2.1'
VERSION = '2.1'


def bound(snapshot):
    return DOCUMENT in snapshot.get('policy_documents', {})


def refs(snapshot, paths):
    return [key for key, item in snapshot['source_index']['evidence'].items()
            if any(a == b or a.startswith(b + '/') or b.startswith(a + '/')
                   for a in paths for b in item['source_refs'])]


def policy_refs(snapshot, sections):
    return [f'P-RYDE-2.1-S{s}' for s in sections if f'P-RYDE-2.1-S{s}' in snapshot['source_index']['policy']]


def _time(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value,str) else None
        return result if result and result.tzinfo else None
    except ValueError:
        return None


def application(snapshot):
    if not bound(snapshot):
        return None
    raw = snapshot['raw']; audit = snapshot['audit']; trip = raw['trip_data']
    kind = snapshot['evidence_pack']['dispute_type']; conditions = []
    def add(cid, status, reason, paths, sections):
        row = {'condition_id': cid, 'status': status, 'reason': reason,
               'evidence_refs': refs(snapshot, paths), 'policy_refs': policy_refs(snapshot, sections)}
        conditions.append(row)
        return row
    gates = [{'code': i['code'], 'reason': i['message'], 'policy_refs': i.get('policy_refs', [])}
             for i in audit['issues'] if i['code'] in {
                 'POLICY_SOURCE_CONFLICT', 'NO_SHOW_THRESHOLD_CLOCK_UNSPECIFIED',
                 'POLICY_APPLICABILITY_UNCONFIRMED', 'EMBEDDED_CLOCK_REQUIRES_RECONCILIATION',
                 'ROUTE_DISTANCE_REQUIRES_HUMAN_REVIEW', 'ROUTE_POLICY_DISTANCE_UNAVAILABLE',
                 'DISPUTE_VALUE_REQUIRES_HUMAN_REVIEW', 'SAFETY_INDICATOR_REQUIRES_HUMAN_REVIEW'}]
    expected = None; amount = None
    metrics = audit['metrics']; source_context = audit.get('policy_context', {})
    tolerance = False
    material_ids = None
    supplemental_actions = []
    traffic_provenance = False
    if kind == 'no_show_charge':
        start, cancel = _time(trip.get('scheduled_time')), _time(trip.get('cancellation_time'))
        elapsed = (cancel-start).total_seconds() if start and cancel else None
        # Exactly five minutes is not silently interpreted as 'after five'.
        status = 'met' if elapsed is not None and elapsed > 300 else 'not_met' if elapsed is not None and elapsed < 300 else 'unknown'
        add('free_wait', status, 'Five free minutes start at scheduled pickup; exact-boundary cancellation requires clarification.',
            ['/trip_data/scheduled_time', '/trip_data/cancellation_time'], ['2.1'])
        records = [(i,r) for i,r in enumerate(raw.get('chat_logs', [])) if r.get('sender') == 'driver'
                   and cancel and _time(r.get('timestamp')) and _time(r['timestamp']) <= cancel]
        messages = [i for i,r in records if r.get('type') == 'message']
        calls = [i for i,r in records if r.get('type') == 'call']
        summaries = [(i,r) for i,r in enumerate(raw.get('app_events',[]))
                     if r.get('event_type')=='contact_attempt_summary' and r.get('coverage_complete') is True
                     and _time(r.get('window_end'))==cancel]
        contact_state = 'met' if messages and calls else 'unknown'
        if summaries:
            declared={(r['message_count'],r['call_count']) for _,r in summaries
                      if type(r.get('message_count')) is int and type(r.get('call_count')) is int}
            if len(declared)==1:
                m,c=next(iter(declared))
                if type(m) is int and type(c) is int and m==len(messages) and c==len(calls):
                    contact_state='met' if m>=1 and c>=1 else 'not_met'
        add('driver_contact', contact_state,
            'At least one in-app message AND one call attempt before cancellation. Missing logs alone do not prove no attempt.',
            [f'/chat_logs/{i}' for i in messages+calls]+[f'/app_events/{i}' for i,_ in summaries], ['2.3'])
        arrival = _time(trip.get('driver_arrival_time'))
        events = [i for i,r in enumerate(raw.get('app_events', [])) if r.get('event_type') == 'driver_arrived'
                  and _time(r.get('timestamp')) and cancel and _time(r['timestamp']) <= cancel]
        timely_events=[i for i in events if start and _time(raw['app_events'][i]['timestamp'])<=start+timedelta(minutes=5)]
        arrival_state = 'met' if arrival and start and arrival <= start+timedelta(minutes=5) and timely_events else 'not_met' if arrival and start and arrival > start+timedelta(minutes=5) and events else 'unknown'
        pickup=trip.get('pickup_location',{})
        if arrival_state=='not_met' and any(g.get('lat')==pickup.get('lat') and g.get('lng')==pickup.get('lng') and _time(g.get('timestamp')) and start and _time(g['timestamp'])<=start+timedelta(minutes=5) for g in raw.get('gps_telemetry',[])):
            arrival_state='unknown'
        add('driver_arrival', arrival_state,
            'Recorded arrival event corroborates timely arrival; driver messages alone are not location evidence.',
            ['/trip_data/driver_arrival_time']+[f'/app_events/{i}' for i in events], ['2.1','2.4'])
        conflicts = any(g['code'] in ('POLICY_SOURCE_CONFLICT','NO_SHOW_THRESHOLD_CLOCK_UNSPECIFIED') for g in gates)
        known = {c['condition_id']:c['status'] for c in conditions}
        charge = 'unknown' if conflicts else 'not_met' if 'not_met' in known.values() else 'met' if all(v=='met' for v in known.values()) else 'unknown'
        add('no_show_charge', charge, 'Fixed fee requires reconciled policy, sufficient scheduled free wait, arrival and both contact attempts.',
            ['/trip_data', '/chat_logs', '/app_events'], ['2.1','2.2','2.3','2.4'])
        if charge=='not_met':
            material_ids=['no_show_charge']+[c['condition_id'] for c in conditions if c['status']=='not_met']
        if arrival_state=='not_met' and contact_state=='not_met' and not conflicts:
            supplemental_actions.append({'action':'goodwill_credit','amount':5,'currency':'SGD','policy_refs':policy_refs(snapshot,['2.4']), 'execution':'recommendation_only'})
        if charge == 'met': expected, amount = 'uphold_charge', 0
        elif charge == 'not_met': expected, amount = 'refund_full', int(Decimal(str(trip.get('cancellation_fee',0)))*100)
    elif kind == 'fare_dispute':
        surge = metrics.get('surge_comparison', {})
        consistent = surge.get('breakdown_consistent_with_surge_only_change') is True
        add('surge_components', 'met' if consistent else 'unknown',
            'Difference must be attributable solely to surge, with unchanged surgeable subtotal and exempt components.',
            surge.get('source_refs', []), ['3.1','3.4','3.5'])
        log = raw.get('surge_pricing_log', {}); start = _time(trip.get('start_time'))
        qm, am = surge.get('quote_multiplier'), surge.get('actual_multiplier')
        changed = am > qm if isinstance(am,(float,int)) and isinstance(qm,(float,int)) else None
        active = _time(log.get('surge_activated_at'))
        timing = 'met' if changed is False or active and start and active <= start else 'unknown'
        add('surge_timing', timing, 'Increased surge must have been activated by pickup; absence of an activation record remains unknown.',
            ['/surge_pricing_log','/trip_data/start_time'], ['3.2','3.3'])
        if changed is False:
            notice = 'met'; reason = 'No increased multiplier requires a new surge notice.'
        elif log.get('rider_notified') is False and log.get('notification_timestamp') is None and log.get('notification_method') is None:
            notice = 'not_met'; reason = 'System log explicitly records no notice; this is not an inference from absent chat.'
        elif log.get('rider_notified') is True:
            timestamp = _time(log.get('notification_timestamp'))
            valid = (timestamp and start and timestamp <= start and
                     log.get('notification_method') in ('in_app','in_app_notification','in-app') and
                     log.get('notified_multiplier') == am and log.get('revised_estimated_fare') == trip.get('actual_fare') and
                     log.get('free_cancellation_offered') is True)
            complete = all(log.get(k) is not None for k in ('notification_timestamp','notification_method','notified_multiplier','revised_estimated_fare','free_cancellation_offered'))
            notice = 'met' if valid else 'not_met' if complete else 'unknown'; reason = 'Notice needs correct multiplier, revised fare, free cancellation and in-app timestamp by pickup.'
        else:
            notice = 'unknown'; reason = 'No explicit notification record; missing data is not a negative notification record.'
        add('surge_notice', notice, reason, ['/surge_pricing_log','/trip_data/start_time'], ['3.2','3.3'])
        charge = ('met' if notice == 'met' else 'not_met') if consistent and timing == 'met' and notice != 'unknown' else 'unknown'
        add('fare_charge', charge, 'Apply the binding quote and surge-only notification rule, not the entire-trip refund.',
            ['/fare_breakdown','/surge_pricing_log','/trip_data'], ['3.1','3.2','3.3','3.4','3.5'])
        if charge == 'met': expected, amount = 'uphold_charge', 0
        elif charge == 'not_met': expected, amount = 'refund_partial', max(surge.get('difference_cents', 0),0)
    elif kind == 'route_deviation':
        route = metrics.get('reported_route_distance', {}); excess = route.get('excess_km')
        tolerance = isinstance(excess,(float,int)) and excess <= 1
        add('distance_tolerance', 'met' if tolerance else 'not_met' if excess is not None else 'unknown',
            'Use reported road-route kilometres; at most one excess kilometre is within the listed tolerance.',
            route.get('source_refs', []), ['1.3','1.4'])
        start, end = _time(trip.get('start_time')), _time(trip.get('end_time'))
        optimal=raw.get('optimal_route',{})
        reference=' '.join([str(optimal.get('route_name',''))]+[str(w.get('location_desc',w.get('road',''))) for w in optimal.get('waypoints',[])]).lower()
        traffic = []; negative_traffic = []
        decision_time=_time(trip.get('route_deviation_time')) or start
        for i,record in enumerate(raw.get('traffic_conditions', [])):
            road_value=record.get('road','')
            road=road_value.split('(')[0].strip().lower().split(' exit')[0] if isinstance(road_value,str) else ''
            on_route=bool(len(road)>=3 and re.search(r'\b'+re.escape(road)+r'\b',reference))
            ts, clear = _time(record.get('timestamp')), _time(record.get('clear_time'))
            overlaps = ts and decision_time and ts <= decision_time and (clear is None or clear >= decision_time)
            if on_route and overlaps and record.get('incident_type') in ('vehicle_fire','heavy_congestion','road_closure','accident'):
                traffic.append(i)
            if on_route and overlaps and record.get('incident_type')=='no_congestion' and record.get('coverage_complete') is True:
                negative_traffic.append(i)
        matching=traffic+negative_traffic
        traffic_provenance=bool(matching) and all(
            isinstance(raw['traffic_conditions'][i].get('api_provider'),str) and raw['traffic_conditions'][i]['api_provider'].strip() and
            isinstance(raw['traffic_conditions'][i].get('api_response_id'),str) and raw['traffic_conditions'][i]['api_response_id'].strip()
            for i in matching)
        traffic_status='unknown' if traffic and negative_traffic else 'met' if traffic else 'not_met' if negative_traffic and traffic_provenance else 'unknown'
        add('route_justification', traffic_status,
            'Supplied historical incident records overlap the recommended route/time; they are not independently authenticated API responses.' if traffic else 'No matching historical traffic verification; API failure/absence is not a proven negative.',
            [f'/traffic_conditions/{i}' for i in matching]+['/optimal_route','/trip_data/start_time','/trip_data/end_time'], ['1.1','1.4'])
        deviation = _time(trip.get('route_deviation_time')); notice_paths=[]; ack_paths=[]
        for i,row in enumerate(raw.get('chat_logs', [])):
            text = row.get('content',row.get('message','')); ts=_time(row.get('timestamp'))
            route_text = re.search(r'\b(route|detour|rerout\w*|alternate|alternative|taking another)\b',text,re.I)
            if row.get('sender')=='driver' and route_text and re.search(r'traffic|congestion|closure|jam|fire',text,re.I):
                limit=deviation or start
                if ts and limit and ts <= limit:notice_paths.append(f'/chat_logs/{i}')
            if row.get('sender')=='rider' and route_text and re.search(r'\b(agree|yes|okay|ok)\b',text,re.I) and not re.search(r"\b(no|not|never|don't|didn't)\b",text,re.I):
                ack_paths.append(f'/chat_logs/{i}')
        negative_notice=[i for i,r in enumerate(raw.get('app_events',[]))
                         if r.get('event_type')=='route_notice_status' and r.get('coverage_complete') is True and r.get('rider_informed') is False]
        notice_status='unknown' if notice_paths and negative_notice else 'met' if notice_paths else 'not_met' if negative_notice else 'unknown'
        add('timely_route_notice', notice_status,
            'Recorded driver notice contains route change/reason and is no later than the observed deviation (or before trip start). Missing call recordings do not prove no verbal notice.',
            notice_paths+[f'/app_events/{i}' for i in negative_notice], ['1.2'])
        add('rider_acknowledgment', 'met' if ack_paths else 'unknown',
            'Explicit contextual rider acknowledgment can establish agreement; generic thanks or missing logs cannot.',
            ack_paths, ['1.4'])
        if tolerance:
            material_ids=['distance_tolerance','extra_charge']
            expected,amount='uphold_charge',0;charge='met'
        elif traffic_status=='met' and notice_status=='met' and ack_paths:
            expected,amount='uphold_charge',0;charge='met'
        elif excess is not None and excess>1 and (traffic_status=='not_met' or traffic_status=='met' and notice_status=='not_met'):
            fee=metrics.get('reported_excess_distance_fare',{}).get('amount_cents')
            # The supplied matrix gives no general percentage for 'partial'. Use a
            # separately recorded distance component, never the entire fare delta.
            if type(fee) is int and fee>0:
                expected,amount='refund_partial',fee;charge='not_met'
                material_ids=['distance_tolerance','route_justification','extra_charge']
                if traffic_status=='met':material_ids.append('timely_route_notice')
            else:charge='unknown'
        else:charge='unknown'
        add('extra_charge', charge, 'Route tolerance/justification and notification must be assessed separately from charging entitlement.',
            route.get('source_refs', [])+notice_paths+ack_paths+[f'/traffic_conditions/{i}' for i in matching]+[f'/app_events/{i}' for i in negative_notice], ['1.3','1.4'])
    else:
        gates.append({'code':'UNSUPPORTED_POLICY_CATEGORY','reason':'Category has no validated automated decision adapter; prepare a human case file.','policy_refs':[]})
    primary={'no_show_charge':'no_show_charge','fare_dispute':'fare_charge','route_deviation':'route_justification'}.get(kind)
    conditions.sort(key=lambda c: c['condition_id']!=primary)
    evidence_only=source_context.get('evidence_only',False)
    reported=[raw['dispute_ticket'].get('description','')]+[r.get('content',r.get('message','')) for r in raw.get('chat_logs',[])]
    if any(re.search(r'不安全|骚扰|襲擊|袭击|威胁|危險駕駛|危险驾驶',text) for text in reported):
        evidence_only=True
        gates.append({'code':'SAFETY_INDICATOR_REQUIRES_HUMAN_REVIEW','reason':'Reported safety indicator: evidence preparation only.','policy_refs':policy_refs(snapshot,['5.1','5.2'])})
    currency=metrics.get('fare_difference',{}).get('currency','SGD')
    if currency!='SGD':gates.append({'code':'UNSUPPORTED_POLICY_CURRENCY','reason':'No currency conversion or alternate tariff is defined.','policy_refs':[]})
    requirement = source_context.get('confidence_requirement', {}).get('minimum')
    precedents = policy_refs(snapshot, [{'route_deviation':'7.1','no_show_charge':'7.3','fare_dispute':'7.2'}.get(kind,'7')])
    repeat_history={'status':'unknown','window_days':30,'reason':'Timestamped no-show cancellations are required; lifetime dispute totals do not establish a rolling-window count.'}
    history_source=raw.get('rider_profile',{}).get('dispute_history',{})
    history=history_source.get('no_show_cancellations') if isinstance(history_source,dict) else None
    reference_time=_time(trip.get('cancellation_time')) or _time(trip.get('start_time'))
    if isinstance(history,list) and reference_time:
        dated={r['trip_id'] for r in history if isinstance(r,dict)
               and isinstance(r.get('trip_id'),str) and r.get('reason')=='rider_no_show'
               and _time(r.get('timestamp')) and reference_time-timedelta(days=30)<=_time(r['timestamp'])<=reference_time}
        repeat_history={'status':'review_flag' if len(dated)>=3 else 'threshold_not_observed', 'window_days':30,'observed_distinct_cancellations':len(dated),
                        'policy_refs':policy_refs(snapshot,['2.5']), 'boundary':'Review flag only, not proof of this dispute or an executed suspension.'}
    if evidence_only:
        for condition in conditions:
            condition.update(status='unknown',reason='Safety case: source basis retained for human review; no automated substantive assessment.')
    return {'document_id': DOCUMENT, 'version': VERSION,
            'document_sha256': snapshot['source_index']['policy'].get('P-RYDE-2.1-S6.2',{}).get('document_sha256'),
            'effective_date':snapshot['policy_documents'][DOCUMENT]['effective_date'],
            'conditions':conditions, 'material_condition_ids': material_ids or [c['condition_id'] for c in conditions],
            'mandatory_human_review':gates,
            'confidence_minimum': requirement, 'precedent_refs':precedents,
            'permitted_decision':None if gates else expected,'refundable_amount_cents':None if gates else amount,
            'route_tolerance_applies':tolerance,'traffic_provenance_recorded':traffic_provenance,
            'supplemental_actions':[] if gates else supplemental_actions,'evidence_only':evidence_only,
            'repeat_no_show_review':repeat_history,
            'confidence_factors':{'credibility_inputs':{side:{'recorded_rating':raw.get(side+'_profile',{}).get('avg_rating'),'fraud_flags':raw.get(side+'_profile',{}).get('fraud_flags')} for side in ('rider','driver')},
                'known_conditions':sum(c['status']!='unknown' for c in conditions),
                'total_conditions':len(conditions),'source_policy_conflicts':[g['code'] for g in gates],
                'precedent_available':bool(precedents),'minimum_required':requirement,
                'calibration':'Policy gives factors and thresholds, not weights or a measured accuracy estimator.'},
            'boundary':'Derived from supplied records and pinned policy, not labels, an awarded refund or independent source authentication.'}


def classify_issue(snapshot, issue):
    app=application(snapshot)
    if not app:return None
    if app['route_tolerance_applies'] and issue['code'] in {
            'ROUTE_JUSTIFICATION_REQUIRES_REVIEW','TRAFFIC_API_PROVENANCE_MISSING','VERBAL_ROUTE_NOTICE_RECORD_MISSING'}:
        return 'informational'
    statuses={c['condition_id']:c['status'] for c in app['conditions']}
    if issue['code']=='SURGE_NOTICE_AFTER_PICKUP' and statuses.get('surge_notice')=='not_met':
        return 'judge_analysis'
    if issue['code']=='SURGE_NOTICE_DETAILS_MISSING' and statuses.get('surge_notice')=='met':
        return 'informational'
    if issue['code']=='TRAFFIC_API_PROVENANCE_MISSING' and app['traffic_provenance_recorded']:
        return 'informational'
    if issue['code']=='VERBAL_ROUTE_NOTICE_RECORD_MISSING' and statuses.get('timely_route_notice')=='not_met':
        return 'informational'
    if issue['code']=='VERBAL_ROUTE_NOTICE_RECORD_MISSING' and statuses.get('route_justification')=='not_met':
        return 'informational'
    if issue['code']=='VERBAL_ROUTE_NOTICE_RECORD_MISSING' and statuses.get('timely_route_notice')=='met' and statuses.get('rider_acknowledgment')=='met':
        return 'informational'
    return None


def communication_refs(snapshot, values):
    return bool(values) and all(snapshot['source_index']['evidence'].get(v,{}).get('kind')=='communication_record' for v in values)


def check_application(snapshot, output):
    app=application(snapshot)
    if not app:return []
    errors=[];final=output['decision']!='escalate'
    if app['evidence_only']:
        if final or output.get('findings') or output.get('refund_amount') is not None:
            errors.append('SAFETY_EVIDENCE_ONLY_NO_RULING')
    if not final:return errors
    if app['mandatory_human_review']:errors.append('POLICY_V21_MANDATORY_HUMAN_REVIEW')
    if app['permitted_decision'] is None:errors.append('POLICY_V21_MATERIAL_CONDITIONS_UNKNOWN')
    elif output['decision'] != app['permitted_decision']:errors.append('POLICY_V21_DECISION_CONFLICT')
    if app['refundable_amount_cents'] is not None:
        amount=output.get('refund_amount')
        if type(amount) in (int,float) and Decimal(str(amount))*100 != app['refundable_amount_cents']:
            errors.append('POLICY_V21_REFUND_COMPONENT_MISMATCH')
    analysis=output.get('case_analysis')
    if not isinstance(analysis,dict):
        return errors+['POLICY_ANALYSIS_REQUIRED']
    cited=analysis.get('precedent_analysis',[])
    if not isinstance(cited,list): cited=[]
    if any(not isinstance(x,dict) or x.get('policy_ref') not in app['precedent_refs'] for x in cited):
        errors.append('POLICY_PRECEDENT_REFERENCE_INVALID')
    if not any(x.get('policy_ref') in app['precedent_refs'] and isinstance(x.get('similarities'),str) and x['similarities'].strip() and isinstance(x.get('differences'),str) and x['differences'].strip() for x in cited if isinstance(x,dict)):
        errors.append('POLICY_PRECEDENT_ANALYSIS_REQUIRED')
    return errors
