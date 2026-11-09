'use strict';
// DOM contract: a refused vendor proposal job shows the server's verified public diagnostic as text only.
const test = require('node:test');
const assert = require('node:assert/strict');
const {Element, document} = require('./companion_dom.cjs');
const {create} = require('../../web/v4_ui.js');

const HEX = c => c.repeat(64);
const SOURCE = 'Vendor: <img src=x onerror=alert(1)>\nCredits: see schedule';
const DIAGNOSTIC = {schema:'public-refusal-diagnostic/1', profile:'monthly', source_sha256:HEX('c'),
  document:{name:'Aster Cove SLA', uri:'urn:authored:test', classification:'synthetic_public'},
  issues:[{code:'UNSUPPORTED_SOURCE_MATERIAL', block:2, start:0, end:37, block_sha256:HEX('e'),
    explanation:'The validator could not represent this passage in the selected adapter family.', quote:'Vendor: <img src=x onerror=alert(1)>'},
    {code:'REQUIRED_TERMS_MISSING', block:null, start:null, end:null, block_sha256:null,
    explanation:'No passage establishes the listed required terms.', quote:null}],
  missing_terms:['claim filing deadline', 'credit remedy']};
const JOB = (status, extra = {}) => ({job_id:'job-1', status, vendor_id:'aster-cove', request_sha256:HEX('a'),
  context_sha256:HEX('b'), candidate_available:false, ...extra});
const PERMITTED = {enabled:true, reason:'APPROVED', request_sha256:HEX('a'), context_sha256:HEX('b'), existing_job:null,
  disclosure:{model:'claude-opus-5-5', tools:[], transmitted_fields:['input','model']}};
const button = (root, name) => root.all('button').find(b => b.textContent === name);
const byClass = (root, cls) => root.all('div').find(n => String(n.className).split(' ').includes(cls));

async function refused(job) {
  const root = new Element('main'), timers = [];
  const api = async (path, body) => {
    if (body === undefined && path === '/api/vendors') return {vendors:[]};
    if (path.endsWith('/proposal-access')) return PERMITTED;
    if (path.endsWith('/proposal-jobs')) return JOB('QUEUED');
    if (body === undefined && path.includes('/proposal-jobs/')) return job;
    throw new Error('Unexpected request ' + path);
  };
  const ui = create({document, reviewForms:true, getAccess:() => ({canDraft:true}), api, schedule:callback => timers.push(callback)});
  await ui.render(root, 'vendors');
  const box = byClass(root, 'v4-generator');
  const f = Object.fromEntries([...box.all('input'), ...box.all('textarea'), ...box.all('select')].map(n => [n.name, n]));
  f.vendor_id.value = 'aster-cove'; f.name.value = 'Aster Cove SLA'; f.uri.value = 'urn:authored:test';
  f.classification.value = 'synthetic_public'; f.profile.value = 'monthly'; f.text.value = SOURCE;
  await button(root, 'Check generation access').listeners.click();
  await button(root, 'Generate proposal').listeners.click();
  await timers.shift()();
  return root;
}

test('a refused job shows fixed explanations, the exact passage and missing terms as text', async () => {
  const root = await refused(JOB('REFUSED', {reason:'PROPOSAL_REFUSED', public_diagnostic:DIAGNOSTIC}));
  const panel = byClass(root, 'v4-refusal');
  assert.ok(panel, 'diagnostic panel rendered');
  const text = panel.textContent;
  for (const expected of ['Why this proposal was refused', DIAGNOSTIC.issues[0].explanation, DIAGNOSTIC.issues[1].explanation,
    'Public source passage · block 2 · characters 0–37 · SHA-256 ' + HEX('e'),
    'Required terms not established by the source: claim filing deadline, credit remedy.',
    'Source: Aster Cove SLA · urn:authored:test · SHA-256 ' + HEX('c'), 'created no candidate'])
    assert.ok(text.includes(expected), expected);
  const quotes = panel.all('blockquote');
  assert.equal(quotes.length, 1);
  assert.equal(quotes[0].textContent, 'Vendor: <img src=x onerror=alert(1)>');
  assert.equal(root.all('img').length, 0);
  assert.match(root.textContent, /refused the model output/);
  assert.equal(button(root, 'Review shadow candidate request'), undefined);
});

test('no diagnostic, a wrong schema or a non-refused job shows nothing extra', async () => {
  for (const job of [JOB('REFUSED', {reason:'PROPOSAL_REFUSED'}),
    JOB('REFUSED', {reason:'PROPOSAL_REFUSED', public_diagnostic:{...DIAGNOSTIC, schema:'other/1'}}),
    JOB('CANCELLED', {public_diagnostic:DIAGNOSTIC})]) {
    const root = await refused(job);
    assert.equal(byClass(root, 'v4-refusal'), undefined, job.status);
  }
});
