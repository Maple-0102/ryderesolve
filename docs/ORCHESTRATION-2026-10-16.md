# Durable orchestration and bounded optional review

The workflow now preserves completed steps when a later provider fails, reports technical failure separately from a policy-driven human referral, and applies explicit execution limits. Public Evidence, Advocate and Judge schemas remain unchanged. These additions live in orchestration metadata and wrappers; neither vendor module was edited.

## Default workflow and recovery

Evidence is prepared and verified against its current snapshot before a saved run can resume. Snapshot, implementation/prompt/schema digest, adapter/model configuration, limits, and optional feature flags must match. Completed provider outputs are reused and validated again; earlier failures remain in the event log. Local checksums detect accidental corruption, not malicious forgery. Custom adapters with additional behavior/configuration must supply a stable `cache_identity`; generic callable identity does not capture arbitrary external state.

The CLI saves each case immediately, plus a run-ID-specific report and a private checkpoint. Checkpoint files use atomic replacement and mode 600. They contain full case inputs and are excluded from Git. Reports and HTML also contain case data; review them before sharing. Never share ADC or `.local/`.

```bash
# Offline; no provider calls.
.venv/bin/python -m ryde_resolve.run_demo --case DISP-003 --output-dir outputs/local-run

# Repeat exactly the original options, adding the run UUID printed in the JSON.
.venv/bin/python -m ryde_resolve.run_demo --case DISP-003 --output-dir outputs/local-run --resume RUN_UUID
```

A provider crash or ambiguous timeout is recorded with unknown usage. A crash after an external response but before it is persisted can require a duplicate call on explicit resume; this is not exactly-once external execution. Budget admission is checked between calls. It cannot cancel an in-flight provider request or infer unknown billed tokens. The same limits apply cumulatively across resumes; exhausted limits require a new run, not a reset through resume.

Defaults: 7 provider calls, 900 active seconds, 300,000 recorded tokens, one retry for HTTP 429/502/503/504, and at most one Judge structural repair. HTTP 400, authentication failures, and ambiguous timeouts are not automatically retried. Retry admission uses the remaining budget. Structural repairs may address covered output/argument structure errors and cannot change the candidate's decision, amount, currency, case, amount unit, or escalation choice. Rejected candidates, raw errors, and repairs are retained. Structural validity is not factual correctness.

## Execution and business statuses

| Metadata | Meaning |
| --- | --- |
| `execution_status=completed` | Workflow finished without technical/contract errors |
| `execution_status=failed` | Transport, contract, checkpoint, or budget failure |
| `business_decision_status=proposed` | Accepted AI proposal, not an executed refund |
| `business_decision_status=awaiting_human` | Business referral from policy, missing information, or reviewer |
| `business_decision_status=unavailable` | No accepted business ruling because execution failed |
| `review_reason_types` | Separate policy gate, policy clarification, evidence gap, invalid output, transport, execution limit, and inference review reasons |

The compatibility `ruling` still uses an escalation-shaped object on execution failure. Consumers must use the status sidecars to distinguish this from a genuine business referral. The UI displays separate labels and includes call usage, recovery history and repair information. `first_pass_valid` remains false after recovery if an earlier stage failed; provider-skipped safety cases use null.

## Policy v2.1 development regression pack

```bash
.venv/bin/python -m evaluation.export_dataset --suite robustness-v21 --output outputs/v21-development-inputs
.venv/bin/python -m evaluation.run_orchestration_checks --output outputs/local-functional-checks.json
```

There are 20 handwritten development expectations derived from three supplied seed cases plus clearly marked synthetic counterfactuals. They cover missing/late notice, SMS, cancellation acknowledgment, consistent multiplier variants, argument ordering, injected instructions, coherent synthetic no-show clocks/contact records, component contradictions, and all four decision categories. Model payloads contain no expected answers, exercise names or labels; scorer labels are separate. This is neither a training set nor independent holdout accuracy. The intentionally reconciled synthetic no-show cases do not clarify the conflicting official policy/example.

The scripted fault comparison uses saved real Advocate arguments as fixed fixtures, not fresh model outputs. One failed Judge plus recovery uses 6 scripted calls with checkpoints versus 10 with a complete restart; this measures call reuse in that fault path, not billed savings. The 20/20 policy checks compare deterministic rules to team-written expectations, not model accuracy. An always-escalate agent receives false-escalation failures rather than a perfect score.

## Optional second-round guidance and inference reviewer

Both features are opt-in. `--issue-guidance` gives both response Advocates the same policy-condition issue list, with the source statuses and references. Opening arguments remain independent and there are still exactly four Advocate calls. Newly cited references are labeled citation coverage, not newly collected or authenticated evidence. No consensus vote or extra debate loop is introduced. Custom Advocates without `run_guided` receive no additional prompt guidance.

`--reviewer vertex` adds one read-only model call only after a program-valid definitive Judge proposal. It checks unsupported inference, omitted counterevidence and decision consistency. Source objections require a candidate target and a verbatim, source-bound quotation. A catalogue supplies exact raw text and pointers; normalized summaries are not accepted as raw quotes. Valid objections can only refer the case to humans; the reviewer cannot award or alter money. Invalid review output is a technical failure, not a business decision. The same underlying model with a separate prompt is not independent ground truth.

```bash
# Paid development probes: one saved valid Fare proposal and one seeded false-notice inference.
.venv/bin/python -m evaluation.run_reviewer_probe --output outputs/local-reviewer-probes.json

# Paid, bounded full pipeline: 4 Advocates + Judge + optional reviewer.
.venv/bin/python -m ryde_resolve.run_demo --case DISP-003 --judge vertex --advocate teammate-vertex --thinking-level LOW --issue-guidance --reviewer vertex --max-calls 6 --transient-retries 0 --judge-repairs 0 --output-dir outputs/local-live
```

These options remain disabled by default while evidence of effectiveness is small. Existing unresolved policy questions and mandatory human gates remain in force. Current source, local test and live development results are recorded in the adjacent validation summary and reviewed run artifacts.

## Validation on October 16, 2026

- Local: **201 root + 121 Evidence + 15 Advocate tests passed**. Four offline cases, actual CLI checkpoint resume and JS interaction checks passed. This is not a native-browser visual test.
- Scripted fault path: 10 calls for complete restart versus 6 for durable resume. All 20 deterministic policy expectations matched; no live model was run over that pack.
- Reviewer probes initially failed source-quote contracts on both responses. Supplying exact raw-text/pointer pairs made the next two development probes valid: saved correct proposal passed, seeded false-notice inference was blocked. Both earlier failures remain available.
- The fresh Fare attempt generated four real issue-guided Advocate outputs and a Judge candidate of SGD 4.50. The Judge finding omitted some condition citations and was rejected before reviewer execution. A bounded citation-coverage repair path and clearer prompt were added; hard semantic conflicts are still rejected.
- The follow-up reused those exact four Advocate outputs, called Judge once and reviewer once, and passed all checks with `refund_partial`, SGD 4.50. No structural repair was needed in that follow-up. It is not described as a fresh successful six-call pipeline.
- Total this change: 11 successful provider responses, 239,998 recorded tokens. Two local ADC preflight failures are separate. No billing balance or monetary savings were measured. The final reused-event UI metadata fix was validated locally and saved live outputs were revalidated against current source without another provider call.

Reviewed machine-readable evidence: [validation summary](../outputs/orchestration-2026-10-16/validation-summary.json). Policy questions remain listed in [the team clarification document](POLICY-QUESTIONS-2026-10-15.zh-CN.md). PR #2 is still open; this integration branch contains its reviewed head, not a merge into `main`.
