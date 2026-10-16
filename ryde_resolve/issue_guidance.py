"""Symmetric issue-focused prompts; progress is citation coverage, not new truth."""
from copy import deepcopy


def build_issue_ledger(calculations):
    policy=calculations.get('policy_application') or {}
    issues=[{'issue_id':c['condition_id'],'record_status':c['status'],'question':c['reason'],
             'evidence_refs':deepcopy(c['evidence_refs']),'policy_refs':deepcopy(c['policy_refs'])}
            for c in policy.get('conditions',[])]
    return {'issues':issues,'boundary':'Conditions are calculated from captured records, not new evidence or a final ruling. Agreement between agents cannot resolve a source gap.'}


def response_guidance(ledger,side):
    return {'side':side,'issues':deepcopy(ledger['issues']),
        'instructions':'Respond to the opponent opening issue by issue. Identify supported, contradicted and still-unknown points with existing evidence/policy references. Explain any genuinely new reasoning without inventing facts. Do not repeat an opening wholesale or treat mutual agreement as verification. If no supporting record exists, preserve that gap.',
        'boundary':ledger['boundary']}


def citation_progress(arguments):
    out={}
    for side in ('rider','driver'):
        def citations(rnd):
            a=arguments[rnd].get(side,{})
            return {ref for field in ('claims','counterpoints') for row in a.get(field,[]) for ref in row.get('evidence_refs',[])}
        before,after=citations('opening'),citations('response')
        out[side]={'newly_cited_evidence_refs':sorted(after-before),'repeated_evidence_refs':sorted(after & before),
                   'boundary':'Newly cited within this transcript, not newly collected or authenticated evidence. No automatic resolution or extra debate round.'}
    return out
