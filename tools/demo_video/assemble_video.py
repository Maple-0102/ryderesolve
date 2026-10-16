"""Align recorded interactions to narration, render captions, and inspect media metadata."""
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/demo-video-2026-10-16-v2'
CAPTURE=ROOT/'output/playwright/video-v2'

def run(args,**kwargs):
    return subprocess.run(args,check=True,**kwargs)

def sync_start(path):
    # An editorial 32px magenta pulse precedes timed browser interactions.
    # Locate its final frame, then remove it and all CLI startup latency.
    pixels=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-t','8','-vf','crop=8:8:0:0,format=rgb24','-f','rawvideo','pipe:1'])
    marks=[]
    for i in range(len(pixels)//192):
        r,g,b=pixels[i*192:i*192+3]
        if r>200 and g<60 and b>200:marks.append(i)
    if not marks:raise ValueError('Missing recording synchronization pulse: '+str(path))
    return (max(marks)+1)/25

def seconds(stamp):
    h,m,s=re.split('[:,]',stamp)[:3]
    ms=stamp.split(',')[1]
    return int(h)*3600+int(m)*60+int(s)+int(ms)/1000

def ass_time(t):
    centis=round(t*100)
    return f'{centis//360000}:{centis//6000%60:02}:{centis//100%60:02}.{centis%100:02}'

def make_ass():
    blocks=(OUT/'RydeResolve-English.srt').read_text(encoding='utf-8').strip().split('\n\n')
    lines=['[Script Info]','ScriptType: v4.00+','PlayResX: 1920','PlayResY: 1080','WrapStyle: 2','ScaledBorderAndShadow: yes','','[V4+ Styles]',
      'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
      'Style: Default,Segoe UI,38,&H00F7FAFC,&H00F7FAFC,&H00162732,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,90,90,37,1','','[Events]',
      'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    last=0
    for block in blocks:
        rows=block.splitlines();a,b=rows[1].split(' --> ');text='\\N'.join(rows[2:])
        t0,t1=seconds(a),seconds(b)
        assert t1>t0>=last and len(rows[2:])<=2,(a,b,text)
        last=t0
        lines.append(f'Dialogue: 0,{ass_time(t0)},{ass_time(t1)},Default,,0,0,0,,{text}')
    (OUT/'RydeResolve-English.ass').write_text('\n'.join(lines)+'\n',encoding='utf-8-sig')
    return len(blocks)

def main():
    book=json.loads((OUT/'timeline.json').read_text(encoding='utf-8'))
    clips=OUT/'rendered-clips';clips.mkdir(exist_ok=True)
    audit=[]
    for scene in book['scenes']:
        source=CAPTURE/(scene['id']+'.webm')
        offset=sync_start(source)
        dest=clips/(scene['id']+'.mkv')
        length=scene['duration'];frames=round(length*25)
        filters=f'[0:v]setpts=PTS-STARTPTS,fade=t=in:st=0:d=0.16,fade=t=out:st={length-.16}:d=0.16[v];[1:a]adelay=300:all=1,apad,atrim=duration={length},asetpts=PTS-STARTPTS[a]'
        run(['ffmpeg','-y','-v','error','-ss',str(offset),'-i',str(source),'-i',str(OUT/'audio'/(scene['id']+'.mp3')),
             '-filter_complex',filters,'-map','[v]','-map','[a]','-frames:v',str(frames),'-t',str(length),'-r','25',
             '-c:v','libx264','-threads','4','-preset','fast','-crf','19','-pix_fmt','yuv420p','-c:a','pcm_s16le','-ar','48000',str(dest)])
        audit.append({'scene':scene['id'],'trim_start':offset,'duration':length,'frames':frames})
        print('ASSEMBLED',scene['id'],'sync',offset,flush=True)
    (OUT/'concat.txt').write_text('\n'.join("file '"+(clips/(s['id']+'.mkv')).as_posix()+"'" for s in book['scenes']),encoding='utf-8')
    count=make_ass()
    meta=[';FFMETADATA1','title=RydeResolve - Every dispute deserves an explanation','comment=English narrated prototype demonstration. Saved live results and offline controls are labeled.']
    for s in book['scenes']:
        meta.extend(['[CHAPTER]','TIMEBASE=1/1000',f"START={round(s['start']*1000)}",f"END={round((s['start']+s['duration'])*1000)}",'title='+s['title']])
    (OUT/'chapters.ffmetadata').write_text('\n'.join(meta),encoding='utf-8')
    dest=OUT/'RydeResolve-Demo-English-1080p.mp4'
    with (OUT/'encoding.log').open('w',encoding='utf-8') as log:
        run(['ffmpeg','-y','-hide_banner','-f','concat','-safe','0','-i','concat.txt','-i','chapters.ffmetadata','-map','0:v','-map','0:a','-map_metadata','1','-map_chapters','1',
          '-vf','ass=RydeResolve-English.ass','-af','loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json',
          '-c:v','libx264','-threads','4','-preset','medium','-crf','20','-pix_fmt','yuv420p','-r','25',
          '-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-movflags','+faststart',dest.name],cwd=OUT,stdout=log,stderr=log)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-show_chapters','-of','json',str(dest)],text=True))
    video=next(s for s in probe['streams'] if s['codec_type']=='video')
    audio=next(s for s in probe['streams'] if s['codec_type']=='audio')
    total=float(probe['format']['duration'])
    assert 300<=total<=480 and video['width']==1920 and video['height']==1080
    assert video['r_frame_rate']=='25/1' and video['codec_name']=='h264' and audio['codec_name']=='aac'
    qa={'source_commit':book['source_commit'],'workbench_source_commit':book['workbench_source_commit'],'duration_seconds':total,'width':video['width'],'height':video['height'],'fps':25,
        'video_codec':video['codec_name'],'audio_codec':audio['codec_name'],'size_bytes':dest.stat().st_size,
        'subtitle_cues':count,'chapter_count':len(probe['chapters']),'sync':audit,'visual_qa':'pending'}
    (OUT/'media-qa.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')
    print(json.dumps(qa,indent=2),flush=True)

if __name__=='__main__':main()
