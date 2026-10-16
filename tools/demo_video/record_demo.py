"""Record actual browser interactions with the Playwright CLI, timed to speech words."""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'outputs/demo-video-2026-10-16'
CAPTURE = ROOT/'output/playwright/video'
SESSION = 'ryde-demo'
BOOK = json.loads((OUT/'timeline.json').read_text(encoding='utf-8'))
REPORT = 'http://127.0.0.1:8775/runs/'
LIVE = json.loads((ROOT/'outputs/workflow-followups-2026-10-16/final-parallel-live/DISP-003.run.json').read_text(encoding='utf-8'))['run_id']
NOSHOW = json.loads((OUT/'offline/DISP-002.run.json').read_text(encoding='utf-8'))['run_id']
ROUTE = json.loads((OUT/'offline/DISP-001.run.json').read_text(encoding='utf-8'))['run_id']
S = lambda heading: 'section:has(> h3:text-is('+json.dumps(heading)+'))'
RESULT = S('Recommendation')
CALC = S('Calculations and open questions')
ADVOCATES = S('Advocate openings and responses')
ASSESS = S('How the Judge assesses both sides')

def cli(*args):
    command = ['npx.cmd','--yes','--package','@playwright/cli@0.1.22','playwright-cli','-s='+SESSION,*map(str,args)]
    proc = subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=150)
    with (CAPTURE/'recording.log').open('a',encoding='utf-8') as log:
        log.write('\nCOMMAND '+str(args)+'\n'+proc.stdout+'\n'+proc.stderr)
    if proc.returncode or '### Error' in proc.stdout:
        raise RuntimeError(proc.stdout[-5000:]+'\n'+proc.stderr[-1000:])
    return proc.stdout

def run_file(name,code):
    path=CAPTURE/(name+'.js')
    path.write_text(code,encoding='utf-8')
    return cli('run-code','--filename',path)

def cue(scene, phrase):
    norm=lambda w:re.sub(r'[^a-z0-9]','',w.lower())
    words=json.loads((OUT/'audio'/(scene['id']+'.words.json')).read_text())
    tokens=[norm(w['text']) for w in words]
    wanted=[norm(w) for w in phrase.split()]
    for i in range(len(tokens)-len(wanted)+1):
        if tokens[i:i+len(wanted)]==wanted:
            return round(words[i]['offset']/1e7+.3,3)
    raise ValueError(f"Missing speech cue {scene['id']}: {phrase}")

def action(phrase,kind,target,value=None):
    return dict(phrase=phrase,kind=kind,target=target,value=value)

plans={
 '01-hook': [('twelve Singapore','glow','#quote'),('sixteen dollars','glow','#charged'),('small fare difference','glow','#difference')],
 '02-value':[('riders perspective','glow','#rider'),('drivers perspective','glow','#driver'),('support teams','glow','#support')],
 '03-workflow':[('Select a case','glow','#select'),('Prepare a versioned','glow','#evidence'),('opening arguments','glow','#advocates'),('A Judge','glow','#judge'),('Programmatic checks','glow','#outcome')],
 '04-case':[('interactive report','point','.case-head'),('proposes a','focus',RESULT),('trace that result','point',RESULT+' a.ref[href="#case-0-evidence-E-024"]')],
 '05-evidence':[('Each fact','point',RESULT+' a.ref[href="#case-0-evidence-E-024"]'),('Clicking a reference','click',RESULT+' a.ref[href="#case-0-evidence-E-024"]'),('surge event','focus','#case-0-evidence-E-024'),('explicit false','text','#case-0-evidence-E-024 pre','"rider_notified": false')],
 '06-policy':[('open the policy reference','click',RESULT+' a.ref[href="#case-0-policy-P-RYDE-2.1-S3.3"]'),('Section three','focus','[id="case-0-policy-P-RYDE-2.1-S3.3"]'),('source excerpt','point','[id="case-0-policy-P-RYDE-2.1-S3.3"] pre')],
 '07-advocates':[('rider advocate','point',ADVOCATES+' .columns > div:first-child h3'),('driver advocate','point',ADVOCATES+' .columns > div:last-child h3'),('supporting records','point','#case-0-argument-opening-driver-claims-0 .ref')],
 '08-response':[('one response round','point',ADVOCATES+' .columns > div:first-child h4:text-is("Response to the other side")'),('The Judge records','focus',ASSESS),('A statement proves','point',ASSESS+' h4:text-is("Claim-by-claim assessment")')],
 '09-decision':[('sixteen fifty','point',CALC+' .metrics li:first-child'),('recommendation preserves','focus',RESULT),('partial refund','point',RESULT+' > p'),('does not move money','point',RESULT+' > p')],
 '10-no-show':[('five free minutes','point','.metrics li:has(b:text-is("Policy free-wait period"))'),('eight minute threshold','focus',CALC+' li:has(> b:text-matches("NO_SHOW_THRESHOLD_CLOCK_UNSPECIFIED"))'),('policy precedence','point',CALC+' li:has(> b:text-matches("POLICY_SOURCE_CONFLICT"))')],
 '11-route':[('four point three','point','.metrics li:has-text("Reported road distance")'),('two kilometers','focus',CALC+' li:has(> b:text-matches("ROUTE_DISTANCE_REQUIRES_HUMAN_REVIEW"))'),('person must','point',CALC+' li:has(> b:text-matches("ROUTE_DISTANCE_REQUIRES_HUMAN_REVIEW"))')],
 '12-workbench':[('select a case','select','#case','DISP-002'),('start processing','click','#start'),('recorded execution stages','focus','#runs'),('Saved live reports','point','#runs a[href="/runs/'+LIVE+'"]')],
 '13-supplement':[('upload a complete','upload','#raw',str((OUT/'synthetic-supplement-DISP-002.json').resolve())),('declare where','fill','#note','SYNTHETIC DEMONSTRATION ONLY: added one rider message. No new official evidence.'),('preview the exact changes','click','#preview'),('clearly labeled synthetic','text','#preview-output','SYNTHETIC DEMONSTRATION ONLY: I was waiting at the north entrance.'),('new snapshot','text','#preview-output','"new_snapshot_id"'),('old result','point','#report')],
 '14-human':[('reviewer','fill','#reviewer','Demo reviewer — not authenticated'),('the decision','point','#decision'),('the reason','fill','#reason','DEMONSTRATION ONLY. Policy clarification remains required; no outcome is being saved.'),('supporting references','check','#evidence input[value="E-003"]'),('Local records','check','#policies input[value="P-RYDE-2.1-S2.1"]'),('does not authenticate','point','#human')],
 '15-recovery':[('checkpointed','glow','#checkpoints'),('Calls active time','glow','#limits'),('provider failure','glow','#failure')],
 '16-evaluation':[('six fresh model calls','glow','#success'),('unsuccessful development attempts','glow','#limits')],
 '17-build':[('evidence and tools','glow','#data'),('advocate system','glow','#agents'),('Judge orchestration','glow','#orchestration')],
 '18-tips':[('JSON schemas','glow','#contracts'),('source hashes','glow','#sources'),('GitHub pull requests','glow','#review')],
 '19-close':[('riders','point','.pill:first-child'),('drivers','point','.pill:nth-child(2)'),('support teams','point','.pill:nth-child(3)')]
}

starts={'04-case':'.case-head','05-evidence':RESULT,'06-policy':RESULT,'07-advocates':ADVOCATES,
        '08-response':ADVOCATES+' .columns > div:first-child h4:text-is("Response to the other side")',
        '09-decision':CALC,'10-no-show':CALC,'11-route':CALC,
        '13-supplement':'main > section:nth-of-type(3)','14-human':'main > section:nth-of-type(4)'}

JS_HELPERS = r'''
  const focus = async (q, smooth=true) => {
    const locator=page.locator(q).first();
    await locator.evaluate((e,s)=>window.scrollTo({top:Math.max(0,e.getBoundingClientRect().top+window.scrollY-133),behavior:s?'smooth':'instant'}),smooth);
    if(smooth)await page.waitForTimeout(650);
  };
  const point = async q => {
    const loc=page.locator(q).first();let b=await loc.boundingBox();
    if(!b)throw Error('Missing visible target: '+q);
    if(b.y<112||b.y>830){await focus(q);b=await loc.boundingBox();}
    const x=b.x+Math.min(b.width/2,180),y=b.y+Math.min(b.height/2,65);
    await page.mouse.move(x,y,{steps:22});
    await page.evaluate(()=>document.querySelectorAll('.demo-focus').forEach(e=>e.classList.remove('demo-focus')));
    await loc.evaluate(e=>e.classList.add('demo-focus'));
    return {loc,x,y};
  };
'''

def prepare(scene):
    if scene['type']=='slide':
        url='http://127.0.0.1:8776/presentation.html?slide='+scene['slide'];badge='Hackathon prototype'
    elif scene['type']=='report':url=REPORT+LIVE;badge='Saved live run · 16 Oct 2026'
    elif scene['type']=='noshow':url=REPORT+NOSHOW;badge='Offline control demonstration · DISP-002'
    elif scene['type']=='route':url=REPORT+ROUTE;badge='Offline control demonstration · DISP-001'
    else:url='http://127.0.0.1:8775/';badge='Offline controls · no new model calls'
    if scene['id']=='01-hook':badge='Official sample · DISP-003'
    context={**scene,'badge':badge}
    setup='async page => {\n'+JS_HELPERS+f'\nawait page.goto({json.dumps(url)});\nawait page.waitForFunction(()=>!!window.demoScene);\nawait page.evaluate(s=>window.demoScene(s),{json.dumps(context)});\n'
    if scene['type']=='workbench':
        setup+='await page.waitForFunction(()=>document.querySelector("#runs").children.length>0);\n'
    if scene['id'] in ('13-supplement','14-human'):
        setup+=f'await page.locator("#parent").selectOption({json.dumps(NOSHOW)}); await page.waitForTimeout(400);\n'
    if scene['id'] in starts:setup+=f'await focus({json.dumps(starts[scene["id"]])},false);\n'
    else:setup+='await page.evaluate(()=>window.scrollTo({top:0,behavior:"instant"}));\n'
    setup+='await page.mouse.move(1830,870);await page.waitForTimeout(300);return {title:await page.title(),untranslated:await page.evaluate(()=>window.demoUntranslated())};\n}'
    run_file(scene['id']+'-setup',setup)
    cli('snapshot')
    cli('screenshot','--filename',CAPTURE/(scene['id']+'-start.png'))

def record(scene):
    prepare(scene)
    actions=[]
    for row in plans[scene['id']]:
        entry=action(*row);entry['at']=cue(scene,entry['phrase']);actions.append(entry)
    actions.sort(key=lambda a:a['at'])
    body='async page => {\n'+JS_HELPERS+'\n'
    body+='await page.evaluate(()=>{const p=document.createElement("div");p.id="demo-sync";document.body.append(p);});await page.waitForTimeout(320);await page.evaluate(()=>document.querySelector("#demo-sync").remove());\nconst started=Date.now();const timings=[];\n'
    body+='const actions='+json.dumps(actions)+';\n'+r'''
    for(const action of actions){
      await page.waitForTimeout(Math.max(0,action.at*1000-450-(Date.now()-started)));
      const q=action.target;
      if(action.kind==='focus'){
        await focus(q);await point(q);
      } else {
        if(action.kind==='text' && q==='#preview-output')await focus(q);
        const {loc,x,y}=await point(q);
        if(action.kind==='text'){
          const box=await loc.evaluate((e,value)=>{const w=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);let n;while(n=w.nextNode()){const i=n.nodeValue.indexOf(value);if(i>=0){const r=document.createRange();r.setStart(n,i);r.setEnd(n,i+value.length);let b=r.getBoundingClientRect();const outer=e.getBoundingClientRect();if(b.y<outer.y||b.bottom>outer.bottom){e.scrollTop+=b.y-outer.y-80;b=r.getBoundingClientRect();}return {x:b.x,y:b.y,width:b.width,height:b.height};}}throw Error('Text target missing');},action.value);
          await page.mouse.move(box.x+box.width+14,box.y+box.height*.5,{steps:16});
        }
        if(action.kind==='click'){
          await page.mouse.click(x,y);await page.waitForTimeout(300);
          if(q==='#preview'){
            await page.waitForFunction(()=>document.querySelector('#preview-output').textContent.includes('preview_id'));
            if(await page.locator('#commit').isDisabled())throw Error('Preview did not enable explicit rerun');
          }
          if(q==='#start')await page.waitForFunction(()=>document.querySelector('#message').textContent.includes('Started:'));
        }
        if(action.kind==='fill'){await loc.fill(action.value);}
        if(action.kind==='select'){await loc.selectOption(action.value);}
        if(action.kind==='upload'){await loc.setInputFiles(action.value);}
        if(action.kind==='check'){await loc.check();}
        if(action.kind==='glow'){await page.evaluate(()=>document.querySelectorAll('.glow').forEach(e=>e.classList.remove('glow')));await loc.evaluate(e=>e.classList.add('glow'));}
      }
      timings.push({cue:action.phrase,target:q,intended:action.at,completed:(Date.now()-started)/1000});
    }
    '''
    body+=f'await page.waitForTimeout(Math.max(0,{scene["duration"]}*1000+400-(Date.now()-started)));return timings;\n}}'
    cli('video-start',CAPTURE/(scene['id']+'.webm'),'--size=1920x1080','--fps=25')
    try:
        result=run_file(scene['id']+'-actions',body)
        (CAPTURE/(scene['id']+'-timing.txt')).write_text(result,encoding='utf-8')
    finally:
        cli('video-stop')
    print('RECORDED',scene['id'],scene['duration'],'seconds',flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--start',type=int,default=1);parser.add_argument('--end',type=int,default=19);parser.add_argument('--scenes',type=int,nargs='+');args=parser.parse_args()
    CAPTURE.mkdir(parents=True,exist_ok=True)
    # Validate every narration cue before starting the recorder.
    for scene in BOOK['scenes']:
        for row in plans[scene['id']]:cue(scene,row[0])
    cli('close')
    cli('open','http://127.0.0.1:8775/','--browser','msedge','--config',ROOT/'tools/demo_video/browser.config.json')
    cli('resize','1920','1080')
    run_file('initialize','async page => {await page.addInitScript({path:"tools/demo_video/demo-overlay.js"});}')
    selected=[BOOK['scenes'][i-1] for i in args.scenes] if args.scenes else BOOK['scenes'][args.start-1:args.end]
    for scene in selected:record(scene)

if __name__=='__main__':main()
