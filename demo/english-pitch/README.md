# RydeResolve competition demo

[Download the English demo video](RydeResolve-Demo-English-1080p.mp4) · [English captions](RydeResolve-English.srt) · [Narration transcript](RydeResolve-English-transcript.txt)

![RydeResolve demo poster](poster.jpg)

The **7 minute 29.7 second** video presents the rider, driver and support-team problem, demonstrates the Agent workflow, and reflects on the build and development tools. It has English neural narration, burned-in English captions, real browser interactions with a visible cursor, and 20 chapter markers. Format: 1920 × 1080, 25 fps, H.264/AAC.

| Time | Content |
| --- | --- |
| 0:00 | User problem and product value |
| 0:42 | Evidence, two advocates, Judge and checks |
| 1:04 | Saved Fare run: evidence, policy, responses and SGD 4.50 suggestion |
| 3:03 | Fare original errors, three program corrections and preserved output |
| 3:30 | Saved No-show run: unresolved threshold clock and policy precedence |
| 3:52 | Saved Route run: invalid source support, human-gate error and rejected output |
| 4:22 | Offline workbench, synthetic supplement preview and human-outcome form |
| 5:27 | Recovery and execution budgets |
| 5:50 | Latest evaluation: 15 calls, 2/3 final checks, 0/3 raw first pass |
| 6:20 | Build reflection and development-tool tips |
| 7:06 | Value and next steps |

All three case reports are byte-identical to the frozen **recording/2026-10-16** commit **52e5b53**. They are saved real model runs, not live calls during the recording. The offline workbench uses main at **f2bfd30**, imports those runs and labels new processing as offline. Each segment identifies its source. The English interface is an editorial translation overlay, not a production localization.

Fare's final suggestion follows two unsupported-argument downgrades and one rider-summary reconciliation, preserving the original model output, decision and amount. No-show awaits policy clarification. Route retains its five validation errors, no accepted ruling, and a null refund amount. The three-case evaluation used four Advocate turns and one Judge per case, with no optional reviewer. Its formal-check counts are development results, not accuracy scores; earlier offline revalidation is separate.

No official attachment or runtime behavior was changed for the recording, no new paid Agent call was made, and no refund or human outcome was saved. The synthetic supplement was previewed without committing a rerun. The original review copy is retained locally.

The [media QA report](media-qa.json) records full decoding, dimensions, chapters, audio measurements, subtitle/script consistency, frozen report and original attachment hashes, and sampled visual review. It verifies the artifact and its stated sources, not model accuracy. Speech uses en-US-AriaNeural at +15%, without background music.

Production sources and reproduction instructions are in [tools/demo_video](../../tools/demo_video/README.md). Intermediates and machine-specific state remain local.

**Competition review material.** The repository owner has authorized public GitHub access to the source and these materials. Making the repository accessible is separate from submitting the competition form; no form submission has been made by this publication step. The MP4 already displays subtitles; avoid adding a duplicate caption layer.

The QA JSON records the pre-publication review state and media hash. The public-access authorization above is later; the MP4 and its recorded evaluation results are unchanged.
