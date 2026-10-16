# RydeResolve Evidence / Data / tools

Evidence 0.3.0 converts case records into traceable facts for the Rider Advocate, Driver Advocate, Judge and UI. It uses deterministic calculations and read-only tools; it does not adjudicate disputes.

This module is maintained in the [team repository](https://github.com/Maple-0102/ryderesolve). It includes official DISP-001/002/003, separately versioned Ryde Policy v2.1, and the synthetic SYN-ROUTE-001 regression case.

Read the [Evidence integration guide](../../docs/EVIDENCE-INTEGRATION.md) for the API, snapshot rules, source manifest and policy gaps. Use the [root README](../../README.md) to run the full team pipeline.

## Standalone setup

Requires Python 3.12+. Run these commands from this module's directory:

```powershell
python -m venv .venv
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe -m pip install -c constraints.txt -e ".[dev]"
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m ryderesolve_evidence serve --port 8765
```

On macOS/Linux, use `python3` and `.venv/bin/python`. Open <http://127.0.0.1:8765> to inspect cases, follow evidence/policy references and download a complete snapshot. Stop the server with Ctrl+C. The local inspector requires no model account or API key.

## Python integration

```python
from ryderesolve_evidence import EvidenceTools

tools = EvidenceTools()
snapshot = tools.prepare_case("DISP-003")
# Pass this pack and audit together; retain snapshot_id for every downstream run.
pack = snapshot["evidence_pack"]
audit = snapshot["audit"]
policy = tools.get_policy(
    "DISP-003", "P-RYDE-2.1-S3.3",
    expected_snapshot_id=snapshot["snapshot_id"],
)
```

Use `prepare_case` for integration. It includes `raw`, `evidence_pack`, `audit`, `source_index` and `policy_documents` in one versioned snapshot. A policy-only change also invalidates old outputs. The package-level `normalize_evidence(raw)` function does not load standalone policy documents automatically.

## CLI examples

```powershell
.venv/Scripts/python.exe -m ryderesolve_evidence list
.venv/Scripts/python.exe -m ryderesolve_evidence prepare DISP-002
.venv/Scripts/python.exe -m ryderesolve_evidence audit DISP-002
.venv/Scripts/python.exe -m ryderesolve_evidence evidence DISP-002 E-002
.venv/Scripts/python.exe -m ryderesolve_evidence policy DISP-003 P-RYDE-2.1-S3.3
.venv/Scripts/python.exe -m ryderesolve_evidence route DISP-001
.venv/Scripts/python.exe -m ryderesolve_evidence export DISP-003 --out work/exports
```

`export` writes pack, audit and index examples. Use `prepare` or the inspector's complete-snapshot download when you also need raw records and policy documents. [Generated examples](examples/generated/README.md) illustrate the contract; [JSON Schemas](ryderesolve_evidence/contracts/) define its fields.

## Source integrity

Original attachments and the import manifest are retained under [sources/official/2026-10-15](sources/official/2026-10-15/). They are excluded from the runtime wheel. Runtime DISP-001 omits explicitly listed answer/editorial fields; DISP-002 and DISP-003 retain their original JSON values. The organizer's source rights and attribution are unchanged. Public repository access for competition review does not grant a new dataset license or independently authenticate these samples. See [publication notes](../../docs/PUBLICATION-NOTES.md).

Preserve official/synthetic labels and case-scoped references. A valid reference proves that a record exists, not that an argument is correct. The local service binds to loopback and rejects external Host/Origin requests; it is a development tool, not an Internet deployment.
