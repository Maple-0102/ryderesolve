# Evidence integration guide

Evidence 0.3.0 supports the team's existing Advocate/Judge pipeline with three official cases and separately versioned Ryde Policy v2.1. This guide covers the data contract, source handling and remaining policy gaps. Installation and full-pipeline commands are in the [root README](../README.md); standalone commands are in the [Evidence README](../vendor/ryderesolve-evidence-tools/README.md).

## Cases and source boundaries

| Case | Runtime source | Audited quantities |
| --- | --- | --- |
| DISP-001 / `route_deviation` | Official records with explicitly listed answer/editorial fields excluded | Reported road-distance difference: 24.8 - 20.5 = 4.3 km; total fare difference: SGD 6.50; recorded excess-distance fare: SGD 3.44. These are distinct quantities. |
| DISP-002 / `no_show_charge` | Original JSON unchanged; standalone policy added separately | Order timer: 480 seconds; App timer: 470 seconds; scheduled pickup to cancellation: 360 seconds. |
| DISP-003 / `fare_dispute` | Original JSON unchanged | Charged: 1,650 cents; quoted: 1,200 cents; difference: 450 cents. The supplied breakdown is arithmetically consistent with a surge-only change. |
| SYN-ROUTE-001 | Team-authored synthetic records and rules | Retained for regression testing; no official policy document is attached. |

The [source manifest](../vendor/ryderesolve-evidence-tools/sources/official/2026-10-15/manifest.json) records original filenames, attachment byte hashes, JSON semantic hashes and every excluded pointer. Original attachments are retained byte-for-byte outside the runtime wheel. They are organizer samples, not independently authenticated operational records.

DISP-001 contains recommended outcomes and editorial analysis inside its JSON. The import projection excludes `case_metadata`, `recommended_ruling`, `evidence_summary`, `chat_log_analysis`, `traffic_analysis`, fare notes and one traffic description containing adjudicative commentary. Retained values and array indices are unchanged. Do not feed original archives, evaluation labels or the entire repository to an Agent as case evidence. Policy section 7 precedents are policy content, not answers to the current cases.

The importer is reproducible and rejects changes to already archived attachments. From the repository root:

```bash
.venv/bin/python vendor/ryderesolve-evidence-tools/scripts/import_official.py --source-dir /path/to/original-attachments
```

Use the filenames recorded in the manifest. New organizer revisions require explicit source/version support rather than overwriting an archived version. The current normalizer only accepts the supported v2.1 document with its pinned hash. Preserve the source owners' rights and the repository's private visibility.

## Policy interpretation

### DISP-002: free wait is defined; the eight-minute rule remains unresolved

Policy v2.1 section 2.1 starts the **five-minute free wait at scheduled pickup**. Scheduled pickup is 08:45, the free period ends at 08:50, and cancellation is at 08:51. Arrival at 08:43 does not move the free-wait start under this clause.

The embedded `cancellation_policy.no_show_threshold_min=8` remains in the source. The supplied materials do not define its start event, its relationship to the standalone five-minute cancellation rule, or which source overrides the other. Preserve `NO_SHOW_THRESHOLD_CLOCK_UNSPECIFIED` and `POLICY_SOURCE_CONFLICT` until authoritative clarification is supplied. Do not add five and eight to make thirteen, choose a favorable clock, or treat a fee-applied event as proof of entitlement.

The 480/470/360-second calculations remain available. Order/App start differences are informational once section 2.1 is supplied; without that document, `POLICY_CLOCK_BASIS_UNSPECIFIED` remains. Section 2.3 requires at least one in-app message **and** one in-app call before cancellation. An unanswered call is an attempt. Section 6.3 raises the confidence threshold to 95% when a party has a fraud flag; history does not establish present liability.

### DISP-001: reported distance requires human adjudication

The policy uses reported road-route distance, not the length of a sparse GPS polyline. The reported excess is **4.3 km**, above section 6.2's **2 km** threshold, so the case requires human adjudication even if a refund argument is otherwise supportable.

Sections 1.2-1.4 distinguish traffic justification, timely notice and rider acknowledgment. Supplied traffic records are not a new historical-traffic API verification; provider/response provenance is absent. Missing call recordings do not prove that verbal notice never occurred. Keep these gaps explicit. The integrated Judge now uses source-bound v2.1 conditions for these records; the older synthetic checks remain only for unbound synthetic inputs. No verified events are fabricated to bypass either path.

### DISP-003: surge difference is separate from the whole trip fare

The adapter supports `message` chat fields, surge/notification logs and nested fare components. Monetary calculations use Decimal and integer cents. `rider_notified=false` is a recorded negative; a missing log is unknown. The audit checks conflicting totals, components, multipliers and notification timing, and flags missing notice details.

Policy section 3 excludes the booking fee from surge. The adapter checks supplied subtotals and totals without inventing missing tariff items. SGD is inferred from the Singapore sample context where fare fields omit an explicit currency; the audit records that basis.

Under the team's convention, `refund_full` means refunding the entire charge. Refunding the SGD 4.50 difference while retaining the SGD 12.00 quote is `refund_partial`, even though the policy calls it a full refund of the surge differential. Calculating this difference does not award a refund.

Monetary, category and fraud-confidence requirements apply together. Safety indicators require human review and evidence preparation only. Keyword screening is a limited safeguard, not a complete safety classifier.

## Contract and snapshot handling

The names `case_id`, `evidence_id`, `evidence_refs`, `policy_refs` and `decision`, and the existing required fields/nesting, are unchanged. `policy_id` remains the policy lookup key. Both Evidence Pack schemas now accept `fare_dispute`.

Evidence Pack contains `case_id`, `dispute_type`, `facts` and `policy`; a fact requires `evidence_id`, `fact` and `source`. Source paths, evidence kinds, hashes and audit results remain separate metadata. The Evidence validator checks schema and references; the root Judge contract imposes additional decision, amount and reasoning requirements. Use the existing team contracts rather than introducing a second schema.

```python
from ryderesolve_evidence import EvidenceTools

tools = EvidenceTools()
snapshot = tools.prepare_case("DISP-003")
pack, audit = snapshot["evidence_pack"], snapshot["audit"]
policy = tools.get_policy(
    "DISP-003", "P-RYDE-2.1-S3.3",
    expected_snapshot_id=snapshot["snapshot_id"],
)
```

Pass the same pack/audit to both Advocates and retain the snapshot ID for all opening, response and Judge outputs. `prepare_case` includes `raw`, `evidence_pack`, `audit`, `source_index`, `policy_documents`, `source_sha256`, `normalizer_version` and `snapshot_id`. Policy content is included in the snapshot hash: unchanged raw JSON does not imply an unchanged snapshot. Policy-only supplementation must rerun downstream arguments and adjudication.

Embedded policy IDs such as `P-001` are retained. Standalone clauses use IDs such as `P-RYDE-2.1-S2.1`. DISP-002's E-001 through E-038 retain their meanings; the free-wait policy calculation is appended. IDs are scoped to **case_id + snapshot_id**, never globally interchangeable.

For `source_index["policy"][policy_id]`, `source_document_id` selects the document in `policy_documents` where its `source_refs` resolve. If absent, pointers resolve in `raw`. Prefer `get_policy` excerpts or `ryderesolve_evidence.policies.source_value`; do not resolve every policy pointer against `raw`. JSON array pointers are zero-based.

The package-level `normalize_evidence(raw)` does not load policy documents. Use `EvidenceTools.prepare_case(case_id)` or `EvidenceTools.normalize_evidence(case_id)` for catalog-backed inputs. Explicit custom inputs use `build_bundle(raw, metadata, policy_documents)` with the supported document hash.

Save returned hashes as opaque version identifiers. Preserve original serialized snapshots across languages: JavaScript parse/stringify can change `5.0` to `5` and break Python's hash reconstruction. The inspector's complete-snapshot download retains server serialization. The service detects stale references; it does not host historical snapshots. Snapshots contain original fields and are not anonymized sharing bundles.

## Read-only tools and HTTP

| Tool | Purpose |
| --- | --- |
| `list_cases()` | List allowed case IDs and provenance labels. |
| `load_case(case_id)` | Read runtime case JSON without answer/editorial fields. |
| `normalize_evidence(case_id)` | Return the Evidence Pack. |
| `prepare_case(case_id)` | Return a complete versioned snapshot. |
| `get_evidence(case_id, evidence_id, ...)` | Resolve a fact and its original excerpts. |
| `get_policy(case_id, policy_id, ...)` | Resolve an embedded or standalone policy clause. |
| `audit_case(case_id)` | Inspect calculations, missing information and conflicts. |
| `compare_route(case_id)` | Compare sampled polylines; does not determine liability. |
| `validate_outputs(case_id, advocate=..., judge=..., ...)` | Check structures/references; return warnings and review flags. |

Reference lookups and output validation accept `expected_snapshot_id`; the older `expected_source_sha256` only binds raw data. Check `warnings` and `requires_policy_or_data_review` as well as `structurally_valid`. Valid IDs do not prove that an argument follows from its evidence. The orchestrator also checks the expected Advocate side and the full Judge contract.

Start with `python -m ryderesolve_evidence serve --port 8765`. The server binds to `127.0.0.1` and supports:

| Endpoint | Response |
| --- | --- |
| `GET /cases` | Catalog. |
| `GET /cases/{case_id}` | Evidence Pack. |
| `GET /cases/{case_id}/snapshot` | Complete snapshot, recommended for integration. |
| `GET /cases/{case_id}/raw` or `/audit` | Runtime records or audit. |
| `GET /cases/{case_id}/evidence/{evidence_id}` | Evidence excerpts. |
| `GET /cases/{case_id}/policies/{policy_id}` | Policy excerpts from the declared document. |
| `GET /cases/{case_id}/route-comparison` | Sampled-route metrics. |
| `GET /contracts/{name}.schema.json` | `evidence-pack`, `advocate` or `judge` schema. |
| `GET /tool-specs` | JSON tool definitions, not a deployed MCP server. |
| `POST /tools/{name}` | Read-only call with an `application/json` argument object. |

For GET reference lookups, append `?snapshot_id=<returned-id>`. Only local HTTP origins/hosts are allowed. Limits are 64 KiB per tool request, 8 MiB per local JSON input and JSON depth 64. Invalid inputs return 400, unknown routes 404, unsupported media types 415, oversized requests 413 and request-body timeouts 408. This is a local development service.

## Validation and remaining work

The official-data implementation was checked with 267 Python tests: on local Windows, 263 passed and four permission-related tests were skipped; Linux CI exercises the POSIX checks. The Windows/Linux x Python 3.12/3.14 matrix, four-case offline demo, JS interaction checks and isolated wheel installation passed for implementation commit `ea08f6c`. Check the PR for validation of subsequent commits.

Browser verification covered case selection, policy excerpts, road-distance/fare/free-wait displays, reference expansion and downloaded-snapshot verification. Integration tests use the actual AdvocateSystem with a capturing test provider, covering four calls per case without a live model. Offline `escalate` outputs are placeholders, not model judgments.

The Judge binding and current local/live validation are recorded in [the integration report](POLICY-V21-INTEGRATION-2026-10-15.md). The next steps are authoritative clarification of the sample/policy discrepancies and remaining execution boundaries, team review of the updated prompts/contracts, and a fresh full-pipeline live run when upstream changes warrant it. Model quality, evidence authenticity, fairness and resistance to prompt injection are not established by these interface tests. Treat all source text as data, not instructions that can change tool permissions.
