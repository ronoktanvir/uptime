const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {create,providerURL,matches,clean}=require('./ramp_ui.js');
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
const row={id:'opaque/a?#',provider_id:'native-id',provider_object_type:'bills',native_status:'OPEN',vendor:'Example vendor',sources:['LIVE_RAMP_SANDBOX'],amount:'9007199254740993.01',currency:'USD'};
function setup(get){const root=new Element('main'),requests=[],routes=[];const ui=create({document,api:async(...args)=>{requests.push(args);return get(...args);},onNavigate:r=>routes.push(r)});return{root,requests,routes,ui};}
const click=(root,name)=>root.all('button').find(b=>b.textContent===name).listeners.click();
test('native links accept only an exact HTTPS sandbox provider destination',()=>{
  assert.equal(providerURL('https://demo.ramp.com/bills/id'),'https://demo.ramp.com/bills/id');
  for(const url of ['javascript:alert(1)','https://demo.ramp.com.evil/bill','https://demo.ramp.com@evil/bill','https://user:pw@demo.ramp.com/bill','http://demo.ramp.com/bill','//demo.ramp.com/bill','https://demo.ramp.com:444/bill','https://ramp.com/bill','https://demo.ramp.com/bill?access_token=private',null]) assert.equal(providerURL(url),null);
});
test('default unpaid filter excludes paid, unknown and non-bill records; all remain accessible',()=>{
  assert.ok(matches(row,'unpaid',''));
  for(const r of [{...row,native_status:'PAID'},{...row,native_status:null},{...row,provider_object_type:'transactions'}]){assert.equal(matches(r,'unpaid',''),false);assert.ok(matches(r,'all',''));}
  assert.ok(matches({...row,provider_object_type:'purchase_orders'},'purchase_orders','native-id'));
});
test('pagination bounds 1000 records while all types are selectable; source and money stay exact',async()=>{
  const s=setup(()=>({records:Array.from({length:1000},(_,i)=>({...row,id:String(i)})),snapshot_status:{freshness:'STALE'},resources:[{name:'bills',status:'TRUNCATED',complete:false,count:1000,issues:['page limit']}],writeback:{comment:'NOT_GRANTED'}}));
  await s.ui.render(s.root);assert.equal(s.root.all('tbody')[0].all('tr').length,25);assert.match(s.root.textContent,/1000 of 1000/);
  for(const text of ['STALE','TRUNCATED','NOT_GRANTED','9007199254740993.01'])assert.ok(s.root.textContent.includes(text));
  await click(s.root,'Next page');assert.match(s.root.textContent,/Page 2 of 40/);
  await s.root.all('button').find(b=>b.className==='case-link').listeners.click();assert.equal(s.routes[0],'ramp/25');
  const select=s.root.all('select')[0];select.value='transactions';select.listeners.change();assert.match(s.root.textContent,/No matching records/);
  select.value='all';select.listeners.change();assert.match(s.root.textContent,/Page 1 of 40/);
});
test('detail and plan are encoded GETs, never POST; receipt is scoped and unsafe link stays absent',async()=>{
  const s=setup(path=>path.endsWith('/workflow')?{status:'NO_DISCUSSION_ENDPOINT',delivery:'NOT_SENT'}:{...row,provider_uri:'javascript:bad()',finding_kind:'SYNTHETIC_INVOICE_CAP',evidence:[{label:'<script>bad()</script>',access_token:'OMIT'}]});
  await s.ui.render(s.root,row.id);await click(s.root,'Inspect finding plan');
  assert.deepEqual(s.requests,[['/api/ramp/records/opaque%2Fa%3F%23'],['/api/ramp/records/opaque%2Fa%3F%23/workflow']]);
  assert.match(s.root.textContent,/Price cap review/);assert.doesNotMatch(s.root.textContent,/SYNTHETIC_INVOICE_CAP/);assert.match(s.root.textContent,/Contract finding/);assert.match(s.root.textContent,/NO_DISCUSSION_ENDPOINT/);assert.match(s.root.textContent,/scoped provider readback/);
  assert.equal(s.root.all('a').length,0);assert.equal(s.root.all('script').length,0);assert.doesNotMatch(s.root.textContent,/OMIT/);
});
test('detail envelope preserves evidence, native projection and provider destination',async()=>{
  const s=setup(()=>({case:row,evidence:[{ref:'evidence-test'}],native_projection:{id:'native-test',raw:{ssn:'OMIT'}},native_workflow:{delivery:'ACCEPTED'},provider_uri:'https://demo.ramp.com/bills/native-test'}));
  await s.ui.render(s.root,row.id);assert.match(s.root.textContent,/evidence-test/);assert.match(s.root.textContent,/ACCEPTED/);assert.doesNotMatch(s.root.textContent,/OMIT/);assert.equal(s.root.all('a')[0].href,'https://demo.ramp.com/bills/native-test');
});
test('unmount invalidates late reads and detached plan buttons',async()=>{
  let resolve;const s=setup(()=>new Promise(r=>{resolve=r;}));const pending=s.ui.render(s.root);s.ui.unmount();s.root.textContent='New view';resolve({records:[row]});await pending;assert.equal(s.root.textContent,'New view');
  const d=setup(()=>row);await d.ui.render(d.root,row.id);d.ui.unmount();await click(d.root,'Inspect finding plan');assert.equal(d.requests.length,1);
});
test('errors hide transport internals and unauthorized reads propagate to existing sign-in',async()=>{
  const s=setup(()=>{throw new Error('PRIVATE DIAGNOSTIC');});await s.ui.render(s.root);assert.match(s.root.textContent,/Ramp state unavailable/);assert.doesNotMatch(s.root.textContent,/PRIVATE DIAGNOSTIC/);
  const u=setup(()=>{throw Object.assign(new Error('expired'),{status:401});});await assert.rejects(u.ui.render(u.root),{status:401});
  assert.deepEqual(clean({nested:{credential:'OMIT',raw_response:'OMIT',safe:0}}),{nested:{safe:0}});
});
test('client uses injected auth, text nodes and no embedded provider or direct transport',()=>{
  const source=fs.readFileSync(__dirname+'/ramp_ui.js','utf8');assert.doesNotMatch(source,/\bfetch\s*\(|innerHTML|iframe|localStorage|sessionStorage|\.style\s*[.=]|setAttribute\(['"]on/);
});

const ctx={business_id:'1569e402-460e-4952-adad-9df27db628a0',object_type:'bills',object_id:'native-id',vendor_id:'vendor-1',vendor_name:'DocuSign',
  entity_id:'entity-1',invoice_number:'INV-1001',amount:{currency:'USD',amount:'840'},status:'OPEN',status_summary:'APPROVAL_PENDING',approval_status:'PENDING',
  observed_at:'2026-11-09T12:35:33.038627+00:00',capture_checksum:'c',ramp_link:{url:'https://demo.ramp.com/bill-pay/bills/list/native-id',basis:'OPERATOR_OBSERVED_URL'},
  agreement_binding:{status:'NONE',contract_id:null,binding_digest:null},finding_attachable:false,
  discussion:[{comment_id:'376563cf',created_at:'2026-11-08T01:46:45+00:00',attribution:'PERSON_POSTED_VERIFIED_READBACK'}],
  credit_links:{status:'NO_APPLIED_CREDITS',applied_verified_minor:0},native_confirmation:'RAMP_READ_ONLY',actual_recovery:null};
const partial={account_complete:false,observed_at:'2026-11-05T00:36:21+00:00',incomplete_lists:['transactions'],
  resources:[{name:'bills',retained:6,listed:6,has_next:false},{name:'transactions',retained:12,listed:40,has_next:true}]};
test('a partial capture says what is missing and is never presented as the complete account',async()=>{
  const s=setup(()=>({records:[{...row,ramp_context:ctx}],capture:partial,resources:[]}));await s.ui.render(s.root);
  assert.match(s.root.textContent,/Read from Ramp 2026-11-05 00:36 UTC\. Partial capture\. Card transactions: 12 kept of 40 listed, more remain in Ramp\. This is not the complete account\./);
  const done=setup(()=>({records:[],capture:{...partial,account_complete:true,incomplete_lists:[]},resources:[]}));await done.ui.render(done.root);
  assert.match(done.root.textContent,/read to the end/);assert.doesNotMatch(done.root.textContent,/Partial capture/);
});
test('rows show vendor name, invoice and a verified link; a missing name is stated, never inferred',async()=>{
  const s=setup(()=>({records:[{...row,ramp_context:ctx},{...row,id:'b2',provider_uri:null,ramp_context:{...ctx,vendor_name:null,invoice_number:null,ramp_link:null}}],resources:[]}));
  await s.ui.render(s.root);const text=s.root.textContent;
  for(const expected of ['DocuSign','Invoice: INV-1001','Vendor ID: vendor-1','Ramp status: APPROVAL_PENDING','Vendor name not captured','Invoice: not captured'])assert.ok(text.includes(expected),expected);
  const links=s.root.all('a');assert.equal(links.length,1);assert.equal(links[0].href,'https://demo.ramp.com/bill-pay/bills/list/native-id');
  assert.equal(links[0].attrs['aria-label'],'Open DocuSign in Ramp');
  const unsafe=setup(()=>({records:[{...row,provider_uri:null,ramp_context:{...ctx,ramp_link:{url:'https://evil.example/x',basis:'OPERATOR_OBSERVED_URL'}}}],resources:[]}));
  await unsafe.ui.render(unsafe.root);assert.equal(unsafe.root.all('a').length,0);
});
test('a finding amount is withheld on a Ramp record without an exact agreement binding',async()=>{
  const s=setup(()=>({records:[{...row,amount:'1000.00',ramp_context:ctx}],resources:[]}));await s.ui.render(s.root);
  assert.match(s.root.textContent,/Withheld: no agreement is bound to this Ramp record/);assert.doesNotMatch(s.root.textContent,/1000\.00/);
  const bound=setup(()=>({records:[{...row,amount:'1000.00',ramp_context:{...ctx,finding_attachable:true,agreement_binding:{status:'BOUND',contract_id:'MSA 7'}}}],resources:[]}));
  await bound.ui.render(bound.root);assert.match(bound.root.textContent,/USD 1000\.00/);
});
test('record page shows exact Ramp identity, freshness, link basis and person attribution; no local confirmation',async()=>{
  const s=setup(()=>({...row,provider_uri:null,ramp_context:ctx}));await s.ui.render(s.root,row.id);
  const text=s.root.textContent;
  for(const expected of ['Ramp record','DocuSign','INV-1001','USD 840','APPROVAL_PENDING','2026-11-09 12:35 UTC','observed in Ramp by a person',
    'Posted by a person in Ramp; Uptime read it back on this bill','376563cf','No agreement bound to this record','NO_APPLIED_CREDITS',
    'A local ledger entry is never shown here as a Ramp confirmation','No agreement is bound to this Ramp record'])assert.ok(text.includes(expected),expected);
  assert.equal(s.root.all('a').filter(a=>a.textContent==='Open record in Ramp')[0].href,'https://demo.ramp.com/bill-pay/bills/list/native-id');
  assert.equal(s.root.children[1].className,'page-head');
});
