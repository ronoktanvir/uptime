'use strict';
// DOM contract for W4's denial acceptance and read-only dispute record. Authored data; not a browser or service proof.
const test = require('node:test');
const assert = require('node:assert/strict');
const {Element, document} = require('./companion_dom.cjs');
const {create} = require('../../web/v4_ui.js');

const ID = 'inbox-n89';
const BASE = '/api/correspondence/claims/' + ID;
const OFFER = d => ({id:'accept-denial', label:'Accept Denial', basis_digest:d.repeat(64), route:'denial-acceptance'});
const CASE = (actions, extra = {}) => ({claim_id:ID, id:ID, stage:'DENIAL_REVIEW', actions, trace_url:BASE + '/trace', sources:[], ...extra});
const TRACE = {disposition:'ACCEPT_DENIAL', category:'CONTRACTUAL_DENIAL', final:true, stale_denial_review:false,
  ledger:{claimed:'40.00', awarded:'0.00'},
  correspondence:[{received_at:'2026-10-13T01:00:00Z', ground:'scheduled maintenance exclusion', category:'CONTRACTUAL_DENIAL',
    text:'Maintenance <script>alert(1)</script> window notified.', interpretation:{source:{quote:'Maintenance <script>alert(1)</script> window'}}}],
  deterministic_checks:[{check:'denial_ground_substantiated', result:true}, {check:'award_not_above_claim', result:true},
    {check:'month_coverage_basis', result:'EXPLICIT_MONTH_REPORT'}],
  permitted_next_actions:[], authority:'Read-only projection. It grants no approval, filing, award, closure or change of claim scope.'};
const button = (root, name) => root.all('button').find(b => b.textContent === name);

function mount({cases, post, canWrite = true}) {
  const root = new Element('main'), calls = [];
  const api = async (path, body) => {
    calls.push({path, body});
    if (body !== undefined) return post(path, body);
    if (path === BASE) return cases.length > 1 ? cases.shift() : cases[0];
    if (path === BASE + '/trace') return TRACE;
    throw new Error('Unexpected request ' + path);
  };
  const ui = create({document, getAccess:() => ({canWrite}), api, reloadAfterMutation:true});
  return {root, calls, ui};
}

test('accept denial posts only the offered basis digest to the dedicated route, then reloads', async () => {
  const s = mount({cases:[CASE([OFFER('a')]), CASE([], {stage:'DENIAL_ACCEPTED'})], post:() => ({stage:'DENIAL_ACCEPTED'})});
  await s.ui.inspect(s.root, ID);
  assert.ok(s.root.textContent.includes('Closes this claim on the substantiated denial ground'));
  await button(s.root, 'Accept denial').listeners.click();
  const posts = s.calls.filter(c => c.body !== undefined);
  assert.deepEqual(posts, [{path:BASE + '/denial-acceptance', body:{basis_digest:'a'.repeat(64)}}]);
  assert.ok(!s.calls.some(c => c.path.endsWith('/actions/accept-denial')));
  assert.equal(s.calls.filter(c => c.path === BASE).length, 2);
  assert.ok(s.root.textContent.includes('recorded the denial acceptance at stage DENIAL_ACCEPTED'));
  assert.equal(button(s.root, 'Accept denial'), undefined);
});

test('a stale basis (409) accepts nothing, reloads and offers the new basis without blocking', async () => {
  const s = mount({cases:[CASE([OFFER('a')]), CASE([OFFER('b')])],
    post:() => { throw Object.assign(new Error('The denial basis changed'), {status:409}); }});
  await s.ui.inspect(s.root, ID);
  await button(s.root, 'Accept denial').listeners.click();
  assert.ok(s.root.textContent.includes('The denial basis changed since this page loaded. Nothing was accepted.'));
  const fresh = button(s.root, 'Accept denial');
  assert.ok(fresh && fresh.disabled !== true);
  await fresh.listeners.click();
  assert.deepEqual(s.calls.filter(c => c.body !== undefined).map(c => c.body.basis_digest), ['a'.repeat(64), 'b'.repeat(64)]);
});

test('a malformed offer or a read-only session cannot accept', async () => {
  const bad = mount({cases:[CASE([{...OFFER('a'), basis_digest:'not-a-digest'}])], post:() => assert.fail('no post')});
  await bad.ui.inspect(bad.root, ID);
  assert.equal(button(bad.root, 'Accept denial'), undefined);
  const viewer = mount({cases:[CASE([OFFER('a')])], post:() => assert.fail('no post'), canWrite:false});
  await viewer.ui.inspect(viewer.root, ID);
  const b = button(viewer.root, 'Accept denial');
  await b.listeners.click();
  assert.equal(viewer.calls.filter(c => c.body !== undefined).length, 0);
});

test('the dispute record is read-only, uses plain labels and keeps vendor text inert', async () => {
  const s = mount({cases:[CASE([])], post:() => assert.fail('no post')});
  await s.ui.inspect(s.root, ID);
  await button(s.root, 'Show dispute record').listeners.click();
  const text = s.root.textContent;
  for (const expected of ['Dispute record', 'denial accepted', 'contractual denial', 'scheduled maintenance exclusion',
    'Denial ground substantiated: pass', 'Award not above the claim: pass', 'Month coverage basis: explicit month report',
    'Permitted next actions: none.', 'Relied-on passage', 'grants no approval'])
    assert.ok(text.includes(expected), expected);
  const quotes = s.root.all('blockquote').map(q => q.textContent);
  assert.deepEqual(quotes, ['Maintenance <script>alert(1)</script> window notified.', 'Maintenance <script>alert(1)</script> window']);
  assert.equal(s.root.all('script').length, 0);
  assert.equal(s.calls.filter(c => c.body !== undefined).length, 0);
  const without = mount({cases:[CASE([], {trace_url:'/elsewhere'})], post:() => assert.fail('no post')});
  await without.ui.inspect(without.root, ID);
  assert.equal(button(without.root, 'Show dispute record'), undefined);
});
