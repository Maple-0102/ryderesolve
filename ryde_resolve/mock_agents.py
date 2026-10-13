"""Transparent offline placeholders. No generated advocacy or automatic verdicts."""
from copy import deepcopy
from ryde_resolve.rule_engine import refs_for_paths


class OfflineAdvocate:
    mode = 'offline_placeholder'

    def __call__(self, snapshot, side, round_name, opponent=None):
        facts = snapshot['evidence_pack']['facts']
        refs = refs_for_paths(snapshot, ['/dispute_ticket/description']) if side == 'rider' else []
        if side == 'driver':
            for i, record in enumerate(snapshot['raw'].get('chat_logs', [])):
                if record.get('sender') == 'driver':
                    refs += refs_for_paths(snapshot, [f'/chat_logs/{i}'])
        selected = [f for f in facts if f['evidence_id'] in refs][:3]
        output = {
            'case_id': snapshot['case_id'], 'side': side,
            'claims': [{'claim': f['fact'], 'evidence_refs': [f['evidence_id']]} for f in selected],
            'counterpoints': [],
            'missing_information': ['Offline placeholder: teammate Advocate model has not been connected.'],
            'round': round_name,
        }
        if round_name == 'response':
            output['missing_information'].append('Opponent opening received; no model-generated rebuttal in offline mode.')
        return output


def review_ruling(snapshot, reasons):
    return {
        'case_id': snapshot['case_id'], 'decision': 'escalate',
        'refund_amount': None, 'currency': 'SGD', 'amount_unit': 'major',
        'findings': [], 'uncertainties': list(dict.fromkeys(reasons)),
        'escalate_to_human': True,
    }


class OfflineJudge:
    mode = 'offline_review'

    def __call__(self, snapshot, arguments, calculations):
        reasons = [f"{issue['code']}: {issue['message']}" for issue in calculations['issues']
                   if issue['severity'] == 'review']
        reasons.append('OFFLINE_MODE: no LLM Judge was called; no automatic ruling is issued.')
        output = review_ruling(snapshot, reasons)
        for metric in calculations['calculations']:
            if 'seconds' in metric:
                text = f"{metric['name']}: {metric['seconds']} seconds; policy clock is unselected."
            else:
                text = metric.get('limitation', 'Calculation does not establish responsibility.')
            output['findings'].append({'finding': text,
                                      'evidence_refs': deepcopy(metric['evidence_refs']), 'policy_refs': [],
                                      'finding_type': 'calculation',
                                      'topic': 'wait_duration' if 'seconds' in metric else 'fare_difference' if 'difference_cents' in metric else 'other'})
        output['case_analysis'] = offline_case_analysis(snapshot, arguments)
        return output


def offline_case_analysis(snapshot, arguments):
    """Expose the questions and actual claim references; do not fake LLM assessments."""
    from .reasoning_checks import argument_paths
    from .review_policy import review_plan
    from .deliberation import condition_specs
    sides = {}
    for side in ('rider', 'driver'):
        paths = sorted(argument_paths(arguments, side))
        evidence_refs = []
        for rnd in ('opening', 'response'):
            out = arguments.get(rnd, {}).get(side, {})
            for claim in out.get('claims', []) + out.get('counterpoints', []):
                evidence_refs.extend(claim['evidence_refs'])
        sides[side] = {'argument_refs': paths, 'assessment': 'unresolved',
                       'reason': 'Offline mode records the supplied arguments; no model has assessed them.',
                       'evidence_refs': list(dict.fromkeys(evidence_refs)), 'policy_refs': []}
    question = ('Which waiting clock governs the no-show charge, and does the evidence meet it?'
                if snapshot['evidence_pack']['dispute_type'] == 'no_show_charge' else
                'Was the route change justified and was the extra charge supported?')
    return {
        'question': question, 'sides': sides,
        'argument_assessments': [
            {'argument_ref': path, 'assessment': 'unresolved',
             'reason': 'Offline scaffold: this individual argument has not been evaluated.',
             'supporting_evidence_refs': [], 'opposing_evidence_refs': [], 'policy_refs': [],
             'missing_information': ['Model-backed assessment required.']}
            for path in sorted(set().union(*(argument_paths(arguments, side) for side in ('rider', 'driver'))))],
        'decision_conditions': [
            {'condition_id': c['condition_id'], 'status': 'unknown', 'reason': c['question'],
             'evidence_refs': [], 'policy_refs': []} for c in condition_specs(snapshot)],
        'disputed_points': [{'issue': question,
                            'reasoning': 'Both sides require assessment against the cited records and policy. Offline mode does not adjudicate.',
                            'evidence_refs': list(dict.fromkeys(r for side in sides.values() for r in side['evidence_refs'])),
                            'policy_refs': []}],
        'review_responses': [{'issue_code': issue['code'], 'status': 'unresolved',
                              'explanation': issue['message'], 'evidence_refs': [], 'policy_refs': []}
                             for issue in review_plan(snapshot)['items'] if issue['category'] != 'informational'],
        'missing_information': ['A model-backed assessment has not been performed.'],
    }
