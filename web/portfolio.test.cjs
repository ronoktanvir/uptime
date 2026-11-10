'use strict';
// The portfolio Overview: rows, tiles, counters and attention, built only from what the server sends.
const test = require('node:test');
const assert = require('node:assert/strict');
const {create, portfolioRows, portfolioTiles, agentCounters, portfolioAttention, nextActor, readBy} = require('./workspace_ui.js');
class Element {
  constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.listeners = {}; this.attrs = {}; this._text = ''; this.className = ''; }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(''); }
  append(...c) { this.children.push(...c); }
  replaceChildren(...c) { this._text = ''; this.children = c; }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener(k, f) { this.listeners[k] = f; }
  focus() {}
  all(t) { return this.children.flatMap(c => [...(c.tagName === t.toUpperCase() ? [c] : []), ...c.all(t)]); }
}
const document = {createElement: t => new Element(t)};
// The shapes a fresh Northwind walkthrough sends (values copied from its workflow view, agreements and saved Ramp workspace).
const stages = (claimed = false) => [{stage: 'estimated', label: 'Estimated', amount: '2400.00', status: 'recorded'},
  {stage: 'claimed', label: 'Claimed', amount: claimed ? '2400.00' : '0.00', status: claimed ? 'recorded' : 'not yet'},
  {stage: 'awarded', label: 'Awarded', amount: '0.00', status: 'not yet'}, {stage: 'posted', label: 'Posted to Local ledger', amount: '0.00', status: 'not yet'},
  {stage: 'applied', label: 'Applied to bill', amount: '0.00', status: 'not yet'}];
const workflow = {vendor: 'Northwind Cloud', company: {name: 'Harborline Analytics'}, as_of: '2026-03-01T12:00:00+00:00',
  months: [{month: '2026-01', outcome: 'ELIGIBLE', amount: '2400.00', currency: 'USD'}, {month: '2026-02', outcome: 'INELIGIBLE', amount: null, currency: 'USD'},
    {month: '2026-03', outcome: 'INSUFFICIENT_EVIDENCE', amount: null, currency: 'USD'}],
  price_finding: {state: 'PREPAYMENT_REVIEW', amount: '1000.00', invoice_id: 'NW-2026-03', month: '2026-03', currency: 'USD'},
  claim: {id: 'inbox-northwind-2026-01', month: '2026-01', state: 'DRAFTED'}, ledger: {destination: 'Local ledger', currency: 'USD'},
  finance: {stages: stages(), attention: [{owner: 'reviewer', title: 'Approve the claim packet before it is filed', detail: 'The claim is at stage DRAFTED.', section: 'finance-recovery'},
    {owner: 'evidence', title: 'Complete March 2026 usage evidence', detail: 'Eligible downtime minutes not provided.', section: 'finance-months'}]},
  next_actions: [{id: 'approve-claim', label: 'Approve January claim'}],
  automation: {enabled: true, state: 'PAUSED', pause: {reason: 'APPROVAL_REQUIRED'}, counts: {person_decisions: 0, automatic_steps: 0}, steps: []}};
const vendors = [{vendor_id: 'calyxquay', vendor: 'CalyxQuay', state: 'ACTIVE', active_version: 'v14', extraction: {method: 'tool_free_model_propositions', model: 'claude-opus-5-5'}},
  {vendor_id: 'northwind-cloud', vendor: 'Northwind Cloud', state: 'ACTIVE', active_version: 'v6', extraction: {method: 'deterministic_document_parser'}}];
const ramp = {verified_records: [{finding: {outcome: 'INSUFFICIENT_EVIDENCE'}, ramp_context: {object_id: 'f74ba12c-95d0-582d-9f62-26d8057d1d37', vendor_name: 'DocuSign',
  invoice_number: 'DD-PREAPPROVAL', amount: {currency: 'USD', amount: '840'}, status: 'OPEN', agreement_binding: {status: 'NONE', contract_id: null}}}]};
const view = row => [row.vendor, row.subject, row.kindLabel, row.amount, row.stage, row.next, row.href];

test('a fresh walkthrough gives one row per item across vendors, months, agreements and Ramp bills', () => {
  assert.deepEqual(portfolioRows(workflow, vendors, ramp).map(view), [
    ['Northwind Cloud', 'January 2026', 'Service credit', '2400.00', 'Estimated', 'Reviewer', '#recovery'],
    ['Northwind Cloud', 'February 2026', 'No credit due', null, 'Closed', null, '#recovery/finance-months'],
    ['Northwind Cloud', 'March 2026', 'Needs usage evidence', null, 'Open', 'Usage source', '#recovery/finance-months'],
    ['Northwind Cloud', 'Invoice NW-2026-03', 'Above contracted price', '1000.00', 'Open · before payment', 'Reviewer', '#recovery/finance-price-exception'],
    ['CalyxQuay', 'Read by Claude Opus 5.5 · recorded run', 'Agreement in force', null, 'In force', null, '#agreements'],
    ['DocuSign', 'Bill DD-PREAPPROVAL', 'No agreement on file', null, 'Evidence gap', 'Reviewer', '#ramp-bill/f74ba12c-95d0-582d-9f62-26d8057d1d37']]);
  assert.equal(portfolioRows(workflow, vendors, ramp).at(-1).detail, 'In Ramp: USD 840 · open');
});

test('the credit row follows the credit’s own latest recorded stage; nothing is added across stages or rows', () => {
  const claimed = {...workflow, finance: {...workflow.finance, stages: stages(true)}};
  assert.deepEqual(view(portfolioRows(claimed, [], null)[0]).slice(2, 5), ['Service credit', '2400.00', 'Claimed']);
  const applied = {...workflow, automation: {...workflow.automation, state: 'COMPLETE'}, next_actions: [],
    finance: {...workflow.finance, stages: stages(true).map(r => ({...r, amount: '2400.00', status: 'recorded'}))}};
  const row = portfolioRows(applied, [], null)[0];
  assert.deepEqual([row.stage, row.open, row.next], ['Applied to bill', false, null]);
  const tiles = portfolioTiles(portfolioRows(workflow, vendors, ramp), vendors, ramp);
  assert.deepEqual(tiles, {agreements: 2, claude: 1, rules: 1, opportunities: 3, byKind: [['credit', 1], ['price', 1], ['evidence', 1]],
    credits: [{subject: 'January 2026', vendor: 'Northwind Cloud', amount: '2400.00', currency: 'USD', stage: 'Estimated'}], bills: 1, unbound: 1});
  assert.ok(!JSON.stringify(tiles).includes('3400'), 'a price exception is never added to a credit');
});

test('who acts next comes from the offered actions and the recorded pause', () => {
  assert.equal(nextActor(workflow), 'Reviewer');
  assert.equal(nextActor({...workflow, next_actions: [], automation: {state: 'PAUSED', pause: {reason: 'ROUTINE_READY'}}}), 'Uptime agent');
  assert.equal(nextActor({...workflow, next_actions: [], automation: {state: 'PAUSED', pause: {reason: 'WAITING'}}}), 'Vendor');
  assert.equal(nextActor({...workflow, next_actions: [], automation: {state: 'COMPLETE'}}), null);
  assert.deepEqual(readBy({method: 'deterministic_document_parser'}), {kind: 'rules', label: 'Read by fixed rules'});
  assert.equal(readBy({method: 'other'}), null);
});

test('agents at work counts recorded facts: Claude readings, Uptime agent steps and reviewer decisions', () => {
  assert.deepEqual(agentCounters(workflow, vendors), {claudeReads: 1, models: ['Claude Opus 5.5'], agentSteps: 0, received: 0, reviewerDecisions: 0});
  const ran = {...workflow, automation: {...workflow.automation, steps: [
    {seq: 1, authority: {kind: 'PERSON'}, state: 'COMPLETED'}, {seq: 2, authority: {kind: 'APPROVED_OPERATION'}, state: 'COMPLETED'},
    {seq: 3, authority: {kind: 'EVENT_INTAKE'}, state: 'COMPLETED'}, {seq: 4, authority: {kind: 'APPROVED_OPERATION'}, state: 'UNCERTAIN'}]}};
  assert.deepEqual(agentCounters(ran, []), {claudeReads: 0, models: [], agentSteps: 1, received: 1, reviewerDecisions: 1});
});

test('needs attention covers the case’s items and every Ramp bill with no agreement on file', () => {
  assert.deepEqual(portfolioAttention(workflow, ramp).map(i => [i.vendor, i.title, i.href]), [
    ['Northwind Cloud', 'Approve the claim packet before it is filed', '#recovery/finance-recovery'],
    ['Northwind Cloud', 'Complete March 2026 usage evidence', '#recovery/finance-months'],
    [null, 'Put an agreement on file for DocuSign bill DD-PREAPPROVAL', '#ramp-bill/f74ba12c-95d0-582d-9f62-26d8057d1d37']]);
});

test('the portfolio page reads the agreements and the saved Ramp workspace and shows rows, tiles and counters', async () => {
  const requests = [], root = new Element('main');
  const answers = {'/api/vendors': {vendors: vendors.map(v => ({vendor_id: v.vendor_id, vendor: v.vendor, state: v.state, active_version: v.active_version}))},
    '/api/vendors/calyxquay': vendors[0], '/api/vendors/northwind-cloud': vendors[1], '/api/ramp/workspace': ramp};
  const ui = create({document, storage: null, api: async path => { requests.push(path); return answers[path]; }});
  await ui.portfolio(root, workflow);
  assert.deepEqual(requests.sort(), ['/api/ramp/workspace', '/api/vendors', '/api/vendors/calyxquay', '/api/vendors/northwind-cloud']);
  const text = root.textContent;
  for (const words of ['Portfolio', 'Agreements on file', '1 read by Claude · 1 by fixed rules', 'Opportunities open', '1 service credit · 1 price exception · 1 awaiting usage evidence',
    'Credits in progress', 'January 2026: $2,400.00 · Estimated', 'Ramp bills tracked', '1 with no agreement on file', 'Agents at work',
    'Contracts read by Claude Opus 5.5, recorded runs', 'Steps run under an approval a reviewer recorded', 'Decisions by the signed-in reviewer account',
    'Needs attention', 'Next: Reviewer', 'Nothing waiting']) assert.ok(text.includes(words), words);
  const rows = root.all('a').filter(a => String(a.className).startsWith('portfolio-row'));
  assert.equal(rows.length, 6);
  assert.deepEqual(rows.map(a => a.href), ['#recovery', '#recovery/finance-months', '#recovery/finance-months', '#recovery/finance-price-exception', '#agreements',
    '#ramp-bill/f74ba12c-95d0-582d-9f62-26d8057d1d37']);
  assert.ok(rows[0].textContent.includes('$2,400.00') && rows[3].textContent.includes('$1,000.00'));
  assert.doesNotMatch(text, /\$3,400|synthetic|simulat|replay|\bdemo\b/i);
});

test('a failed read of the agreements or Ramp leaves that part unavailable, never filled in', async () => {
  const root = new Element('main');
  const ui = create({document, storage: null, api: async path => { if (path !== '/api/workspace/workflow') throw new Error('refused'); return {workflow}; }});
  await ui.portfolio(root);
  const text = root.textContent;
  assert.ok(text.includes('The agreements list could not be read.'));
  assert.ok(text.includes('The saved Ramp workspace could not be read.'));
  assert.ok(text.includes('January 2026'));
});

test('the case page names the vendor and the month and links back to the portfolio; its price card has its own id', async () => {
  const root = new Element('main');
  const ui = create({document, storage: null, api: async () => ({workflow})});
  await ui.render(root, workflow, {section: 'finance-price-exception'});
  const back = root.all('a').find(a => a.textContent === 'Portfolio');
  assert.equal(back.href, '#overview');
  assert.ok(root.all('p').some(p => p.textContent === 'January 2026 service credit · Contract review & recovery'));
  assert.ok(root.all('h1').some(h => h.textContent === 'Northwind Cloud'));
  assert.ok(root.all('article').some(a => a.id === 'finance-price-exception'));
  assert.ok(root.all('section').some(s => s.id === 'finance-recovery'));
});
