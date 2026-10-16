# Legacy contract fixtures

The JSON files in this directory are preserved pre-v0.3 fixtures for Advocate schema tests. They predate the standalone Ryde Policy v2.1 and must not be used as the current official case source or mixed with new snapshots.

For current DISP-001/002/003, use the installed Evidence module's `EvidenceTools().prepare_case(case_id)`, then pass `snapshot['evidence_pack']` and `snapshot['audit']` together. `examples/integrate_evidence.py` already follows that path; it invokes a real provider and uses the caller's quota. The root offline integration tests cover all three cases without a model call.
