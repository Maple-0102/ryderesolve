# Advocate integration guide

The Advocate module prepares source-grounded arguments for the rider and driver in the RydeResolve workflow. It consumes a versioned Evidence snapshot, cites evidence and policy IDs, and returns structured arguments for the Judge. Advocates do not issue the final ruling or execute a refund.

This guide describes the Advocate contract, integration flow and case-specific boundaries. Repository setup and full-pipeline commands are in the [root README](../README.md). Evidence source handling is documented in the [Evidence integration guide](EVIDENCE-INTEGRATION.md); policy v2.1 integration and unresolved questions are covered in [the policy integration report](POLICY-V21-INTEGRATION-2026-10-15.md) and [the policy questions list](POLICY-QUESTIONS-2026-10-15.zh-CN.md).

## Scope and workflow

| Stage | Responsibility | Advocate boundary |
| --- | --- | --- |
| Evidence | Load the case, normalize source records, attach the applicable policy, calculate metrics and produce a versioned snapshot | Use only the supplied snapshot and its audit; do not treat excluded editorial/answer fields as evidence |
| Advocate | Produce a rider argument and a driver argument, each with evidence and policy references | Present positions and counterpoints; do not decide liability, choose an unresolved rule or determine an executed refund |
| Judge | Assess both sides' arguments against the same evidence snapshot and applicable policy | Make a proposal only when required policy conditions and validation checks permit it |
| Orchestration | Bind outputs to snapshot and round, enforce policy gates, validate outputs and route review | Keep policy-driven human referral distinct from technical failure |

The opening arguments are independent. In the response round, each side may receive the other side's opening output. Both sides receive the same opportunity to respond. A response must use the same `snapshot_id` as the opposing opening; stale or mismatched arguments are rejected.

## Official cases and source boundaries

| Case | Dispute type | Advocate-relevant records and limits |
| --- | --- | --- |
| DISP-001 | `route_deviation` | Reported road routes are 24.8 km actual and 20.5 km recommended, a 4.3 km difference. The recorded excess-distance fare is SGD 3.44; the total fare difference is SGD 6.50. These amounts are distinct. Policy v2.1 section 6.2 requires human review above 2 km. |
| DISP-002 | `no_show_charge` | Scheduled pickup is 08:45 and cancellation is 08:51. The recorded order wait is 480 seconds, the app timer is 470 seconds, and scheduled pickup to cancellation is 360 seconds. Policy v2.1 section 2.1 starts five free minutes at scheduled pickup, while the case also contains an eight-minute no-show threshold whose clock and relationship to the five-minute rule are unresolved. |
| DISP-003 | `fare_dispute` | The recorded quote is 1,200 cents and the charge is 1,650 cents, a difference of 450 cents (SGD 4.50). The supplied breakdown is consistent with a surge-only change. Separate the rider's report from the pricing and notification records. |
| SYN-ROUTE-001 | `route_deviation` | Team-authored synthetic fixture retained for regression tests. It is not an official organizer case and has no attached official policy document. |

Official sample records are not independently authenticated operational records. Use the evidence IDs and policy IDs from the active snapshot, not IDs copied from another case or an older snapshot. DISP-001 editorial recommendations and answer fields are excluded from runtime model inputs; do not reintroduce them through copied notes or expected answers.

## Claim attribution and output contract

Each item in `claims` and `counterpoints` contains:

| Field | Purpose |
| --- | --- |
| `claim` | A concise, user-visible argument. Keep separate propositions in separate items. |
| `evidence_refs` | Exact `evidence_id` values supporting the wording in this claim. |
| `policy_refs` | Exact `policy_id` values for the rule being discussed. |
| `claim_type` | One of `party_statement`, `system_record`, `derived_calculation`, `policy_application`, or `advocacy_inference`. |
| `evidence_status` | One of `reported`, `recorded`, `derived`, `conditional`, or `unverified`. |

The labels describe the kind and status of support; they are not a truth score and do not certify that an event occurred. The `claim_type` and `evidence_status` fields are requested by the prompt and accepted by the Advocate schema. For backward compatibility, older output can remain structurally valid without them, but the validator emits `MISSING_PROVENANCE_LABEL`; new outputs should include both fields.

Keep a party's statement separate from a system record about the same event. For example:

| Claim | Type / status | What it establishes |
| --- | --- | --- |
| “The rider says no arrival notification was received.” | `party_statement` / `reported` | The rider made that statement; it does not independently establish whether a notification was sent or received. |
| “The supplied app log records `rider_notified=false`.” | `system_record` / `recorded` | The supplied system record contains a negative notification value; it does not prove what happened outside that record. |
| “The supplied chat log does not show a route-change notice.” | `system_record` / `recorded` | The reviewed log does not show such a message; it does not establish that no verbal notice occurred. |

If a record is absent, say “the supplied records do not show …” and identify the records reviewed when possible. Do not convert missing data into proof that an event did not happen. A sent alert is not proof of delivery or reading; sparse GPS samples are not proof of uninterrupted presence; a system fee event is not proof that the fee met policy.

The top-level response contains `case_id`, `side`, `position`, `claims`, `counterpoints` and `missing_information`. `position` states the side's requested outcome; it is not the Judge's decision. Empty evidence references are permitted only for clearly unsupported requests or assertions and trigger a warning. The validator checks output structure and that cited IDs exist in the current pack; it does not verify semantic support.

## Applying policy without taking over the Judge's role

### DISP-001: route deviation

Use the reported road-route difference for the policy threshold, not the length of a sparse GPS polyline. The 4.3 km difference exceeds the 2 km threshold in section 6.2, so the case must be referred for human review. Advocate may present arguments about route justification, timely notice, rider acknowledgment and the fare components, but it must not present a refund amount as an Advocate decision or imply that a supporting argument removes the human-review gate.

Sections 1.2–1.4 address traffic justification, notice and acknowledgment separately. The supplied historical traffic records are not independently authenticated API responses. Missing call recordings do not prove that verbal notice did not occur. Keep those evidence limits explicit and distinguish the SGD 3.44 excess-distance fare from the SGD 6.50 total fare difference.

### DISP-002: no-show charge

Section 2.1 starts the five-minute free wait at the scheduled pickup time. With pickup scheduled for 08:45, that period ends at 08:50; the driver's 08:43 arrival does not move the policy start time. The case's separate eight-minute threshold remains unresolved: the supplied materials do not establish its clock or how it relates to the five-minute rule. Preserve this as a policy/source conflict and do not combine the thresholds or select a favorable clock.

Section 2.3 requires at least one in-app message and one in-app call before cancellation. An unanswered call is an attempted contact. A fee-applied event alone does not establish compliance. A rider or driver fraud/history flag is relevant only where the supplied policy says so; it does not prove responsibility for this trip.

### DISP-003: fare and surge

Keep the quoted fare, charged fare, total difference, surge differential and any exempt fee components distinct. The system's explicit `rider_notified=false` record may be described as a recorded negative; a missing notification log is unknown. Do not infer notification from the rider proceeding with the trip.

Policy sections 3.1–3.5 govern the quote, surge change, notification and exempt booking fee. Cite the applicable clauses from the current Evidence Pack and describe only what the supplied pricing and notification records support. Under the team's whole-trip convention, refunding the SGD 4.50 surge difference is `refund_partial`, even if the policy describes refunding the surge differential in full. The Advocate states the side's argument; the Judge and policy gates determine the outcome.

## Integration

Use the current Evidence snapshot for both sides and all rounds. Do not use the Advocate package's copied example fixtures as live case inputs.

```python
from ryde_resolve.teammate_advocate import TeammateAdvocate
from ryde_resolve.evidence import EvidenceGateway

snapshot = EvidenceGateway().prepare("DISP-003")
# The orchestrator invokes TeammateAdvocate for rider and driver,
# binds outputs to snapshot_id/round, and sends validated arguments to the Judge.
```

The repository's CLI can run the integrated flow with the configured provider. For example:

```bash
.venv/bin/python -m ryde_resolve.run_demo \
  --case DISP-002 \
  --judge vertex \
  --advocate teammate-vertex \
  --thinking-level LOW \
  --output-dir outputs/local-run
```

This command sends case material and agent outputs to the configured provider. Offline mode is the default; do not describe an offline placeholder run as a live model result. The exact number of calls depends on enabled rounds, optional guidance/reviewer features and recovery behavior; see the [orchestration guide](ORCHESTRATION-2026-10-16.md).

## Validation and limitations

The Advocate validator checks JSON shape, case and side, finite values, and evidence/policy reference membership. It warns on empty evidence references and missing provenance labels. Root orchestration performs additional snapshot, role, round and policy checks. These checks do not prove that a claim is factually true or that its citations semantically support every clause; Judge assessment and human review remain necessary for those questions.

The integration check on 16 October 2026 for the code merged as `f909ad4` passed 229 root Judge/orchestration tests, 121 Evidence tests and 17 Advocate tests: 367 local tests in total. Local fake-provider checks also exercised both sides and both rounds for DISP-001, DISP-002 and DISP-003, confirming that the provenance labels reach the Judge unchanged. These checks establish interface compatibility and execution behavior, not model accuracy.

No new live model call was performed for this documentation update or that integration check. Earlier live results and their version-specific limitations are recorded in the [workflow follow-up report](WORKFLOW-FOLLOWUPS-2026-10-16.md) and [Judge claim-scope report](JUDGE-STATEMENT-SCOPE-2026-10-16.md). The latest combined Advocate/Judge prompts still require fresh end-to-end model evaluation, including the known notification variants and whole-claim support issues. Test success does not establish case accuracy, evidence authenticity, fairness, or complete resistance to prompt injection.
