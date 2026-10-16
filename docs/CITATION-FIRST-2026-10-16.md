# Citation-before-rating follow-up — 2026-10-16

The two source-rating errors from the previous fresh Route were absent in a new Judge call on that same transcript. A subsequent fresh five-call Route also passed without program corrections. Manual inspection then found two material-gap arguments graded as literal communications. A final guidance refinement and one new Judge call on that second transcript corrected both to incident-fact / insufficient-evidence, again without program corrections.

## Implementation

The policy-bound Judge generation schema now orders each assessment as argument path → scope → supporting/opposing references → policy references → missing information → explanation → rating. This makes source selection and gaps precede the rating in the provider's generation order. It preserves all public fields, enums, required fields and production validators. Supporting AND partly-supported incident ratings must have independently relevant incident records in their actual supporting-reference list, not merely numerical facts mentioned in prose.

Material-availability claims do not become literal communications merely by citing available chat. The existing public contract has two scopes; the Judge is instructed to retain the unknown incident conclusion as incident-fact / insufficient-evidence and describe the captured-material gap in the explanation. The inventory does not create an evidence ID or prove real-world absence of notice.

No semantic classification by keyword, automatic answer insertion, validation weakening, vendor change, new training dataset or architecture change was introduced. Existing conservative fallback and full validation remain active.

## Retained evaluations

| Stage | Runtime commit | Calls | Raw first-pass | Program corrections | Interpretation |
| --- | --- | ---: | --- | ---: | --- |
| Re-Judge of the previous two-error Route transcript | `f2e8d99` | 1 | Pass | 0 | Direct comparison on exactly the same saved Advocates. |
| Fresh official Route, all four Advocates and Judge new | `f2e8d99` | 5 | Pass | 0 | Formal checks pass; manual inspection identified two material-gap scope concerns, retained here. |
| Final Re-Judge of that new transcript | `cd0f585` | 1 | Pass | 0 | Both gap rows now incident_fact / insufficient_evidence, with empty supporting-reference lists and explicit missing audio. |
| Final-code offline replay of three original official outputs | `cd0f585` | 0 | 0/3 | Route 5; No-show 1; Fare 3 | 3/3 final acceptance after existing corrections; not new model output. |

Artifacts: [same-transcript comparison](../outputs/citation-first-2026-10-16/rejudge-last-route/judge-regressions.json), [fresh Route](../outputs/citation-first-2026-10-16/fresh-route/fresh-pipeline.json), [fresh Route page](../outputs/citation-first-2026-10-16/fresh-route/ryde-evaluation.html), [final Re-Judge](../outputs/citation-first-2026-10-16/final-rejudge-new-route/judge-regressions.json), [final offline replay](../outputs/citation-first-2026-10-16/offline-final/revalidation.json).

The final runtime digest is `2c2b0c71bda14e65e8f4661413483faa9c4552798ae2dcfa84da2e4648a46604`. The earlier full fresh run uses digest `8502828f1922a3d30f56ca8100eb7a1aa3be44eba2ee8daafd336b1acaf843e8`. The final version has one fresh Judge call, not a newly sampled full pipeline.

All three new Judge results request human review with a null refund amount. The protected issue statuses stay unresolved and complete. In the direct comparison, the measured-distance/fare part of the mixed allegation now cites actual trip metrics; the unsupported notice allegation remains explicitly unverified. A separate bare rider allegation is rated insufficient evidence.

Seven calls recorded 206,504 tokens (50,383 + 105,711 + 50,410). This is recorded usage, not a billed amount. No retry, Judge repair, optional reviewer, training or repeated rerun to replace a failed result was used. Earlier artifacts and manual concerns are retained separately.

Final root suite: 254 tests pass. With unchanged Evidence (121) and Advocate (17), local validated total is 392. New regression coverage checks that generation orders citations and gaps before rating while preserving the shared contract and rejection of old unsupported outputs. New report UI checks pass. Existing recording-package integrity still passes.

## Teammate presentation and video

Neither original attachment was edited or uploaded. The four-slide architecture text remains consistent with this change. The recorded video is 6:58.52; its visuals were sampled at 14 points, plus visible subtitle OCR every two seconds. The visible examples retain the fare refund suggestion, unresolved No-show clock, Route human threshold, distinction between saved live reports and offline controls, and no-payment boundary. No claim that every case universally passes first try was found in those samples.

This does not require rerecording the architecture or the existing demonstration. Keep its existing recorded-version labels. Do not relabel that footage as this final new run. This inspection covers sampled visuals and visible subtitles, not a complete audio-track review or a guarantee about every frame. A small conditional offline-placeholder explanation is visible in the Advocate panel; it is existing UI help, but a caption could clarify the saved-live versus offline distinction if the team finds it confusing.

## Practical limits

The targeted errors were absent in these retained development checks; a small number of same-case runs cannot establish an accuracy rate or guarantee future model behavior. Source categories are not semantic-entailment or authenticity proof. A formal pass is separately reported from the manual scope concerns found in the intermediate run. Fare and No-show were not newly sampled on the final runtime. Keep human review, conservative corrections and full validation enabled.
