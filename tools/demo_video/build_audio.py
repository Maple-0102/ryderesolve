"""Synthesize English narration and build word-aligned subtitles for the demo."""
import asyncio
import html
import hashlib
import json
import re
from pathlib import Path
import subprocess
import textwrap
import edge_tts

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/demo-video-2026-10-16-v2'

def duration(path):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', str(path)], text=True))

def stamp(t):
    ms = round(t * 1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'

async def main():
    book = json.loads((ROOT / 'tools/demo_video/storyboard.json').read_text(encoding='utf-8'))
    (OUT / 'audio').mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(3)
    async def synth(scene):
        path = OUT / 'audio' / (scene['id'] + '.mp3')
        marks_path = path.with_suffix('.words.json')
        key_path = path.with_suffix('.sha256')
        key = hashlib.sha256(json.dumps([scene['narration'], book['voice'], book['rate']]).encode()).hexdigest()
        if not (path.exists() and marks_path.exists() and key_path.exists() and key_path.read_text() == key):
            async with semaphore:
                marks = []
                speech = edge_tts.Communicate(scene['narration'], book['voice'], rate=book['rate'], boundary='WordBoundary')
                with path.open('wb') as audio:
                    async for chunk in speech.stream():
                        if chunk['type'] == 'audio':
                            audio.write(chunk['data'])
                        elif chunk['type'] == 'WordBoundary':
                            marks.append({k: v for k, v in chunk.items() if k != 'type'})
                marks_path.write_text(json.dumps(marks, indent=2), encoding='utf-8')
                key_path.write_text(key)
        scene['audio_duration'] = duration(path)
        scene['duration'] = round((scene['audio_duration'] + 1.1) * 25) / 25
        print(scene['id'], scene['duration'], flush=True)
    await asyncio.gather(*(synth(s) for s in book['scenes']))
    cues, start = [], 0.0
    for scene in book['scenes']:
        scene['start'] = round(start, 3)
        words = json.loads((OUT / 'audio' / (scene['id'] + '.words.json')).read_text(encoding='utf-8'))
        original = scene['narration'].split()
        normalized = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
        assert len(original) == len(words)
        for token, word in zip(original, words):
            assert normalized(token) == normalized(word['text']), (token, word['text'])
            word['text'] = token  # Retain the reviewed script's punctuation in captions.
        group = []
        for i, word in enumerate(words):
            group.append(word)
            text = ' '.join(html.unescape(w['text']) for w in group)
            if len(text) >= 76 or word['text'].endswith(('.', '?', '!')) or i == len(words) - 1:
                t0 = start + .3 + group[0]['offset'] / 10_000_000
                t1 = start + .3 + (group[-1]['offset'] + group[-1]['duration']) / 10_000_000
                cues.append((t0, t1, '\n'.join(textwrap.wrap(text, width=52))))
                group = []
        start += scene['duration']
    book['duration'] = round(start, 3)
    assert 300 <= start <= 480, f'Video length is outside the required 5–8 minutes: {start}'
    for i in range(len(cues) - 1):
        a,b,text = cues[i]
        cues[i] = (a, min(b+.10, cues[i+1][0]-.025), text)
    (OUT/'RydeResolve-English.srt').write_text('\n\n'.join(f'{i+1}\n{stamp(a)} --> {stamp(b)}\n{text}' for i,(a,b,text) in enumerate(cues))+'\n', encoding='utf-8')
    (OUT/'timeline.json').write_text(json.dumps(book, indent=2), encoding='utf-8')
    (OUT/'RydeResolve-English-transcript.txt').write_text('\n\n'.join(s['title']+'\n'+s['narration'] for s in book['scenes']), encoding='utf-8')
    print('Total duration:', round(start, 2), 'seconds; subtitles:', len(cues), flush=True)

if __name__ == '__main__':
    asyncio.run(main())
