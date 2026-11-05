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

test('agreement amendments and adapter history retain actual references and scripted principal detail',async()=>{
 const data={...projection,contract:{...projection.contract,summary:'Monthly fee and service credit schedule.',documents:[{title:'Amendment 1',ref:'NW-AM1#2',version:'1',effective_at:'2026-03-01',description:'The service-period cap becomes USD 11,000.'}]},reviewer:{...projection.reviewer,principal:'scripted-test-reviewer'},onboarding:{vendor:'CalyxQuay',state:'ACTIVE',version:'cq-v2',history:[{at:'2026-01-01',event:'Shadow evaluation passed',ref:'shadow-cq'},{at:'2026-01-02',event:'Version approved',ref:'review-cq'},{at:'2026-01-03',event:'Version activated',ref:'activate-cq'},{at:'2026-01-04',event:'Version rolled back',ref:'rollback-cq'}]},ledger:{...projection.ledger,awarded:'2400.00',posted:'2400.00',applied:'2400.00',bill:{...projection.ledger.bill,outstanding_amount:'9600.00'}}};
 const s=setup(()=>({workflow:data}));await s.ui.render(s.root);
 for(const value of ['Amendment 1','NW-AM1#2','2026-03-01','USD 11,000','scripted-test-reviewer','CalyxQuay','shadow-cq','review-cq','activate-cq','rollback-cq','$9,600.00','$1,000.00'])assert.ok(s.root.textContent.includes(value),value);
 assert.doesNotMatch(s.root.textContent,/synthetic|simulat|replay|demo/i);
 assert.equal(s.root.all('a').find(a=>a.textContent==='Inspect vendor contracts').href,'#vendors');
 assert.deepEqual(data.sources,['SYNTHETIC_CUSTOMER']);assert.equal(data.mode,'replay');
});

test('invoice periods and source usage details preserve server observations and null without arithmetic',async()=>{
 const data={...projection,months:[{...projection.months[2],invoice:{id:'NW-MAR-2026',issued_at:'2026-03-01',service_start:'2026-03-01',service_end:'2026-04-01'},evidence:[{label:'Coverage',ref:'usage-mar#coverage',value:null},{label:'Eligible downtime',ref:'usage-mar#downtime',value:'0 minutes observed'}],trace:['Required full-month coverage is unavailable.']}]};
 const s=setup(()=>({workflow:data}));await s.ui.render(s.root);
 const detail=s.root.all('details').find(n=>n.all('summary').some(x=>x.textContent==='Inspect invoice & usage'));
 assert.ok(detail);for(const value of ['NW-MAR-2026','2026-03-01','2026-04-01','usage-mar#coverage','Not provided','0 minutes observed','Required full-month coverage is unavailable.'])assert.ok(detail.textContent.includes(value),value);
 assert.equal(s.root.all('tbody')[0].all('tr')[0].children[2].textContent,'Not determined');
 assert.equal(data.months[0].amount,null);assert.equal(data.months[0].evidence[0].value,null);
});

test('application invoice comes only from current projection and pricing failures remain visible without classification prefix',async()=>{
 const data={...projection,months:projection.months.map(m=>({...m,amount:null})),price_finding:{...projection.price_finding,amount:null,state:'UNSUPPORTED_RULE',reason:'Synthetic invoice only; no live Ramp bill bound.; Future performance requires separate advance-billing rules.'},ledger:{...projection.ledger,applied:'2400.00',bill:{id:'NW-2026-04',issued_at:'2026-04-01',service_start:'2026-04-01',service_end:'2026-05-01',original_amount:'11000.00',outstanding_amount:'8600.00'}}};
 const s=setup(()=>({workflow:data}));await s.ui.render(s.root);
 for(const value of ['NW-2026-04','2026-04-01','2026-05-01','$11,000.00','$8,600.00','Future performance requires separate advance-billing rules.'])assert.ok(s.root.textContent.includes(value),value);
 assert.doesNotMatch(s.root.textContent,/synthetic|9,600/ig);assert.ok(data.months.every(m=>m.amount===null));assert.equal(data.price_finding.amount,null);
});
