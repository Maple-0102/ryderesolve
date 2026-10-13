"""Offline integration: real Evidence module + stub model. No real Gemini output."""
import json
from ryderesolve_evidence import EvidenceTools
from ryderesolve_advocate import AdvocateSystem, CallableProvider

tools = EvidenceTools()
for case in ("DISP-002", "SYN-ROUTE-001"):
    snapshot = tools.prepare_case(case)
    def stub(system, user):
        pack = json.loads(user)["evidence_pack"]
        side = "rider" if "SIDE = rider." in system else "driver"
        return {"case_id": pack["case_id"], "side": side, "position": "request_review",
                "claims": [{"claim": "OFFLINE STUB: recorded evidence needs assessment.",
                            "evidence_refs": [pack["facts"][0]["evidence_id"]], "policy_refs": []}],
                "counterpoints": [], "missing_information": []}
    pair = AdvocateSystem(CallableProvider(stub)).run_pair(snapshot["evidence_pack"], snapshot["audit"], rebuttal=True)
    for side, output in pair["final"].items():
        report = tools.validate_outputs(case, advocate=output, expected_snapshot_id=snapshot["snapshot_id"])
        assert report["structurally_valid"], report
        print(case, side, "offline integration PASS; warning codes:", [w["code"] for w in report["warnings"]])
