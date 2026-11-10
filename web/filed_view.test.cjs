'use strict';
// What was filed, on the case page: read only from the case record the page already loads. A DOM harness.
const test = require('node:test');
const assert = require('node:assert/strict');
const {create, filedSummary, readByChip} = require('./v4_ui.js');
class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.listeners = {}; this.attrs = {}; this.value = ''; this._text = ''; }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text + this.children.map(n => n.textContent).join(' '); }
  append(...nodes) { this.children.push(...nodes); }
  prepend(...nodes) { this.children.unshift(...nodes); }
  replaceChildren(...nodes) { this._text = ''; this.children = nodes; }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener(k, f) { this.listeners[k] = f; }
  all(tag) { return this.children.flatMap(n => [...(n.tagName === tag ? [n] : []), ...n.all(tag)]); }
}
const document = {createElement: tag => new Element(tag)};
const D = c => c.repeat(64);
// The Northwind case record's own shape: a filed claim and a filed response, each with its packet and receipt.
const scope = {account: 'harborline-001', vendor: 'Northwind Cloud', contract: 'NW-2026-001', service: 'Cloud Hosting', invoice: 'NW-2026-01', currency: 'USD', month: '2026-01'};
const claim = {id: 'LOCAL-ddea5d4149401ba6eece61e7', action: 'submit-claim', at: '2026-03-01T12:00:00+00:00', digest: D('d'), requested: '2400.00',
  approval: {action: 'approve-claim', actor: 'scripted-test-reviewer', at: '2026-03-01T12:00:00+00:00', digest: D('d')},
  packet: {claim: 'inbox-northwind-2026-01', scope, destination: 'isolated-local-simulator', subject: 'SLA Claim', version: D('5'), requested: '2400.00',
    agreement_id: 'NW-2026-001', filing_cutoff: '2026-03-03T00:00:00+00:00', terms_digest: D('a'), artifacts: [{kind: 'invoice', digest: D('1')}, {kind: 'status', digest: D('2')}]}};
const response = {...claim, id: 'LOCAL-6342a4e31a1d31eecf8a9006', action: 'submit-response', at: '2026-03-02T12:10:00+00:00',
  approval: {...claim.approval, action: 'approve-response', at: '2026-03-02T09:05:00+00:00'},
  packet: {...claim.packet, terms_digest: D('b'), in_reply_to: claim.id, argument: 'The requested scoped artifact is independently verified against the filed source records.',
    disclosed_artifact: {ref: 'NW-JAN-LOG-001', type: 'resource_log'}, artifacts: [...claim.packet.artifacts, {kind: 'artifact', digest: D('3')}, {kind: 'unmatched', digest: D('9')}]}};
const evidence = [{label: 'invoice', detail: 'northwind-invoice-2026-01 · billing', digest: D('1')}, {label: 'status', detail: 'northwind-status-2026-01 · status', digest: D('2')},
  {label: 'artifact', detail: 'northwind-jan-resource-log · customer', digest: D('3'), artifact_ref: 'NW-JAN-LOG-001'}];
const rows = summary => Object.fromEntries(summary.rows);

test('a filed claim prints exactly the packet’s own fields in plain labels', () => {
  const summary = filedSummary(claim, evidence);
  assert.equal(summary.kind, 'Claim');
  assert.deepEqual(summary.rows, [['Period', 'January 2026'], ['Service', 'Cloud Hosting'], ['Amount requested', '$2,400.00'], ['Agreement', 'NW-2026-001'],
    ['Contract version', D('5')], ['Cited clause', 'Not sent by the server'],
    ['Evidence references', ['invoice · northwind-invoice-2026-01 · billing', 'status · northwind-status-2026-01 · status']],
    ['Destination', 'Vendor claims intake (local)'], ['Receipt', 'LOCAL-ddea5d4149401ba6eece61e7'], ['Filed', 'Mar 1, 2026, 12:00 UTC'],
    ['Approved by', 'scripted-test-reviewer, Mar 1, 2026, 12:00 UTC'], ['Terms fingerprint', D('a')]]);
});

test('the response adds only what its packet carries; an unmatched evidence digest is shown as its digest', () => {
  const r = rows(filedSummary(response, evidence));
  assert.equal(r['In reply to'], claim.id);
  assert.equal(r.Argument, response.packet.argument);
  assert.equal(r['Disclosed document'], 'NW-JAN-LOG-001 · resource log');
  assert.deepEqual(r['Evidence references'].slice(2), ['artifact · northwind-jan-resource-log · customer · NW-JAN-LOG-001', 'unmatched · Digest ' + D('9')]);
});

test('a field the server does not send is printed as not sent, never guessed; amounts stay exact', () => {
  const bare = filedSummary({packet: {requested: '9007199254740993.01', scope: {}}}, []);
  const r = rows(bare);
  for (const name of ['Period', 'Service', 'Agreement', 'Contract version', 'Cited clause', 'Evidence references', 'Destination', 'Receipt', 'Filed', 'Approved by'])
    assert.equal(r[name], 'Not sent by the server', name);
  assert.equal(r['Amount requested'], '9,007,199,254,740,993.01 (currency not sent by the server)');
  assert.equal(bare.kind, 'Filing');
  for (const name of ['In reply to', 'Argument', 'Disclosed document', 'Terms fingerprint']) assert.ok(!(name in r), name);
  assert.equal(rows(filedSummary({}, null))['Amount requested'], 'Not sent by the server');
  assert.equal(rows(filedSummary({packet: {requested: '0.00', scope: {currency: 'EUR'}}}))['Amount requested'], 'EUR 0.00');
  assert.equal(rows(filedSummary({packet: {requested: null, scope: {currency: 'USD'}}}))['Amount requested'], 'Not sent by the server');
});

test('the case page shows What was filed below the correspondence, closed until opened, from the record it already loaded', async () => {
  const root = new Element('main'), requests = [];
  const data = {id: 'inbox-northwind-2026-01', scope, stage: 'AWARDED', currency: 'USD', evidence, submissions: [claim, response],
    timeline: [{at: '2026-03-01T12:00:00+00:00', event: 'Approved exact local packet.', actor: 'scripted-test-reviewer'}], replies: []};
  const ui = create({document, getAccess: () => ({canWrite: false}), api: async path => { requests.push(path); return data; }});
  await ui.inspect(root, 'inbox-northwind-2026-01');
  assert.deepEqual(requests, ['/api/correspondence/claims/inbox-northwind-2026-01']);
  const titles = root.all('h2').map(h => h.textContent);
  assert.ok(titles.indexOf('Correspondence, in order') > titles.indexOf('Where this claim stands'));
  const filed = root.all('details').find(s => s.children[0] && s.children[0].textContent === 'What was filed');
  assert.ok(filed, 'a closed section'); assert.notEqual(filed.open, true);
  const order = [...root.all('section'), ...root.all('details')].map(n => n.children[0] && n.children[0].textContent);
  const flat = JSON.stringify(root, (k, v) => k === 'listeners' || k === 'attrs' ? undefined : v);
  assert.ok(flat.indexOf('"What was filed"') > flat.indexOf('"Correspondence, in order"'), 'below the correspondence');
  assert.ok(order.includes('What was filed'));
  assert.deepEqual(filed.all('h3').map(h => h.textContent), ['Claim', 'Response']);
  const text = filed.textContent;
  assert.doesNotMatch(text, /isolated-local-simulator/);
  for (const value of ['January 2026', 'Cloud Hosting', '$2,400.00', 'NW-2026-001', '5555555555…', 'Not sent by the server', 'Vendor claims intake (local)',
    'LOCAL-ddea5d4149401ba6eece61e7', 'scripted-test-reviewer', 'northwind-invoice-2026-01', 'The amounts are not added together.']) assert.ok(text.includes(value), value);
  assert.equal(filed.all('dd').find(d => d.textContent === '5555555555…').attrs.title, D('5'));
  assert.doesNotMatch(text, /\$4,800|4800/);
  assert.doesNotMatch(text, /\bagent\b|\bAI\b|Ramp|sent to the vendor|delivered/i);
  const none = new Element('main');
  const empty = create({document, getAccess: () => ({}), api: async () => ({id: 'x', submissions: []})});
  await empty.inspect(none, 'x');
  assert.ok(!none.all('summary').some(h => h.textContent === 'What was filed'));
});

test('how a contract was read: two chips mapped from the server’s method and model, nothing guessed', () => {
  assert.deepEqual(readByChip({method: 'deterministic_document_parser'}), {label: 'Read by fixed rules', kind: 'rules'});
  assert.deepEqual(readByChip({method: 'tool_free_model_propositions', model: 'claude-opus-5-5'}), {label: 'Read by Claude Opus 5.5 · recorded run', kind: 'model'});
  assert.equal(readByChip({method: 'tool_free_model_propositions', model: 'other-model'}), null);
  assert.equal(readByChip({method: 'something_else'}), null);
  assert.equal(readByChip(null), null);
});

test('an agreement card shows the chip beside its name and keeps the server’s own words in its fields', async () => {
  const root = new Element('main');
  const vendor = {vendor_id: 'northwind', name: 'Northwind Cloud', state: 'ACTIVE', revision: 1, active_version: 'v1', extraction: {method: 'deterministic_document_parser'}};
  const ui = create({document, getAccess: () => ({}), api: async path => path === '/api/vendors' ? {vendors: [vendor]} : vendor});
  await ui.render(root, 'vendors');
  const text = root.textContent;
  assert.ok(text.includes('Read by fixed rules'));
  assert.ok(text.includes('deterministic document parser'));
  assert.doesNotMatch(text, /Claude/);
});
