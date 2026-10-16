"""Generation constraints; post-generation evidence/business checks remain authoritative."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def judge_output_schema(policy_bound=False, arguments=None):
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
        'A charge-based refund rule does not support a claim that refund requires proving the detour was unjustified.')
    ledger['reason']['description'] = (
        'Cover the original WHOLE claim at argument_ref, using: Original assertion; attribution/communication support; incident support/opposition; policy consequence/remaining gap. '
        'Explicitly name any unproved full-trip inference or mismatch between route justification and extra-charge entitlement. '
        'Do not substitute the policy wording for the claim and call the original supported.')
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
