"""Requires teammate's Evidence Tools installed; performs paid live model calls."""
from ryderesolve_evidence import EvidenceTools
from ryderesolve_advocate import AdvocateSystem, GeminiProvider

tools = EvidenceTools()
snapshot = tools.prepare_case("DISP-002")
pair = AdvocateSystem(GeminiProvider.from_env()).run_pair(
    snapshot["evidence_pack"], snapshot["audit"])
for side, output in pair["final"].items():
    report = tools.validate_outputs("DISP-002", advocate=output,
                                   expected_snapshot_id=snapshot["snapshot_id"])
    assert report["structurally_valid"], report["errors"]
    print(side, output, report)
# Pass pair['final'] into your own Judge. Do not reconstruct Evidence IDs.
