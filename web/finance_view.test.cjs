const test=require('node:test');
const assert=require('node:assert/strict');
const {create}=require('./workspace_ui.js');
class Element {
  constructor(tag){this.tagName=tag;this.children=[];this.listeners={};this.attrs={};this._text='';this.value='';}
  set textContent(v){this._text=String(v);this.children=[];}
  get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
  append(...c){this.children.push(...c);}
  replaceChildren(...c){this._text='';this.children=c;}
  setAttribute(k,v){this.attrs[k]=v;}
  addEventListener(k,f){this.listeners[k]=f;}
  set innerHTML(v){throw new Error('innerHTML is not used');}
  all(t){return this.children.flatMap(c=>[...(c.tagName===t?[c]:[]),...c.all(t)]);}
}
const document={createElement:t=>new Element(t)};
const finance={attention:[
  {kind:'CLAIM_DEADLINE',title:'File the January 2026 claim before the deadline',detail:'Claims must be received before 2026-03-03T00:00:00+00:00.',owner:'reviewer',section:'finance-recovery',refs:['claim-1']},
  {kind:'MISSING_USAGE',title:'Complete March 2026 usage evidence',detail:'Eligible downtime minutes not provided. This month is not ineligible.',owner:'evidence',section:'finance-months',refs:['usage-3']}],
  stages:[],bill:{},ramp:{destination:'Local ledger',linked_record:null,note:'No Ramp bill is linked to this agreement. Credits in this workspace are recorded in Local ledger.'},sections:{}};
const projection={vendor:'Northwind Cloud',contract:{title:'Service Level Agreement',version:'v1',ref:'urn:sla',documents:[]},reviewer:{},
  months:[{month:'2026-01',outcome:'ELIGIBLE',amount:'2400.00',currency:'USD',reason:'r',citations:[],calculation:['2 completed shortfall increments; 20% credit after the contractual cap.'],
    inputs:{governing_fee:'12000.00',currency:'USD',fee_version:'fee-ref-1',eligible_downtime_minutes:'135',completed_steps:'2',credit_percent:'20',claim_cutoff:'2026-03-03T00:00:00+00:00',monitor_ref:'usage-1'}}],
  price_finding:{state:'PREPAYMENT_REVIEW',amount:'1000.00',currency:'USD',reason:'r',citations:[],lines:[{line_id:'hosting',version:'amendment-v2',billed:'12000.00',expected:'11000.00',delta:'1000.00',direction:'OVERCHARGE'}]},
  claim:{id:'claim-1',state:'DRAFTED',receipt_id:null},connection:{destination:'Local ledger'},
  ledger:{destination:'Local ledger',claimed:'0.00',awarded:'0.00',posted:'0.00',applied:'0.00',currency:'USD',bill:{},record_ids:{}},
  onboarding:{vendor:'CalyxQuay',state:'ACTIVE',version:'v-1',reviewer:{name:'Dana Reyes',authority_kind:'SCRIPTED_REVIEWER'},history:[{at:'t1',event:'Imported',ref:'1',actor:'scripted-test-reviewer'},{at:'t2',event:'Activated',ref:'2',actor:'scripted-test-reviewer'}]},
  next_actions:[],audit:[],finance};
function mount(api,onUnauthorized){const root=new Element('main'),requests=[];const ui=create({document,onUnauthorized,api:async(...args)=>{requests.push(args);return api(...args);}});return {root,requests,ui};}
const guideForm=root=>root.all('form')[0];
const guideInput=root=>guideForm(root).all('input')[0];
async function askGuide(root,question){guideInput(root).value=question;await guideForm(root).listeners.submit({preventDefault(){}});}

test('attention items, destination and calculation inputs render from the server summary only',async()=>{
  const s=mount(()=>({workflow:projection}));await s.ui.render(s.root,projection);const view=s.root.textContent;
  for(const expected of ['Needs attention','Reviewer action','File the January 2026 claim before the deadline','Evidence needed','Complete March 2026 usage evidence',
    'Ramp record','Not linked','No Ramp bill is linked to this agreement.','Open Ramp records','Calculation inputs','$12,000.00','fee-ref-1','20%',
    'amendment-v2','$11,000.00','not included in the credit stages','CalyxQuay coverage in this workspace','Dana Reyes · Scripted reviewer',
    'Every entry is recorded by scripted-test-reviewer.','Ask about this case','Stages of the same credit'])
    assert.ok(view.includes(expected),expected);
  assert.doesNotMatch(view,/post to ramp|synthetic|simulat|replay|\bdemo\b/i);
  assert.equal(s.root.all('a').find(a=>a.textContent==='Open Ramp records').href,'#records');
  assert.deepEqual(s.requests,[]);
});

test('guide posts only the question, renders cited sentences and states it changed nothing',async()=>{
  const answer={sentences:[{text:'The January claim must be received before 2026-03-03.',citations:['claim.deadline']}],
    citations:[{id:'claim.deadline',label:'Filing deadline',ref:'claim-1',section:'finance-recovery'}],abstained:false,
    scope_note:'This answer covers only the cited records. Anything not cited is not established by this case.',as_of:'2026-03-01T12:00:00+00:00'};
  const s=mount((path,body)=>body ? answer : {workflow:projection});await s.ui.render(s.root,projection);
  await askGuide(s.root,'  When is the deadline?  ');
  assert.deepEqual(s.requests,[['/api/workspace/guide',{question:'When is the deadline?'}]]);
  const out=s.root.textContent;
  for(const expected of ['must be received before 2026-03-03','Source: Filing deadline','claim-1','covers only the cited records','Read only; nothing was changed.'])
    assert.ok(out.includes(expected),expected);
});

test('abstention and failure messages; empty questions are not sent',async()=>{
  let fail=false;
  const abstain={sentences:[{text:"This case's records don't answer that.",citations:[]}],citations:[],abstained:true,scope_note:null,as_of:'t'};
  const s=mount((path,body)=>{if(body&&fail)throw Object.assign(new Error('server detail'),{status:500});return body ? abstain : {workflow:projection};});
  await s.ui.render(s.root,projection);
  await askGuide(s.root,'   ');assert.equal(s.requests.length,0);assert.ok(s.root.textContent.includes('Enter a question about this case.'));
  await askGuide(s.root,'What is the weather?');assert.ok(s.root.textContent.includes("This case's records don't answer that."));
  assert.equal(s.root.all('div').filter(d=>d.className==='guide-abstain').length,1);
  fail=true;await askGuide(s.root,'Why?');
  assert.ok(s.root.textContent.includes('The guide could not answer just now. Nothing was changed. Try again.'));
  assert.doesNotMatch(s.root.textContent,/server detail/);
});

test('an expired session on a guide question returns to sign-in and stales the form',async()=>{
  let logins=0;
  const s=mount((path,body)=>{if(body)throw Object.assign(new Error('Session expired'),{status:401});return {workflow:projection};},()=>{logins++;});
  await s.ui.render(s.root,projection);
  await askGuide(s.root,'What needs attention?');await askGuide(s.root,'Again?');
  assert.equal(logins,1);assert.equal(s.requests.length,1);
});

test('without a server summary the view keeps its previous layout and offers no guide',async()=>{
  const plain={...projection,finance:undefined};
  const s=mount(()=>({workflow:plain}));await s.ui.render(s.root,plain);
  assert.equal(s.root.all('form').length,0);
  assert.ok(!s.root.textContent.includes('Needs attention'));
});
