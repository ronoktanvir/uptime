const test=require('node:test');
const assert=require('node:assert/strict');
const {create}=require('./workspace_ui.js');
class Element {
  constructor(tag){this.tagName=tag;this.children=[];this.listeners={};this.attrs={};this._text='';this.value='';this.disabled=false;}
  set textContent(v){this._text=String(v);this.children=[];}
  get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
  append(...c){this.children.push(...c);}
  replaceChildren(...c){this._text='';this.children=c;}
  setAttribute(k,v){this.attrs[k]=v;}
  addEventListener(k,f){this.listeners[k]=f;}
  all(t){return this.children.flatMap(c=>[...(c.tagName===t?[c]:[]),...c.all(t)]);}
}
const document={createElement:t=>new Element(t)};
const projection={vendor:'Northwind Cloud',contract:{title:'SLA',version:'v1',ref:'urn:sla',documents:[]},reviewer:{},months:[],
  price_finding:{},claim:{id:'claim-1',state:'AWARDED'},connection:{destination:'Local ledger'},
  ledger:{destination:'Local ledger',currency:'USD',bill:{},record_ids:{}},next_actions:[],audit:[],
  finance:{attention:[],stages:[],bill:{},ramp:{destination:'Local ledger',linked_record:null,note:'No Ramp bill is linked.'},sections:{}}};
const ANSWER={sentences:[{text:'Credits in this workspace are recorded in Local ledger.',citations:['ramp']}],
  citations:[{id:'ramp',label:'Destination',ref:null,section:'finance-ramp'}],abstained:false,scope_note:'Covers cited records.',as_of:'t'};
function mount(api){const root=new Element('main'),calls=[];const ui=create({document,api:async(...a)=>{calls.push(a);return api(...a);}});return {root,calls,ui};}
const suggestion=(root,name)=>root.all('button').find(b=>b.textContent===name);

test('suggested questions are offered as a labelled group of ordinary buttons',async()=>{
  const s=mount(()=>ANSWER);await s.ui.render(s.root,projection);
  const group=s.root.all('div').find(d=>d.className==='guide-suggestions');
  assert.equal(group.attrs.role,'group');assert.equal(group.attrs['aria-label'],'Suggested questions');
  assert.deepEqual(group.all('button').map(b=>b.textContent),['What needs my attention?','How was the January credit calculated?',
    'Why is March undetermined?','Did the credit reach Ramp?']);
  assert.ok(group.all('button').every(b=>b.type==='button'));
});

test('a suggestion fills the question, asks once through the read-only route and shows the cited answer',async()=>{
  let release;const s=mount((path,body)=>new Promise(r=>{release=()=>r(ANSWER);}));await s.ui.render(s.root,projection);
  const pending=suggestion(s.root,'Did the credit reach Ramp?').listeners.click();
  assert.equal(s.root.all('input')[0].value,'Did the credit reach Ramp?');
  assert.ok(s.root.all('button').filter(b=>b.className==='quiet suggestion').every(b=>b.disabled));
  await suggestion(s.root,'What needs my attention?').listeners.click();
  release();await pending;
  assert.deepEqual(s.calls,[['/api/workspace/guide',{question:'Did the credit reach Ramp?'}]]);
  assert.ok(s.root.textContent.includes('Credits in this workspace are recorded in Local ledger.'));
  assert.ok(s.root.all('button').filter(b=>b.className==='quiet suggestion').every(b=>!b.disabled));
});

test('suggestions are not offered without the server summary',async()=>{
  const s=mount(()=>ANSWER);await s.ui.render(s.root,{...projection,finance:undefined});
  assert.equal(suggestion(s.root,'Did the credit reach Ramp?'),undefined);
});
