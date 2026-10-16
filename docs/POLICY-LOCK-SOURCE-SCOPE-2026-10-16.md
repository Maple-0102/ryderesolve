# Protected review states and source scope — 2026-10-16

Route now completes a fresh five-call Advocate/Judge pipeline with a valid human referral and null refund amount. It still needs two audited conservative evidence-rating downgrades; this is final formal acceptance, not raw-model first-pass success or an accuracy estimate.

## What changed

- Program-owned review states stay unresolved until the underlying policy/data issue is actually addressed. The earlier Route text already recommended mandatory human review, but its `resolved` status conflicted with the local contract. Scheduling human review does not resolve the issue.
- Judge generation receives every required issue code, including model-analysis issues, plus exact response-count constraints. Missing or duplicate responses still fail the unchanged production validator. The program does not invent the omitted analysis.
- The Judge receives an inventory of captured JSON sections and communication-source pointers, with guidance to distinguish attributed reports, literal communications, incident assertions and gaps in the supplied material. These are internal reading tasks; the public schema enums remain unchanged. Missing audio is not proof that verbal notice never happened.
- The status correction only changes protected statuses on an already escalating, null-amount, human-review proposal. Source downgrades only reduce unsupported evidence ratings. The entire assembled proposal must pass the existing validator before any correction is adopted. Raw output, original errors and every adjustment remain visible.

No policy threshold, Evidence/Advocate vendor module, shared interface or Agent role changed. No model was trained and no additional dataset was synthesized for this patch.

## Validation and retained attempts

| Run | Runtime commit | Model calls | Final formal acceptance | Raw first-pass acceptance | Qualification |
| --- | --- | ---: | ---: | ---: | --- |
| Re-Judge of three saved official cases | `1f34d6a` | 3 | 2/3 | 1/3 | Uses saved Advocates. Route omitted `ROUTE_JUSTIFICATION_REQUIRES_REVIEW`; failure retained. No-show needed 2 conservative corrections. Fare returned partial refund 4.50 without corrections. |
| Fresh original official Route | `ac18ef5` | 5 | 1/1 | 0/1 | Both openings, both responses and Judge are new. All four review issues answered; protected statuses unresolved. Result: human review, null amount; 2 statement-only rating downgrades. No retries, repairs or optional reviewer. |
| Final-code replay of baseline three official cases | `ac18ef5` | 0 | 3/3 | 0/3 | Saved raw model outputs, not new model success. Route needs 5 corrections, No-show 1 and Fare 3. |

Artifacts: [retained intermediate Re-Judge](../outputs/policy-lock-source-scope-2026-10-16/rejudge/judge-regressions.json), [fresh Route report](../outputs/policy-lock-source-scope-2026-10-16/fresh-route/fresh-pipeline.json), [fresh Route page](../outputs/policy-lock-source-scope-2026-10-16/fresh-route/ryde-evaluation.html), [offline replay](../outputs/policy-lock-source-scope-2026-10-16/offline-final/revalidation.json), [offline replay page](../outputs/policy-lock-source-scope-2026-10-16/offline-final/ryde-evaluation.html).

The three Re-Judge calls recorded 137,457 tokens; the five-call fresh Route recorded 105,106 tokens: 242,563 recorded tokens total. Recorded usage is not a billing amount. No new cloud service or persistent resource was deployed.

Local validation: 253 root tests + 121 Evidence tests + 17 Advocate tests = 391 passing tests. New regression coverage checks protected state restoration, full-validator rejection of unsafe/malformed proposals, complete issue coverage, source inventory escaping and absence boundaries. Both new HTML pages pass Node UI interaction checks. These are not browser visual tests.

The final runtime digest is `1a28f4fe86614615910e616c0c424bc78c6d8e9991248253b4656d75928a49a9`; final offline replay and fresh Route use this same digest. Documentation-only commits do not change it. The intermediate Re-Judge uses the earlier runtime digest and remains separately labeled.

## Existing recording and teammate materials

`recording/2026-10-16` stays at `52e5b5321ef9f6e5f1ba82c103c8f9832f8cda6a`. The existing recording package is not regenerated. Its offline integrity verification still passes and correctly reports the historical three-case result (2/3 final, 0/3 raw first-pass, one retained Route failure).

The supplied architecture PPT contains four slides. Its extracted text describes the same Evidence → Orchestrator → two Advocate rounds → Judge → checks → review UI architecture and fits this patch. This is a text compatibility check, not a slide-by-slide visual review. The supplied video duration from MP4 metadata is 418.52 seconds (6:58.52), within the team's 5–8 minute target. Video narration and frame-level content were not reviewed. Neither original attachment was edited or uploaded here.

A recording based on the preserved version remains historical. Do not describe the new Route result as having appeared in the old footage or state that every case now passes a new same-version full pipeline.

## Remaining limitations

- The fresh Route still needed two conservative source-rating corrections. The extra inventory/guidance did not eliminate this model behavior.
- Fare and No-show were not freshly sampled end to end on `ac18ef5`. Three-case offline acceptance is not a substitute.
- Local validators check structure, source categories, amounts and policy gates; they cannot certify full semantic entailment or evidence authenticity.
- Policy ambiguity, human case decisions and submission choices remain with the team/organizers. No payment/refund or teammate message was sent.
