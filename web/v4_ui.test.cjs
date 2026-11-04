'use strict';
// A behavioral DOM harness: no browser-layout or browser-auth claims.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {create, parseJSON} = require('./v4_ui.js');
class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.listeners = {}; this.attrs = {}; this.value = ''; this._text = ''; }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text + this.children.map(n => n.textContent).join(' '); }
  append(...nodes) { this.children.push(...nodes); }
  prepend(...nodes) { this.children.unshift(...nodes); }
  replaceChildren(...nodes) { this._text = ''; this.children = nodes; }
  setAttribute(k,v) { this.attrs[k] = v; }
  addEventListener(k,f) { this.listeners[k] = f; }
  all(tag) { return this.children.flatMap(n => [...(n.tagName === tag ? [n] : []), ...n.all(tag)]); }
  reportValidity() { return [...this.all('input'), ...this.all('textarea'), ...this.all('select')].every(n => !n.required || n.value); }
}
const document = {createElement: tag => new Element(tag)};
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;}); return {resolve,reject,promise}; };
function setup({write=false, get, post} = {}) {
  const root = new Element('main'), requests = [];
  const state = {identity:'reviewer-from-server',enrollment:'verified',gate:'passed',canWrite:write};
  const ui = create({document, getAccess:() => state, api:async (path,body) => {
    requests.push({path,body});
    if (body !== undefined) return post ? post(path,body) : {receipt_id:'receipt-test',sources:['FIXTURE']};
    return get ? get(path) : {vendors:[{vendor_id:'vendor/independent',revision:3, sources:['SYNTHETIC_CUSTOMER'],actions:[{id:'activate/3',label:'Activate reviewed version'}]}]};
  }});
  return {root,requests,state,ui};
}
const findButton = (root,text) => root.all('button').find(n => n.textContent === text);
const findForm = (root,text) => root.all('form').find(n => n.all('button').some(b => b.textContent === text));
function fill(form, values) { [...form.all('input'),...form.all('textarea'),...form.all('select')].forEach(n => {n.value=values[n.name] ?? '';}); }
const submit = form => form.listeners.submit({preventDefault(){}});
const intake = {vendor_id:'new/vendor',name:'Source record',uri:'https://terms.invalid/version',classification:'public',text:'<img src=x onerror=bad()>',overlay:'{"account":"customer-a","currency":"USD"}'};

test('starts read-only even with returned actions; fields contain no sample values', async () => {
  const {root,ui,requests} = setup(); await ui.render(root,'vendors');
  assert.match(root.textContent,/Read-only/);
  assert.ok(root.all('button').filter(b=>b.type==='submit').every(b=>b.disabled));
  const activation = findButton(root,'Activate reviewed version'); assert.equal(activation.disabled,true);
  await activation.listeners.click();
  assert.equal(requests.length,1);
  assert.ok([...root.all('input'),...root.all('textarea')].every(n=>n.value===''));
});
test('vendor intake sends exact separate public document and overlay through injected client', async () => {
  const {root,ui,requests} = setup({write:true}); await ui.render(root,'vendors');
  const f = findForm(root,'Generate candidate'); fill(f,intake); await submit(f);
  const r = requests.at(-1);
  assert.equal(r.path,'/api/vendors/new%2Fvendor/candidates');
  assert.deepEqual(r.body,{document:{name:intake.name,uri:intake.uri,classification:intake.classification,text:intake.text},overlay:{account:'customer-a',currency:'USD'}});
  assert.equal('role' in r.body,false); assert.match(root.textContent,/receipt-test/);
  assert.equal(findButton(root,'Activate reviewed version').disabled,true,'requires reconciliation after mutation');
});
test('invalid JSON never sends a request and leaves form data intact', async () => {
  const {root,ui,requests} = setup({write:true}); await ui.render(root,'vendors');
  const f = findForm(root,'Generate candidate'); fill(f,{...intake,overlay:'not JSON'}); await submit(f);
  assert.equal(requests.length,1); assert.match(root.textContent,/Enter valid JSON for overlay/);
  assert.equal(f.all('textarea').find(n=>n.name==='text').value,intake.text);
  assert.throws(()=>parseJSON('[]','overlay'),/JSON object/);
  assert.throws(()=>parseJSON('[]','tests'),/non-empty/);
});
test('test revision is server supplied; money strings remain exact', async () => {
  const {root,ui,requests} = setup({write:true}); await ui.render(root,'vendors');
  const f = findForm(root,'Submit independent tests');
  const tests = [{name:'independent boundary',facts:{monthly_fee_cents:'900719925474099300'},expected:{outcome:'INELIGIBLE',amount:'0.00'}}];
  fill(f,{tests:JSON.stringify(tests)}); await submit(f);
  assert.deepEqual(requests.at(-1),{path:'/api/vendors/vendor%2Findependent/tests',body:{revision:3,tests}});
});
test('active evaluation uses provided facts without invented vendor, outcome or award', async () => {
  const {root,ui,requests} = setup({write:true}); await ui.render(root,'vendors');
  const f = findForm(root,'Evaluate into a case'); fill(f,{facts:'{"account":"new-account","month":"2026-10","monthly_fee_cents":0}'}); await submit(f);
  assert.deepEqual(requests.at(-1),{path:'/api/vendors/vendor%2Findependent/evaluate',body:{facts:{account:'new-account',month:'2026-10',monthly_fee_cents:0}}});
});
test('returned action IDs are encoded and POST has no client authority', async () => {
  const {root,ui,requests} = setup({write:true}); await ui.render(root,'vendors');
  await findButton(root,'Activate reviewed version').listeners.click();
  assert.deepEqual(requests.at(-1),{path:'/api/vendors/vendor%2Findependent/actions/activate%2F3',body:{}});
});
test('write guard rechecks revoked access even for previously rendered buttons', async () => {
  const {root,ui,state,requests} = setup({write:true}); await ui.render(root,'vendors');
  state.canWrite=false; await findButton(root,'Activate reviewed version').listeners.click();
  assert.equal(requests.length,1); ui.refreshAccess(); assert.equal(findButton(root,'Activate reviewed version').disabled,true);
});
test('inflight mutations suppress duplicates; lost responses require successful refresh', async () => {
  const pending=deferred(); const {root,ui,requests}=setup({write:true,post:()=>pending.promise});
  await ui.render(root,'vendors'); const b=findButton(root,'Activate reviewed version');
  const first=b.listeners.click(); await b.listeners.click(); assert.equal(requests.length,2);
  pending.reject(new Error('do not leak response internals')); await first;
  assert.match(root.textContent,/outcome may be unknown/); assert.doesNotMatch(root.textContent,/response internals/);
  await b.listeners.click(); assert.equal(requests.length,2);
  await findButton(root,'Refresh server state').listeners.click(); assert.equal(findButton(root,'Activate reviewed version').disabled,false);
});
test('stale navigation results cannot replace a later view and unmounted actions cannot send', async () => {
  const d=deferred(); const {root,ui,requests}=setup({write:true,get:()=>d.promise});
  const p=ui.render(root,'vendors'); await ui.render(root,'portfolio',{portfolio:{label:'current',sources:['FIXTURE'],metrics:{awarded:'0.00'}}});
  d.resolve({vendors:[{vendor_id:'stale'}]}); await p; assert.doesNotMatch(root.textContent,/stale/);
  const s=setup({write:true}); await s.ui.render(s.root,'vendors'); const b=findButton(s.root,'Activate reviewed version'); s.ui.unmount(s.root); await b.listeners.click(); assert.equal(s.requests.length,1);
});
test('correspondence setup sends scoped identity only and has no event/service credential form', async () => {
  const {root,ui,requests}=setup({write:true,get:()=>({claims:[]})}); await ui.render(root,'disputes');
  const f=findForm(root,'Create scoped case'); const values=Object.fromEntries(f.all('input').map(n=>[n.name,'value-'+n.name])); fill(f,values); await submit(f);
  const {claim_id,...scope}=values;
  assert.deepEqual(requests.at(-1),{path:'/api/correspondence/claims',body:{claim_id,scope}});
  assert.ok(!root.all('input').some(n=>/secret|token|role|award|message/.test(n.name)));
  assert.ok(requests.every(r=>!r.path.endsWith('/events'))); assert.match(root.textContent,/CLI ingestion/);
});
test('case inspector shows receipt timeline, exact source, IDs, unknowns and safe text', async () => {
  const data={claim_id:'case/a',sources:['SIMULATED_VENDOR'],events:[{receipt_id:'receipt-11',text:'<script>bad()</script>'}],bill_id:'bill-17',application_id:null,financials:{awarded:'0.00'},actions:[{id:'review/packet',label:'Review packet'}],service_secret:'NEVER-RENDER'};
  const {root,ui,requests}=setup({write:true,get:()=>data}); await ui.inspect(root,'case/a');
  assert.equal(requests[0].path,'/api/correspondence/claims/case%2Fa');
  for(const value of ['receipt-11','bill-17','SIMULATED_VENDOR','Not provided','0.00','<script>bad()</script>']) assert.ok(root.textContent.includes(value));
  assert.equal(root.all('script').length,0); assert.doesNotMatch(root.textContent,/NEVER-RENDER/);
  await findButton(root,'Review packet').listeners.click(); assert.deepEqual(requests.at(-1),{path:'/api/correspondence/claims/case%2Fa/actions/review%2Fpacket',body:{}});
});
test('portfolio comparison preserves exact decimals, zero, unknown and server cohorts', async () => {
  const {root,ui,requests}=setup(); await ui.render(root,'portfolio',{portfolio:{label:'All accounts',sources:['LIVE_RAMP_SANDBOX'],metrics:{applied:'0.00',awarded:null}},seeded:{label:'Named rehearsal',sources:['FIXTURE'],metrics:{awarded:'9007199254740993.01'}}});
  for(const text of ['All accounts','Named rehearsal','0.00','Not provided','9007199254740993.01','FIXTURE','LIVE_RAMP_SANDBOX']) assert.ok(root.textContent.includes(text));
  assert.equal(requests.length,0);
});
test('failed reads expose no writable intake, no error details, and unknown provenance is explicit', async () => {
  const s=setup({write:true,get:()=>{throw new Error('sensitive diagnostic');}}); await s.ui.render(s.root,'vendors');
  assert.equal(s.root.all('form').length,0); assert.match(s.root.textContent,/State unavailable/); assert.doesNotMatch(s.root.textContent,/sensitive diagnostic/);
  await s.ui.render(s.root,'case',{id:'missing-source'}); assert.match(s.root.textContent,/Provenance unknown/);
});
test('extension uses no transport, browser storage, HTML injection or inline styles', () => {
  const source=fs.readFileSync(__dirname+'/v4_ui.js','utf8');
  assert.doesNotMatch(source,/\bfetch\s*\(|localStorage|sessionStorage|innerHTML|\.style\s*[.=]|setAttribute\(['"]on/);
  assert.match(source,/global\.UptimeV4 = api/);
});

test('catalog summary loads reviewer-bound detail before rendering version actions', async () => {
  const {root,ui,requests}=setup({write:true,get:path => path === '/api/vendors' ? {vendors:[{vendor_id:'new-vendor',revision:7}]} : {vendor_id:'new-vendor',revision:7,state:'APPROVED',actions:[{id:'activate~7~digest',label:'Activate version 7'}]}});
  await ui.render(root,'vendors');
  assert.deepEqual(requests.map(r=>r.path),['/api/vendors','/api/vendors/new-vendor']);
  await findButton(root,'Activate version 7').listeners.click();
  assert.deepEqual(requests.at(-1),{path:'/api/vendors/new-vendor/actions/activate~7~digest',body:{}});
});
test('failed vendor detail keeps that vendor read-only without hiding intake', async () => {
  const {root,ui}=setup({write:true,get:path=>{ if(path==='/api/vendors') return {vendors:[{vendor_id:'unavailable',revision:4}]}; throw new Error('unavailable'); }});
  await ui.render(root,'vendors'); assert.match(root.textContent,/Vendor details unavailable/);
  assert.equal(findButton(root,'Evaluate into a case'),undefined);
  assert.ok(findForm(root,'Generate candidate'));
});
test('unsupported projection requests never fall through to an empty API route', async () => {
  const {ui,root,requests}=setup(); await assert.rejects(ui.render(root,'portfolio'),/projection is required/);
  assert.equal(requests.length,0);
});
