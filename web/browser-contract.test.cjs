// Dependency-free DOM contract harness; real browser accessibility/layout remains an integration check.
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.attrs = {}; this.listeners = {}; this.value = ''; this.dataset = {}; this._text = ''; this.open = false; this.isConnected = true; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(''); }
  append(...children) { this.children.push(...children); }
  add(child) { this.append(child); }
  replaceChildren(...children) { this._text = ''; this.children = children; }
  get firstChild() { return this.children[0]; }
  setAttribute(k,v) { this.attrs[k] = v; }
  removeAttribute(k) { delete this.attrs[k]; }
  addEventListener(k,fn) { this.listeners[k] = fn; }
  querySelectorAll(tag) { return this.children.flatMap(c => [...(c.tagName === tag ? [c] : []), ...c.querySelectorAll(tag)]); }
  querySelector(tag) { return this.querySelectorAll(tag)[0]; }
  showModal() { this.open = true; }
  close() { this.open = false; this.listeners.close?.(); }
  focus() {}
}
const flush = () => new Promise(resolve => setImmediate(resolve));
async function setup(unauthorized = false, initialHash = '#dashboard', workflowResponse = {workflow:null}, workflowStatus = 200, onboardingResponse = null) {
  const nodes = Object.fromEntries(['content','notice','inspector','case-content','workspace-name','account','refresh','close-inspector'].map(id => [id,new Element('div')]));
  const requests = [], window = {}, location = {hash:initialHash};
  const source = ['SYNTHETIC_CUSTOMER','SIMULATED_VENDOR'];
  const item = {id:'case/1',vendor:'<img src=x onerror=alert(1)>',title:'Contract test',stage:'DRAFT',outcome:'ELIGIBLE',amount:'12.00',currency:'USD',sources:source};
  const context = {document:{querySelector:s => nodes[s.slice(1)],querySelectorAll:() => [],createElement:t => new Element(t)}, window:{addEventListener:(k,fn) => window[k]=fn},location,URL,Option:function(label,value){const e=new Element('option');e.textContent=label;e.value=value;return e;},fetch:async(path,options) => {
    requests.push({path,options});
    let data = path === '/api/workspace/workflow' ? workflowResponse : path === '/api/ramp/workspace' ? {source_mode:'TEST_ONLY',records:[{...item,provider_id:'native-1',provider_object_type:'bills',native_status:'OPEN'}],resources:[]} : path === '/api/dashboard' ? {workspace:'Test workspace',as_of:'test timestamp',metrics:[{label:'Simulated award',value:'12.00',sources:source}],cases:[item],audit:[{at:'test',event:'Recorded',sources:source}],ramp:{sources:['UNAVAILABLE']}} : path === '/api/onboarding' ? onboardingResponse || {vendor:'Test vendor',state:'DRAFT',sources:source,checks:[{label:'Golden check',passed:true,detail:'Test result'}],history:['Draft created'],actions:[]} : path === '/api/guide' ? {answer:'Read-only answer',sources:source} : {...item,financials:[],clauses:[{label:'Unsafe link',uri:'javascript:alert(1)'}],evidence:[],trace:['Deterministic trace'],timeline:[],actions:[{id:'approve',label:'Approve draft'}]};
    const status=unauthorized ? 401 : path === '/api/workspace/workflow' ? workflowStatus : 200;
    return {ok:status===200,status,headers:{get:()=>'application/json'},json:async()=>data};
  }};
  context.window.uptimeAuth = {session:()=>({subject:'test.reader'}), signInForm:()=>{
    const form = new Element('form'); form.textContent='Sign in to Uptime'; return form;
  }};
  context.window.uptimeAPI = async (path,payload) => {
    const options = {method:payload===undefined?'GET':'POST', credentials:'omit',
      ...(payload===undefined ? {} : {body:JSON.stringify(payload)})};
    const response = await context.fetch(path,options);
    if (!response.ok) { const error=new Error('Authentication required'); error.status=response.status; throw error; }
    return response.json();
  };
  context.window.document = context.document;
  context.history = {pushState:(_,__,url)=>{location.hash=url;}};
  vm.runInNewContext(fs.readFileSync(__dirname+'/ramp_ui.js','utf8'),context);
  vm.runInNewContext(fs.readFileSync(__dirname+'/workspace_ui.js','utf8'),context);
  vm.runInNewContext(fs.readFileSync(__dirname+'/app.js','utf8'),context); await flush(); return {nodes,requests,window,location};
}
test('ledger consumes API data, keeps sources exact and treats markup as text', async () => {
  const {nodes,requests} = await setup();
  assert.equal(requests[0].path,'/api/dashboard');
  assert.equal(requests[0].options.credentials,'omit');
  assert.match(nodes.content.textContent,/<img src=x onerror=alert\(1\)>/);
  assert.equal(nodes.content.querySelectorAll('img').length,0);
  assert.doesNotMatch(nodes.content.textContent,/SYNTHETIC_CUSTOMER|SIMULATED_VENDOR/);
  assert.match(nodes.content.textContent,/\$12.00/);
});
test('inspector action uses encoded route, empty POST and no client identity', async () => {
  const {nodes,requests} = await setup();
  await nodes.content.querySelectorAll('button').find(b=>b.className==='case-link').listeners.click();
  assert.equal(nodes.inspector.open,true);
  assert.ok(requests.some(r=>r.path==='/api/cases/case%2F1'));
  assert.equal(nodes['case-content'].querySelectorAll('a').length,0);
  const action = nodes['case-content'].querySelectorAll('button').find(b=>b.textContent==='Approve draft');
  await action.listeners.click({currentTarget:action});
  const post = requests.find(r=>r.options.method==='POST');
  assert.equal(post.path,'/api/cases/case%2F1/actions/approve');
  assert.equal(post.options.body,'{}');
  assert.equal(post.options.credentials,'omit');
});
test('onboarding keeps unproven event provenance explicit', async () => {
  const {nodes,location,window} = await setup(); location.hash='#onboarding'; window.hashchange(); await flush();
  assert.match(nodes.content.textContent,/Golden check/); assert.match(nodes.content.textContent,/Source not provided/);
  assert.ok(nodes.content.querySelectorAll('span').some(n=>n.className==='pill valid'));
});
test('unauthorized session offers named account login', async () => {
  const {nodes} = await setup(true); assert.match(nodes.content.textContent,/Sign in to Uptime/);
});

test('default landing is Ramp, deep links encode opaque IDs, explicit rehearsal retains dashboard', async () => {
  const {nodes,requests,location,window}=await setup(false,'');
  assert.equal(requests[0].path,'/api/workspace/workflow');
  assert.equal(requests[1].path,'/api/ramp/workspace');
  assert.match(nodes.content.textContent,/Ramp worklist/);
  await nodes.content.querySelectorAll('button').find(b=>b.className==='case-link').listeners.click();
  await flush();
  assert.equal(location.hash,'#ramp/case%2F1');
  assert.ok(requests.some(r=>r.path==='/api/ramp/records/case%2F1'));
  assert.equal(nodes.inspector.open,false);
  location.hash='#rehearsal';window.hashchange();await flush();
  assert.match(nodes.content.textContent,/Evidence ledger/);
  location.hash='#ramp';window.hashchange();await flush();
  assert.match(nodes.content.textContent,/Ramp worklist/);
});
test('Ramp authentication failures reuse named sign-in and skip link does not change route', async () => {
  const denied=await setup(true,'#ramp');assert.match(denied.nodes.content.textContent,/Sign in to Uptime/);
  const s=await setup(false,'#ramp');const count=s.requests.length;
  s.location.hash='#workspace';s.window.hashchange();await flush();
  assert.equal(s.requests.length,count);assert.match(s.nodes.content.textContent,/Ramp worklist/);
});

test('configured workspace renders inside the finance shell and keeps native records accessible', async () => {
  const s=await setup(false,'#ramp',{workflow:{vendor:'Northwind Cloud',company:'Northwind Finance',months:[],ledger:{destination:'Local ledger'},claim:{state:'DRAFT'},next_actions:[]}});
  assert.match(s.nodes.content.textContent,/Northwind Cloud/);
  assert.equal(s.nodes['workspace-name'].textContent,'Northwind Finance');
  assert.equal(s.requests.length,1);
  s.location.hash='#records';s.window.hashchange();await flush();
  assert.match(s.nodes.content.textContent,/Ramp worklist/);
  assert.equal(s.requests[1].path,'/api/ramp/workspace');
});
test('workflow authorization and server errors never silently fall back to native records', async () => {
  for(const status of [403,500]) {
    const s=await setup(false,'#ramp',{workflow:null},status);
    assert.match(s.nodes.content.textContent,/Unable to load this view/);
    assert.equal(s.requests.length,1);
    assert.equal(s.requests[0].path,'/api/workspace/workflow');
  }
});

test('stale reviewer authority keeps recorded checks separate from current verification',async()=>{
 const s=await setup(false,'#onboarding',{workflow:null},200,{vendor:'CalyxQuay',state:'REVIEW_REQUIRED',checks_status:'REVIEW_REQUIRED',checks:[],recorded_checks:[{label:'Prior shadow check',passed:true}],actions:[]});
 assert.match(s.nodes.content.textContent,/Current verification/);assert.match(s.nodes.content.textContent,/REVIEW_REQUIRED/);assert.match(s.nodes.content.textContent,/No validation results returned/);
 assert.equal(s.nodes.content.querySelectorAll('span').filter(n=>n.className==='pill valid').length,0);
 const history=s.nodes.content.querySelectorAll('details').find(n=>n.textContent.includes('Recorded checks'));
 assert.ok(history);assert.match(history.textContent,/Prior shadow check/);assert.notEqual(history.open,true);
});
test('server stage labels render as sent; the browser never renames a state to hide its destination', async () => {
  const {nodes} = await setup();
  assert.match(nodes.content.textContent,/Simulated award/);
  assert.doesNotMatch(nodes.content.textContent,/Awarded credit/);
  const source = fs.readFileSync(__dirname+'/app.js','utf8');
  assert.doesNotMatch(source,/presentationLabel|evidenceDescription|'Simulated award'\s*:/);
});
test('the one-bill route makes one request, the saved Ramp workspace, and never reads the workflow projection', async () => {
  const workflow={workflow:{vendor:'Northwind Cloud',company:'Northwind Finance',months:[],ledger:{destination:'Local ledger'},claim:{state:'DRAFT'},next_actions:[]}};
  const s=await setup(false,'#ramp-bill/NATIVE-1',workflow);
  assert.deepEqual(s.requests.map(r=>r.path),['/api/ramp/workspace']);
  assert.match(s.nodes.content.textContent,/This workspace has no saved record for this Ramp bill\./);
  assert.doesNotMatch(s.nodes.content.textContent,/Northwind|Local ledger/);
  assert.equal(s.nodes['workspace-name'].textContent,'Uptime');
  // Leaving the bill for the Overview reads the workflow as usual; coming back reads only the Ramp workspace again.
  s.location.hash='#overview';s.window.hashchange();await flush();
  assert.equal(s.requests[1].path,'/api/workspace/workflow');
  const before=s.requests.length;
  s.location.hash='#ramp-bill/native-1';s.window.hashchange();await flush();
  assert.deepEqual(s.requests.slice(before).map(r=>r.path),['/api/ramp/workspace']);
});
