// Pure script unit test with minimal DOM doubles; no browser or navigation.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const page=fs.readFileSync('outputs/ryde-evaluation.html','utf8');
const scripts=[...page.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.strictEqual(scripts.length,1);
function element(data={}) {return {...data,handlers:{},attrs:{},addEventListener(n,f){this.handlers[n]=f},setAttribute(k,v){this.attrs[k]=v}}}
const buttons=[element({dataset:{case:'case-0'}}),element({dataset:{case:'case-1'}})];
const panels=[{id:'case-0',hidden:false},{id:'case-1',hidden:true}];
const target={open:false};const links=[element({hash:'#case-0-evidence-E-001'})];
const document={querySelectorAll(s){return {'[data-case]':buttons,'[role=tabpanel]':panels,'a.ref':links}[s]||[]},getElementById(id){return id==='case-0-evidence-E-001'?target:null}};
vm.runInNewContext(scripts[0][1],{document});
buttons[1].handlers.click();assert(panels[0].hidden);assert(!panels[1].hidden);
assert.strictEqual(buttons[1].attrs['aria-selected'],'true');
buttons[0].handlers.click();assert(!panels[0].hidden);assert(panels[1].hidden);
links[0].handlers.click();assert(target.open);
console.log('UI script unit checks passed: case switching, aria-selected, reference disclosure. Not a browser visual test.');
