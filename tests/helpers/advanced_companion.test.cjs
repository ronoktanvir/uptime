'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {Element,document} = require('./companion_dom.cjs');
const {create} = require('../../web/v4_ui.js');
const button = (root,name) => root.all('button').find(b => b.textContent === name);
const submit = form => form.listeners.submit({preventDefault(){}});
function setup(extra={}) {
  const root = new Element('main'), calls = [];
  const ui = create({document, reviewForms:true, getAccess:()=>({canWrite:true}), api:async(path,body)=>{
    calls.push({path,body}); return body === undefined ? {vendors:[]} : {state:'SHADOW'};
  }, ...extra});
  return {root,ui,calls};
}
test('wizard reviews exact bytes, invalidates edits and posts only after confirmation',async()=>{
  const {root,ui,calls}=setup(); await ui.render(root,'vendors');
  const form=root.all('form')[0];
  const fields=[...form.all('input'),...form.all('textarea'),...form.all('select')];
  const values={vendor_id:'new',name:'source',uri:'https://example.invalid/terms',classification:'public',text:'untrusted <script>',overlay:'{"account":"observed"}'};
  fields.forEach(f=>{f.value=values[f.name];});
  await submit(form); assert.equal(calls.length,1); assert.match(root.textContent,/Review exact local request/);
  fields.find(f=>f.name==='name').value='revised';
  await submit(form); assert.equal(calls.length,1,'programmatic changes also invalidate exact review');
  await submit(form); assert.equal(calls.length,2); assert.equal(calls[1].body.document.name,'revised');
  assert.equal(calls[1].body.document.text,'untrusted <script>');
});
test('successful mutation reloads state; a lost response does not erase uncertainty',async()=>{
  let refreshed=0;
  const s=setup({reloadAfterMutation:true,onRefresh:()=>{refreshed++;},api:async(path,body)=>body===undefined?{vendors:[{vendor_id:'x',actions:[{id:'approve',label:'Approve'}]}]}:{state:'APPROVED'}});
  await s.ui.render(s.root,'vendors'); await button(s.root,'Approve').listeners.click(); assert.equal(refreshed,1);
  const bad=setup({reloadAfterMutation:true,onRefresh:()=>{refreshed++;},api:async(path,body)=>{if(body!==undefined) throw Error('lost'); return {vendors:[{vendor_id:'x',actions:[{id:'approve',label:'Approve'}]}]};}});
  await bad.ui.render(bad.root,'vendors'); await button(bad.root,'Approve').listeners.click();
  assert.equal(refreshed,1); assert.match(bad.root.textContent,/outcome may be unknown/); assert.equal(button(bad.root,'Approve').disabled,true);
});
test('catalog preserves observed quarantine and credit states without inventing metrics',async()=>{
  const {root,ui,calls}=setup(); await ui.render(root,'catalog',{source_mode:'REPLAY',credit_sync:{journal:{quarantined:true,recorded_cents:0,actual_recovery:null}}});
  assert.equal(calls.length,0); assert.match(root.textContent,/quarantined true/); assert.match(root.textContent,/actual recovery Not provided/);
  assert.match(root.textContent,/Terms verification metrics not returned/);
  assert.deepEqual(root.all('a').map(a=>a.href),['#ramp','#vendors','#disputes','#dashboard','#lab','#regression']);
});
test('receipt actions reload the same correspondence case',async()=>{
  let reads=0;
  const s=setup({reloadAfterMutation:true,api:async(path,body)=>body===undefined?{id:'inbox-x',stage:++reads===1?'DRAFT':'REVIEWED',actions:[{id:'review',label:'Review'}]}:{}});
  await s.ui.inspect(s.root,'inbox-x'); await button(s.root,'Review').listeners.click();
  assert.equal(reads,2); assert.match(s.root.textContent,/REVIEWED/); assert.match(s.root.textContent,/untrusted evidence/);
});
const {companionPlan,companionRoute} = require('../../web/app.js');
test('explicit V3 and companion routes preserve primary Ramp fallback',()=>{
  for(const route of ['dashboard','lab','regression','vendors','disputes','advanced','disputes/inbox-x']) assert.equal(companionRoute(route),route);
  for(const route of ['','unknown','ramp/record']) assert.equal(companionRoute(route),'ramp');
});
test('provider plan never advertises unsupported writes or invents delivery',()=>{
  for(const entity of ['draft-bills','transactions','purchase-orders',null]) {
    const plan=companionPlan({object_type:entity,method:'POST',path:'/provider/path',required_scope:'write',delivery:'NOT_SENT',sources:['REPLAY']});
    assert.equal(plan.status,'UNSUPPORTED_ENTITY'); assert.equal(plan.method,undefined); assert.equal(plan.path,undefined);
    assert.equal(plan.delivery,'NOT_SENT'); assert.deepEqual(plan.sources,['REPLAY']);
  }
  assert.equal(companionPlan({object_type:'bills',delivery:'NOT_SENT'}).status,'READ_ONLY_PROPOSAL');
});
