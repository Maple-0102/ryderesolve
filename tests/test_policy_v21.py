"""Policy applicability, admissible communications and hard gates on supplied records."""
from copy import deepcopy
from datetime import datetime,timedelta
import json
import tempfile
from pathlib import Path
import unittest
from ryderesolve_evidence.core import build_bundle
from ryde_resolve.evidence import EvidenceGateway,verify_snapshot
from ryde_resolve.policy_v21 import application,check_application
from ryde_resolve.contracts import check_judge
from ryde_resolve.agents import build_judge_messages
from ryde_resolve.mock_agents import OfflineAdvocate,offline_case_analysis
from ryde_resolve.orchestrator import RydeOrchestrator
from ryde_resolve.rule_engine import calculate_rules
from ryde_resolve.statement_gate import downgrade_statement_only_review
from ryde_resolve.ui import render_html


def variant(base,mutate):
    raw=deepcopy(base['raw']);mutate(raw)
    b=build_bundle(raw,{'data_origin':'synthetic','policy_origin':'organizer_policy_document','source_url':None},base['policy_documents'])
    return {'case_id':b.pack['case_id'],'snapshot_id':b.audit['snapshot_id'],'source_sha256':b.audit['source_sha256'],
            'normalizer_version':b.audit['normalizer_version'],'raw':b.raw,'audit':b.audit,'evidence_pack':b.pack,
            'source_index':{'evidence':b.evidence_index,'policy':b.policy_index},'policy_documents':b.policy_documents}


def arguments(s):
    return {rnd:{side:OfflineAdvocate()(s,side,rnd) for side in ('rider','driver')} for rnd in ('opening','response')}


def completed(s,args):
    app=application(s);a=offline_case_analysis(s,args)
    refs=list(dict.fromkeys(r for c in app['conditions'] for r in c['evidence_refs']))
    ps=list(dict.fromkeys(r for c in app['conditions'] for r in c['policy_refs']))
    a['decision_conditions']=deepcopy(app['conditions']);a['missing_information']=[]
    for row in a['argument_assessments']:
        row.update(assessment='partly_supported',supporting_evidence_refs=refs,policy_refs=ps,missing_information=[])
    for side in a['sides'].values():side.update(assessment='partly_supported',evidence_refs=refs,policy_refs=ps)
    for p in a['disputed_points']:p.update(evidence_refs=refs,policy_refs=ps)
    for p in a['review_responses']:p.update(status='resolved',evidence_refs=refs,policy_refs=ps)
    a['precedent_analysis']=[{'policy_ref':app['precedent_refs'][0], 'similarities':'Matching dispute category and applicable policy.', 'differences':'Current figures and facts must be calculated separately.'}]
    amount=app['refundable_amount_cents']
    return {'case_id':s['case_id'],'decision':app['permitted_decision'] or 'uphold_charge','refund_amount':amount/100 if amount is not None else 0,
            'currency':'SGD','amount_unit':'major','confidence':.99,'escalate_to_human':False,'uncertainties':[],
            'findings':[{'finding':'Test-only conditional conclusion from source-bound conditions.', 'finding_type':'inference','topic':'responsibility',
                         'condition_refs':[c['condition_id'] for c in app['conditions']],'evidence_refs':refs,'policy_refs':ps}], 'case_analysis':a}


class PolicyV21Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fare=EvidenceGateway().prepare('DISP-003');cls.route=EvidenceGateway().prepare('DISP-001');cls.no_show=EvidenceGateway().prepare('DISP-002')

    def test_versioned_policy_is_in_judge_input_and_labels_are_not(self):
        s=self.route;verify_snapshot(s)
        payload=json.loads(build_judge_messages(s,arguments(s),calculate_rules(s))[1]['content'])
        self.assertIn('RYDE-POLICY-V2.1',payload['policy_documents'])
        self.assertNotIn('recommended_ruling',json.dumps(payload));self.assertNotIn('expected_refund_amount',json.dumps(payload))
        self.assertEqual(application(s)['version'],'2.1');self.assertTrue(application(s)['document_sha256'])
        self.assertIsNone(application(EvidenceGateway().prepare('SYN-ROUTE-001')))

    def test_wait_basis_is_explicit_but_old_threshold_is_not_silently_overridden(self):
        app=application(self.no_show);cs={c['condition_id']:c for c in app['conditions']}
        self.assertEqual(cs['free_wait']['status'],'met');self.assertEqual(cs['driver_contact']['status'],'met')
        self.assertEqual(cs['no_show_charge']['status'],'unknown')
        self.assertTrue(any(g['code']=='POLICY_SOURCE_CONFLICT' for g in app['mandatory_human_review']))
        self.assertEqual(calculate_rules(self.no_show)['free_wait_clock']['ends_at'],'2026-09-13T08:50:00+08:00')

    def test_route_distance_is_a_hard_gate_not_a_precomputed_refund(self):
        app=application(self.route)
        self.assertTrue(any(g['code']=='ROUTE_DISTANCE_REQUIRES_HUMAN_REVIEW' for g in app['mandatory_human_review']))
        out=completed(self.route,arguments(self.route));out.update(decision='refund_partial',refund_amount=3.44)
        self.assertIn('POLICY_V21_MANDATORY_HUMAN_REVIEW',check_judge(self.route,out,arguments(self.route))[0])
        self.assertEqual(calculate_rules(self.route)['decision_amount_rules']['supported_route_excess_limit'],3.44)

    def test_surge_only_unnotified_refund_is_component_not_entire_trip(self):
        s=self.fare;a=arguments(s);out=completed(s,a)
        self.assertEqual(out['decision'],'refund_partial');self.assertEqual(out['refund_amount'],4.5)
        self.assertFalse(check_judge(s,out,a)[0],check_judge(s,out,a)[0])
        out['refund_amount']=16.5
        self.assertIn('POLICY_V21_REFUND_COMPONENT_MISMATCH',check_judge(s,out,a)[0])

    def test_precedent_is_required_and_unknown_reference_cannot_pass(self):
        s=self.fare;a=arguments(s);out=completed(s,a);out['case_analysis']['precedent_analysis']=[]
        self.assertIn('POLICY_PRECEDENT_ANALYSIS_REQUIRED',check_judge(s,out,a)[0])
        out['case_analysis']['precedent_analysis']=[{'policy_ref':'P-FAKE','similarities':'same','differences':'different'}]
        self.assertIn('POLICY_PRECEDENT_REFERENCE_INVALID',check_judge(s,out,a)[0])

    def test_bad_condition_cannot_be_laundered_by_correct_policy_id(self):
        s=self.fare;a=arguments(s);out=completed(s,a)
        next(c for c in out['case_analysis']['decision_conditions'] if c['condition_id']=='surge_notice')['status']='met'
        self.assertTrue(any('POLICY_CONDITION_RECORD_CONFLICT' in e for e in check_judge(s,out,a)[0]))

    def test_missing_notification_data_is_not_false(self):
        s=variant(self.fare,lambda raw:raw.pop('surge_pricing_log'))
        self.assertEqual(next(c for c in application(s)['conditions'] if c['condition_id']=='surge_notice')['status'],'unknown')
        self.assertIsNone(application(s)['permitted_decision'])

    def test_notification_content_and_deadline_are_checked(self):
        def notice(raw):
            raw['surge_pricing_log'].update(rider_notified=True,notification_method='in_app',notification_timestamp='2026-09-14T21:04:45+08:00',notified_multiplier=1.5,revised_estimated_fare=16.5,free_cancellation_offered=True)
        s=variant(self.fare,notice);self.assertEqual(application(s)['permitted_decision'],'uphold_charge')
        def late(raw):notice(raw);raw['surge_pricing_log']['notification_timestamp']='2026-09-14T21:06:00+08:00'
        s=variant(self.fare,late);self.assertEqual(application(s)['permitted_decision'],'refund_partial')
        def incomplete(raw):notice(raw);raw['surge_pricing_log'].pop('free_cancellation_offered')
        self.assertIsNone(application(variant(self.fare,incomplete))['permitted_decision'])

    def test_dispute_value_thresholds_not_entire_trip_price(self):
        def fare_variant(diff):
            def mutate(raw):
                raw['dispute_ticket']['description']='Synthetic threshold test.'
                total=13+diff; raw['trip_data'].update(upfront_quote=13,actual_fare=total,fare_difference=diff)
                raw['fare_breakdown']['upfront_quote'].update(total=13,surgeable_subtotal=10)
                raw['fare_breakdown']['actual_fare'].update(total=total,surgeable_subtotal=10,surge_amount=diff,surge_multiplier=1+diff/10)
                raw['fare_breakdown']['comparison'].update(total_difference=diff,surge_amount_difference=diff)
                raw['surge_pricing_log']['trip_start_surge']=1+diff/10
                for role in ('rider','driver'):raw[role+'_profile']['fraud_flags']=0
            return variant(self.fare,mutate)
        for diff,minimum,human in [(9,.0,False),(10,.8,False),(50,.8,False),(50.01,.0,True)]:
            app=application(fare_variant(diff))
            self.assertEqual(app['confidence_minimum'] or 0,minimum)
            self.assertEqual(any(g['code']=='DISPUTE_VALUE_REQUIRES_HUMAN_REVIEW' for g in app['mandatory_human_review']),human)

    def test_fraud_flag_raises_threshold_not_fault(self):
        s=variant(self.fare,lambda raw:raw['rider_profile'].update(fraud_flags=1));a=arguments(s);out=completed(s,a)
        self.assertEqual(application(s)['confidence_minimum'],.95)
        out['confidence']=.94;self.assertIn('POLICY_CONFIDENCE_REQUIREMENT_NOT_MET',check_judge(s,out,a)[0])
        out['confidence']=.95;self.assertFalse(check_judge(s,out,a)[0])

    def test_safety_preflight_calls_no_advocate_or_judge(self):
        for text in ['Driver threatened me during the trip.','司机威胁我，让我觉得不安全。']:
            s=variant(self.fare,lambda raw:raw['dispute_ticket'].update(description=text))
            class Gateway:
                def prepare(self,case):return deepcopy(s)
            def forbidden(*args,**kwargs):raise AssertionError('Safety case must not call a ruling provider')
            r=RydeOrchestrator(Gateway(),forbidden,forbidden).run(s['case_id'])
            self.assertTrue(r['providers_skipped']);self.assertFalse(r['validation_errors']);self.assertEqual(r['ruling']['decision'],'escalate')
            self.assertEqual(r['ruling']['findings'],[])

    def test_communication_scope_does_not_require_external_consent_proof(self):
        s=self.fare;a=arguments(s);out=completed(s,a)
        ref=next(k for k,v in s['source_index']['evidence'].items() if v['source_refs']==['/chat_logs/0'])
        row=out['case_analysis']['argument_assessments'][0]
        row.update(assessment='supported',assessment_scope='communication_act',supporting_evidence_refs=[ref],opposing_evidence_refs=[])
        errors=check_judge(s,out,a)[0]
        self.assertFalse(any('ARGUMENT_ASSESSMENT_WITHOUT_RECORD_SUPPORT' in e for e in errors),errors)
        row['assessment_scope']='incident_fact'
        self.assertTrue(any('ARGUMENT_ASSESSMENT_WITHOUT_RECORD_SUPPORT' in e for e in check_judge(s,out,a)[0]))

    def test_one_km_tolerance_keeps_unknown_context_nonmaterial(self):
        def mutate(raw):
            raw['trip_data'].update(actual_distance_km=21.5,excess_distance_km=1.0)
        s=variant(self.route,mutate);a=arguments(s);out=completed(s,a)
        self.assertTrue(application(s)['route_tolerance_applies'])
        self.assertFalse(check_judge(s,out,a)[0],check_judge(s,out,a)[0])

    def test_missing_call_is_void_only_with_complete_contact_records(self):
        def mutate(raw):
            raw['cancellation_policy'].pop('no_show_threshold_min')
            raw['chat_logs']=[r for r in raw['chat_logs'] if r.get('type')!='call']
            raw['rider_profile']['fraud_flags']=0
        s=variant(self.no_show,mutate)
        self.assertIsNone(application(s)['permitted_decision'])
        def complete(raw):
            mutate(raw)
            count=sum(r.get('sender')=='driver' and r.get('type')=='message' for r in raw['chat_logs'])
            raw['app_events'].append({'timestamp':'2026-09-13T08:51:10+08:00','event_type':'contact_attempt_summary',
                'details':'Synthetic complete contact-log fixture.', 'coverage_complete':True,
                'window_end':raw['trip_data']['cancellation_time'],'message_count':count,'call_count':0})
        s=variant(self.no_show,complete)
        self.assertEqual(application(s)['permitted_decision'],'refund_full')
        self.assertFalse(check_judge(s,completed(s,arguments(s)),arguments(s))[0])

    def test_five_minute_boundary_is_not_chosen_by_model(self):
        def at(seconds):
            def mutate(raw):
                raw['cancellation_policy'].pop('no_show_threshold_min')
                raw['trip_data']['cancellation_time']=(datetime.fromisoformat(raw['trip_data']['scheduled_time'])+timedelta(seconds=seconds)).isoformat()
            return variant(self.no_show,mutate)
        self.assertEqual(next(c for c in application(at(299))['conditions'] if c['condition_id']=='free_wait')['status'],'not_met')
        self.assertEqual(next(c for c in application(at(300))['conditions'] if c['condition_id']=='free_wait')['status'],'unknown')
        self.assertEqual(next(c for c in application(at(301))['conditions'] if c['condition_id']=='free_wait')['status'],'met')

    def test_route_distance_boundary_uses_reported_km(self):
        for km,human in [(2,False),(2.01,True)]:
            def mutate(raw):raw['trip_data'].update(actual_distance_km=20.5+km,excess_distance_km=km)
            app=application(variant(self.route,mutate))
            self.assertEqual(any(g['code']=='ROUTE_DISTANCE_REQUIRES_HUMAN_REVIEW' for g in app['mandatory_human_review']),human)

    def test_traffic_after_route_choice_or_on_alternate_road_is_not_justification(self):
        def mutate(raw):
            raw['trip_data']['route_deviation_time']='2026-09-12T13:20:00+08:00'
            raw['traffic_conditions']=[{'road':'PIE','timestamp':'2026-09-12T13:40:00+08:00','clear_time':None,'incident_type':'vehicle_fire'},
                {'road':'ECP','timestamp':'2026-09-12T13:05:00+08:00','clear_time':None,'incident_type':'heavy_congestion'}]
        app=application(variant(self.route,mutate))
        self.assertEqual(next(c for c in app['conditions'] if c['condition_id']=='route_justification')['status'],'unknown')

    def test_safety_rejects_refund_even_if_money_and_confidence_would_qualify(self):
        s=variant(self.fare,lambda raw:raw['dispute_ticket'].update(safety_related=True))
        out=completed(self.fare,arguments(self.fare))
        self.assertIn('SAFETY_EVIDENCE_ONLY_NO_RULING',check_application(s,out))
        self.assertIsNone(application(s)['permitted_decision'])

    def test_malformed_precedent_and_condition_data_fail_without_exceptions(self):
        out=completed(self.fare,arguments(self.fare));out['case_analysis']=['wrong shape']
        self.assertIn('POLICY_ANALYSIS_REQUIRED',check_application(self.fare,out))

    def route_with_records(self,notice=True):
        def mutate(raw):
            raw['dispute_ticket']['description']='Synthetic v2.1 route notification test.'
            raw['trip_data'].update(actual_distance_km=22.0,excess_distance_km=1.5)
            for record in raw['traffic_conditions']:
                record.update(api_provider='synthetic historical fixture',api_response_id='fixture-response')
            if notice:
                raw['chat_logs'] += [
                    {'timestamp':'2026-09-12T13:11:00+08:00','sender':'driver','message':'Traffic jam on PIE; taking an alternate route via ECP.'},
                    {'timestamp':'2026-09-12T13:12:00+08:00','sender':'rider','message':'Yes, I agree to the alternate route.'}]
                raw['chat_logs'].sort(key=lambda r:r['timestamp'])
            else:
                raw['app_events']=[{'timestamp':'2026-09-12T13:53:00+08:00','event_type':'route_notice_status',
                    'details':'Synthetic complete notification channels record.','coverage_complete':True,'rider_informed':False}]
        return variant(self.route,mutate)

    def test_contextual_chat_acknowledgment_allows_agreed_route(self):
        s=self.route_with_records();a=arguments(s);out=completed(s,a)
        self.assertEqual(application(s)['permitted_decision'],'uphold_charge')
        self.assertFalse(check_judge(s,out,a)[0],check_judge(s,out,a)[0])

    def test_justified_route_with_explicit_no_notice_refunds_distance_component(self):
        s=self.route_with_records(notice=False);a=arguments(s);out=completed(s,a)
        self.assertEqual(application(s)['permitted_decision'],'refund_partial');self.assertEqual(out['refund_amount'],3.44)
        self.assertFalse(check_judge(s,out,a)[0],check_judge(s,out,a)[0])
        out['refund_amount']=6.5;self.assertIn('POLICY_V21_REFUND_COMPONENT_MISMATCH',check_judge(s,out,a)[0])

    def test_polite_thanks_is_not_contextual_route_approval(self):
        s=self.route_with_records()
        def mutate(raw):
            for row in raw['chat_logs']:
                if row.get('sender')=='rider' and 'alternate route' in row.get('message',''):row['message']='Great, thanks!'
        s=variant(s,mutate)
        self.assertEqual(next(c for c in application(s)['conditions'] if c['condition_id']=='rider_acknowledgment')['status'],'unknown')
        self.assertIsNone(application(s)['permitted_decision'])


    def test_generation_schema_does_not_allow_a_side_to_omit_second_round(self):
        from jsonschema import Draft202012Validator
        from ryde_resolve.output_schema import judge_output_schema
        s=self.fare;a=arguments(s);out=completed(s,a)
        out['case_analysis']['argument_assessments']=[dict(row,assessment_scope='incident_fact') for row in out['case_analysis']['argument_assessments']]
        schema=judge_output_schema(policy_bound=True,arguments=a)
        self.assertFalse(list(Draft202012Validator(schema).iter_errors(out)))
        for side in ('rider','driver'):out['case_analysis']['sides'][side]['argument_refs']=out['case_analysis']['sides'][side]['argument_refs'][:1]
        self.assertEqual(len(list(Draft202012Validator(schema).iter_errors(out))),2)


    def test_repeat_no_show_counts_distinct_trips_within_thirty_days(self):
        def mutate(raw):
            raw['rider_profile']['dispute_history']['no_show_cancellations']=[
                {'trip_id':'old','timestamp':'2026-07-01T08:00:00+08:00','reason':'rider_no_show'},
                *[{'trip_id':key,'timestamp':'2026-09-10T08:00:00+08:00','reason':'rider_no_show'} for key in ('A','B','C','C')]]
        app=application(variant(self.no_show,mutate))
        self.assertEqual(app['repeat_no_show_review']['observed_distinct_cancellations'],3)
        self.assertEqual(app['repeat_no_show_review']['status'],'review_flag')
        self.assertIsNone(app['permitted_decision'])  # History cannot waive source conflict.

    def test_goodwill_credit_is_separate_from_reversing_the_recorded_fee(self):
        def mutate(raw):
            raw['cancellation_policy'].pop('no_show_threshold_min')
            raw['trip_data'].update(driver_arrival_time='2026-09-13T08:50:30+08:00',driver_wait_start='2026-09-13T08:50:30+08:00')
            raw['chat_logs']=[r for r in raw['chat_logs'] if r.get('sender')=='system']
            raw['app_events']=[r for r in raw['app_events'] if r['event_type'] not in ('driver_called_rider','wait_timer_expired')]
            for r in raw['app_events']:
                if r['event_type'] in ('driver_arrived','wait_timer_started'):r['timestamp']='2026-09-13T08:50:30+08:00'
                if r['event_type']=='rider_notified':r['timestamp']='2026-09-13T08:50:35+08:00'
            raw['app_events'].append({'timestamp':'2026-09-13T08:51:10+08:00','event_type':'contact_attempt_summary','details':'Synthetic complete logs.',
                'coverage_complete':True,'window_end':raw['trip_data']['cancellation_time'],'message_count':0,'call_count':0})
            raw['app_events'].sort(key=lambda r:r['timestamp'])
            for point in raw['gps_telemetry']:
                if point['timestamp']<'2026-09-13T08:50:30+08:00':point['lat']+=.001
        s=variant(self.no_show,mutate);app=application(s)
        self.assertEqual(app['refundable_amount_cents'],500)
        self.assertEqual(app['supplemental_actions'][0]['action'],'goodwill_credit')
        self.assertEqual(app['supplemental_actions'][0]['amount'],5)
        self.assertEqual(app['supplemental_actions'][0]['execution'],'recommendation_only')
