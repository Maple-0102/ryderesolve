# English hackathon demonstration

A 7 minute 29.7 second competition pitch covering the user problem, project overview, core Agent features and usage, build reflection, and development-tool tips. The saved case reports are fixed to recording/2026-10-16 at **52e5b5321ef9f6e5f1ba82c103c8f9832f8cda6a**. The offline workbench uses main at **f2bfd30c25ca64b302f3b6d6dfc0276808f9a920**. Both are identified in the video.

The video uses English neural narration, word-aligned English subtitles, 1920 × 1080 browser capture, actual mouse actions and visible click feedback. The presentation layer translates interface labels and adds chapter headings; it does not change application data, model outputs, policy rules, or backend behavior.

## Demonstration sources

- All three case walkthroughs use the byte-identical saved report HTML and run JSON from the frozen recording branch. Each is labeled **Saved real run**; browsing makes no new model calls.
- Fare retains the SGD 4.50 suggestion and shows the original errors and three corrections: two argument downgrades and one rider-summary reconciliation. Original output, decision and amount remain preserved.
- No-show awaits policy clarification. Route retains four invalid argument assessments and an improperly resolved human gate; the candidate is rejected and the amount remains null.
- The evaluation summary is 15 saved fresh calls, 2/3 final formal acceptance, and 0/3 raw first-pass acceptance. This is a development result, not an accuracy score. No optional reviewer was used; earlier offline revalidation is separate.
- The workbench imports the three saved runs. New processing is labeled **Offline controls** and uses no paid model calls.
- The supplement file is explicitly synthetic. Previewing it is a real workbench action; no official attachment or policy is overwritten. The human-outcome form is demonstrated without saving a business decision.
- The pitch retains the unresolved no-show policy conflict, mandatory route-review gate, and the distinction between a refund suggestion and an executed transaction. It makes no general accuracy, fairness, production-deployment or measured support-cost claim.

## Files

| File | Purpose |
| --- | --- |
| `prepare_assets.py` | Stage byte-identical frozen reports and a synthetic preview fixture. |
| `storyboard.json` | Reviewed narration, chapter titles and source baseline. |
| `presentation.html` | Introductory, architectural and reflection visuals. |
| `demo-overlay.js` | Editorial English labels, cursor and chapter overlay. |
| `browser.config.json` | English browser locale, including native file-input labels. |
| `build_audio.py` | Narration, word timing, transcript and SRT subtitles. |
| `record_demo.py` | Speech-cued real browser interactions via Playwright CLI. |
| `assemble_video.py` | Synchronization, caption rendering, audio normalization and media checks. |
| `verify_video.py` | Full decoding, loudness, caption/source checks and frames for visual review. |

Generated narration, intermediate recordings, local workbench state and large render files stay under the ignored `outputs/demo-video-2026-10-16-v2/` and `output/playwright/video-v2/` directories.

## Reproduce

Install the root project requirements in its local environment. Video production additionally needs Node/npm, Playwright CLI, Microsoft Edge, FFmpeg/ffprobe, and a separate Python environment containing this directory's requirements. English speech synthesis requires network access and sends the reviewed narration to the speech service; it does not send case files or credentials.

Stage the frozen reports, then generate narration. The Git history must contain the recording commit:

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe tools/demo_video/prepare_assets.py
.venv/Scripts/python.exe -m venv .local/video-venv
.local/video-venv/Scripts/python.exe -m pip install -r tools/demo_video/requirements.txt
.local/video-venv/Scripts/python.exe tools/demo_video/build_audio.py
```

Start the offline workbench on port 8775 with a fresh workspace, importing the three frozen saved runs. On subsequent restarts of the same workspace, omit all `--import-run` arguments.

```powershell
.venv/Scripts/python.exe -m ryde_resolve.workbench --directory outputs/demo-video-2026-10-16-v2/workbench --port 8775 --import-run outputs/latest-flow-2026-10-16/recording/r21-fare-original.run.json --import-run outputs/latest-flow-2026-10-16/recording/r21-route-original.run.json --import-run outputs/latest-flow-2026-10-16/recording/r21-noshow-original.run.json
```

Serve this presentation directory on a separate loopback port:

```powershell
.venv/Scripts/python.exe -m http.server 8776 --bind 127.0.0.1 --directory outputs/demo-video-2026-10-16-v2/web
```

prepare_assets.py creates the supplement fixture from the saved DISP-002 raw JSON with one additional `chat_logs` message: sender `rider`, type `message`, timestamp `2026-09-13T08:51:10+08:00`, content `SYNTHETIC DEMONSTRATION ONLY: I was waiting at the north entrance.` It is inserted chronologically and saved as `outputs/demo-video-2026-10-16-v2/synthetic-supplement-DISP-002.json`. It is a synthetic statement recorded after cancellation, not verification of the rider's earlier location.

```powershell
.local/video-venv/Scripts/python.exe tools/demo_video/record_demo.py
.local/video-venv/Scripts/python.exe tools/demo_video/assemble_video.py
.local/video-venv/Scripts/python.exe tools/demo_video/verify_video.py
```

Recording can be resumed by scene with `--start N --end N` or `--scenes N`. There are 20 scenes; the added correction sequence is 09a-audit. Use `--prepare-only` for setup screenshots. Re-recording operational scenes may add another local offline run or preview; it never enables live mode. Stop the two local servers after recording.

The recorder inserts a short synchronization pulse before each scene. Assembly removes the pulse and CLI startup latency, then aligns narration and actions to the same time origin. Visual QA and source verification are still required before delivery; successful encoding alone does not establish a complete demonstration.

## Delivery

The final deliverables are `RydeResolve-Demo-English-1080p.mp4`, `RydeResolve-English.srt`, and `RydeResolve-English-transcript.txt`. The MP4 includes burned-in subtitles and chapter markers. Keep the subtitle file for platforms that accept a separate caption track; disable duplicate captions if using the burned-in version.

The repository owner has authorized public GitHub access for competition review. Check the submitted video link in a signed-out browser. Repository publication and competition form submission are separate steps; no competition form submission is performed by these scripts.

The original review copy is retained locally under outputs/demo-video-2026-10-16/review-v1-backup/. It is not an additional submission asset.
