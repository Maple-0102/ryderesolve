// Script interaction checks with DOM/fetch doubles; no visual-browser claim.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const page=fs.readFileSync('ryde_resolve/workbench.html','utf8');
const script=[...page.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)][0][1].replace('__PAID__','true');
class Element {
  constructor(tag='div'){this.tag=tag;this.children=[];this.handlers={};this.value='';this.files=[];this.dataset={};this.disabled=false;this.checked=false;this.textContent='';}
  addEventListener(k,fn){this.handlers[k]=fn;}
  append(...items){for(const i of items){this.children.push(i);if(this.tag==='select'&&!this.value)this.value=i.value;}}
  replaceChildren(...items){this.children=[];this.value='';this.append(...items);}
  get options(){return this.children;}
  querySelectorAll(q){return this.children.filter(c=>q==='label'?c.tag==='label':c.tag==='input'&&c.checked);}
  remove(){}
}
const elements=Object.fromEntries([...page.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],new Element()]));
elements.parent.tag='select';elements.case.value='DISP-003';elements.kind.value='synthetic';
let calls=[],deferredPreview=null;
const ctx=vm.createContext({document:{getElementById:id=>elements[id],createElement:tag=>new Element(tag),createTextNode:text=>text},setInterval(){},console,
  fetch:async(path,options)=>{const data=options?.body?JSON.parse(options.body):null;calls.push({path,data});
    let out=[];
    if(path==='/api/runs')out=[{case_id:'DISP-001',run_id:'parent',execution_status:'completed',decision:'escalate',can_supplement:true,timeline:[]}];
    else if(path.endsWith('/refs'))out={evidence:[{id:'E-001',text:'Recorded source'}],policy:[{id:'P-001',text:'Policy'}]};
    else if(path==='/api/supplement/preview')out=deferredPreview?await deferredPreview:{preview_id:'preview-1',changes:[]};
    else if(path==='/api/start'||path==='/api/supplement/commit')out={run_id:'new-run'};
    return {ok:true,json:async()=>out};
  }});
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  vm.runInContext(script,ctx);await tick();await tick();
  assert(calls.every(c=>!c.data),'Opening and refreshing page must not write or call a model');
  assert.equal(elements.parent.value,'parent');
  await elements.start.handlers.click();assert(!calls.some(c=>c.path==='/api/start'),'Missing paid confirmation must block start');
  elements['paid-confirm'].checked=true;await elements.start.handlers.click();
  assert(calls.find(c=>c.path==='/api/start').data.confirm_model_calls===true);assert(!elements['paid-confirm'].checked);
  elements.raw.files=[{size:12,text:async()=>'{"case":"demo"}'}];elements.note.value='synthetic note';
  let release;deferredPreview=new Promise(resolve=>release=resolve);
  const pending=elements.preview.handlers.click();await tick();elements.note.handlers.input();release({preview_id:'stale'});await pending;
  assert(elements.commit.disabled,'Changed input must invalidate an in-flight preview');
  deferredPreview=null;await elements.preview.handlers.click();assert(!elements.commit.disabled);
  const before=calls.filter(c=>c.path==='/api/supplement/commit').length;
  await elements.commit.handlers.click();assert.equal(calls.filter(c=>c.path==='/api/supplement/commit').length,before);
  elements['paid-confirm'].checked=true;await elements.commit.handlers.click();
  assert.equal(calls.filter(c=>c.path==='/api/supplement/commit').length,before+1);
  assert(elements.commit.disabled);assert(!elements['paid-confirm'].checked);
  console.log('Workbench script checks passed: read-only load, paid confirmation, stale preview rejection, explicit commit. No visual browser test.');
})().catch(e=>{console.error(e);process.exitCode=1;});
