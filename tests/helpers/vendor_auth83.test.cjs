'use strict';
// Authored transport failures; real signed expired-session coverage is in Python.
const test = require('node:test'), assert = require('node:assert/strict');
const {Element,document} = require('./companion_dom.cjs');
const {create} = require('../../web/v4_ui.js');
const unauthorized = () => Object.assign(new Error('Expired disposable session'),{status:401});
const button = (root,name) => root.all('button').find(n=>n.textContent===name);
const click = (s,name) => button(s.root,name).listeners.click();
const status = root => root.all('p').find(n=>n.className==='v4-status')?.textContent;
const deferred = () => {let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const job = state => ({job_id:'job-kept',status:state,candidate_available:state==='SUCCEEDED',proposal:{clauses:[{quote:'Public source',field:'heading',value:null}]}});
function setup() {
  const root=new Element('main'),calls=[],timers=[];
  const s={root,calls,timers,fail:null,reads:job('QUEUED'),existing:null,unauthorized:0};
  s.ui=create({document,getAccess:()=>({canWrite:true,canDraft:true}),reviewForms:true,
    onUnauthorized:()=>{s.unauthorized++;root.replaceChildren(new Element('sign-in'));},schedule:fn=>timers.push(fn),
    api:async(path,body)=>{
      calls.push({path,body});
      if(s.fail?.(path,body)) throw unauthorized();
      if(path==='/api/vendors') return {vendors:[{vendor_id:'test-vendor',revision:3,actions:[{id:'review',label:'Review fixture'}]}]};
      if(path==='/api/correspondence/claims') return {claims:[]};
      if(path.endsWith('/proposal-access')) return {enabled:true,request_sha256:'a'.repeat(64),existing_job:s.existing};
      if(path.endsWith('/proposal-jobs')) return job('QUEUED');
      if(path.includes('/proposal-jobs/') && body===undefined) return s.reads;
      return {id:'inbox-fixture',state:'SHADOW',actions:[]};
    }});
  return s;
}
async function mount(s) {
  await s.ui.render(s.root,'vendors');
  const box=s.root.all('div').find(n=>String(n.className).includes('v4-generator'));
  const fields=Object.fromEntries([...box.all('input'),...box.all('select'),...box.all('textarea')].map(n=>[n.name,n]));
  for(const [k,v] of Object.entries({vendor_id:'fixture',name:'Public document',uri:'urn:authored:83',classification:'synthetic_public',
    profile:'monthly',attempt_nonce:'initial',text:'Public source'})) fields[k].value=v;
  return fields;
}
function signedOut(s) {
  assert.equal(s.unauthorized,1);
  assert.equal(s.root.children[0].tagName,'sign-in');
  assert.doesNotMatch(s.root.textContent,/uncertain|unavailable|unknown/);
}
for(const view of ['vendors','disputes','case']) test(view+' initial read401 requests sign-in once',async()=>{
  const s=setup();s.fail=()=>true;
  if(view==='case') await s.ui.inspect(s.root,'inbox-fixture'); else await s.ui.render(s.root,view);
  signedOut(s); assert.equal(s.calls.length,1);
});
test('vendor detail401 cannot become a partial read-only vendor card',async()=>{
  const s=setup();
  const ui=create({document,getAccess:()=>({canDraft:true}),onUnauthorized:()=>{s.unauthorized++;s.root.replaceChildren(new Element('sign-in'));},
    api:async(path)=>{s.calls.push({path});if(path==='/api/vendors') return {vendors:[{vendor_id:'x'}]};throw unauthorized();}});
  await ui.render(s.root,'vendors');signedOut(s);assert.equal(s.calls.length,2);
});
for(const kind of ['action','access','submit','poll','candidate']) test(kind+'401 revokes detached controls and never retries a POST',async()=>{
  const s=setup();await mount(s);
  if(kind==='candidate') s.existing=job('SUCCEEDED');
  if(['submit','poll','candidate'].includes(kind)) await click(s,'Check generation access');
  if(kind==='poll') await click(s,'Generate proposal');
  let control;
  if(kind==='candidate') {
    const overlay=s.root.all('textarea').find(n=>n.name==='overlay');overlay.value='{"account":"private"}';
    await click(s,'Review shadow candidate request');control=button(s.root,'Confirm shadow candidate');
  } else control=button(s.root,{action:'Review fixture',access:'Check generation access',submit:'Generate proposal',poll:'Refresh proposal status'}[kind]);
  const before=s.calls.length;s.fail=()=>true;
  await control.listeners.click();signedOut(s);assert.equal(control.disabled,true);
  assert.equal(s.calls.length,before+1);
  await control.listeners.click();
  for(const timer of [...s.timers]) await timer();
  assert.equal(s.calls.length,before+1);assert.equal(s.unauthorized,1);
});
test('terminal polling updates live status but preserves later overlay review',async()=>{
  const s=setup();const fields=await mount(s);await click(s,'Check generation access');await click(s,'Generate proposal');
  assert.match(status(s.root),/QUEUED/);
  s.reads=job('SUCCEEDED');await s.timers.shift()();
  assert.match(status(s.root),/SUCCEEDED/);assert.doesNotMatch(status(s.root),/QUEUED/);
  const overlay=s.root.all('textarea').find(n=>n.name==='overlay');overlay.value='{"account":"private"}';
  await click(s,'Review shadow candidate request');
  const reviewed=status(s.root),old=button(s.root,'Confirm shadow candidate');
  await click(s,'Refresh proposal status');
  assert.equal(status(s.root),reviewed);assert.equal(overlay.value,'{"account":"private"}');
  fields.text.value+=' changed';fields.text.listeners.input();
  const before=s.calls.length;await old.listeners.click();s.ui.refreshAccess();
  assert.equal(old.disabled,true);assert.equal(s.calls.length,before);
});
test('late401 from a detached view cannot replace the current screen',async()=>{
  const old=deferred(),root=new Element('main');let redirects=0;
  const ui=create({document,onUnauthorized:()=>redirects++,api:path=>path==='/api/vendors'?old.promise:Promise.resolve({claims:[]})});
  const pending=ui.render(root,'vendors');await ui.render(root,'disputes');old.reject(unauthorized());await pending;
  assert.equal(redirects,0);assert.match(root.textContent,/Correspondence & disputes/);assert.doesNotMatch(root.textContent,/State unavailable/);
});
test('parallel401 requests redirect once and old refresh cannot overwrite sign-in',async()=>{
  const a=deferred(),b=deferred(),root=new Element('main');let redirects=0,calls=0;
  const ui=create({document,onUnauthorized:()=>{redirects++;root.replaceChildren(new Element('sign-in'));},api:async(path)=>{
    calls++;if(path==='/api/vendors')return {vendors:[{vendor_id:'a'},{vendor_id:'b'}]};return path.endsWith('/a')?a.promise:b.promise;
  }});
  const pending=ui.render(root,'vendors');await new Promise(resolve=>setImmediate(resolve));
  const refresh=button(root,'Refresh server state');a.reject(unauthorized());b.reject(unauthorized());await pending;
  assert.equal(redirects,1);await refresh.listeners.click();assert.equal(calls,3);assert.equal(root.children[0].tagName,'sign-in');
});
test('an older overlapping status read cannot undo a newer terminal result or overlay review',async()=>{
  const s=setup();await mount(s);await click(s,'Check generation access');await click(s,'Generate proposal');
  const old=deferred();s.reads=old.promise;const waiting=click(s,'Refresh proposal status');
  s.reads=job('SUCCEEDED');await click(s,'Refresh proposal status');
  const overlay=s.root.all('textarea').find(n=>n.name==='overlay');overlay.value='{"account":"private"}';
  await click(s,'Review shadow candidate request');const reviewed=status(s.root);
  old.resolve(job('RUNNING'));await waiting;
  assert.equal(status(s.root),reviewed);assert.equal(overlay.value,'{"account":"private"}');
  assert.ok(button(s.root,'Confirm shadow candidate'));
  assert.equal(s.calls.filter(call=>call.body!==undefined&&call.path.endsWith('/proposal-jobs')).length,1);
});
