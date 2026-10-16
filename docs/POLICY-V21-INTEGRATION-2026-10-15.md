# Policy v2.1 integration and validation — 2026-10-15

The integration branch combines Judge PR #1, Evidence PR #2 at `2e4850e4fe1a44e963b26024c5cda4ede3efbf8c`, and source-bound policy checks. It does not merge either PR into `main`. The repository remains private. The source byte archives and scorer labels stay outside model inputs.

## Resulting behavior

- The Judge receives the versioned policy sidecar, cited clauses and audited application conditions. Snapshot identity binds the raw case and the policy document. No-show free wait starts at the scheduled pickup time; the embedded eight-minute rule remains a source conflict requiring human clarification.
- Official Route decisions use reported road distance. DISP-001 is 4.3 km over the recommended route and must be escalated under section 6.2. The current-case suggested refund is excluded from model inputs. Traffic justification, timely notice, contextual rider acknowledgment and distance-fare entitlement are separate conditions. Missing call recordings or API records are not affirmative evidence of non-notification/no congestion.
- Fare DISP-003 reverses the unnotified SGD 4.50 surge difference and retains the SGD 12 quote. Booking fees stay surge-exempt. Missing notice data differs from an explicit negative log. A refund of the difference is `refund_partial` in the team's whole-charge interface.
- Monetary/category/fraud requirements apply together. Safety indicators short-circuit Advocate and Judge calls; the system prepares evidence for human review without determining fault or recommending a resolution. The keyword screen is limited, not a complete safety detector.
- The Judge must address relevant precedents and cover both parties' opening and response claims. Record-supported incident findings are checked separately from supported statements about what a party said. Invalid outputs, raw errors and program adjustments remain visible.
- The provider response schema stays compact for long debates; local validation still requires complete claim coverage. Short debates retain exact array bounds. This avoids the over-constrained schema observed during the first full Fare attempt, without relaxing local completeness checks. The precise cause of the provider HTTP 400 was not returned.
- Rolling 30-day no-show history can create a review flag, not an executed account suspension. A proposed SGD 5 goodwill credit is separate from reversing a cancellation fee. A non-SGD currency or a no-show fee other than SGD 5 is not given an invented tariff; the unexpected-fee review gate is explicitly a team safeguard.
- The UI shows source policy identity, conditions, confidence factors, mandatory review reasons and precedents. Static case switching does not call a provider.

## Evidence PR review

The policy sidecar is pinned to `RYDE-POLICY-V2.1`, canonical SHA-256 `2a90f8974e09e417c60300b2cb05a616d2cc12bdea893eba6456ca686d1c244f`, effective 2026-01-01. Policy source pointers resolve against their declared `source_document_id`; embedded pointers still resolve against raw data. Policy changes invalidate snapshot identity. Official current-case editorial/answer material is excluded; policy section 7 precedents remain admissible.

The integration adapts the root Judge/orchestrator and preserves the vendored Evidence implementation. Source archives, import manifest, four-case packaging, policy documents and schemas were checked by the local Evidence and wheel tests. PR #2's head was rechecked on 2026-10-15 and was unchanged. The remote check connector required sign-in, so this report does not assert current remote CI success.

## Validation

Local macOS, Python 3.12:

| Check | Result |
|---|---|
| Root tests after contact/acknowledgment patch `cb53669` | 174 passed |
| Evidence tests | 121 passed |
| Advocate tests | 15 passed |
| Offline demo | Four cases, zero validation errors |
| JS case/reference interaction smoke | Passed |
| Isolated installed wheel smoke | Passed; source archives excluded from runtime package |
| Native Chrome visual inspection | Case switching, Fare view and policy/condition panels displayed without observed layout overlap |

Loopback HTTP tests required permission to bind local ports; the restricted-sandbox attempt failed at socket binding, and the permitted rerun passed. No paid provider is used by the unit/offline tests. Remote Windows/Linux matrix results are not independently verified here.

Real Gemini calls used `gemini-3.8-flash`, location `global`, thinking `LOW`:

1. The first three-case Judge suite rejected the Fare answer because side summaries omitted response-round claim paths, although the proposed refund amount was correct. A targeted schema fix and Fare rerun passed.
2. Three same-version Judge checks at `c5e774f` passed. The first full Fare flow then completed four real Advocate calls but its Judge request returned HTTP 400. That failed run and its raw error are retained.
3. At `a4068dc`, the exact four prior real Advocate outputs were replayed against the unchanged Fare snapshot, followed by **one new real Judge call**. The result was `refund_partial`, SGD 4.50, no raw validation errors and no program adjustments. This is not a fresh five-call run.
4. The release Judge suite at `a4068dc` passed all three cases: Route escalates, No-show escalates, Fare refunds SGD 4.50. Arguments are policy-derived development fixtures, not newly generated live Advocates or an official answer key. Three cases do not establish real-world accuracy.
5. The subsequent `cb53669` patch accepts valid in-app call events, deduplicates duplicate chat/event call records, requires contact strictly before cancellation, preserves conflicting complete contact summaries, and prevents post-trip/stale rider acknowledgment from establishing agreement. Four new tests cover those behaviors. All three saved release Judge outputs and the saved replay-flow Judge output pass the updated checks **offline**; no additional cloud calls were made for this patch.

Saved artifacts under `outputs/policy-v21-2026-10-15/` include release results, the original failed full Fare run, the successful replay flow, revalidation and usage summaries. Intermediate failed development suites remain locally retained and their error records appear in the usage summary. Token usage is not a billed-cost or balance measurement.

## Remaining decisions

The detailed [Chinese question list](POLICY-QUESTIONS-2026-10-15.zh-CN.md) distinguishes sample/policy discrepancies from implementation ambiguities. Priority issues are DISP-001's example ruling versus AI authority, DISP-002's eight-minute rule versus the scheduled five-minute clock, Route partial/full refund semantics, consent/notice evidence, and whether supplied traffic records satisfy historical API requirements. Team safeguards are not organizer clarifications.

After the team agrees on interfaces and obtains applicable clarifications, update those expectations and run a fresh full pipeline on the changed inputs. Do not merge older-version scores or copied answers into a current accuracy claim.
