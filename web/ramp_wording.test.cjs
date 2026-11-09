const test=require('node:test');
const assert=require('node:assert/strict');
const {create}=require('./ramp_ui.js');
class Element {
  constructor(tag){this.tagName=tag;this.children=[];this.listeners={};this.attrs={};this._text='';this.value='';}
  set textContent(v){this._text=String(v);this.children=[];}
  get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
  append(...c){this.children.push(...c);}
  replaceChildren(...c){this._text='';this.children=c;}
  setAttribute(k,v){this.attrs[k]=v;}
  addEventListener(k,f){this.listeners[k]=f;}
  all(t){return this.children.flatMap(c=>[...(c.tagName===t?[c]:[]),...c.all(t)]);}
}
const document={createElement:t=>new Element(t)};
const row={id:'bill-1',provider_id:'native-1',provider_object_type:'bills',native_status:'OPEN',vendor:'Example vendor',
  title:'Synthetic gross invoice cap rehearsal',stage:'SIMULATION_ONLY',outcome:'ELIGIBLE',amount:'40.00',currency:'USD',
  provider_uri:'https://demo.ramp.com/bill-pay/bills/list/native-1'};
const data={records:[row],snapshot_status:{freshness:'HISTORICAL_REPLAY'},resources:[{name:'vendors',status:'TRUNCATED',complete:false}],
  credit_sync:{award_provenance:'SIMULATED_VENDOR',stage_sources:['SIMULATED_VENDOR','UNAVAILABLE']},writeback:{comment:'NOT_GRANTED'}};
function render(get){const root=new Element('main');const ui=create({document,api:async p=>get(p),onNavigate:()=>{}});return {root,ui};}

test('worklist codes read as ordinary, meaning-preserving wording; other codes stay exact',async()=>{
  const s=render(()=>data);await s.ui.render(s.root);const text=s.root.textContent;
  for(const expected of ['Saved capture (not live)','Invoice cap review','Scenario only, not a finding','Local counterparty, not a vendor','Vendors: partial list','NOT_GRANTED','UNAVAILABLE'])
    assert.ok(text.includes(expected),expected);
  assert.doesNotMatch(text,/synthetic|simulat|historical_replay/i);
  const open=s.root.all('a').find(a=>a.textContent==='Open in Ramp');
  assert.equal(open.href,'https://demo.ramp.com/bill-pay/bills/list/native-1');
  assert.equal(open.rel,'noopener noreferrer');assert.equal(open.attrs['aria-label'],'Open Example vendor in Ramp');
});

test('a record page leads with its native Ramp route; an unverified URL offers none',async()=>{
  const s=render(()=>({...row,native_workflow:{status:'NOT_SENT'}}));await s.ui.render(s.root,row.id);
  const head=s.root.children[1];
  assert.equal(head.all('a')[0].textContent,'Open record in Ramp');
  assert.equal(s.root.all('a').filter(a=>a.textContent==='Open record in Ramp').length,1);
  assert.ok(s.root.textContent.includes('Invoice cap review'));
  const t=render(()=>({...row,provider_uri:'https://ramp.example/bill'}));await t.ui.render(t.root,row.id);
  assert.equal(t.root.all('a').filter(a=>a.textContent==='Open record in Ramp').length,0);
  assert.ok(t.root.textContent.includes('Native destination unavailable'));
});
