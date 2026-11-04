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
async function setup(unauthorized = false) {
  const nodes = Object.fromEntries(['content','notice','inspector','case-content','workspace-name','refresh','close-inspector'].map(id => [id,new Element('div')]));
  const requests = [], window = {}, location = {hash:'#dashboard'};
  const source = ['SYNTHETIC_CUSTOMER','SIMULATED_VENDOR'];
  const item = {id:'case/1',vendor:'<img src=x onerror=alert(1)>',title:'Contract test',stage:'DRAFT',outcome:'ELIGIBLE',amount:'12.00',currency:'USD',sources:source};
  const context = {document:{querySelector:s => nodes[s.slice(1)],querySelectorAll:() => [],createElement:t => new Element(t)}, window:{addEventListener:(k,fn) => window[k]=fn},location,URL,Option:function(label,value){const e=new Element('option');e.textContent=label;e.value=value;return e;},fetch:async(path,options) => {
    requests.push({path,options});
    let data = path === '/api/dashboard' ? {workspace:'Test workspace',as_of:'test timestamp',metrics:[{label:'Simulated award',value:'12.00',sources:source}],cases:[item],audit:[{at:'test',event:'Recorded',sources:source}],ramp:{sources:['UNAVAILABLE']}} : path === '/api/onboarding' ? {vendor:'Test vendor',state:'DRAFT',sources:source,checks:[{label:'Golden check',passed:true,detail:'Test result'}],history:['Draft created'],actions:[]} : path === '/api/guide' ? {answer:'Read-only answer',sources:source} : {...item,financials:[],clauses:[{label:'Unsafe link',uri:'javascript:alert(1)'}],evidence:[],trace:['Deterministic trace'],timeline:[],actions:[{id:'approve',label:'Approve draft'}]};
    return {ok:!unauthorized,status:unauthorized?401:200,headers:{get:()=>'application/json'},json:async()=>data};
  }};
  vm.runInNewContext(fs.readFileSync(__dirname+'/app.js','utf8'),context); await flush(); return {nodes,requests,window,location};
}
test('ledger consumes API data, keeps sources exact and treats markup as text', async () => {
  const {nodes,requests} = await setup();
  assert.equal(requests[0].path,'/api/dashboard');
  assert.equal(requests[0].options.credentials,'same-origin');
  assert.match(nodes.content.textContent,/<img src=x onerror=alert\(1\)>/);
  assert.equal(nodes.content.querySelectorAll('img').length,0);
  assert.match(nodes.content.textContent,/SIMULATED_VENDOR/);
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
  assert.equal(post.options.credentials,'same-origin');
});
test('onboarding keeps unproven event provenance explicit', async () => {
  const {nodes,location,window} = await setup(); location.hash='#onboarding'; window.hashchange(); await flush();
  assert.match(nodes.content.textContent,/Golden check/); assert.match(nodes.content.textContent,/Source not provided/);
  assert.ok(nodes.content.querySelectorAll('span').some(n=>n.className==='pill valid'));
});
test('unauthorized link provides local bootstrap recovery guidance', async () => {
  const {nodes} = await setup(true); assert.match(nodes.content.textContent,/bootstrap login URL/); assert.match(nodes.content.textContent,/local demo/);
});
