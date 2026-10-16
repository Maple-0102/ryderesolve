"""Execution outcome is separate from the business ruling; legacy JSON is retained."""
from .review_policy import review_plan


def annotate_execution(result):
    errors=result['validation_errors'];reasons=[]
    if errors:
        result['execution_status']='failed';result['business_decision_status']='unavailable'
        for error in errors:
            if error.startswith(('RUN_','CHECKPOINT_','RESUME_')):reason='execution_limit_or_resume_error'
            elif any(marker in error for marker in ('HTTP_','TIMEOUT','CONNECTION','ADC_','CONFIG')):reason='transport_error'
            else:reason='output_invalid'
            if reason not in reasons:reasons.append(reason)
    else:
        result['execution_status']='completed'
        if result['ruling']['decision']!='escalate':result['business_decision_status']='proposed'
        else:
            result['business_decision_status']='awaiting_human'
            snapshot=result.get('snapshot')
            if snapshot:
                applied=result['calculations'].get('policy_application') or {}
                if any(g['code'] in ('ROUTE_DISTANCE_REQUIRES_HUMAN_REVIEW','DISPUTE_VALUE_REQUIRES_HUMAN_REVIEW','SAFETY_INDICATOR_REQUIRES_HUMAN_REVIEW') for g in applied.get('mandatory_human_review',[])):
                    reasons.append('policy_gate')
                if any(i['code'] in ('POLICY_SOURCE_CONFLICT','NO_SHOW_THRESHOLD_CLOCK_UNSPECIFIED') for i in snapshot['audit']['issues']):
                    reasons.append('policy_clarification')
                if any(i['category']!='informational' and i['code'] not in ('ROUTE_DISTANCE_REQUIRES_HUMAN_REVIEW','DISPUTE_VALUE_REQUIRES_HUMAN_REVIEW','SAFETY_INDICATOR_REQUIRES_HUMAN_REVIEW','POLICY_SOURCE_CONFLICT','NO_SHOW_THRESHOLD_CLOCK_UNSPECIFIED') for i in review_plan(snapshot)['items']):
                    reasons.append('missing_evidence')
            if result.get('reviewer_blocked'):reasons.append('inference_review')
            if not reasons:reasons.append('human_review_requested')
    result['review_reason_types']=reasons
    result['first_pass_valid']=None if result.get('providers_skipped') else not result['judge_raw_validation_errors'] and not result['validation_errors'] and not any(e['status'] in ('failed','interrupted') for e in result['communication_log'])
