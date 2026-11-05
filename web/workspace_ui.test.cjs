const test=require('node:test');
const assert=require('node:assert/strict');
const {create,money}=require('./workspace_ui.js');
class Element {
  constructor(tag){this.tagName=tag;this.children=[];this.listeners={};this.attrs={};this._text='';}
  set textContent(v){this._text=String(v);this.children=[];}
  get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
  append(...c){this.children.push(...c);}
  replaceChildren(...c){this._text='';this.children=c;}
  setAttribute(k,v){this.attrs[k]=v;}
  addEventListener(k,f){this.listeners[k]=f;}
  all(t){return this.children.flatMap(c=>[...(c.tagName===t?[c]:[]),...c.all(t)]);}
}
const document={createElement:t=>new Element(t)};
const projection={vendor:'Northwind Cloud',contract:{title:'Cloud Services Agreement',version:'2026-01',ref:'NW-CSA-2026'},reviewer:{name:'Dana Reyes',role:'Contract Counsel',authority_kind:'SCRIPTED_REVIEWER'},months:[{month:'January 2026',outcome:'ELIGIBLE',amount:'2400.00',currency:'USD',reason:'Eligible downtime exceeds the service threshold.',citations:[{label:'Service credit schedule, §4',ref:'NW-CSA-2026#4'}]},{month:'February 2026',outcome:'INELIGIBLE',amount:'0.00',currency:'USD',reason:'Availability meets the threshold.'},{month:'March 2026',outcome:'INSUFFICIENT_EVIDENCE',amount:null,currency:'USD',reason:'Full-month measurement pending.'}],price_finding:{state:'REVIEW_REQUIRED',amount:'1000.00',currency:'USD',reason:'Invoice exceeds amended price cap.',citations:[{label:'Amendment 1, §2',ref:'NW-AM1#2'}]},claim:{id:'nw-jan',state:'DRAFT',receipt_id:null},ledger:{destination:'Local ledger',claimed:'0.00',awarded:'0.00',posted:'0.00',applied:'0.00',currency:'USD',bill:{id:'NW-MAR-2026',original_amount:'12000.00',outstanding_amount:'12000.00'},record_ids:{}},next_actions:[{id:'draft/claim',label:'Prepare claim'}],audit:[],sources:['SYNTHETIC_CUSTOMER'],mode:'replay'};
function setup(api){const root=new Element('main'),requests=[];const ui=create({document,api:async(...args)=>{requests.push(args);return api ? api(...args) : {workflow:projection};}});return{root,requests,ui};}
test('Northwind renders separate exact stages, uncertainty and cited source records without classification chrome',async()=>{
 const s=setup();await s.ui.render(s.root);const view=s.root.textContent;
 for(const expected of ['Northwind Cloud','$2,400.00','$0.00','Not determined','$1,000.00','Local ledger','NW-CSA-2026#4','NW-AM1#2','Dana Reyes','Scripted reviewer']) assert.ok(view.includes(expected),expected);
 assert.doesNotMatch(view,/synthetic|simulat|replay|demo/i);
 assert.equal(s.root.all('tbody')[0].all('tr').length,3);
 assert.equal(s.root.all('article').length,4);
});
test('actions use signed injected transport, encoded server IDs and suppress duplicate dispatch',async()=>{
 let release;const s=setup((path,body)=>body ? new Promise(r=>{release=r;}) : {workflow:projection});await s.ui.render(s.root);
 const action=s.root.all('button')[0];const pending=action.listeners.click();await action.listeners.click();
 assert.deepEqual(s.requests,[['/api/workspace/workflow'],['/api/workspace/workflow/actions/draft%2Fclaim',{}]]);
 release(projection);await pending;assert.equal(s.requests.length,3);
});
test('lost action response blocks repeat until explicit server refresh and stale buttons cannot act',async()=>{
 const s=setup((path,body)=>{if(body)throw new Error('private transport details');return {workflow:projection};});await s.ui.render(s.root);
 const action=s.root.all('button')[0];await action.listeners.click();await action.listeners.click();assert.equal(s.requests.length,2);assert.match(s.root.textContent,/Refresh to check/);assert.doesNotMatch(s.root.textContent,/private transport/);
 await s.ui.render(s.root);await action.listeners.click();assert.equal(s.requests.length,3);
 s.ui.unmount();await s.root.all('button')[0].listeners.click();assert.equal(s.requests.length,3);
});
test('decimal display never rounds through Number and missing monetary observations remain unknown',()=>{
 assert.equal(money('9007199254740993.01'),'$9,007,199,254,740,993.01');assert.equal(money(null),'Not determined');assert.equal(money('0.00'),'$0.00');assert.equal(money('NaN'),'Not determined');
});
