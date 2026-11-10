// The one-bill page for the panel beside Ramp: three cases, one request, and nothing from another agreement.
const test=require('node:test');
const assert=require('node:assert/strict');
const {create}=require('./ramp_ui.js');
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
const BILL='f74ba12c-95d0-582d-9f62-26d8057d1d37', OTHER='ae98c421-2c70-5586-8719-4fe8acd7ceda';
const ctx={business_id:'1569e402-460e-4952-adad-9df27db628a0',object_type:'bills',object_id:BILL,vendor_id:'vendor-1',vendor_name:'DocuSign',
  invoice_number:'DD-PREAPPROVAL',amount:{currency:'USD',amount:'840'},status:'OPEN',status_summary:'APPROVAL_PENDING',approval_status:'PENDING',
  observed_at:'2026-11-09T22:00:38.031951+00:00',ramp_link:{url:'https://demo.ramp.com/bill-pay/bills/list/'+BILL,basis:'OPERATOR_OBSERVED_URL'},
  agreement_binding:{status:'NONE',contract_id:null},finding_attachable:false,
  discussion:[{comment_id:'376563cf',created_at:'2026-11-08T01:46:45+00:00',attribution:'PERSON_POSTED_VERIFIED_READBACK'}],
  credit_links:{status:'NO_APPLIED_CREDITS',applied_verified_minor:0},native_confirmation:'RAMP_READ_ONLY',actual_recovery:null};
const verified={kind:'SAVED_VERIFIED_RECORD',live_read:false,started_by:'PERSON',excerpt:true,capture:{observed_at:'2026-11-09T22:00:38.031951+00:00'},ramp_context:ctx,
  finding:{outcome:'INSUFFICIENT_EVIDENCE',finding_kind:'UNBOUND_RECORD',missing:['Record-specific governing terms and service/line evidence are not bound.'],amount:null},
  contract_terms:'NONE_BOUND',actual_recovery:null};
const other={...ctx,business_id:null,object_id:OTHER,vendor_name:null,invoice_number:null,ramp_link:null,discussion:[],credit_links:{status:'UNKNOWN'}};
const plain={id:'bill-'+OTHER,title:'bills: evidence review',provider_id:OTHER,provider_object_type:'bills',native_status:'OPEN',outcome:'INSUFFICIENT_EVIDENCE',stage:'PREPAYMENT_REVIEW',
  amount:null,currency:'USD',sources:['LIVE_RAMP_SANDBOX'],ramp_context:other};
const scenario={id:'rehearsal/cap-'+OTHER,title:'Synthetic gross invoice cap rehearsal',provider_id:OTHER,provider_object_type:'bills',native_status:'OPEN',outcome:'ELIGIBLE',stage:'SIMULATION_ONLY',
  amount:'40.00',currency:'USD',finding_kind:'SYNTHETIC_INVOICE_CAP',sources:['LIVE_RAMP_SANDBOX','SYNTHETIC_CUSTOMER'],
  ramp_context:{...other,agreement_binding:{status:'HYPOTHETICAL',contract_id:null}}};
const capture={custody:'packaged_receipt',business_id:null,account_complete:false,observed_at:'2026-11-05T00:36:21+00:00',incomplete_lists:['transactions'],
  resources:[{name:'transactions',retained:12,listed:40,has_next:true}]};
const workspace={records:[scenario,plain],capture,verified_record:verified,resources:[]};
function open(data){const root=new Element('main'),requests=[];const ui=create({document,api:async(...args)=>{requests.push(args);return data;},onNavigate:()=>{}});return {root,requests,ui};}
const hrefs=root=>root.all('a').map(a=>[a.textContent,a.href]);
// Nothing from the walkthrough's own agreement may appear beside a Ramp bill it is not bound to.
const UNRELATED=/Northwind|service credit|price exception|claim|\$2,400|\$8,600|\$11,000|\$1,000/i;

test('the verified bill shows what Ramp holds, what Uptime found and the person-posted note, from one read',async()=>{
  const s=open(workspace);await s.ui.bill(s.root,BILL.toUpperCase());const text=s.root.textContent;
  assert.deepEqual(s.requests,[['/api/ramp/workspace']]);
  for(const expected of ['Verified Ramp record','DocuSign','Invoice DD-PREAPPROVAL','USD 840','OPEN','APPROVAL_PENDING','PENDING',BILL,
    'Saved record read from Ramp Nov 9, 2026, 22:00 UTC, started by a person. Not a live read.',
    'Evidence gap: the governing agreement or usage evidence is missing','Record-specific governing terms and service/line evidence are not bound.',
    'No agreement on file for this bill.','No contract finding is attached to this bill.','No credits applied to this bill.',
    'Posted by a person in Ramp; Uptime read it back on this bill · Nov 8, 2026, 01:46 UTC · Comment ID: 376563cf',
    'Uptime has made no write to Ramp. A local ledger entry is never shown here as a Ramp confirmation.'])assert.ok(text.includes(expected),expected);
  assert.deepEqual(hrefs(s.root),[['Open the full record','#records']]);
  assert.doesNotMatch(text,UNRELATED);
  assert.doesNotMatch(text,/40\.00|Scenario|Eligible/);
});

test('a bill found only in the saved worklist shows that worklist’s own statement, no outcome and no scenario beside it',async()=>{
  const s=open(workspace);await s.ui.bill(s.root,OTHER);const text=s.root.textContent;
  assert.deepEqual(s.requests,[['/api/ramp/workspace']]);
  for(const expected of ['Ramp bill in the saved worklist','Vendor name not captured','Invoice not captured','USD 840','APPROVAL_PENDING',OTHER,
    'Saved worklist from an earlier Ramp demo installation; its Ramp business is not recorded in this capture. Read from Ramp Nov 5, 2026, 00:36 UTC. Partial capture.',
    'This is not the complete account.','No agreement on file for this bill.','No contract finding is attached to this bill.','Credit status unknown from this read.',
    'bills: evidence review','Review before payment','One contract scenario about this bill is kept in Ramp records. A scenario is not a finding on this bill.'])assert.ok(text.includes(expected),expected);
  // Beside a Ramp bill the page states no outcome and lists no scenario: its title, outcome and amount stay in Ramp records.
  assert.doesNotMatch(text,/40\.00|Eligible|ELIGIBLE|eligible|Needs evidence|Invoice cap review|cap rehearsal|refund|credit found/);
  assert.deepEqual(hrefs(s.root),[['Open this record','#ramp/bill-'+OTHER],['Open Ramp records','#records']]);
  assert.doesNotMatch(text,UNRELATED);assert.doesNotMatch(text,/DocuSign|Not a live read/);
});

test('an unknown, empty or malformed bill id says so in one sentence and offers Ramp records',async()=>{
  for(const id of ['00000000-0000-0000-0000-000000000000','',null,BILL.slice(0,8)]){
    const s=open(workspace);await s.ui.bill(s.root,id);
    assert.ok(s.root.textContent.includes('This workspace has no saved record for this Ramp bill.'),String(id));
    assert.ok(s.root.textContent.includes('Uptime shows a bill here only when it holds a saved read of it from Ramp. Nothing about this bill is inferred.'),String(id));
    // A well-formed id is named; anything else is not repeated back.
    assert.equal(s.root.textContent.includes('00000000-0000-0000-0000-000000000000'),id==='00000000-0000-0000-0000-000000000000',String(id));
    assert.deepEqual(hrefs(s.root),[['Open Ramp records','#records']]);
    assert.doesNotMatch(s.root.textContent,/DocuSign|USD 840|40\.00/);assert.deepEqual(s.requests,[['/api/ramp/workspace']]);
  }
  const bare=open({records:[],resources:[]});await bare.ui.bill(bare.root,BILL);
  assert.ok(bare.root.textContent.includes('This workspace has no saved record for this Ramp bill.'));
});

test('a bound agreement and an attachable finding are stated as such; other bindings are never called bound',async()=>{
  const bound=open({records:[],verified_record:{...verified,ramp_context:{...ctx,agreement_binding:{status:'BOUND',contract_id:'MSA 7'},finding_attachable:true}}});
  await bound.ui.bill(bound.root,BILL);
  assert.ok(bound.root.textContent.includes('Agreement on file: MSA 7.'));assert.ok(bound.root.textContent.includes('A contract finding can be attached to this bill.'));
  for(const [status,words] of [['HYPOTHETICAL','Hypothetical terms only; no agreement on file for this bill.'],['CONFLICT','Agreement records for this bill conflict; needs review.'],['SOMETHING_NEW','Agreement binding not recorded for this bill.']]){
    const s=open({records:[],verified_record:{...verified,ramp_context:{...ctx,agreement_binding:{status}}}});await s.ui.bill(s.root,BILL);
    assert.ok(s.root.textContent.includes(words),status);assert.doesNotMatch(s.root.textContent,/Agreement on file:/);
  }
});

test('a failed read shows no bill and an expired session propagates to sign-in',async()=>{
  const root=new Element('main');const ui=create({document,api:async()=>{throw new Error('PRIVATE DIAGNOSTIC');},onNavigate:()=>{}});
  await ui.bill(root,BILL);assert.match(root.textContent,/Ramp state unavailable/);assert.doesNotMatch(root.textContent,/PRIVATE DIAGNOSTIC|DocuSign/);
  const expired=create({document,api:async()=>{throw Object.assign(new Error('expired'),{status:401});},onNavigate:()=>{}});
  await assert.rejects(expired.bill(new Element('main'),BILL),{status:401});
});

// ---- The page inside the side panel (openApp given) ----
function inPanel(data){const opened=[];const root=new Element('main'),requests=[];
  const ui=create({document,api:async(...args)=>{requests.push(args);return data;},onNavigate:()=>{},openApp:route=>opened.push(route)});return {root,requests,ui,opened};}
const buttons=root=>root.all('button');
const BANNED=/eligible|credit found|refund|claim|Northwind|price exception|service credit|demo data|synthetic|sample/i;

test('in the panel each state has one primary button, Open Uptime, that asks for one allowed route and is not a link',async()=>{
  for(const [id,route] of [[BILL,'records'],[OTHER,'records'],['00000000-0000-0000-0000-000000000000','overview']]){
    const s=inPanel(workspace);await s.ui.bill(s.root,id);
    const [only,...rest]=buttons(s.root);assert.equal(rest.length,0,id);assert.equal(only.textContent,'Open Uptime');assert.equal(only.className,'panel-open-app-button');
    assert.deepEqual(s.opened,[]);only.listeners.click();assert.deepEqual(s.opened,[route],id);
    // No link moves the panel itself to another page of the app.
    assert.deepEqual(hrefs(s.root),[],id);
    assert.doesNotMatch(s.root.textContent,BANNED,id);
  }
});

test('in the panel the verified bill keeps every statement word for word',async()=>{
  const s=inPanel(workspace);await s.ui.bill(s.root,BILL);const text=s.root.textContent;
  for(const expected of ['Verified Ramp record','DocuSign','Invoice DD-PREAPPROVAL','USD 840','OPEN','APPROVAL_PENDING','PENDING',
    'Saved record read from Ramp Nov 9, 2026, 22:00 UTC, started by a person. Not a live read.',
    'Evidence gap: the governing agreement or usage evidence is missing','No agreement on file for this bill.','No contract finding is attached to this bill.',
    'No credits applied to this bill.','Posted by a person in Ramp; Uptime read it back on this bill · Nov 8, 2026, 01:46 UTC · Comment ID: 376563cf',
    'Uptime has made no write to Ramp. A local ledger entry is never shown here as a Ramp confirmation.'])assert.ok(text.includes(expected),expected);
  assert.doesNotMatch(text,/Posted to Ramp|Ramp confirmed|confirmed in Ramp|written to Ramp/i);
  assert.deepEqual(s.requests,[['/api/ramp/workspace']]);
});

test('with no Ramp bill open the page reads nothing and says so calmly',()=>{
  for(const openApp of [null,true]){
    const opened=[],requests=[];const root=new Element('main');
    const ui=create({document,api:async(...a)=>{requests.push(a);return workspace;},onNavigate:()=>{},openApp:openApp?route=>opened.push(route):null});
    ui.noBill(root);const text=root.textContent;
    for(const expected of ['This tab','No Ramp bill open','Open a bill in Ramp, and Uptime shows here what it holds for that bill.'])assert.ok(text.includes(expected),expected);
    assert.deepEqual(requests,[]);assert.doesNotMatch(text,/DocuSign|USD|840|saved record/i);assert.doesNotMatch(text,BANNED);
    if(openApp){const [b]=buttons(root);assert.equal(b.textContent,'Open Uptime');b.listeners.click();assert.deepEqual(opened,['overview']);assert.deepEqual(hrefs(root),[]);}
    else assert.deepEqual(hrefs(root),[['Open Ramp records','#records']]);
  }
});

test('outside the panel no state shows the panel button',async()=>{
  for(const id of [BILL,OTHER,'00000000-0000-0000-0000-000000000000']){const s=open(workspace);await s.ui.bill(s.root,id);assert.deepEqual(buttons(s.root),[],id);}
});

test('panel mode is on only when the page is framed, and its message is addressed to one extension origin',()=>{
  const app=require('./app.js');
  // The panel's home route is its own page; a bill id still opens the bill, and no other route changed.
  assert.equal(app.companionRoute('ramp-bill'),'ramp-bill-none');assert.equal(app.companionRoute('ramp-bill/'+BILL),'ramp-bill');
  assert.equal(app.companionRoute('records'),'records');assert.equal(app.companionRoute('overview'),'ramp');
  const page={};page.self=page;page.top=page;assert.equal(app.framed(page),false);
  const child={self:null,top:{}};child.self=child;assert.equal(app.framed(child),true);
  assert.equal(app.framed(undefined),false);
  const denied={get self(){return this;},get top(){throw new Error('blocked');}};assert.equal(app.framed(denied),true);
  const EXT='chrome-extension://kibophanbmnepbmhpampfagpjfhjfcnl';
  assert.equal(app.panelParent({ancestorOrigins:[EXT]}),EXT);
  for(const origins of [undefined,[],[EXT,EXT],['https://demo.ramp.com'],['http://127.0.0.1:8776'],['chrome-extension://short'],['moz-extension://kibophanbmnepbmhpampfagpjfhjfcnl']])
    assert.equal(app.panelParent({ancestorOrigins:origins}),null,String(origins));
  // The panel's styles are all scoped to the framed page, in one block of the stylesheet.
  const css=require('node:fs').readFileSync(__dirname+'/style.css','utf8');
  const block=css.slice(css.indexOf('/* 16. Side panel'));
  assert.ok(block.length>0 && css.indexOf('/* 16. Side panel')>0);
  assert.equal(css.split('.panel-mode').length-1,block.split('.panel-mode').length-1);
  const selectors=block.split('}').filter(r=>r.includes('{')).flatMap(r=>r.replace(/\/\*[\s\S]*?\*\//g,'').split('{')[0].split(',')).map(x=>x.trim());
  assert.ok(selectors.includes('.panel-mode body') && selectors.length>=15,String(selectors.length));
  for(const selector of selectors)assert.ok(/^\.panel-mode\s|^\.panel-open-app|^\.ramp-bill-empty/.test(selector),selector);
});
