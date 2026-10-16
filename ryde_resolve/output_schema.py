"""Generation constraints; post-generation evidence/business checks remain authoritative."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def judge_output_schema(policy_bound=False, arguments=None, snapshot=None):
    """Complete Judge shape without any case-specific expected decision or scoring labels."""
    string = {'type': 'string'}
    strings = {'type': 'array', 'items': string}
    finding_properties = {
        'finding': string, 'evidence_refs': strings, 'policy_refs': strings,
        'finding_type': {'type': 'string', 'enum': ['statement', 'observation', 'calculation', 'inference', 'context']},
        'topic': {'type': 'string', 'enum': ['presence', 'contact_attempt', 'wait_duration', 'route_justification', 'fare_difference', 'responsibility', 'other']},
        'condition_refs': strings,
    }
    analysis = json.loads((ROOT / 'schemas/judge-analysis.schema.json').read_text())
    ledger = analysis['properties']['argument_assessments']['items']['properties']
    if policy_bound:
        analysis['required'].append('precedent_analysis')
        analysis['properties']['argument_assessments']['items']['required'].append('assessment_scope')
        ledger['assessment_scope']['description'] = 'communication_act assesses ONLY literal recorded communication, using communication_record IDs for its required evidence list; party_statement/ticket attribution alone cannot prove the incident. Read claim_support_guide. Mixed factual clauses require incident_fact evaluation; never grade an easier paraphrase.'
    if arguments is not None:
        from .reasoning_checks import argument_paths
        all_paths=[]
        count=sum(len(argument_paths(arguments,side)) for side in ('rider','driver'))
        for side in ('rider','driver'):
            paths=sorted(argument_paths(arguments,side));all_paths.extend(paths)
            listing=analysis['properties']['sides']['properties'][side]['properties']['argument_refs']
            listing['description']='List EVERY actual path in BOTH rounds, including repeated wording. Required paths: '+', '.join(paths)
            if count<=8:
                listing.update(minItems=len(paths),maxItems=len(paths))
        rows=analysis['properties']['argument_assessments']
        if count<=8:
            rows.update(minItems=len(all_paths),maxItems=len(all_paths))
        rows['description']='Exactly one assessment per actual argument path; complete coverage is checked locally. Total rows: '+str(len(all_paths))
    ledger['assessment']['description'] = (
        'Rate the ORIGINAL complete claim, not a corrected paraphrase. supported requires every substantive clause. '
        'A charge-based refund rule does not support a claim that refund requires proving the detour was unjustified. '
        'Choose this rating AFTER selecting the cited records and describing the missing clauses. '
        'For incident_fact, ticket/chat attribution alone cannot earn supported OR partly_supported. '
        'If no independently relevant incident record appears in supporting_evidence_refs, use insufficient_evidence '
        'unless actual opposing evidence justifies contradicted. A supported attribution clause alone is not partial incident support.')
    ledger['supporting_evidence_refs']['description'] = (
        'Select only records that support the ORIGINAL assertion under assessment_scope. '
        'For incident_fact, supported AND partly_supported require an independently relevant incident record '
        'in THIS list; a complaint/ticket or repeated chat alone is insufficient. '
        'A factual number mentioned only in reason does not count as a cited record. '
        'Never add an unrelated record to satisfy this requirement.')
    ledger['missing_information']['description'] = (
        'List the substantive clauses not established by the selected records. '
        'An absent recording does not prove absence of verbal notice. '
        'A mixed claim can have known attribution but insufficient incident evidence.')
    ledger['reason']['description'] = (
        'Cover the original WHOLE claim at argument_ref, using: Original assertion; attribution/communication support; incident support/opposition; policy consequence/remaining gap. '
        'Explicitly name any unproved full-trip inference or mismatch between route justification and extra-charge entitlement. '
        'Do not substitute the policy wording for the claim and call the original supported.')
    if policy_bound:
        # Gemini emits object fields in propertyOrdering: inspect sources and gaps
        # before committing to a rating. The public schema/validator is unchanged.
        order=('argument_ref','assessment_scope','supporting_evidence_refs','opposing_evidence_refs',
               'policy_refs','missing_information','reason','assessment')
        analysis['properties']['argument_assessments']['items']['properties'] = {
            key:ledger[key] for key in order}
    properties = {
        'case_id': string,
        'decision': {'type': 'string', 'enum': ['uphold_charge', 'refund_full', 'refund_partial', 'escalate']},
        'refund_amount': {'type': ['number', 'null'], 'minimum': 0},
        'currency': {'type': 'string', 'enum': ['SGD']},
        'amount_unit': {'type': 'string', 'enum': ['major']},
        'findings': {'type': 'array', 'items': {'type': 'object', 'properties': finding_properties,
                                             'required': list(finding_properties), 'additionalProperties': False}},
        'uncertainties': strings,
        'escalate_to_human': {'type': 'boolean'},
        'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
        'case_analysis': analysis,
    }
    if snapshot is not None:
        from .review_contract import program_review_contract
        contract=program_review_contract(snapshot)
        fixed=contract['fixed_review_statuses']
        required_codes=contract['required_review_codes']
        if required_codes:
            reviews=analysis['properties']['review_responses']
            reviews.update(minItems=len(required_codes),maxItems=len(required_codes),
                description='Exactly one response for EVERY required issue code, including both program-protected and model-analysis issues: '+', '.join(required_codes)+'. Fixed status rows do not replace responses to model-analysis issues.')
            reviews['items']['properties']['issue_code']['enum']=list(required_codes)
        if fixed:
            status=analysis['properties']['review_responses']['items']['properties']['status']
            status['description']='Program-owned unresolved status for these issue codes: '+', '.join(row['issue_code'] for row in fixed)+'. Referring to a human is not resolving the issue.'
            from .review_policy import review_plan
            if not any(item['category']=='judge_analysis' for item in review_plan(snapshot)['items']):
                status['enum']=['unresolved']
        if contract['required_decision']=='escalate':
            properties['decision']['enum']=['escalate']
            properties['refund_amount']['description']='Must be null: the program review plan requires human referral.'
            properties['escalate_to_human']['description']='Must be true: the program review plan requires human referral.'
    required = list(properties)
    properties['notes'] = strings  # Optional non-material notes, allowed by the local contract.
    return {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}


def vertex_response_schema(schema):
    """Compile JSON Schema to Vertex's documented responseSchema subset.

    Unsupported constraints (e.g. pattern and uniqueItems) remain in local validators.
    They are not silently treated as evidence of validity by this compiler.
    """
    out = {}
    kind = schema.get('type')
    if isinstance(kind, list):
        non_null = [t for t in kind if t != 'null']
        if len(non_null) != 1:
            raise ValueError('Unsupported generation schema union')
        kind = non_null[0]
        out['nullable'] = 'null' in schema['type']
    if kind is None and 'enum' in schema and all(isinstance(v, str) for v in schema['enum']):
        kind = 'string'
    if kind is not None:
        out['type'] = kind.upper()
    for key in ('enum', 'minimum', 'maximum', 'minItems', 'maxItems', 'description'):
        if key in schema:
            out[key] = schema[key]
    if 'properties' in schema:
        out['properties'] = {key: vertex_response_schema(value) for key, value in schema['properties'].items()}
        out['propertyOrdering'] = list(out['properties'])
    if 'required' in schema:
        out['required'] = list(schema['required'])
    if 'items' in schema:
        out['items'] = vertex_response_schema(schema['items'])
    return out
