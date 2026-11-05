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
