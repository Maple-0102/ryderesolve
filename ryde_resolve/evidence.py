"""Thin adapter over versioned EvidenceTools and its source-bound policy documents."""
from ryderesolve_evidence import EvidenceTools
from ryderesolve_evidence.core import build_bundle
from ryderesolve_evidence.validation import validate_agent_outputs


class EvidenceGateway:
    def __init__(self, tools=None):
        self.tools = tools or EvidenceTools()

    def prepare(self, case_id):
        snapshot = self.tools.prepare_case(case_id)
        verify_snapshot(snapshot)
        return snapshot


def verify_snapshot(snapshot):
    """Rebuild using the same normalizer; reject mixed raw/pack/index/audit versions."""
    audit = snapshot['audit']
    bundle = build_bundle(snapshot['raw'], {k: audit.get(k) for k in
                         ('data_origin', 'policy_origin', 'source_url')}, snapshot.get('policy_documents'))
    expected = {
        'case_id': bundle.pack['case_id'],
        'snapshot_id': bundle.audit['snapshot_id'],
        'source_sha256': bundle.audit['source_sha256'],
        'normalizer_version': bundle.audit['normalizer_version'],
        'evidence_pack': bundle.pack,
        'audit': bundle.audit,
        'source_index': {'evidence': bundle.evidence_index, 'policy': bundle.policy_index},
    }
    for key, value in expected.items():
        if snapshot.get(key) != value:
            raise ValueError(f'SNAPSHOT_MISMATCH: {key}')
    if snapshot.get('policy_documents', {}) != bundle.policy_documents:
        raise ValueError('SNAPSHOT_MISMATCH: policy_documents')
    return bundle


def validate_snapshot_output(snapshot, *, advocate=None, judge=None):
    # Validate against this run's captured snapshot, not a second disk read.
    return validate_agent_outputs(verify_snapshot(snapshot), advocate=advocate, judge=judge)
