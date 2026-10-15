"""Policy-derived development expectations, not organizer answer labels or a holdout."""
from copy import deepcopy
from ryde_resolve.evidence import EvidenceGateway
from ryde_resolve.policy_v21 import refs,policy_refs


def build_policy_exercises():
    output=[]
    for case in ('DISP-001','DISP-002','DISP-003'):
        s=EvidenceGateway().prepare(case)
        if case=='DISP-001':
            statements={'rider':'Reported actual distance is 24.8 km and recommended distance is 20.5 km; review the recorded excess-distance fare.',
                        'driver':'Supplied PIE traffic records report a vehicle fire and congestion during the trip; these are sample records, not a newly authenticated API response.'}
            paths={'rider':['/trip_data','/fare_breakdown'], 'driver':['/traffic_conditions']};sections=['1.2','1.3','1.4','6.2']
            decision,amount='escalate',None;purpose='Reported 4.3 km exceeds the human-review threshold; do not copy the embedded example answer.'
        elif case=='DISP-002':
            statements={'rider':'The recorded cancellation was six minutes after scheduled pickup. Please reconcile the standalone free-wait rule with the embedded threshold.',
                        'driver':'App records include arrival, messages and an unanswered call attempt before cancellation.'}
            paths={'rider':['/trip_data','/cancellation_policy'], 'driver':['/app_events','/chat_logs']};sections=['2.1','2.2','2.3','6.3']
            decision,amount='escalate',None;purpose='Five-minute scheduled free wait is defined; embedded eight-minute clock/source precedence remain unresolved.'
        else:
            statements={'rider':'Recorded quote is SGD 12 and charge is SGD 16.50; the system surge log explicitly records rider_notified=false.',
                        'driver':'The supplied component breakdown records a multiplier increase from 1.0 to 1.5 and the same SGD 9 surgeable subtotal.'}
            paths={'rider':['/trip_data','/surge_pricing_log'], 'driver':['/fare_breakdown']};sections=['3.1','3.2','3.3','3.4','3.5']
            decision,amount='refund_partial',4.5;purpose='Apply the documented unnotified surge-only difference and retain the original fare.'
        args={rnd:{side:{'case_id':case,'side':side,'position':'request_review',
                        'claims':[{'claim':statements[side],'evidence_refs':refs(s,paths[side]),'policy_refs':policy_refs(s,sections)}],
                        'counterpoints':[],'missing_information':[]}
                   for side in ('rider','driver')} for rnd in ('opening','response')}
        output.append({'exercise_id':'V21-'+case,'snapshot':s,'arguments':deepcopy(args),
                       'expected':{'decision':decision,'refund_amount':amount},'purpose':purpose,
                       'order_pair':None,'split':'policy_v21_development','provenance':'Expectations independently derived from supplied policy; current-case recommended outcomes excluded.'})
    return output
