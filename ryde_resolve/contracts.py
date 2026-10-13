"""Shared schemas come from EvidenceTools; these are provisional Judge business checks."""
from decimal import Decimal
from ryde_resolve.evidence import validate_snapshot_output
from ryde_resolve.rule_engine import charged_amount
from .reasoning_checks import check_finding_support, check_case_analysis
from .review_policy import unresolved_issues

ALLOWED_DECISIONS = {'uphold_charge', 'refund_full', 'refund_partial', 'escalate'}


def check_advocate(snapshot, output, side):
    report = validate_snapshot_output(snapshot, advocate=output)
    errors = [f"{x['code']}: {x['message']}" for x in report['errors']]
    if isinstance(output, dict) and output.get('side') != side:
        errors.append('ROLE_MISMATCH: expected ' + side)
    return errors, report['warnings']


def check_judge(snapshot, output, arguments=None):
    report = validate_snapshot_output(snapshot, judge=output)
    errors = [f"{x['code']}: {x['message']}" for x in report['errors']]
    if errors:
        return errors, report['warnings']
    decision = output['decision']
    if decision not in ALLOWED_DECISIONS:
        errors.append('UNKNOWN_DECISION')
    for key in ('refund_amount', 'escalate_to_human', 'uncertainties'):
        if key not in output:
            errors.append('MISSING_JUDGE_FIELD: ' + key)
    if output.get('currency') != 'SGD' or output.get('amount_unit') != 'major':
        errors.append('AMOUNT_UNIT: expected SGD major units (dollars)')
    notes = output.get('notes', [])
    if not isinstance(notes, list) or any(not isinstance(n, str) or not n.strip() for n in notes):
        errors.append('INVALID_NON_MATERIAL_NOTES')
    if decision == 'escalate':
        if output.get('escalate_to_human') is not True or output.get('refund_amount') is not None:
            errors.append('ESCALATION_CONFLICT: refund must be null and human review true')
        if not output.get('uncertainties'):
            errors.append('ESCALATION_REASON_MISSING')
    else:
        if output.get('uncertainties'):
            errors.append('FINAL_WITH_UNRESOLVED_UNCERTAINTIES')
        if output.get('escalate_to_human') is not False:
            errors.append('DECISION_REVIEW_CONFLICT')
        if not output.get('findings') or any(not f['evidence_refs'] or not f['policy_refs']
                                            for f in output['findings']):
            errors.append('UNSUPPORTED_RULING: cite evidence and policy')
        amount = output.get('refund_amount')
        if type(amount) not in (int, float):
            errors.append('INVALID_REFUND_AMOUNT')
        else:
            money = Decimal(str(amount))
            charged = charged_amount(snapshot)
            if money.as_tuple().exponent < -2:
                errors.append('INVALID_REFUND_PRECISION')
            if charged is None or money > charged:
                errors.append('REFUND_EXCEEDS_CHARGE_OR_CHARGE_UNKNOWN')
            if decision == 'uphold_charge' and money != 0:
                errors.append('UPHOLD_REFUND_CONFLICT')
            if decision == 'refund_full' and money != charged:
                errors.append('FULL_REFUND_MISMATCH')
            if decision == 'refund_partial' and not (charged is not None and 0 < money < charged):
                errors.append('PARTIAL_REFUND_MISMATCH')

    support_errors, support_warnings = check_finding_support(snapshot, output)
    analysis_errors, analysis_warnings = check_case_analysis(snapshot, output, arguments)
    errors.extend(support_errors + analysis_errors)
    if decision != 'escalate':
        if analysis_errors or unresolved_issues(snapshot, output.get('case_analysis')):
            errors.append('UNRESOLVED_DATA_OR_POLICY_REVIEW')
    return errors, report['warnings'] + support_warnings + analysis_warnings
