"""Judge-only source-use hints; no verdict, text entailment or validation bypass."""
from .reasoning_checks import evidence_categories


def claim_support_guide(snapshot, arguments):
    index=snapshot['source_index']['evidence']
    groups={'communication_records':[], 'attributed_party_statements':[],
            'candidate_incident_records':[], 'background_only':[]}
    for ref,item in index.items():
        if item['kind']=='communication_record':groups['communication_records'].append(ref)
        if item['kind']=='party_statement':groups['attributed_party_statements'].append(ref)
        categories=evidence_categories(snapshot,[ref])
        if categories-{'history','statement','context'}:groups['candidate_incident_records'].append(ref)
        elif item['kind'] not in ('communication_record','party_statement'):groups['background_only'].append(ref)
    rows=[]
    for rnd in ('opening','response'):
        for side in ('rider','driver'):
            for field,text_key in (('claims','claim'),('counterpoints','claim')):
                for i,row in enumerate(arguments.get(rnd,{}).get(side,{}).get(field,[])):
                    refs=row.get('evidence_refs',[])
                    rows.append({'argument_ref':f'/{rnd}/{side}/{field}/{i}',
                        'original_text':row.get(text_key,''),
                        'cited_communication_records':[r for r in refs if r in groups['communication_records']],
                        'cited_party_statements':[r for r in refs if r in groups['attributed_party_statements']],
                        'cited_candidate_incident_records':[r for r in refs if r in groups['candidate_incident_records']],
                        'other_or_unknown_cited_refs':[r for r in refs if r not in index or r in groups['background_only']]})
    return {'reference_groups':groups,'arguments':rows,
        'boundary':'Source-kind hints only, not case evidence or an assessment of claim truth. Read original raw records and the WHOLE claim. A candidate record can be irrelevant or contradictory. No source gap or policy gate is resolved here.',
        'scope_rules':[
            'communication_act evaluates only literal recorded communication, not the truth of what the speaker alleges. Its required support/opposition list must contain communication_record IDs only under the existing contract.',
            'party_statement IDs preserve attributed reports. A ticket statement and a repeated chat assertion are not independent corroboration of the incident.',
            'For a mixed assertion, do not rate the whole claim supported merely because its opening attribution or one clause is recorded. Explain each unsupported clause. Use incident_fact and insufficient_evidence where the alleged event lacks support; do not label it contradicted solely because a log is absent.',
            'A system record contradicting an alleged incident may support contradicted with that record in opposing_evidence_refs. Never reuse a reference in both opposing and supporting roles.',
            'A literal quote/query can be assessed as communication_act using matching communication IDs only. Do not replace the original claim with an easier paraphrase.',
            'Unsubstantiated party assertions do not alone force human review when all material decision conditions are independently established. Material unknown conditions and mandatory human gates still require escalation.'
        ]}
