"""Versioned local routing policy, not organizer policy and not model-editable."""
from copy import deepcopy

REVIEW_POLICY_VERSION = '0.5'
ANALYSABLE = {'ROUTE_JUSTIFICATION_REQUIRES_REVIEW'}


def review_plan(snapshot):
    items = []
    for issue in snapshot['audit']['issues']:
        from .policy_v21 import classify_issue
        override = classify_issue(snapshot, issue)
        category = override or ('informational' if issue['severity'] == 'info' else
                    'judge_analysis' if issue['code'] in ANALYSABLE else 'requires_clarification')
        item={**deepcopy(issue), 'category':category}
        if override:
            item['classification_basis']='Bound policy v2.1 and captured records determine whether this issue is material; original Evidence issue retained.'
        items.append(item)
    return {'version': REVIEW_POLICY_VERSION, 'items': items,
            'note': 'Unknown review codes default to clarification. The model cannot clear these by assertion.'}


def unresolved_issues(snapshot, analysis=None):
    responses = {x['issue_code']: x for x in (analysis or {}).get('review_responses', [])}
    unresolved = []
    for issue in review_plan(snapshot)['items']:
        if issue['category'] == 'informational':
            continue
        if issue['category'] == 'requires_clarification':
            unresolved.append(issue['code'])
        elif responses.get(issue['code'], {}).get('status') != 'resolved':
            unresolved.append(issue['code'])
    return unresolved
