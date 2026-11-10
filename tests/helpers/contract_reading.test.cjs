'use strict';
// How a contract was read (demo line, November 10): pure term-to-sentence linking, replay order and job state words,
// plus the Agreements page's two-column view and the live reading panel against a recorded fake API client.
// Authored controls only: no server, no model.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {Element, document} = require('./companion_dom.cjs');
const R = require('../../web/contract_reading.js');
const {create} = require('../../web/v4_ui.js');

const ROOT = path.resolve(__dirname, '..', '..');
const TEXT = 'Vendor: Calyx.\nCredit is 12% below 99.9%.\nVendor: Calyx.\n';

test('the sample contracts are the authored fixtures, byte for byte', () => {
  assert.equal(R.SAMPLES.length, 3);
  for (const sample of R.SAMPLES) {
    const fixture = JSON.parse(fs.readFileSync(path.join(ROOT, sample.fixture), 'utf8'));
    assert.deepEqual(sample.document, fixture);
    assert.match(sample.vendor_id, /^[a-z0-9][a-z0-9_-]{0,79}$/);
  }
  assert.deepEqual(R.TAKES, ['retry-take1', 'retry-take2', 'retry-take3']);
});

test('a term is tied to its sentence at its recorded position, or found word for word, or named as missing', () => {
  const terms = [
    {id:1, quote:'Vendor: Calyx.', start:0, end:14},
    {id:2, quote:'Credit is 12% below 99.9%.', start:null, end:null},
    {id:3, quote:'Vendor: Calyx.', start:null, end:null},
    {id:4, quote:'Not in the contract.', start:null, end:null},
    {id:5, quote:'Credit is 12% below 99.9%.', start:3, end:20}];
  const links = R.linkTerms(TEXT, terms);
  assert.deepEqual(links[0], {id:1, start:0, end:14, match:'recorded'});
  assert.deepEqual(links[1], {id:2, start:15, end:41, match:'found'});
  // A repeated quote takes its next unused occurrence.
  assert.deepEqual(links[2], {id:3, start:42, end:56, match:'found'});
  assert.deepEqual(links[3], {id:4, start:null, end:null, match:'missing'});
  // A recorded position whose text differs is not trusted; the quote is searched for instead.
  assert.equal(links[4].match, 'moved');
  assert.deepEqual(R.verbatim(links), {total:5, found:4, atRecorded:1, all:false});
  assert.equal(R.verbatim(links.slice(0, 3)).all, true);
  assert.equal(R.verbatim([]).all, false);
});

test('segments cover the text exactly and name the terms over each piece', () => {
  const links = R.linkTerms(TEXT, [{id:'a', quote:'Calyx.\nCredit', start:null, end:null}, {id:'b', quote:'Credit is', start:null, end:null}]);
  const pieces = R.segments(TEXT, links);
  assert.equal(pieces.map(p => p.text).join(''), TEXT);
  assert.deepEqual(pieces.find(p => p.text === 'Credit').ids, ['a', 'b']);
  assert.deepEqual(pieces.find(p => p.text === 'Calyx.\n').ids, ['a']);
  assert.deepEqual(pieces[0].ids, []);
});

test('replay goes through the found terms in reading order and skips missing ones', () => {
  const links = [{id:3, start:40, end:50}, {id:1, start:0, end:5}, {id:2, start:null, end:null}, {id:4, start:0, end:3}, {id:10, start:40, end:50}];
  assert.deepEqual(R.replayOrder(links), [4, 1, 3, 10]);
});

test('job states read as submitted, started, finished, or failed with the reason', () => {
  assert.equal(R.jobStateWords({status:'QUEUED'}).word, 'Submitted');
  assert.equal(R.jobStateWords({status:'RUNNING'}).word, 'Started: Claude is reading the contract');
  assert.match(R.jobStateWords({status:'SUCCEEDED'}).word, /^Finished: every quote was checked/);
  assert.equal(R.jobStateWords({status:'REFUSED', reason:'proposal_validation_failed'}).word, 'Finished: validation refused this reading');
  assert.equal(R.jobStateWords({status:'REFUSED', reason:'provider_failed'}).word, 'Failed: the model call failed');
  assert.equal(R.jobStateWords({status:'UNCERTAIN', reason:'provider_timeout'}).word, 'Failed: the model did not finish within the allowed time');
  assert.equal(R.jobStateWords({status:'CANCELLED', reason:'restart_before_dispatch'}).word, 'Failed: the server restarted before the call');
  assert.equal(R.jobStateWords({status:'REFUSED', reason:'something_new'}).word, 'Failed: something new');
  assert.equal(R.jobStateWords({status:'QUEUED'}).terminal, false);
  assert.equal(R.jobStateWords({status:'UNCERTAIN'}).terminal, true);
});

test('a take is fresh, running, used, not approved, unconfigured or read by fixed rules', () => {
  assert.equal(R.takeState({outcome:'NOT_SUBMITTED'}), 'fresh');
  assert.equal(R.takeState({outcome:'PENDING'}), 'running');
  assert.equal(R.takeState({outcome:'SELECTED', selected:{method:'public_proposal_job'}}), 'used');
  assert.equal(R.takeState({outcome:'NO_SUPPORTED_FAMILY'}), 'used');
  assert.equal(R.takeState({outcome:'APPROVAL_REQUIRED'}), 'not_approved');
  assert.equal(R.takeState({outcome:'PROVIDER_UNCONFIGURED'}), 'unconfigured');
  assert.equal(R.takeState({outcome:'SELECTED', selected:{method:'deterministic_document_parser'}}), 'fixed_rules');
  assert.equal(R.takeState(null), 'unknown');
});

const CALYX = {vendor_id:'calyxquay', name:'CalyxQuay', state:'ACTIVE', revision:14, active_version:'v14', actions:[],
  reviewer:'scripted-test-reviewer', reviewer_kind:'scripted_test', interpretation_reviewer:'scripted-test-reviewer',
  extraction:{method:'tool_free_model_propositions', model:'claude-opus-5-5', at:'2026-11-05T01:59:33.188612+00:00', session:'s-1'},
  source_text:TEXT,
  manifest:{citations:[
    {id:1, field:'resource_terms', quote:'Vendor: Calyx.', start:0, end:14, propositions:{vendor:'Calyx'}},
    {id:2, field:'resource_terms', quote:'Credit is 12% below 99.9%.', start:15, end:41, propositions:{tiers:[{below:'99.9', credit:'12'}], boundary:'strict_below'}}]}};
const NORTHWIND = {vendor_id:'northwind-cloud', name:'Northwind Cloud', state:'ACTIVE', revision:6, active_version:'v6', actions:[],
  reviewer:'scripted-test-reviewer', reviewer_kind:'scripted_test', interpretation_reviewer:null,
  extraction:{method:'deterministic_document_parser'}, source_text:'Service Level Agreement\nVendor: Northwind Cloud\n',
  manifest:{vendor:'Northwind Cloud', citations:[{id:1, field:'heading', quote:'Service Level Agreement', start:0, end:23},
    {id:2, field:'vendor', quote:'Vendor: Northwind Cloud', start:24, end:47}]}};

test('terms of an installed agreement carry their labels and the values the server sent', () => {
  const calyx = R.termsFromRecord(CALYX);
  assert.deepEqual(calyx.map(t => t.label), ['Vendor', 'Tiers, boundary']);
  assert.deepEqual(calyx[0].value, {vendor:'Calyx'});
  assert.equal(R.termLabel('resource_terms', {nonmaterial:'section heading'}), 'Not a term: section heading');
  const northwind = R.termsFromRecord(NORTHWIND);
  assert.deepEqual(northwind.map(t => [t.label, t.value]), [['Heading', null], ['Vendor', 'Northwind Cloud']]);
  assert.deepEqual(R.readingSummary(CALYX), {kind:'model', model:'claude-opus-5-5', modelName:'Claude Opus 5.5',
    recordedAt:'2026-11-05T01:59:33.188612+00:00', session:'s-1', approver:'scripted-test-reviewer', approverKind:'scripted_test', interpretationAccepted:true});
  assert.equal(R.readingSummary(NORTHWIND).kind, 'rules');
  assert.equal(R.readingSummary({extraction:{method:'other'}}).kind, null);
});

const byClass = (root, cls) => [root, ...root.all('div'), ...root.all('p'), ...root.all('span'), ...root.all('pre'), ...root.all('li'), ...root.all('details')]
  .filter(n => String(n.className).split(' ').includes(cls));
const button = (root, name) => root.all('button').find(b => b.textContent === name);

function page(vendors, access = {}) {
  const root = new Element('main'), calls = [], timers = [];
  const api = async (p, body) => { calls.push({p, body}); if (p === '/api/vendors') return {vendors}; throw Object.assign(new Error('x'), {status:404}); };
  const ui = create({document, getAccess:() => access, api, schedule:(callback, ms) => timers.push({callback, ms})});
  return {root, ui, calls, timers};
}

test('a model-read agreement shows its text beside its terms, the record’s facts and a recorded replay', async () => {
  const s = page([CALYX]);
  await s.ui.render(s.root, 'vendors');
  const box = byClass(s.root, 'v4-reading')[0];
  const text = box.textContent;
  assert.match(text, /How this contract was read/);
  assert.match(text, /Claude Opus 5\.5 read this contract/);
  assert.match(text, /Model: claude-opus-5-5/);
  assert.match(text, /Every quoted sentence was found word for word in the source \(2 of 2, checked on this page\)/);
  assert.match(text, /Interpretation accepted by scripted-test-reviewer \(a scripted test account, not a person\)/);
  assert.match(text, /Recorded run · Nov 5, 2026, 01:59 UTC/);
  assert.doesNotMatch(text, /\blive\b/i);
  const sentences = byClass(box, 'v4-reading-sentence'), terms = byClass(box, 'v4-reading-term');
  assert.deepEqual(sentences.map(n => n.textContent), ['Vendor: Calyx.', 'Credit is 12% below 99.9%.']);
  // Hovering a term lights its sentence; hovering a sentence lights its term.
  terms[1].listeners.mouseenter();
  assert.match(sentences[1].className, /v4-lit/); assert.doesNotMatch(sentences[0].className, /v4-lit/);
  sentences[0].listeners.mouseenter();
  assert.match(terms[0].className, /v4-lit/); assert.doesNotMatch(terms[1].className, /v4-lit/);
  // Replay: every term hidden, then shown one at a time in reading order with its sentence lit.
  await button(box, 'Replay the reading').listeners.click();
  assert.equal(terms.filter(t => /v4-replay-hidden/.test(t.className)).length, 1);
  assert.match(sentences[0].className, /v4-lit/);
  s.timers.shift().callback();
  assert.equal(terms.filter(t => /v4-replay-hidden/.test(t.className)).length, 0);
  assert.match(sentences[1].className, /v4-lit/);
  s.timers.shift().callback();
  assert.ok(button(box, 'Replay the reading'));
  assert.equal(sentences.filter(n => /v4-lit/.test(n.className)).length, 0);
});

test('a rules-read agreement says fixed rules read it and names no model', async () => {
  const s = page([NORTHWIND]);
  await s.ui.render(s.root, 'vendors');
  const text = byClass(s.root, 'v4-reading')[0].textContent;
  assert.match(text, /Read by fixed rules/);
  assert.match(text, /No model was used/);
  assert.match(text, /Recorded reading by fixed rules/);
  assert.match(text, /Approved by scripted-test-reviewer/);
  assert.doesNotMatch(s.root.textContent, /Claude|Recorded run/);
});

test('when the server sends no source text, the view says exactly what is missing', async () => {
  const s = page([{...CALYX, source_text:undefined}]);
  await s.ui.render(s.root, 'vendors');
  const text = byClass(s.root, 'v4-reading')[0].textContent;
  assert.match(text, /The server did not send the contract’s source text for this agreement/);
  assert.match(text, /Vendor: Calyx\./);
  assert.equal(button(s.root, 'Replay the reading'), undefined);
});

// ---- The live reading panel ----
const HEX = c => c.repeat(64);
const MONTHLY = 'monthly-availability/1', RESOURCE = 'resource-month/1';
const CORVID = R.SAMPLES[0].document;
const CLAUSES = [{quote:'This contract is identified as CDC-SLA-07.', field:'agreement', value:'CDC-SLA-07'},
  {quote:'The service provider under this agreement is Corvid Data Cooperative.', field:'vendor', value:'Corvid Data Cooperative'}];
const JOB = (id, status, extra = {}) => ({job_id:id, status, vendor_id:'corvid-ledger', request_sha256:HEX('a'), context_sha256:HEX('b'), ...extra});
const DONE = JOB('j-1', 'SUCCEEDED', {finished_at:'2026-11-10T18:02:03Z', provider:{model:'claude-opus-5-5'}, candidate_available:true,
  proposal:{model:'claude-opus-5-5', clauses:CLAUSES}});
const FAM = (family, label, job, extra = {}) => ({family, label, job, request_sha256:HEX('c'), ...extra});
const VIEW = (outcome, families, extra = {}) => ({outcome, families, selected:null, review_requirements:[], ...extra});

function livePage(access, answers, jobs) {
  const root = new Element('main'), calls = [], timers = [];
  const api = async (p, body) => {
    calls.push({p, body:body === undefined ? undefined : JSON.parse(JSON.stringify(body))});
    if (p === '/api/vendors') return {vendors:[]};
    if (p.endsWith('/proposal-access')) return answers.access(body);
    if (p.endsWith('/proposal-jobs')) return answers.submit(body);
    if (p.includes('/proposal-jobs/')) { const id = p.split('/').pop(); return (jobs[id] || []).length > 1 ? jobs[id].shift() : jobs[id][0]; }
    throw new Error('Unexpected ' + p);
  };
  const ui = create({document, getAccess:() => access, api, schedule:(callback, ms) => timers.push({callback, ms})});
  return {root, ui, calls, timers};
}
const settle = () => new Promise(resolve => setImmediate(resolve));
async function drive(s, promise) {
  for (let i = 0; i < 50; i++) { await settle(); if (s.timers.length) s.timers.shift().callback(); }
  await promise;
}

test('the live panel is offered only to an account that may stage drafts', async () => {
  const s = livePage({}, {}, {});
  await s.ui.render(s.root, 'vendors');
  assert.doesNotMatch(s.root.textContent, /Read a contract with Claude/);
  const w = livePage({canDraft:true}, {}, {});
  await w.ui.render(w.root, 'vendors');
  assert.match(w.root.textContent, /Read a contract with Claude/);
  assert.match(w.root.textContent, /Live: Start sends the chosen contract to Claude Opus 5\.5 now/);
});

test('a live reading submits one real job request, shows each job state as it changes, then the terms beside their sentences, unreviewed', async () => {
  let submitted = false;
  const families = () => [FAM(MONTHLY, 'Monthly availability', JOB('j-1', 'QUEUED')), FAM(RESOURCE, 'Resource month', JOB('j-2', 'QUEUED'))];
  const answers = {
    access: body => !submitted ? (body.attempt_nonce === 'retry-take1' ? VIEW('NOT_SUBMITTED', [FAM(MONTHLY, 'Monthly availability', null), FAM(RESOURCE, 'Resource month', null)]) : null)
      : VIEW('SELECTED', [FAM(MONTHLY, 'Monthly availability', {job_id:'j-1', status:'SUCCEEDED'}),
        FAM(RESOURCE, 'Resource month', {job_id:'j-2', status:'REFUSED'}, {refusal:{explanations:['Required resource terms are absent.'], passages:[], missing_terms:['resource denominator']}})],
        {selected:{family:MONTHLY, method:'public_proposal_job', job_id:'j-1'}}),
    submit: () => { submitted = true; return VIEW('PENDING', families()); }};
  const jobs = {'j-1':[JOB('j-1', 'RUNNING'), DONE], 'j-2':[JOB('j-2', 'RUNNING'), JOB('j-2', 'REFUSED', {reason:'proposal_validation_failed'})]};
  const s = livePage({canDraft:true}, answers, jobs);
  await s.ui.render(s.root, 'vendors');
  const panel = byClass(s.root, 'v4-live-read')[0] || s.root.all('section').find(n => /v4-live-read/.test(n.className));
  const seen = [];
  const states = panel.all('ul').find(n => /v4-live-states/.test(n.className));
  const original = states.replaceChildren.bind(states);
  states.replaceChildren = (...nodes) => { original(...nodes); if (nodes.length) seen.push(states.textContent); };
  await drive(s, button(panel, 'Start a live reading').listeners.click());
  const posts = s.calls.filter(c => c.body !== undefined);
  assert.deepEqual(posts.map(c => c.p), ['/api/vendors/corvid-ledger/proposal-access', '/api/vendors/corvid-ledger/proposal-jobs', '/api/vendors/corvid-ledger/proposal-access']);
  assert.deepEqual(posts[1].body, {document:CORVID, profile:'auto', attempt_nonce:'retry-take1'});
  assert.ok(!s.calls.some(c => /candidate|actions|approve|activate/.test(c.p)), 'nothing is staged or approved');
  assert.match(seen[0], /Monthly availability: Submitted/);
  assert.ok(seen.some(t => /Started: Claude is reading the contract/.test(t)));
  assert.match(seen.at(-1), /Monthly availability: Finished: every quote was checked/);
  assert.match(seen.at(-1), /Resource month: Finished: validation refused this reading/);
  const result = panel.textContent;
  assert.match(result, /Claude Opus 5\.5 read this contract just now/);
  assert.match(result, /Live run · finished Nov 10, 2026, 18:02 UTC · job j-1/);
  assert.match(result, /Every quoted sentence was found word for word in the source \(2 of 2, checked on this page\)/);
  assert.match(result, /Uptime selected the Monthly availability rule family/);
  assert.match(result, /Unreviewed: nothing is staged or approved/);
  assert.match(result, /Required resource terms are absent\./);
  assert.doesNotMatch(result, /Recorded run|Earlier run/);
  const sentences = byClass(panel, 'v4-reading-sentence').map(n => n.textContent);
  assert.deepEqual(sentences, [CLAUSES[1].quote, CLAUSES[0].quote]);
});

test('used takes are never resent: the latest one is shown as an earlier run, not a live one', async () => {
  const used = VIEW('SELECTED', [FAM(MONTHLY, 'Monthly availability', {job_id:'j-1', status:'SUCCEEDED'})], {selected:{family:MONTHLY, method:'public_proposal_job', job_id:'j-1'}});
  const s = livePage({canDraft:true}, {access: () => used, submit: () => { throw new Error('must not submit'); }}, {'j-1':[DONE]});
  await s.ui.render(s.root, 'vendors');
  await drive(s, button(s.root, 'Start a live reading').listeners.click());
  assert.equal(s.calls.filter(c => c.p.endsWith('/proposal-jobs')).length, 0);
  assert.equal(s.calls.filter(c => c.p.endsWith('/proposal-access')).length, 3);
  const text = s.root.textContent;
  assert.match(text, /Every approved take of this contract has already been read\. Showing the most recent one: an earlier run, not a live one\./);
  assert.match(text, /Earlier run \(recorded\) · finished/);
  assert.doesNotMatch(text, /just now|Live run/);
});

test('without an approval or a configured model nothing is sent, and the page says why', async () => {
  const notApproved = livePage({canDraft:true}, {access: () => VIEW('APPROVAL_REQUIRED', [FAM(MONTHLY, 'Monthly availability', null)]), submit: () => { throw new Error('no'); }}, {});
  await notApproved.ui.render(notApproved.root, 'vendors');
  await drive(notApproved, button(notApproved.root, 'Start a live reading').listeners.click());
  assert.match(notApproved.root.textContent, /Claude is not approved to read this exact text, so nothing was sent/);
  assert.equal(notApproved.calls.filter(c => c.p.endsWith('/proposal-access')).length, 1);
  const off = livePage({canDraft:true}, {access: () => VIEW('PROVIDER_UNCONFIGURED', []), submit: () => { throw new Error('no'); }}, {});
  await off.ui.render(off.root, 'vendors');
  await drive(off, button(off.root, 'Start a live reading').listeners.click());
  assert.match(off.root.textContent, /Live reading is not set up on this server\. Start the workspace with setup_northwind\.py --model-jobs/);
  assert.equal(off.calls.filter(c => c.p.endsWith('/proposal-jobs')).length, 0);
});
