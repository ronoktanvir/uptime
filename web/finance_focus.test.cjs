const test=require('node:test');
const assert=require('node:assert/strict');
const {create}=require('./workspace_ui.js');
const document={activeElement:null,createElement:t=>new Element(t)};
class Element {
  constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.listeners={};this.attrs={};this._text='';this.value='';this.disabled=false;}
  set textContent(v){this._text=String(v);this.children=[];}
  get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
  append(...c){this.children.push(...c);}
  replaceChildren(...c){this._text='';this.children=c;}
  setAttribute(k,v){this.attrs[k]=v;}
  addEventListener(k,f){this.listeners[k]=f;}
  focus(){document.activeElement=this;}
  all(t){return this.children.flatMap(c=>[...(c.tagName===t.toUpperCase()?[c]:[]),...c.all(t)]);}
}
const base={vendor:'Northwind Cloud',contract:{title:'SLA',version:'v1',ref:'urn:sla',documents:[]},reviewer:{},months:[],price_finding:{},
  claim:{id:'claim-1',month:'2026-01',state:'DRAFTED'},connection:{destination:'Local ledger'},ledger:{destination:'Local ledger',currency:'USD',bill:{},record_ids:{}},audit:[]};
const step=(label,id)=>({...base,next_actions:[{id,label,group:'claim'}]});
function mount(responses){const root=new Element('main'),calls=[];const queue=[...responses];
  const ui=create({document,api:async(path,body)=>{calls.push([path,body]);const r=queue.shift();if(r instanceof Error)throw r;return r;}});return {root,calls,ui};}
const button=(root,name)=>root.all('button').find(b=>b.textContent===name);

test('after a recorded action, focus moves to the next offered step',async()=>{
  const s=mount([{recorded:true},{workflow:step('File January claim','a2')}]);
  await s.ui.render(s.root,step('Approve January claim','a1'));
  document.activeElement=null;
  await button(s.root,'Approve January claim').listeners.click();
  assert.equal(document.activeElement,button(s.root,'File January claim'));
});

test('when no step remains, focus moves to the recovery heading',async()=>{
  const s=mount([{recorded:true},{workflow:{...base,next_actions:[]}}]);
  await s.ui.render(s.root,step('Apply credit to eligible invoice','a11'));
  await button(s.root,'Apply credit to eligible invoice').listeners.click();
  assert.equal(document.activeElement.tagName,'H2');assert.equal(document.activeElement.textContent,'January recovery');
});

test('a failed action does not move focus, and a later refresh does not steal it',async()=>{
  const s=mount([new Error('timeout')]);
  await s.ui.render(s.root,step('Approve January claim','a1'));
  const approve=button(s.root,'Approve January claim');approve.focus();
  await approve.listeners.click();
  assert.equal(document.activeElement,approve);
  assert.ok(s.root.textContent.includes('Refresh to check the recorded outcome before continuing.'));
  // The action is recorded but its reload fails: no focus moves now, and a later ordinary render does not move it either.
  const r=mount([{recorded:true},new Error('reload failed')]);
  await r.ui.render(r.root,step('Approve January claim','a1'));
  document.activeElement=null;
  await button(r.root,'Approve January claim').listeners.click();
  assert.equal(document.activeElement,null);
  await r.ui.render(r.root,step('File January claim','a2'));
  assert.equal(document.activeElement,null,'an ordinary render never moves focus');
});
