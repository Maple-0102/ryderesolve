"""Check the rendered delivery and extract real frames for a separate visual review."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/demo-video-2026-10-16'
VIDEO = OUT / 'RydeResolve-Demo-English-1080p.mp4'
QA_FRAMES = OUT / 'qa-frames'


def capture(args):
    return subprocess.check_output(args, text=True, encoding='utf-8')


def main():
    book = json.loads((OUT / 'timeline.json').read_text(encoding='utf-8'))
    qa = json.loads((OUT / 'media-qa.json').read_text(encoding='utf-8'))
    probe = json.loads(capture(['ffprobe', '-v', 'error', '-show_streams',
                               '-show_format', '-show_chapters', '-of', 'json', str(VIDEO)]))
    video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    audio = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
    assert abs(float(probe['format']['duration']) - book['duration']) < .15
    assert int(video['nb_frames']) == round(book['duration'] * 25)
    assert video['width'] == 1920 and video['height'] == 1080
    assert video['codec_name'] == 'h264' and audio['codec_name'] == 'aac'
    assert audio['channels'] == 2 and audio['sample_rate'] == '48000'
    assert len(probe['chapters']) == len(book['scenes']) == 19
    for chapter, scene in zip(probe['chapters'], book['scenes']):
        assert abs(float(chapter['start_time']) - scene['start']) < .002

    # Full decoding checks both tracks, rather than trusting the file header.
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(VIDEO),
                              '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-'],
                             capture_output=True, text=True, encoding='utf-8', check=True)
    assert not decoded.stderr.strip(), decoded.stderr
    analysis = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(VIDEO), '-vn',
                               '-af', 'silencedetect=noise=-45dB:d=1.6,ebur128=peak=true',
                               '-f', 'null', '-'], capture_output=True, text=True,
                              encoding='utf-8', check=True)
    (OUT / 'audio-analysis.log').write_text(analysis.stderr, encoding='utf-8')
    loudness = float(re.findall(r'I:\s*(-?[\d.]+) LUFS', analysis.stderr)[-1])
    peak = float(re.findall(r'Peak:\s*(-?[\d.]+) dBFS', analysis.stderr)[-1])
    long_silences = [float(v) for v in re.findall(r'silence_duration: ([\d.]+)', analysis.stderr)]
    assert -17 <= loudness <= -15 and peak <= -1.0, (loudness, peak)
    assert not long_silences or max(long_silences) < 2.5, long_silences

    srt = (OUT / 'RydeResolve-English.srt').read_text(encoding='utf-8')
    blocks = srt.strip().split('\n\n')
    captions = ' '.join(' '.join(block.splitlines()[2:]) for block in blocks)
    narration = ' '.join(s['narration'] for s in book['scenes'])
    assert captions.split() == narration.split()
    assert len(blocks) == 125

    vendor = ROOT / 'vendor/ryderesolve-evidence-tools'
    manifest = json.loads((vendor / 'sources/official/2026-10-15/manifest.json').read_text(encoding='utf-8'))
    verified_sources = []
    for name, record in manifest['files'].items():
        digest = hashlib.sha256((vendor / record['archive_path']).read_bytes()).hexdigest()
        assert digest == record['file_sha256'], name
        verified_sources.append(name)

    QA_FRAMES.mkdir(exist_ok=True)
    samples = []
    for scene in book['scenes']:
        for suffix, offset in [('a', 3.5), ('b', scene['duration'] * .72)]:
            timestamp = scene['start'] + offset
            path = QA_FRAMES / f"{scene['id']}-{suffix}.png"
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(timestamp),
                            '-i', str(VIDEO), '-frames:v', '1', str(path)], check=True)
            samples.append((path, timestamp))
    for batch_start in range(0, len(samples), 8):
        batch = samples[batch_start:batch_start + 8]
        sheet = Image.new('RGB', (1280, 4 * 380), '#e5ecee')
        draw = ImageDraw.Draw(sheet)
        for i, (path, timestamp) in enumerate(batch):
            with Image.open(path) as frame:
                frame.thumbnail((640, 360))
                x, y = (i % 2) * 640, (i // 2) * 380
                sheet.paste(frame.convert('RGB'), (x, y + 20))
                draw.text((x + 10, y + 2), f'{path.stem} at {timestamp:.2f}s', fill='#132a37')
        sheet.save(QA_FRAMES / f'contact-{batch_start // 8 + 1}.jpg', quality=92)

    qa.update({
        'full_decode': 'passed, both audio and video',
        'frame_count': int(video['nb_frames']),
        'audio_integrated_lufs': loudness,
        'audio_true_peak_dbfs': peak,
        'silences_over_1_6_seconds': long_silences,
        'captions_match_narration': True,
        'narration_word_count': len(narration.split()),
        'original_archives_verified': verified_sources,
        'video_sha256': hashlib.sha256(VIDEO.read_bytes()).hexdigest(),
        'visual_sample_count': len(samples),
        'visual_qa': 'pending review of extracted frames',
    })
    (OUT / 'media-qa.json').write_text(json.dumps(qa, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in qa.items() if k != 'sync'}, indent=2))


if __name__ == '__main__':
    main()
