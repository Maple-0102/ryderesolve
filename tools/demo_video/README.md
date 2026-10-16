# English hackathon demonstration

An approximately seven-minute competition pitch covering the user problem, project overview, core Agent features and usage, build reflection, and development-tool tips. The source baseline is team `main` at `fb374f1` (16 October 2026).

The video uses English neural narration, word-aligned English subtitles, 1920 × 1080 browser capture, actual mouse actions and visible click feedback. The presentation layer translates interface labels and adds chapter headings; it does not change application data, model outputs, policy rules, or backend behavior.

## Demonstration sources

- The fare walkthrough uses the saved real six-call result at `outputs/workflow-followups-2026-10-16/final-parallel-live/DISP-003.run.json`. It is labeled **Saved live run** throughout, and is not presented as a fresh call against the current prompts.
- No-show, route and operational controls use the current offline pipeline. They are labeled **Offline control demonstration** or **Offline controls**. No new paid model calls are made for video production.
- The supplement file is explicitly synthetic. Previewing it is a real workbench action; no official attachment or policy is overwritten. The human-outcome form is demonstrated without saving a business decision.
- The pitch retains the unresolved no-show policy conflict, mandatory route-review gate, and the distinction between a refund suggestion and an executed transaction. It makes no general accuracy, fairness, production-deployment or measured support-cost claim.

## Files

| File | Purpose |
| --- | --- |
| `storyboard.json` | Reviewed narration, chapter titles and source baseline. |
| `presentation.html` | Introductory, architectural and reflection visuals. |
| `demo-overlay.js` | Editorial English labels, cursor and chapter overlay. |
| `browser.config.json` | English browser locale, including native file-input labels. |
| `build_audio.py` | Narration, word timing, transcript and SRT subtitles. |
| `record_demo.py` | Speech-cued real browser interactions via Playwright CLI. |
| `assemble_video.py` | Synchronization, caption rendering, audio normalization and media checks. |
| `verify_video.py` | Full decoding, loudness, caption/source checks and frames for visual review. |

Generated narration, intermediate recordings, local workbench state and large render files stay under the ignored `outputs/demo-video-2026-10-16/` and `output/playwright/video/` directories.

## Reproduce

Install the root project requirements in its local environment. Video production additionally needs Node/npm, Playwright CLI, Microsoft Edge, FFmpeg/ffprobe, and a separate Python environment containing this directory's requirements. English speech synthesis requires network access and sends the reviewed narration to the speech service; it does not send case files or credentials.

Generate fresh offline reports at the expected location:

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe -m ryde_resolve.run_demo --parallel-advocates --issue-guidance --output-dir outputs/demo-video-2026-10-16/offline
.venv/Scripts/python.exe -m venv .local/video-venv
.local/video-venv/Scripts/python.exe -m pip install -r tools/demo_video/requirements.txt
.local/video-venv/Scripts/python.exe tools/demo_video/build_audio.py
```

Start the offline workbench on port 8775 with a fresh workspace, importing the saved live fare run and the two newly generated offline reports. On subsequent restarts of the same workspace, omit all `--import-run` arguments.

```powershell
.venv/Scripts/python.exe -m ryde_resolve.workbench --directory outputs/demo-video-2026-10-16/workbench --port 8775 --parallel-advocates --import-run outputs/workflow-followups-2026-10-16/final-parallel-live/DISP-003.run.json --import-run outputs/demo-video-2026-10-16/offline/DISP-001.run.json --import-run outputs/demo-video-2026-10-16/offline/DISP-002.run.json
```

Serve this presentation directory on a separate loopback port:

```powershell
.venv/Scripts/python.exe -m http.server 8776 --bind 127.0.0.1 --directory tools/demo_video
```

The supplement fixture is a copy of the offline DISP-002 raw JSON with one additional `chat_logs` message: sender `rider`, type `message`, timestamp `2026-09-13T08:51:10+08:00`, content `SYNTHETIC DEMONSTRATION ONLY: I was waiting at the north entrance.` Append it in chronological order and save it as `outputs/demo-video-2026-10-16/synthetic-supplement-DISP-002.json`. It is a synthetic statement recorded after cancellation, not verification of the rider's earlier location.

```powershell
.local/video-venv/Scripts/python.exe tools/demo_video/record_demo.py
.local/video-venv/Scripts/python.exe tools/demo_video/assemble_video.py
.local/video-venv/Scripts/python.exe tools/demo_video/verify_video.py
```

Recording can be resumed by scene with `--start N --end N`. Re-recording operational scenes may add another local offline run or preview; it never enables live mode. Stop the two local servers after recording.

The recorder inserts a short synchronization pulse before each scene. Assembly removes the pulse and CLI startup latency, then aligns narration and actions to the same time origin. Visual QA and source verification are still required before delivery; successful encoding alone does not establish a complete demonstration.

## Delivery

The final deliverables are `RydeResolve-Demo-English-1080p.mp4`, `RydeResolve-English.srt`, and `RydeResolve-English-transcript.txt`. The MP4 includes burned-in subtitles and chapter markers. Keep the subtitle file for platforms that accept a separate caption track; disable duplicate captions if using the burned-in version.

The repository is private. A private GitHub asset is suitable for teammate review but is not a judge-accessible public submission link. Public or unlisted hosting is a separate publication step; no competition form submission is performed by these scripts.
