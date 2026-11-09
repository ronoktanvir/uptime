'use strict';
// DOM contract: a refused rule family shows the server's verified public diagnostic as text only (decision 97 flow).
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
const SUMMARY = {codes:['REQUIRED_TERMS_MISSING'], explanations:['No passage establishes the listed required terms.'],
  passages:['Credits: see schedule'], missing_terms:['credit remedy']};
const JOB = (id, status) => ({job_id:id, status, vendor_id:'aster-cove', request_sha256:HEX('a'), context_sha256:HEX('b'), candidate_available:false});
const FAMILY = (family, label, extra) => ({family, label, enabled:true, approval_reason:null, job:null, state:null, refusal:null,
  public_diagnostic:null, attempts:{total:1, validated:0, structural_refusals:1}, ...extra});
const VIEW = families => ({schema:'automatic-family-selection/1', outcome:'NO_SUPPORTED_FAMILY', selected:null,
  offline:{accepted:false, reason:'NOT_CANONICAL'}, families,
  review_requirements:['No supported rule family represents this source.'], source_sha256:HEX('c'), selection_sha256:HEX('f'),
  authority:{approval_gate:false, dispatch_authorized:false}});
const button = (root, name) => root.all('button').find(b => b.textContent === name);
const byClass = (root, cls) => root.all('div').filter(n => String(n.className).split(' ').includes(cls));

async function refused(view) {
  const root = new Element('main'), calls = [];
  const api = async (path, body) => {
    calls.push({path, body});
    if (body === undefined && path === '/api/vendors') return {vendors:[]};
    if (path.endsWith('/proposal-access')) return view;
    throw new Error('Unexpected request ' + path);
  };
  const ui = create({document, reviewForms:true, getAccess:() => ({canDraft:true}), api, schedule:() => {}});
  await ui.render(root, 'vendors');
  const box = byClass(root, 'v4-generator')[0];
  const f = Object.fromEntries([...box.all('input'), ...box.all('textarea'), ...box.all('select')].map(n => [n.name, n]));
  f.vendor_id.value = 'aster-cove'; f.name.value = 'Aster Cove SLA'; f.uri.value = 'urn:authored:test';
  f.classification.value = 'synthetic_public'; f.text.value = SOURCE;
  await button(root, 'Check generation access').listeners.click();
  return {root, calls};
}

test('a refused family shows its verified diagnostic; a family without one shows the summary', async () => {
  const {root, calls} = await refused(VIEW([
    FAMILY('monthly-availability/1', 'Monthly availability', {job:JOB('job-1', 'REFUSED'), state:'REFUSED_STRUCTURAL', refusal:SUMMARY, public_diagnostic:DIAGNOSTIC}),
    FAMILY('resource-month/1', 'Resource month', {job:JOB('job-2', 'REFUSED'), state:'REFUSED_READING', refusal:SUMMARY})]));
  const panels = byClass(root, 'v4-refusal');
  assert.equal(panels.length, 2);
  const verified = panels[0].textContent, summary = panels[1].textContent;
  for (const expected of ['Why this family was refused', DIAGNOSTIC.issues[0].explanation, DIAGNOSTIC.issues[1].explanation,
    'Public source passage · block 2 · characters 0–37 · SHA-256 ' + HEX('e'),
    'Required terms not established by the source: claim filing deadline, credit remedy.',
    'Source: Aster Cove SLA · urn:authored:test · SHA-256 ' + HEX('c'), 'created no candidate'])
    assert.ok(verified.includes(expected), expected);
  // One panel per family: the verified diagnostic replaces the summary rather than repeating it.
  assert.equal((verified.match(/Why this family was refused/g) || []).length, 1);
  assert.ok(summary.includes('Why this family was refused') && summary.includes('Credits: see schedule'));
  assert.ok(!summary.includes('characters') && !summary.includes('SHA-256'), 'the summary carries no offsets or digests');
  const quotes = root.all('blockquote').map(q => q.textContent);
  assert.deepEqual(quotes, ['Vendor: <img src=x onerror=alert(1)>', 'Credits: see schedule']);
  assert.equal(root.all('img').length, 0);
  assert.equal(button(root, 'Review shadow candidate request'), undefined);
  assert.deepEqual(calls.filter(c => c.body !== undefined).map(c => c.path), ['/api/vendors/aster-cove/proposal-access']);
});

test('a foreign or malformed diagnostic falls back to the summary; no refusal shows nothing extra', async () => {
  for (const diagnostic of [{...DIAGNOSTIC, schema:'other/1'}, 'not an object']) {
    const {root} = await refused(VIEW([FAMILY('monthly-availability/1', 'Monthly availability',
      {job:JOB('job-1', 'REFUSED'), state:'REFUSED_STRUCTURAL', refusal:SUMMARY, public_diagnostic:diagnostic})]));
    const panels = byClass(root, 'v4-refusal');
    assert.equal(panels.length, 1);
    assert.ok(panels[0].textContent.includes('Why this family was refused'));
    assert.ok(!panels[0].textContent.includes('SHA-256'), 'a rejected diagnostic contributes no verified detail');
  }
  const {root} = await refused(VIEW([FAMILY('monthly-availability/1', 'Monthly availability', {job:JOB('job-1', 'CANCELLED'), state:'INCONCLUSIVE'})]));
  assert.equal(byClass(root, 'v4-refusal').length, 0);
});
