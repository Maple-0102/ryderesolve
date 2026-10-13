"""Typed reasoning and selective gates. Variants exist only inside tests."""
import copy
import unittest
from evaluation.fixtures import with_verification
from ryde_resolve.contracts import check_judge
from ryde_resolve.evidence import EvidenceGateway
from ryde_resolve.mock_agents import OfflineAdvocate, OfflineJudge, offline_case_analysis, review_ruling
from ryde_resolve.orchestrator import RydeOrchestrator
from ryde_resolve.reasoning_checks import check_finding_support
from ryde_resolve.review_policy import review_plan
from ryde_resolve.rule_engine import calculate_rules, refs_for_paths


def args_for(s):
    return {rnd: {side: OfflineAdvocate()(s, side, rnd) for side in ('rider', 'driver')}
            for rnd in ('opening', 'response')}



def analysed_route(s, arguments, *, decision='uphold_charge'):
    a = offline_case_analysis(s, arguments)
    context = refs_for_paths(s, ['/app_events/2'])
    policy = refs_for_paths(s, ['/route_policy/context_rule', '/route_policy/refund_rule'], 'policy')
    for side in a['sides'].values():
        side.update(assessment='partly_supported', reason='Test adapter compares claims with the structured verification record.',
                    evidence_refs=context, policy_refs=policy)
    for row in a['argument_assessments']:
        row.update(assessment='partly_supported', supporting_evidence_refs=context,
                   policy_refs=policy, missing_information=[], reason='Synthetic test assessment against verification record.')
    for condition in a['decision_conditions']:
        condition.update(status='met' if decision == 'uphold_charge' else 'not_met',
                         evidence_refs=context, policy_refs=policy, reason='Explicit synthetic test verification.')
    a['missing_information'] = []
    a['disputed_points'][0].update(reasoning='Test assessment uses structured context, not the measured distance alone.',
                                  evidence_refs=context, policy_refs=policy)
    a['review_responses'][0].update(status='resolved', explanation='The fixture supplies independently attributed structured context and charge verification.',
                                    evidence_refs=context, policy_refs=policy)
    return {'case_id': s['case_id'], 'decision': decision, 'refund_amount': 0 if decision == 'uphold_charge' else 5,
            'currency': 'SGD', 'amount_unit': 'major', 'escalate_to_human': False,
            'uncertainties': [], 'case_analysis': a,
            'findings': [{'finding': 'Test-only inference from the supplied context and fee verification.',
                          'evidence_refs': context, 'policy_refs': policy,
                          'finding_type': 'inference', 'topic': 'responsibility',
                          'condition_refs': ['route_justification', 'extra_charge']}]}


class ReasoningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.no_show = EvidenceGateway().prepare('DISP-002')
        cls.route = EvidenceGateway().prepare('SYN-ROUTE-001')

    def test_review_classification_does_not_rewrite_source(self):
        original = copy.deepcopy(self.no_show)
        self.assertEqual({i['category'] for i in review_plan(self.no_show)['items']}, {'requires_clarification'})
        r = review_plan(self.route)
        self.assertEqual([i['category'] for i in r['items']], ['informational', 'judge_analysis'])
        self.assertEqual(self.no_show, original)

    def test_unknown_review_code_is_not_auto_resolvable(self):
        s = copy.deepcopy(self.no_show)
        s['audit']['issues'] = [{'code': 'NEW_UNKNOWN', 'severity': 'review'}]
        self.assertEqual(review_plan(s)['items'][0]['category'], 'requires_clarification')

    def test_model_cannot_clear_no_show_policy_ambiguity(self):
        a = args_for(self.no_show)
        out = OfflineJudge()(self.no_show, a, calculate_rules(self.no_show))
        out['case_analysis']['review_responses'][0]['status'] = 'resolved'
        errors, _ = check_judge(self.no_show, out, a)
        self.assertTrue(any('CANNOT_SELF_RESOLVE' in e for e in errors))

    def test_statement_can_be_attributed_but_cannot_become_observation(self):
        out = review_ruling(self.no_show, ['review'])
        out['findings'] = [{'finding': 'Rider says the driver was absent.', 'evidence_refs': ['E-002'], 'policy_refs': [],
                            'finding_type': 'statement', 'topic': 'presence'}]
        self.assertFalse(check_finding_support(self.no_show, out)[0])
        out['findings'][0].update(finding='Driver absence is established.', finding_type='observation')
        self.assertTrue(check_finding_support(self.no_show, out)[0])

    def test_driver_message_is_not_independent_route_proof(self):
        out = review_ruling(self.route, ['review'])
        out['findings'] = [{'finding': 'Traffic justified the detour.', 'evidence_refs': ['E-014'], 'policy_refs': ['P-001'],
                            'finding_type': 'inference', 'topic': 'route_justification'}]
        self.assertTrue(any('ROUTE_CONTEXT_NOT_VERIFIED' in e for e in check_finding_support(self.route, out)[0]))

    def test_history_and_distance_cannot_establish_fault_alone(self):
        for ref in ('E-018', 'E-023', 'E-021'):
            out = review_ruling(self.route, ['review'])
            out['findings'] = [{'finding': 'Driver at fault.', 'evidence_refs': [ref], 'policy_refs': ['P-005'],
                                'finding_type': 'inference', 'topic': 'responsibility'}]
            self.assertTrue(check_finding_support(self.route, out)[0], ref)

    def test_call_metadata_and_fare_arithmetic_not_false_positives(self):
        out = review_ruling(self.no_show, ['review'])
        out['findings'] = [{'finding': 'An unanswered call is recorded.', 'evidence_refs': ['E-019'], 'policy_refs': [],
                            'finding_type': 'observation', 'topic': 'contact_attempt'}]
        self.assertFalse(check_finding_support(self.no_show, out)[0])
        metrics = calculate_rules(self.route)['calculations']
        fare = next(x for x in metrics if x['name'] == 'fare_difference')
        self.assertEqual(fare['evidence_refs'], ['E-021'])
        out = OfflineJudge()(self.route, args_for(self.route), calculate_rules(self.route))
        self.assertFalse(check_finding_support(self.route, out)[0])

    def test_analysis_requires_both_sides_and_actual_claims(self):
        arguments = args_for(self.route)
        out = OfflineJudge()(self.route, arguments, calculate_rules(self.route))
        self.assertFalse(check_judge(self.route, out, arguments)[0])
        del out['case_analysis']['sides']['rider']
        self.assertTrue(check_judge(self.route, out, arguments)[0])
        out = OfflineJudge()(self.route, arguments, calculate_rules(self.route))
        out['case_analysis']['sides']['driver']['argument_refs'] = []
        self.assertIn('UNADDRESSED_ARGUMENT: driver', check_judge(self.route, out, arguments)[0])

    def test_analysis_bad_references_and_missing_reviews_rejected(self):
        args = args_for(self.route)
        for mutation in ('bad_evidence', 'bad_policy', 'bad_argument', 'missing_review', 'duplicate_review'):
            out = OfflineJudge()(self.route, args, calculate_rules(self.route)); a = out['case_analysis']
            if mutation == 'bad_evidence': a['disputed_points'][0]['evidence_refs'] = ['E-999']
            if mutation == 'bad_policy': a['disputed_points'][0]['policy_refs'] = ['P-999']
            if mutation == 'bad_argument': a['sides']['rider']['argument_refs'] = ['/response/driver/claims/0']
            if mutation == 'missing_review': a['review_responses'] = []
            if mutation == 'duplicate_review': a['review_responses'] *= 2
            self.assertTrue(check_judge(self.route, out, args)[0], mutation)

    def test_resolved_label_and_generic_trip_event_do_not_bypass_gate(self):
        s = self.route; args = args_for(s)
        out = analysed_route(s, args)
        out['case_analysis']['review_responses'][0]['evidence_refs'] = ['E-016']
        out['findings'][0]['evidence_refs'] = ['E-016']
        errors, _ = check_judge(s, out, args)
        self.assertIn('ROUTE_RESOLUTION_CONTEXT_MISSING', errors)

    def test_context_verified_test_variant_can_reach_final_decision(self):
        # Test data stays in memory; does not alter the team's original case files.
        s = with_verification(self.route)
        class Gateway:
            def prepare(self, case_id): return copy.deepcopy(s)
        r = RydeOrchestrator(evidence_gateway=Gateway(), judge_runner=lambda snap, args, calc: analysed_route(snap,args)).run(s['case_id'])
        self.assertFalse(r['validation_errors'], r['validation_errors'])
        self.assertEqual(r['ruling']['decision'], 'uphold_charge')
        self.assertFalse(r['ruling']['escalate_to_human'])

    def test_verified_unsupported_charge_can_refund_supported_excess(self):
        s = with_verification(self.route, justified=False, charged=False); args = args_for(s)
        out = analysed_route(s,args,decision='refund_partial')
        self.assertFalse(check_judge(s,out,args)[0])
        out['refund_amount'] = 7
        self.assertIn('REFUND_EXCEEDS_SUPPORTED_ROUTE_EXCESS',check_judge(s,out,args)[0])

    def test_context_decision_conflict_cannot_be_resolved(self):
        s = with_verification(self.route, justified=False, charged=False); args = args_for(s)
        self.assertIn('ROUTE_RESOLUTION_DECISION_CONFLICT',check_judge(s,analysed_route(s,args),args)[0])

    def test_uncited_conflicting_context_cannot_be_cherry_picked(self):
        s = with_verification(self.route, contradiction=True); args = args_for(s)
        self.assertIn('CONFLICTING_ROUTE_VERIFICATION',check_judge(s,analysed_route(s,args),args)[0])

    def test_history_changes_do_not_remove_no_show_blockers(self):
        s = copy.deepcopy(self.no_show); s['raw']['rider_profile']['avg_rating'] = 5.0
        self.assertEqual(review_plan(s), review_plan(self.no_show))
        self.assertIsNone(calculate_rules(s)['selected_clock'])

    def test_malformed_analysis_fails_cleanly(self):
        for invalid in ([], 'text', {'sides': []}, None):
            out = review_ruling(self.route, ['review']);out['case_analysis'] = invalid
            errors, _ = check_judge(self.route,out,args_for(self.route))
            if invalid is not None:self.assertTrue(errors)

    def test_accepted_side_needs_more_than_party_statement(self):
        args = args_for(self.route)
        out = OfflineJudge()(self.route,args,calculate_rules(self.route))
        out['case_analysis']['sides']['rider']['assessment'] = 'accepted'
        self.assertIn('SIDE_SUPPORTED_BY_STATEMENT_OR_HISTORY_ONLY: rider',check_judge(self.route,out,args)[0])

    def test_malformed_finding_classifications_fail_without_crashing(self):
        for key in ('finding_type', 'topic'):
            for value in ([], {}, 1, True):
                with self.subTest(key=key, value=value):
                    args = args_for(self.route)
                    out = OfflineJudge()(self.route, args, calculate_rules(self.route))
                    out['findings'][0][key] = value
                    errors, _ = check_judge(self.route, out, args)
                    self.assertTrue(any('INVALID_FINDING_CLASSIFICATION' in e for e in errors))

    def test_final_ruling_requires_analysis_and_responsibility_inference(self):
        s = with_verification(self.route); args = args_for(s)
        out = analysed_route(s, args)
        del out['case_analysis']
        self.assertIn('CASE_ANALYSIS_REQUIRED', check_judge(s, out, args)[0])
        out = analysed_route(s, args)
        out['findings'][0].update(finding_type='statement', topic='other')
        self.assertIn('NO_DECISION_INFERENCE', check_judge(s, out, args)[0])

    def test_parent_source_matching_respects_pointer_boundaries(self):
        self.assertEqual(refs_for_paths(self.route, ['/fare_breakdown/charged_total_cents']), ['E-021'])
        self.assertEqual(refs_for_paths(self.route, ['/fare_breakdownx/charged_total_cents']), [])
