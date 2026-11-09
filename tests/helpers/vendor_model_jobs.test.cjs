'use strict';
// DOM contract for public proposal generation with automatic rule-family selection (decision 97, D05),
// using a recorded fake API client. Authored controls only: this is not an end-to-end browser, shared-service
// or model proof.
const test = require('node:test');
const assert = require('node:assert/strict');
const {Element, document} = require('./companion_dom.cjs');
const {create} = require('../../web/v4_ui.js');

const SOURCE = '\n  Vendor: <img src=x onerror=alert(1)>\r\nAgreement: ACC-2026-17\t \n';
const HEX = c => c.repeat(64);
const JOB = (status, extra = {}) => ({job_id:'job-1', status, vendor_id:'aster-cove', request_sha256:HEX('a'),
  context_sha256:HEX('b'), candidate_available:false, ...extra});
const SUCCEEDED = JOB('SUCCEEDED', {candidate_available:true, proposal:{profile:'monthly-propositions', attempt_nonce:'initial',
  source_sha256:HEX('c'), proposal_sha256:HEX('d'), model:'claude-opus-5-5', session:'synthetic-test-double-not-a-model-session',
  document:{name:'Aster Cove SLA', uri:'urn:authored:test', classification:'synthetic_public'},
  clauses:[{quote:'Vendor: <img src=x onerror=alert(1)>', field:'vendor', value:'<b>Aster</b>'},
    {quote:'Agreement: ACC-2026-17', field:'agreement', value:'ACC-2026-17'}]}});
const FAMILY = (family, label, extra = {}) => ({family, label, profile:'server-chosen', enabled:true, approval_reason:null,
  context_sha256:HEX('b'), request_sha256:HEX('a'), disclosure:{model:'claude-opus-5-5', tools:[], transmitted_fields:['input','model']},
  job:null, state:null, refusal:null, attempts:{total:0, validated:0, structural_refusals:0}, ...extra});
const MONTHLY = 'monthly-availability/1', RESOURCE = 'resource-month/1';
const VIEW = (outcome, families, extra = {}) => ({schema:'automatic-family-selection/1', mode:'automatic', outcome,
  selected:null, offline:{accepted:false, method:'deterministic_document_parser', reason:'NOT_CANONICAL'},
  families, review_requirements:[], source_sha256:HEX('c'), selection_sha256:HEX('e'),
  authority:{approval_gate:false, dispatch_authorized:false}, ...extra});
const READY = VIEW('NOT_SUBMITTED', [FAMILY(MONTHLY, 'Monthly availability'), FAMILY(RESOURCE, 'Resource month')]);
const PENDING = VIEW('PENDING', [FAMILY(MONTHLY, 'Monthly availability', {job:JOB('QUEUED'), state:'PENDING'}),
  FAMILY(RESOURCE, 'Resource month', {job:JOB('QUEUED', {job_id:'job-2'}), state:'PENDING'})]);
const REFUSAL = {codes:['REQUIRED_TERMS_MISSING'], explanations:['No passage establishes the listed required terms.'],
  passages:['Vendor: <img src=x onerror=alert(1)>'], missing_terms:['claim filing deadline']};
const SELECTED = VIEW('SELECTED', [FAMILY(MONTHLY, 'Monthly availability', {job:JOB('SUCCEEDED'), state:'VALIDATED'}),
  FAMILY(RESOURCE, 'Resource month', {job:JOB('REFUSED', {job_id:'job-2'}), state:'REFUSED_READING', refusal:REFUSAL})],
  {selected:{family:MONTHLY, method:'public_proposal_job', job_id:'job-1', profile:'monthly-propositions'},
   review_requirements:['Uptime selected the monthly availability family: it alone validated the complete source.',
     'Resource month: No passage establishes the listed required terms. Missing: claim filing deadline.']});
const BODY = {document:{name:'Aster Cove SLA', uri:'urn:authored:test', classification:'synthetic_public', text:SOURCE},
  profile:'auto', attempt_nonce:'initial'};

const button = (root, name) => root.all('button').find(b => b.textContent === name);
const click = (root, name) => button(root, name).listeners.click();
const byClass = (root, cls) => root.all('div').find(n => String(n.className).split(' ').includes(cls));
const posts = (s, suffix) => s.calls.filter(c => c.body !== undefined && c.path.endsWith(suffix));
const gets = (s, part) => s.calls.filter(c => c.body === undefined && c.path.includes(part));

function setup({answer = READY, submit, statuses = {}, access = {canDraft:true}} = {}) {
  const root = new Element('main'), calls = [], timers = [];
  let accessAnswer = answer;
  const api = async (path, body) => {
    calls.push({path, body:body === undefined ? undefined : JSON.parse(JSON.stringify(body))});
    if (body === undefined && path === '/api/vendors') return {vendors:[]};
    if (path.endsWith('/proposal-access')) return typeof accessAnswer === 'function' ? accessAnswer() : accessAnswer;
    if (path.endsWith('/proposal-jobs')) return submit ? submit() : PENDING;
    if (body === undefined && path.includes('/proposal-jobs/')) {
      const id = decodeURIComponent(path.split('/').pop()), queue = statuses[id] || [];
      return queue.length ? queue.shift() : JOB('RUNNING', {job_id:id});
    }
    if (path.endsWith('/candidate') || path.endsWith('/candidates')) return {state:'SHADOW', reviewer:null, actions:[]};
    throw new Error('Unexpected request ' + path);
  };
  const ui = create({document, reviewForms:true, getAccess:() => access, api, schedule:(callback, ms) => timers.push({callback, ms})});
  return {root, ui, calls, timers, answer:value => { accessAnswer = value; }};
}

async function mounted(options) {
  const s = setup(options);
  await s.ui.render(s.root, 'vendors');
  const box = byClass(s.root, 'v4-generator');
  const f = Object.fromEntries([...box.all('input'), ...box.all('textarea'), ...box.all('select')].map(n => [n.name, n]));
  f.vendor_id.value = 'aster-cove'; f.name.value = BODY.document.name; f.uri.value = BODY.document.uri;
  f.classification.value = 'synthetic_public'; f.text.value = SOURCE;
  return {...s, box, f};
}

test('the client never names a rule family', async () => {
  const s = await mounted();
  assert.equal(s.f.profile, undefined, 'no extraction profile control exists');
  assert.equal(s.box.all('select').filter(n => /profile/i.test(n.getAttribute?.('aria-label') || n.name)).length, 0);
  await click(s.root, 'Check generation access');
  assert.equal(posts(s, '/proposal-access')[0].body.profile, 'auto');
});

test('generation controls stay disabled without draft access and send nothing', async () => {
  const s = await mounted({access:{}});
  assert.equal(button(s.root, 'Check generation access').disabled, true);
  assert.equal(button(s.root, 'Generate proposals').disabled, true);
  await click(s.root, 'Check generation access');
  await click(s.root, 'Generate proposals');
  assert.equal(s.calls.filter(c => c.body !== undefined).length, 0);
});

test('access check posts exact untrimmed public fields only; unapproved families keep generation disabled', async () => {
  const requirement = 'An operator must approve the exact public request for every supported family before automatic selection starts. Not yet approved: Resource month.';
  const s = await mounted({answer:VIEW('APPROVAL_REQUIRED', [FAMILY(MONTHLY, 'Monthly availability'),
    FAMILY(RESOURCE, 'Resource month', {enabled:false, approval_reason:'exact_request_not_approved'})], {review_requirements:[requirement]})});
  assert.equal(s.f.attempt_nonce.value, 'initial');
  await click(s.root, 'Check generation access');
  const sent = posts(s, '/proposal-access');
  assert.equal(sent.length, 1);
  assert.equal(sent[0].path, '/api/vendors/aster-cove/proposal-access');
  assert.deepEqual(sent[0].body, BODY);
  assert.equal(sent[0].body.document.text, SOURCE, 'leading/trailing whitespace and CRLF are preserved');
  assert.deepEqual(Object.keys(sent[0].body).sort(), ['attempt_nonce', 'document', 'profile']);
  assert.ok(s.root.textContent.includes(requirement), 'review requirements are shown verbatim');
  assert.match(s.root.textContent, /this exact document request needs operator approval/);
  assert.equal(button(s.root, 'Generate proposals').disabled, true);
  await click(s.root, 'Generate proposals');
  assert.equal(posts(s, '/proposal-jobs').length, 0, 'browser state cannot grant generation');
});

test('any edit invalidates access confirmation, including programmatic edits', async () => {
  const s = await mounted();
  await click(s.root, 'Check generation access');
  assert.equal(button(s.root, 'Generate proposals').disabled, false);
  s.f.text.value = SOURCE + ' '; s.f.text.listeners.input();
  assert.equal(button(s.root, 'Generate proposals').disabled, true);
  assert.doesNotMatch(s.root.textContent, /Automatic rule-family selection/);
  await click(s.root, 'Check generation access');
  assert.equal(posts(s, '/proposal-access')[1].body.document.text, SOURCE + ' ');
  s.f.attempt_nonce.value = 'retry-1';  // no event fired
  await click(s.root, 'Generate proposals');
  assert.equal(posts(s, '/proposal-jobs').length, 0);
  assert.match(s.root.textContent, /changed after its access check/);
  assert.equal(button(s.root, 'Generate proposals').disabled, true);
});

test('explicit generation, GET-only polling, explicit refresh, safe text and staging only the selected job', async () => {
  const s = await mounted({statuses:{'job-1':[JOB('RUNNING'), SUCCEEDED, SUCCEEDED], 'job-2':[JOB('RUNNING', {job_id:'job-2'}), JOB('REFUSED', {job_id:'job-2'})]}});
  await click(s.root, 'Check generation access');
  await click(s.root, 'Generate proposals');
  assert.equal(posts(s, '/proposal-jobs').length, 1);
  assert.deepEqual(posts(s, '/proposal-jobs')[0].body, BODY);
  assert.equal(button(s.root, 'Generate proposals').disabled, true);
  assert.equal(s.timers.length, 1);
  await s.timers.shift().callback();
  await s.timers.shift().callback();
  assert.equal(s.timers.length, 0, 'polling stops when every family job is terminal');
  assert.deepEqual(gets(s, '/proposal-jobs/').map(c => c.path), ['/api/vendors/aster-cove/proposal-jobs/job-1',
    '/api/vendors/aster-cove/proposal-jobs/job-2', '/api/vendors/aster-cove/proposal-jobs/job-1', '/api/vendors/aster-cove/proposal-jobs/job-2']);
  assert.equal(posts(s, '/proposal-access').length, 1, 'polling never posts');
  assert.match(s.root.textContent, /Every family evaluation has finished/);
  assert.equal(button(s.root, 'Review shadow candidate request'), undefined, 'no staging before a SELECTED outcome');
  s.answer(SELECTED);
  await click(s.root, 'Refresh proposal status');
  assert.equal(posts(s, '/proposal-access').length, 2);
  assert.equal(posts(s, '/proposal-jobs').length, 1, 'refresh never resubmits');
  assert.ok(s.root.textContent.includes(SELECTED.review_requirements[1]));
  assert.match(s.root.textContent, /Why this family was refused/);
  assert.match(s.root.textContent, /claim filing deadline/);
  for (const quote of s.root.all('blockquote').filter(n => n.textContent.includes('<img'))) {
    assert.equal(quote.textContent, 'Vendor: <img src=x onerror=alert(1)>');
    assert.equal(quote.children.length, 0, 'quotes render as text, never markup');
  }
  assert.equal(s.root.all('img').length + s.root.all('b').length, 0);
  assert.match(s.root.textContent, /unreviewed and not approved/);
  for (const name of ['Approve', 'Approve reviewed tests', 'Activate', 'Activate for local evaluation']) assert.equal(button(s.root, name), undefined);
  const overlay = byClass(s.root, 'v4-candidate').all('textarea')[0];
  overlay.value = '{"account":"clearwater-001","fee_line_ref":"queue-monthly"}';
  await click(s.root, 'Review shadow candidate request');
  assert.equal(posts(s, '/candidate').length, 0);
  assert.match(s.root.textContent, /Review exact candidate request/);
  overlay.value = '{"account":"clearwater-002"}'; overlay.listeners.input();
  await click(s.root, 'Review shadow candidate request');
  assert.equal(posts(s, '/candidate').length, 0, 'editing the overlay requires another review');
  await click(s.root, 'Confirm shadow candidate');
  const staged = posts(s, '/candidate');
  assert.equal(staged.length, 1);
  assert.equal(staged[0].path, '/api/vendors/aster-cove/proposal-jobs/job-1/candidate');
  assert.deepEqual(staged[0].body, {overlay:{account:'clearwater-002'}});
  for (const call of s.calls.filter(c => !c.path.endsWith('/candidate'))) {
    assert.ok(!JSON.stringify(call.body ?? null).includes('clearwater'), 'the private overlay never joins a generation request');
  }
});

test('offline selection stages the exact source through the deterministic candidate route with no job', async () => {
  const offline = VIEW('SELECTED', [FAMILY(MONTHLY, 'Monthly availability'), FAMILY(RESOURCE, 'Resource month')],
    {selected:{family:MONTHLY, method:'deterministic_document_parser', job_id:null, profile:null},
     offline:{accepted:true, method:'deterministic_document_parser', reason:null}});
  const s = await mounted({answer:offline});
  await click(s.root, 'Check generation access');
  assert.equal(button(s.root, 'Generate proposals').disabled, true);
  assert.match(s.root.textContent, /no model call/);
  const overlay = byClass(s.root, 'v4-candidate').all('textarea')[0];
  overlay.value = '{"account":"clearwater-003"}';
  await click(s.root, 'Review shadow candidate request');
  await click(s.root, 'Confirm shadow candidate');
  const staged = posts(s, '/candidates');
  assert.equal(staged.length, 1);
  assert.equal(staged[0].path, '/api/vendors/aster-cove/candidates');
  assert.deepEqual(staged[0].body, {document:BODY.document, overlay:{account:'clearwater-003'}});
  assert.equal(staged[0].body.document.text, SOURCE, 'the staged source is the exact untrimmed text');
  assert.equal(posts(s, '/proposal-jobs').length + gets(s, '/proposal-jobs/').length, 0);
});

test('non-selected outcomes and non-selected jobs offer no staging control', async () => {
  for (const outcome of ['AMBIGUOUS', 'NO_SUPPORTED_FAMILY', 'INCOMPLETE']) {
    const s = await mounted({answer:VIEW(outcome, [FAMILY(MONTHLY, 'Monthly availability', {job:JOB('SUCCEEDED'), state:'VALIDATED'}),
      FAMILY(RESOURCE, 'Resource month', {job:JOB('SUCCEEDED', {job_id:'job-2'}), state:'VALIDATED'})],
      {review_requirements:['More than one supported rule family validated this complete source.']})});
    await click(s.root, 'Check generation access');
    assert.equal(button(s.root, 'Review shadow candidate request'), undefined, outcome);
    assert.equal(posts(s, '/candidate').length + posts(s, '/candidates').length, 0);
    assert.match(s.root.textContent, /No candidate can be staged/);
  }
  // A job the selection did not choose never receives a staging control, even when the server marks it available.
  const t = await mounted({answer:{...SELECTED, selected:{...SELECTED.selected, job_id:'job-1'}}, statuses:{'job-1':[{...SUCCEEDED, job_id:'job-3'}]}});
  await click(t.root, 'Check generation access');
  assert.equal(button(t.root, 'Review shadow candidate request'), undefined, 'a mismatched job is not shown or staged');
});

test('a lost reservation response is recovered by an explicit access recheck, never a second POST', async () => {
  const s = await mounted({submit:() => { throw new Error('connection reset'); }});
  await click(s.root, 'Check generation access');
  await click(s.root, 'Generate proposals');
  assert.match(s.root.textContent, /may have been queued/);
  assert.equal(button(s.root, 'Generate proposals').disabled, true);
  await click(s.root, 'Generate proposals');
  assert.equal(posts(s, '/proposal-jobs').length, 1);
  s.answer(PENDING);
  await click(s.root, 'Check generation access');
  assert.equal(posts(s, '/proposal-jobs').length, 1);
  assert.match(s.root.textContent, /job-1/);
  assert.equal(button(s.root, 'Generate proposals').disabled, true);
  assert.equal(s.timers.length, 1, 'read-only status polling resumes for the recovered jobs');
});

test('superseded or unmounted asynchronous responses are ignored', async () => {
  let release;
  const s = await mounted({answer:() => new Promise(resolve => { release = () => resolve(READY); })});
  const pending = click(s.root, 'Check generation access');
  s.f.name.value = 'Edited name'; s.f.name.listeners.input();
  release(); await pending;
  assert.equal(button(s.root, 'Generate proposals').disabled, true);
  assert.doesNotMatch(s.root.textContent, /Automatic rule-family selection/);
  const t = await mounted();
  await click(t.root, 'Check generation access');
  await click(t.root, 'Generate proposals');
  t.ui.unmount(t.root);
  const before = t.calls.length;
  await t.timers.shift().callback();
  assert.equal(t.calls.length, before);
});

test('local deterministic intake stays a separate, labeled local validation form', async () => {
  const s = setup();
  await s.ui.render(s.root, 'vendors');
  assert.ok(button(s.root, 'Stage local candidate'));
  assert.match(s.root.textContent, /does not call a model/);
  assert.equal(s.root.all('form').length, 1, 'generation is not a form and cannot be submitted implicitly');
  assert.equal(s.calls.filter(c => c.body !== undefined).length, 0);
});
