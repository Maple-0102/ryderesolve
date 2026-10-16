# Judge / Orchestration follow-ups — 2026-10-16

Based on merged main `e765eab238fc1d652054d168e7489a5f6d482178`. Work is on `judge/workflow-followups`. Public Evidence/Advocate/Judge schemas and both vendor modules are unchanged.

## What was implemented

1. **Fresh model execution and a small paired comparison.** Three development cases compare a decision-only single Judge, four fresh Advocates + Judge, and an extra reviewer of the exact same debate candidate. No scorer labels enter model inputs. Failures remain in the report. One duplicate supporting/opposing reference error can receive the existing single structural repair; a repair cannot change the decision or refund amount. Advocate prompts ask for atomic claims.
2. **A local operational workbench.** Upload the complete amended raw JSON, declare synthetic or unverified provenance, preview literal source differences, then explicitly start one supplement run. Official policy documents remain pinned. The child rebuilds all four arguments and retains parent/child snapshot IDs, source note and the original result. Local human outcomes require a reviewer name, explanation, finite cents within the charged amount, and existing evidence/policy references. Entries are append-only and do not overwrite the AI or execute refunds.
3. **More specific response coordination.** Both validated openings are grouped against policy conditions by shared source IDs. Each issue lists actual `/opening/.../claims/...` paths for each side, its recorded status and source references. Shared references are candidate discussion points, not proof of contradiction. Both sides get the same issue list and only the opponent's opening; neither sees the opponent's response. One response round then Judge; agreement cannot fill an unknown source.
4. **Opt-in concurrent Advocates and actual progress display.** Four separate adapters/model clients avoid shared role, prompt and transport state. Openings run as a pair, then both outputs are validated before responses; both responses are validated before Judge. The parent thread reserves the pair's call budget and alone writes events, usage and checkpoints. A failed pair drains both branches; a successful half survives for resume. Retry/time/token/call limits remain cumulative. Actual events drive the timeline, including reuse, failure, interrupted and optional skipped stages.

The workbench listens only on `127.0.0.1`, checks Host/Origin/startup token, accepts JSON with a body limit and stores runtime records privately. Reloading, browsing, previewing and human entry do not call models. This is a local demonstration tool: reviewer identity and uploaded provenance are self-declared, not authenticated. It is not a multi-user production service. Failed/restarted workers are shown as failed/interrupted, rather than endlessly running. Workbench resume controls are not implemented; the CLI retains version-bound resume for compatible case runs.

## Real-model observations — retain both success and failure

All calls used the existing Google Cloud project, Gemini `gemini-3.8-flash`, LOW thinking. No new cloud deployment or persistent resource was created.

- Initial fresh main flow: five calls, rejected for `ARGUMENT_CONFLICTING_REFERENCE_ROLE`; reviewer not reached. A compound claim mixed a recorded event with entitlement. The same source was listed in opposing and supporting roles.
- Frozen three-case comparison: 19 calls, no retries or repairs. One original Fare case and two team-authored variations of the same seed. They are development examples, not a held-out dataset, official answer key or trained model.
- Final integrated concurrent Fare run: **six fresh calls**, no replay, no repair; refund suggestion **SGD 4.50**; all production checks passed; reviewer passed. Runtime implementation digest matches commit `a2d21d3`; the later Judge prompt follow-up is recorded separately in `JUDGE-STATEMENT-SCOPE-2026-10-16.md`. Recorded active time was about 65.9 seconds for this one run. This is not a controlled speedup measurement.

The comparison has two separate measurements:

| Variant | Common decision/source checks + expected decision/amount | Full production flow accepted |
|---|---:|---:|
| Single Judge | 2 / 3 | Not applicable: no Advocate coverage contract |
| Debate + Judge raw candidate | 3 / 3 | 1 / 3 |
| Debate + reviewer | Reviewer reached on 1 / 3 | 1 / 3 |

The original `comparison.json` is immutable. `secondary-analysis.json` applies the shared checks to saved raw candidates without calls or changing release gates. The two rejected debate candidates had the expected business decision but mislabeled the scope/support of rider statements. For example, “the rider says they received no notification” does not establish that no notification was sent. Repeating that statement in chat is also not independent corroboration. Their raw candidates remain rejected, even though common decision checks pass.

The single Judge failure was `NO_DECISION_INFERENCE`: its amount/decision matched the expected outcome but lacked the required explicit decision inference. These failures count; a technical fallback to human is not scored as a correct business escalation. The added reviewer was not evaluated on the rejected candidates. This sample cannot establish general accuracy or that extra agents improve outcomes.

The frozen comparison predates the completed issue pairing and concurrency. Its exact runtime delta against base main is retained in `comparison/runtime.patch`, with file hashes in `runtime-manifest.json`. Apply that zero-context patch with `git apply --unidiff-zero` to the base commit in a separate checkout to inspect the comparison source. Do not confuse its implementation hash with the later final pipeline. Both versions keep identical captured policy/evidence boundaries.

## Validation

- Root: **224 passed**.
- Evidence: **121 passed**.
- Advocate: **15 passed**.
- Total: **360 passed**, including local HTTP and concurrency/failure tests.
- Four-case offline run with parallelism and issue guidance: no validation errors. These outputs are placeholders, not model quality evidence.
- Static report JS and workbench script interaction checks passed: paid confirmation, read-only page load, stale preview rejection and explicit commit.
- Browser check: local page loaded, actual run statuses shown, a clearly labeled demo human result saved and read back. The original AI artifact remained unchanged. Screenshot records are demonstration data; the SGD 3.44 human form entry is not the AI's Route ruling.
- Final fresh live candidate revalidated against current contracts with no error.
- CI configuration includes the new script and parallel offline run. Local results do not assert remote CI passed.

Total this iteration: **30 provider calls with recorded responses; 456,813 recorded tokens; 0 unknown-usage calls**. This is provider-reported token use, not a currency charge or verified credit balance. The final six-call run accounted for 104,414 tokens. No further live calls were made to chase a perfect three-case score.

## Commands

From the repository after installing `requirements.txt`:

```bash
# Offline workbench: opening the page does not call a model.
.venv/bin/python -m ryde_resolve.workbench --parallel-advocates

# Import a saved genuine run into a new offline workspace.
.venv/bin/python -m ryde_resolve.workbench \
  --directory outputs/my-workbench \
  --import-run outputs/workflow-followups-2026-10-16/final-parallel-live/DISP-003.run.json
```

Open `http://127.0.0.1:8765`. Import once; when restarting the same workspace, omit `--import-run`. Stop the local server with Ctrl+C. Existing runtime records remain on disk and are ignored by Git.

```bash
# Paid actions enabled. This workbench preset uses four Advocates, Judge,
# optional-stage reviewer enabled, issue guidance, max 7 calls, no network retry.
# Each start/supplement also requires its UI confirmation checkbox.
.venv/bin/python -m ryde_resolve.workbench --live --parallel-advocates

# CLI: individual switches remain optional; the default is sequential.
.venv/bin/python -m ryde_resolve.run_demo --case DISP-003 \
  --judge vertex --advocate teammate-vertex --thinking-level LOW \
  --reviewer vertex --issue-guidance --parallel-advocates \
  --max-calls 7 --transient-retries 0 --judge-repairs 1 \
  --output-dir outputs/new-live-run

# Costs up to 21 calls. Choose a NEW output directory; old attempts are retained.
.venv/bin/python -m evaluation.compare_workflows --live \
  --output outputs/new-three-case-comparison
```

CLI checkpoints bind snapshot, runtime implementation, runner identities, options and limits. Change any of these and resume is rejected. In-flight requests may finish after a time/token threshold; admission checks prevent starting the next pair once a recorded limit is reached. Parallelism does not promise fewer tokens or a fixed speedup.

## Next priority

Fix atomic self-report claims and their Judge support scope with the Advocate teammate, using the retained failures as development regressions. Preserve the rule that a rider/driver statement proves what was said, not what happened. Then evaluate the frozen regression cases and separate new variations, reporting business correctness and production rejection rates separately. No new training dataset or model fine-tuning is needed for this step. Extra debate rounds and a default extra reviewer are not justified by the present comparison.

The two organizer policy ambiguities remain in `POLICY-QUESTIONS-2026-10-15.zh-CN.md`. Supplemented statements do not bypass mandatory human gates, including the official 4.3 km Route case.
