# Pre-merge self-check — October 16, 2026

Reviewed the integration branch and Evidence PR #2 before merging into `main` at the repository owner's request.

- Evidence PR #2 still points to `2e4850e4fe1a44e963b26024c5cda4ede3efbf8c`. Its Evidence vendor tree is byte-identical to the integration branch and its head is already an ancestor of the integration branch.
- Reviewed source/policy boundaries, excluded editorial answers, source-bound references, current contract compatibility, provider failures, retry/repair limits, and recovery event rendering. Existing organizer policy ambiguities remain explicit and conservatively referred to humans; they are not reported as clarified by the organizer.
- Found and fixed one recovery edge: a hard process stop leaves a `running` checkpoint event without completion timing. Resume now marks this old event interrupted, preserves unknown provider usage and renders an unknown duration. A regression reproduces the persisted pre-call state and verifies recovery without regenerating the four completed Advocates.
- Latest local checks: **202 root + 121 Evidence + 15 Advocate tests passed**. The four-case offline demo, JavaScript interaction checks and `git diff --check` passed. No new cloud-model calls were made for this audit.
- The Code Review connector could not read remote CI diagnostics because it requires a ChatGPT sign-in. Remote CI results and native-browser visual validation are not claimed. GitHub PR metadata reported both PRs mergeable without conflicts before the final audit patch. Normal merge operations must respect repository protection; no admin override is authorized or used.

The latest audit supersedes the earlier 201-root-test count for the recovery patch. Previous live-model results are historical development checks; they have not been relabeled as new full-pipeline tests.
