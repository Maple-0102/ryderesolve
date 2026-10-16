"""Stage exact frozen reports and a clearly labeled synthetic preview fixture.

No model calls. Original report HTML/JSON remain byte-identical to recording/2026-10-16.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/demo-video-2026-10-16-v2'
PIN = '52e5b5321ef9f6e5f1ba82c103c8f9832f8cda6a'
PACKAGE = 'outputs/latest-flow-2026-10-16/recording'

def main():
    (OUT / 'web/recording').mkdir(parents=True, exist_ok=True)
    (OUT / 'audio').mkdir(exist_ok=True)
    copied = []
    for name in ('fare', 'noshow', 'route'):
        for suffix in ('html', 'run.json'):
            relative = f'{PACKAGE}/r21-{name}-original.{suffix}'
            source = subprocess.check_output(['git', 'show', f'{PIN}:{relative}'], cwd=ROOT)
            assert (ROOT / relative).read_bytes() == source, relative
            target = OUT / 'web/recording' / Path(relative).name
            target.write_bytes(source)
            copied.append({'file': relative, 'sha256': hashlib.sha256(source).hexdigest()})
    index = subprocess.check_output(['git', 'show', f'{PIN}:{PACKAGE}/index.html'], cwd=ROOT)
    (OUT / 'web/recording/index.html').write_bytes(index)
    shutil.copy2(ROOT / 'tools/demo_video/presentation.html', OUT / 'web/presentation.html')
    # Matching speech cache is checked by build_audio.py before reuse.
    for cache in (ROOT / 'outputs/demo-video-2026-10-16/audio').glob('*'):
        destination = OUT / 'audio' / cache.name
        if not destination.exists():
            shutil.copy2(cache, destination)
    run = json.loads((OUT / 'web/recording/r21-noshow-original.run.json').read_text(encoding='utf-8'))
    raw = run['snapshot']['raw']
    raw['chat_logs'].append({'timestamp': '2026-09-13T08:51:10+08:00', 'sender': 'rider',
                            'type': 'message', 'content': 'SYNTHETIC DEMONSTRATION ONLY: I was waiting at the north entrance.'})
    raw['chat_logs'].sort(key=lambda row: row['timestamp'])
    (OUT / 'synthetic-supplement-DISP-002.json').write_text(json.dumps(raw, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (OUT / 'recording-sources.json').write_text(json.dumps({'commit': PIN, 'files': copied}, indent=2) + '\n', encoding='utf-8')
    print(f'Staged {len(copied)} byte-identical report files; no model calls.')

if __name__ == '__main__':
    main()
