"""Program-owned review states; no model may clear a captured policy/data gate."""
from copy import deepcopy
from .review_policy import review_plan

VERSION='1'


def program_review_contract(snapshot):
    from .policy_v21 import bound
    if not bound(snapshot):
        return {'version':VERSION,'fixed_review_statuses':[],'required_review_codes':[],'model_analysis_codes':[],'required_decision':None,
                'boundary':'No program-owned v2.1 review fields for this snapshot.'}
    items=[item for item in review_plan(snapshot)['items'] if item['category']!='informational']
    fixed=[{'issue_code':item['code'],'status':'unresolved'}
           for item in items if item['category']=='requires_clarification']
    return {'version':VERSION,'fixed_review_statuses':fixed,
            'required_review_codes':[item['code'] for item in items],
            'model_analysis_codes':[item['code'] for item in items if item['category']=='judge_analysis'],
            'required_decision':'escalate' if fixed else None,
            'boundary':'Statuses are owned by the captured program review plan. Identifying or arranging human referral does not resolve the underlying issue. Preserve these unresolved statuses; explain the issue using actual sources. No policy, missing evidence or human outcome is created.'}


def lock_review_statuses(snapshot,proposal):
    """Only restore protected status fields on an already null-amount referral.

    Never change a decision, amount, explanation, source, finding or condition.
    Caller must retain the raw output and validate the entire assembled candidate.
    """
    from .reasoning_checks import ANALYSIS_VALIDATOR
    candidate=deepcopy(proposal)
    if (not isinstance(candidate,dict) or candidate.get('decision')!='escalate'
        or candidate.get('refund_amount') is not None or candidate.get('escalate_to_human') is not True):
        return candidate,[]
    analysis=candidate.get('case_analysis')
    if not isinstance(analysis,dict) or list(ANALYSIS_VALIDATOR.iter_errors(analysis)):
        return candidate,[]
    contract=program_review_contract(snapshot)
    fixed={row['issue_code']:row['status'] for row in contract['fixed_review_statuses']}
    changes=[]
    for row in analysis['review_responses']:
        required=fixed.get(row['issue_code'])
        if required is None or row['status']==required:continue
        before=deepcopy(row);row['status']=required
        changes.append({'rule':'program_review_status_lock','issue_code':row['issue_code'],
                        'original':before,'adjusted':deepcopy(row),'contract_version':VERSION,
                        'boundary':'Program-owned unresolved status restored. Existing human referral/null amount and all explanations, references, findings and conditions preserved. Human handling has not been completed.'})
    return candidate,changes
