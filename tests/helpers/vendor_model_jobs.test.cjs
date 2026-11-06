'use strict';
// DOM contract for public proposal generation with a recorded fake API client.
// Authored controls only: this is not an end-to-end browser, shared-service or model proof.
const test = require('node:test');
const assert = require('node:assert/strict');
const {Element, document} = require('./companion_dom.cjs');
const {create} = require('../../web/v4_ui.js');

const SOURCE = '\n  Vendor: <img src=x onerror=alert(1)>\r\nAgreement: ACC-2026-17\t \n';
const HEX = c => c.repeat(64);
const JOB = (status, extra = {}) => ({job_id:'job-1', status, vendor_id:'aster-cove', request_sha256:HEX('a'),
  context_sha256:HEX('b'), candidate_available:false, ...extra});
const SUCCEEDED = JOB('SUCCEEDED', {candidate_available:true, proposal:{profile:'monthly', attempt_nonce:'initial',
  source_sha256:HEX('c'), proposal_sha256:HEX('d'), model:'claude-opus-5-5', session:'synthetic-test-double-not-a-model-session',
  document:{name:'Aster Cove SLA', uri:'urn:authored:test', classification:'synthetic_public'},
  clauses:[{quote:'Vendor: <img src=x onerror=alert(1)>', field:'vendor', value:'<b>Aster</b>'},
    {quote:'Agreement: ACC-2026-17', field:'agreement', value:'ACC-2026-17'}]}});
const PERMITTED = {enabled:true, reason:'APPROVED', request_sha256:HEX('a'), context_sha256:HEX('b'), existing_job:null,
  disclosure:{model:'claude-opus-5-5', tools:[], transmitted_fields:['input','model']}};
const BODY = {document:{name:'Aster Cove SLA', uri:'urn:authored:test', classification:'synthetic_public', text:SOURCE},
  profile:'monthly', attempt_nonce:'initial'};

const button = (root, name) => root.all('button').find(b => b.textContent === name);
const click = (root, name) => button(root, name).listeners.click();
const byClass = (root, cls) => root.all('div').find(n => String(n.className).split(' ').includes(cls));
const posts = (s, suffix) => s.calls.filter(c => c.body !== undefined && c.path.endsWith(suffix));

function setup({answer = PERMITTED, submit, statuses = [], access = {canDraft:true}} = {}) {
  const root = new Element('main'), calls = [], timers = [];
  let accessAnswer = answer;
  const api = async (path, body) => {
    calls.push({path, body:body === undefined ? undefined : JSON.parse(JSON.stringify(body))});
    if (body === undefined && path === '/api/vendors') return {vendors:[]};
    if (path.endsWith('/proposal-access')) return typeof accessAnswer === 'function' ? accessAnswer() : accessAnswer;
    if (path.endsWith('/proposal-jobs')) return submit ? submit() : JOB('QUEUED');
    if (body === undefined && path.includes('/proposal-jobs/')) return statuses.length ? statuses.shift() : JOB('RUNNING');
    if (path.endsWith('/candidate')) return {state:'SHADOW', reviewer:null, actions:[]};
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
  f.classification.value = 'synthetic_public'; f.profile.value = 'monthly'; f.text.value = SOURCE;
  return {...s, box, f};
}

test('generation controls stay disabled without draft access and send nothing', async () => {
  const s = await mounted({access:{}});
  assert.equal(button(s.root, 'Check generation access').disabled, true);
  assert.equal(button(s.root, 'Generate proposal').disabled, true);
  await click(s.root, 'Check generation access');
  await click(s.root, 'Generate proposal');
  assert.equal(s.calls.filter(c => c.body !== undefined).length, 0);
});

test('access check posts exact untrimmed public fields only; server refusal keeps generation disabled', async () => {
  const s = await mounted({answer:{...PERMITTED, enabled:false, reason:'APPROVAL_REQUIRED'}});
  assert.equal(s.f.attempt_nonce.value, 'initial');
  await click(s.root, 'Check generation access');
  const sent = posts(s, '/proposal-access');
  assert.equal(sent.length, 1);
  assert.equal(sent[0].path, '/api/vendors/aster-cove/proposal-access');
  assert.deepEqual(sent[0].body, BODY);
  assert.equal(sent[0].body.document.text, SOURCE, 'leading/trailing whitespace and CRLF are preserved');
  assert.deepEqual(Object.keys(sent[0].body).sort(), ['attempt_nonce', 'document', 'profile']);
  assert.match(s.root.textContent, /APPROVAL_REQUIRED/);
  assert.equal(button(s.root, 'Generate proposal').disabled, true);
  await click(s.root, 'Generate proposal');
  assert.equal(posts(s, '/proposal-jobs').length, 0, 'browser state cannot grant generation');
});

test('any edit invalidates access confirmation, including programmatic edits', async () => {
  const s = await mounted();
  await click(s.root, 'Check generation access');
  assert.equal(button(s.root, 'Generate proposal').disabled, false);
  s.f.text.value = SOURCE + ' '; s.f.text.listeners.input();
  assert.equal(button(s.root, 'Generate proposal').disabled, true);
  assert.doesNotMatch(s.root.textContent, /Server generation access/);
  await click(s.root, 'Check generation access');
  assert.equal(posts(s, '/proposal-access')[1].body.document.text, SOURCE + ' ');
  s.f.attempt_nonce.value = 'retry-1';  // no event fired
  await click(s.root, 'Generate proposal');
  assert.equal(posts(s, '/proposal-jobs').length, 0);
  assert.match(s.root.textContent, /changed after its access check/);
  assert.equal(button(s.root, 'Generate proposal').disabled, true);
});

test('explicit generation, read-only polling, safe quotes and a separate overlay request', async () => {
  const s = await mounted({statuses:[JOB('RUNNING'), SUCCEEDED]});
  await click(s.root, 'Check generation access');
  await click(s.root, 'Generate proposal');
  assert.equal(posts(s, '/proposal-jobs').length, 1);
  assert.deepEqual(posts(s, '/proposal-jobs')[0].body, BODY);
  assert.equal(button(s.root, 'Generate proposal').disabled, true);
  assert.equal(s.timers.length, 1);
  await s.timers.shift().callback();
  await s.timers.shift().callback();
  assert.equal(s.timers.length, 0, 'polling stops at a terminal state');
  const reads = s.calls.filter(c => c.path.includes('/proposal-jobs/'));
  assert.deepEqual(reads.map(c => [c.path, c.body]), [['/api/vendors/aster-cove/proposal-jobs/job-1', undefined],
    ['/api/vendors/aster-cove/proposal-jobs/job-1', undefined]]);
  const quote = s.root.all('blockquote').find(n => n.textContent.includes('<img'));
  assert.equal(quote.textContent, 'Vendor: <img src=x onerror=alert(1)>');
  assert.equal(quote.children.length, 0, 'quotes render as text, never markup');
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

test('a lost reservation response is recovered by an explicit access recheck, never a second POST', async () => {
  const s = await mounted({submit:() => { throw new Error('connection reset'); }});
  await click(s.root, 'Check generation access');
  await click(s.root, 'Generate proposal');
  assert.match(s.root.textContent, /may have been queued/);
  assert.equal(button(s.root, 'Generate proposal').disabled, true);
  await click(s.root, 'Generate proposal');
  assert.equal(posts(s, '/proposal-jobs').length, 1);
  s.answer({...PERMITTED, existing_job:JOB('QUEUED')});
  await click(s.root, 'Check generation access');
  assert.equal(posts(s, '/proposal-jobs').length, 1);
  assert.match(s.root.textContent, /already has a proposal job/);
  assert.match(s.root.textContent, /job-1/);
  assert.equal(button(s.root, 'Generate proposal').disabled, true);
  assert.equal(s.timers.length, 1, 'read-only status polling resumes for the recovered job');
});

test('superseded or unmounted asynchronous responses are ignored', async () => {
  let release;
  const s = await mounted({answer:() => new Promise(resolve => { release = () => resolve(PERMITTED); })});
  const pending = click(s.root, 'Check generation access');
  s.f.name.value = 'Edited name'; s.f.name.listeners.input();
  release(); await pending;
  assert.equal(button(s.root, 'Generate proposal').disabled, true);
  assert.doesNotMatch(s.root.textContent, /Server generation access/);
  const t = await mounted({statuses:[SUCCEEDED]});
  await click(t.root, 'Check generation access');
  await click(t.root, 'Generate proposal');
  t.ui.unmount(t.root);
  const before = t.calls.length;
  await t.timers.shift().callback();
  assert.equal(t.calls.length, before);
});

test('refused or stale results offer no candidate and are never retried automatically', async () => {
  const s = await mounted({statuses:[JOB('REFUSED', {reason:'PROPOSAL_REFUSED'})]});
  await click(s.root, 'Check generation access');
  await click(s.root, 'Generate proposal');
  await s.timers.shift().callback();
  assert.match(s.root.textContent, /refused the model output/);
  assert.equal(button(s.root, 'Review shadow candidate request'), undefined);
  assert.equal(s.timers.length, 0);
  assert.equal(posts(s, '/proposal-jobs').length, 1);
  const t = await mounted({statuses:[JOB('SUCCEEDED', {candidate_available:false, refusal:'STALE_CONTEXT'})]});
  await click(t.root, 'Check generation access');
  await click(t.root, 'Generate proposal');
  await t.timers.shift().callback();
  assert.match(t.root.textContent, /semantics changed after generation/);
  assert.equal(button(t.root, 'Review shadow candidate request'), undefined);
});

test('local deterministic intake stays a separate, labeled local validation form', async () => {
  const s = setup();
  await s.ui.render(s.root, 'vendors');
  assert.ok(button(s.root, 'Stage local candidate'));
  assert.match(s.root.textContent, /does not call a model/);
  assert.equal(s.root.all('form').length, 1, 'generation is not a form and cannot be submitted implicitly');
  assert.equal(s.calls.filter(c => c.body !== undefined).length, 0);
});
