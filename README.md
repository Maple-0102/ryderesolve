# RydeResolve

Team project for the Tencent Cloud Hackathon: Evidence, Rider/Driver Advocates, and Judge orchestration.

The team repository is [Maple-0102/ryderesolve](https://github.com/Maple-0102/ryderesolve). Evidence 0.3 supports official cases DISP-001, DISP-002 and DISP-003 with Ryde Policy v2.1. SYN-ROUTE-001 remains an explicitly synthetic regression case.

Start with the [Evidence integration guide](docs/EVIDENCE-INTEGRATION.md) for the current data contract, policy sources and unresolved no-show rules.

## Install and run offline

Requires Python 3.12+. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m ryde_resolve.run_demo
```

On Windows, use `python` to create the environment and `.venv\Scripts\python.exe` for subsequent commands. Set `$env:PYTHONUTF8 = '1'` in PowerShell.

The default run uses the Evidence module with placeholder Advocates and an offline Judge. It makes no model calls. Open `outputs/ryde-evaluation.html` to inspect the run; switching cases in this static page does not call a model. Use `--case DISP-001`, `--case DISP-002` or `--case DISP-003` to run one case.

## Recording version (2026-10-16)

Open [the static recording index](outputs/latest-flow-2026-10-16/recording/index.html) locally after cloning. It needs no model account and makes no calls. See the [7-minute recording guide](docs/RECORDING-GUIDE-2026-10-16.md) and [latest validation and limitations](docs/LATEST-FLOW-VALIDATION-2026-10-16.md).

The final fresh check used 15 calls for the three official cases: Fare and No-show passed after audited conservative corrections; Route was safely blocked for invalid source/policy-resolution claims. This is 2/3 final formal acceptance, 0/3 raw first-pass acceptance, not a model accuracy score. Earlier successful traces and offline revalidation remain historical evidence.

## Judge follow-up (2026-10-16)

The [protected review states and source-scope follow-up](docs/POLICY-LOCK-SOURCE-SCOPE-2026-10-16.md) adds program-owned unresolved states, complete issue coverage and a captured-material inventory. A fresh five-call official Route pipeline now passes final checks after two audited source-rating downgrades (raw first-pass still fails). Three retained official outputs also pass offline replay; Fare and No-show have not been freshly rerun end to end on this patch. The recording version above stays preserved.

## Code ownership

| Component | Location |
| --- | --- |
| Evidence / Data / tools | `vendor/ryderesolve-evidence-tools/` |
| Advocate | `vendor/ryderesolve-advocate-system/` |
| Judge / orchestration / integrated UI | `ryde_resolve/`, `prompts/`, `schemas/` |
| Tests and evaluation | `tests/`, `evaluation/` |

The two vendored modules retain their contracts. See the existing [Advocate integration notes](docs/ADVOCATE-INTEGRATION-2026-10-13.md), [Judge v0.8 contract](docs/INTEGRATION-v0.8.md) and [contribution guidelines](CONTRIBUTING.md) for the team's established workflow. Make changes on a branch and open a pull request against `main`.

## Validation

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m unittest discover -s vendor/ryderesolve-evidence-tools/tests -v
.venv/bin/python -m unittest discover -s vendor/ryderesolve-advocate-system/tests -v
.venv/bin/python -m ryde_resolve.run_demo --output-dir outputs/offline-check
node tests/test_ui_script.cjs outputs/offline-check/ryde-evaluation.html
node tests/test_workbench_script.cjs
.venv/bin/python vendor/ryderesolve-evidence-tools/tests/wheel_smoke.py
```

These checks include local HTTP fixtures and isolated package installation, but do not call paid models. CI runs on Windows and Linux with Python 3.12 and 3.14; check the PR's current commit. POSIX permission tests are skipped on Windows and run on Linux. Keep `scorer-only-labels.json`, expected outcomes and original source archives outside model inputs.

The [2026-10-13 evaluation record](docs/VALIDATION-2026-10-13.md) and [saved live run](outputs/team-live-2026-10-13/ryde-evaluation.html) predate Policy v2.1. Their results do not establish model quality on the current snapshots. Policy v2.1 binding is implemented in this integration branch. See the [2026-10-15 integration and validation record](docs/POLICY-V21-INTEGRATION-2026-10-15.md). Three same-version live Judge checks passed; the successful Fare integration reuses four previously generated real Advocate outputs with one new live Judge call. At that stage a fresh five-call pipeline had not passed. The [2026-10-16 follow-up record](docs/WORKFLOW-FOLLOWUPS-2026-10-16.md) now includes a fresh successful six-call Advocate/Judge/reviewer pipeline and retains unsuccessful comparison attempts. The saved outputs also pass offline revalidation after the later contact/acknowledgment patch.

The current policy-derived Judge development suite is available separately:

```bash
.venv/bin/python -m evaluation.run_judge_suite --suite official-v21 --judge vertex --thinking-level LOW --output outputs/judge-v21-local.json
```

This command makes three paid Judge calls with hand-authored Advocate arguments. These are development expectations derived from the policy, not an official answer key or a holdout.

## Run the live Gemini pipeline

Live runs consume the caller's Google Cloud quota. Use your own authorization. The current adapter expects the SDK at `.local/google-cloud-sdk/bin/gcloud` and Application Default Credentials (ADC) at `.local/gcloud/application_default_credentials.json`. The ADC quota project must match the configured project, and the credential file requires mode `600`. Use macOS, Linux or Windows through WSL for this adapter; keep credentials and machine-specific settings under the ignored `.local/` directory.

Example `.local/vertex-config.json`, matching the saved baseline configuration:

```json
{
  "project": "YOUR_PROJECT_ID",
  "model": "gemini-3.8-flash",
  "location": "global"
}
```

The model must be available to your account and project. To run one case:

```bash
.venv/bin/python -m ryde_resolve.run_demo --case DISP-002 --judge vertex --advocate teammate-vertex --thinking-level LOW --output-dir outputs/team-live-local
```

The ADP adapter is present, but a deployed Tencent ADP application has not been verified.

## Durable execution and optional review

The workflow now saves stage checkpoints, resumes compatible runs without regenerating completed provider outputs, distinguishes execution failures from policy referrals, and enforces call/time/recorded-token limits. A 20-case Policy v2.1 development regression pack is available. Optional symmetric second-round issue guidance and an inference reviewer are disabled by default. See [workflow behavior, recovery commands and test boundaries](docs/ORCHESTRATION-2026-10-16.md).

The [recording-integrity and optional context-format optimization](docs/RECORDING-INTEGRITY-2026-10-16.md) adds zero-call artifact verification and opt-in JSON whitespace compaction. The pinned recording branch remains at `52e5b53`. Compaction preserves all input data and is disabled by default; its model/cost impact has not been measured.

## Remaining integration work

- Resolve the sample/threshold and no-show source discrepancies in the [detailed policy questions](docs/POLICY-QUESTIONS-2026-10-15.zh-CN.md). Current conservative handling is explicit and is not an organizer clarification.
- Team-review the merged Evidence/Advocate/Judge interfaces and complete a fresh full live pipeline run when the policy decisions or upstream outputs change. DISP-001 exceeds the 2 km route threshold and requires human adjudication.
- Keep evaluations tied to their exact source and policy versions; do not combine older results into a new accuracy claim.

## Local supplement and human-review workbench

```bash
.venv/bin/python -m ryde_resolve.workbench --parallel-advocates
```

Open `http://127.0.0.1:8765`. The default uses offline placeholders. It shows actual stage events, source-difference previews, one explicit supplement round, and append-only local human outcomes. It preserves prior AI suggestions and official policy documents. See the [commands, live-mode controls and development comparison](docs/WORKFLOW-FOLLOWUPS-2026-10-16.md). Existing static reports remain historical views; a model suggestion is never an executed refund.

For the CLI, `--parallel-advocates` runs each pair concurrently with separate clients, validation barriers, checkpoints and cumulative budgets. Default execution remains sequential. The optional reviewer and issue guidance remain explicit CLI flags; extra agents do not establish better accuracy.
