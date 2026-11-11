const test = require('node:test');
const assert = require('node:assert/strict');
const TC = require('./template_claim_ui.js');
const W = require('./workspace_ui.js');

class Element {
  constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.attrs = {}; this._text = ''; this.className = ''; this.listeners = {}; }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return [this._text, ...this.children.map(c => c.textContent)].filter(Boolean).join(' '); }
  append(...c) { this.children.push(...c); }
  replaceChildren(...c) { this._text = ''; this.children = c; }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener(k, f) { this.listeners[k] = f; }
  querySelector() { return null; }
  all(pred) { return this.children.flatMap(c => [...(pred(c) ? [c] : []), ...(c.all ? c.all(pred) : [])]); }
}
const doc = {createElement: t => new Element(t), getElementById: () => null};

const reading = {read_by: 'FIXED_RULES', template_id: 'halcyon-availability-addendum/1', template_sha256: 'ab'.repeat(32),
  built_by: 'Claude agents: three readers and a template builder', approved_by: 'scripted-test-reviewer', build_id: 'tb_7a01',
  reading_id: 'rd_a1', read_at: '2026-11-10T13:05:00Z', model_calls: 0};

test('the reading card says fixed rules, the template, who built it and the approving account; never calls code an agent', () => {
  const lines = TC.readingLines(reading);
  assert.equal(lines[0], 'Read by fixed rules: approved template halcyon-availability-addendum/1 (SHA-256 abababababab…), with no model call.');
  assert.equal(lines[1], 'Template built by Claude agents: three readers and a template builder, approved by the reviewer account scripted-test-reviewer.');
  const card = TC.readingCard({reading, reading_current: false}, doc);
  const words = card.textContent;
  assert.match(words, /How this contract was read/);
  assert.match(words, /A newer reading of this contract exists/);
  assert.doesNotMatch(words, /Uptime agent|rules agent/i);
  const link = card.all(n => n.tagName === 'A')[0];
  assert.equal(link.href, '#template-build/tb_7a01');
  assert.equal(TC.readingCard({}, doc), null);
  // No approving account reported: said so, never invented.
  assert.match(TC.readingLines({...reading, approved_by: null})[1], /approval account not reported/);
});

test('the case page is the recovery page over the case routes, with the reading card and no Northwind links', async () => {
  const calls = [];
  const view = {vendor: 'Halcyon Grid Services', reading, price_finding: null, onboarding: null,
    claim: {id: 'inbox-halcyon-a-2026-10', month: '2026-10', state: 'NOT_OPENED'}, ledger: {currency: 'USD', destination: 'Local ledger'},
    finance: {stages: [{stage: 'estimated', label: 'Estimated', amount: '2000.00', status: 'recorded'}], attention: [], ramp: {}},
    next_actions: [{id: 'action-1', label: 'Approve October claim'}], months: [], automation: {enabled: true, state: 'PAUSED', steps: [], counts: {}}};
  const api = async (path, body) => { calls.push([path, body]); return {workflow: view}; };
  const page = TC.create({api, document: doc, workspace: W});
  const root = new Element('main');
  await page.render(root, 'halcyon-a');
  assert.deepEqual(calls[0], ['/api/template-claims/halcyon-a', undefined]);
  const words = root.textContent;
  assert.match(words, /How this contract was read/);
  assert.match(words, /Approve October claim/);
  assert.doesNotMatch(words, /price review|Ask about this case|See the full activity history|Open this claim’s case/i);
  const button = root.all(n => n.tagName === 'BUTTON' && n._text === 'Approve October claim')[0];
  await button.listeners.click();
  assert.deepEqual(calls[1], ['/api/template-claims/halcyon-a/actions/action-1', {}]);
});

test('a template estimate with a claim shows the claim stage, amount and who is next on the portfolio', () => {
  const opportunity = {vendor: 'Halcyon Grid Services', period: '2026-10', kind: 'service_credit', amount: '2000.00', currency: 'USD', stage: 'ESTIMATED',
    agreement: {id: 'HGS-PAA-2026-0412', read_by: 'template:halcyon-availability-addendum/1'}, route: 'agreements', source: 'template'};
  const before = W.portfolioRows({opportunities: [opportunity]}, [], null).find(r => r.vendor === 'Halcyon Grid Services');
  assert.equal(before.stage, 'Estimated · not claimed');
  assert.equal(before.href, '#agreements');
  const posted = W.portfolioRows({opportunities: [{...opportunity, claim: {href: '#template-claim/halcyon-a', stage: 'posted',
    label: 'Posted to Local ledger', amount: '2000.00', next: 'Reviewer'}}]}, [], null).find(r => r.vendor === 'Halcyon Grid Services');
  assert.deepEqual([posted.stage, posted.amount, posted.next, posted.href, posted.open], ['Posted to Local ledger', '2000.00', 'Reviewer', '#template-claim/halcyon-a', true]);
  const applied = W.portfolioRows({opportunities: [{...opportunity, claim: {href: '#template-claim/halcyon-a', stage: 'applied',
    label: 'Applied to bill', amount: '2000.00', next: null}}]}, [], null).find(r => r.vendor === 'Halcyon Grid Services');
  assert.deepEqual([applied.stage, applied.next, applied.open], ['Applied to bill', null, false]);
});

test('steps of the opening are tagged by who took them', () => {
  assert.equal(W.actorTag({authority: {kind: 'APPROVED_OPERATION', actor: 'scripted-test-reviewer'}}).label, 'Uptime · automatic');
  assert.equal(W.actorTag({authority: {kind: 'EVENT_INTAKE', source_subject: 'halcyon-a-2026-10-status'}}).label, 'Status source');
  assert.equal(W.actorTag({authority: {kind: 'EVENT_INTAKE', source_subject: 'halcyon-a-2026-10-vendor'}}).label, 'Vendor');
  assert.equal(W.actorTag({authority: {kind: 'PERSON', actor: 'scripted-test-reviewer'}}).label, 'Reviewer decision');
});

// The build page (web/template_builder_ui.js): the contract the template was built from can be read after approval,
// and "Open the claim" appears only when the server marks a claim as available for that reading.
const TB = require('./template_builder_ui.js');
class Node2 {
  constructor(tag) { this.tagName = tag; this.children = []; this.listeners = {}; this.attrs = {}; this._text = ''; this.className = ''; this.disabled = false; }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text + this.children.map(c => ' ' + c.textContent).join(''); }
  append(...c) { this.children.push(...c); }
  replaceChildren(...c) { this._text = ''; this.children = c; }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener(k, f) { this.listeners[k] = f; }
  all(pred) { return this.children.flatMap(c => [...(pred(c) ? [c] : []), ...c.all(pred)]); }
}
const doc2 = {createElement: t => new Node2(t)};
const sample = {id: 'halcyon-availability-addendum', title: 'Halcyon Grid: Platform Availability Addendum', vendor: 'Halcyon Grid Services',
  document: {id: 'halcyon-a', title: 'Platform Availability Addendum · Save Time Inc', chars: 6097},
  next_documents: [{id: 'halcyon-c', title: 'Addendum C', vendor: 'Halcyon Grid Services', chars: 5033}]};
const STEPS = ['classify', 'reader-1', 'reader-2', 'reader-3', 'build', 'checks', 'review'].map(id => ({id, actor: 'UPTIME', label: id, state: 'DONE', detail: {}}));
const approved = {id: 'tb_7a01', sample_id: sample.id, state: 'APPROVED', steps: STEPS, terms: [], checks: [], readings: [], error: null,
  template: {id: 'halcyon-availability-addendum/1', sha256: 'ab'.repeat(32), rules: 9, state: 'APPROVED', approved_by: 'scripted-test-reviewer'}};
const agreement = {agreement_id: 'HGS-PAA-2026-0412', state: 'SHADOW', read_by: 'template:halcyon-availability-addendum/1', month: '2026-10',
  availability_percent: '99.410', credit_percent: '25', monthly_fee: '8000.00', credit: {amount: '2000.00', currency: 'USD', stage: 'ESTIMATED'}, inputs: [], evaluation: 'x'};
const readingOf = (id, a) => ({id: 'rd_' + id, status: 'ACCEPTED', document: {id, title: id, vendor: 'Halcyon Grid Services'}, read_by: 'TEMPLATE',
  template: {id: approved.template.id, sha256: approved.template.sha256}, model_calls: 0, terms: [], found: 9, total: 9, guards: [], reasons: [], agreement: a});
function page(answer) {
  const requests = [], root = new Node2('main');
  const ui = TB.create({document: doc2, now: () => Date.parse('2026-11-10T13:10:00Z'), setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 1, clearInterval: () => {},
    onNavigate: () => {}, onUnauthorized: () => {}, api: async (path, body) => {
      requests.push(body === undefined ? [path] : [path, body]);
      if (path === '/api/template-builds' && body === undefined) return {enabled: true, reason: null, samples: [sample], builds: [], templates: []};
      return answer(path, body);
    }});
  return {ui, root, requests};
}
const named = (root, name) => root.all(c => c.tagName === 'button' && c._text === name)[0];
const claimLinks = root => root.all(c => c.tagName === 'a' && c._text === 'Open the claim');

test('after approval the build page offers to read the contract the template was built from, beside the next contract', async () => {
  const p = page((path, body) => path.endsWith('/read') ? {reading: readingOf('halcyon-a', {...agreement, claim: {available: true, case: 'halcyon-a'}})} : {build: approved});
  await p.ui.run(p.root, 'tb_7a01');
  assert.ok(named(p.root, 'Read the next contract with the template'));
  const own = named(p.root, 'Read this contract with the approved template');
  assert.ok(own);
  await own.listeners.click();
  assert.deepEqual(p.requests.find(r => r[0].endsWith('/read')), ['/api/template-builds/tb_7a01/read', {document_id: 'halcyon-a'}]);
  const links = claimLinks(p.root);
  assert.equal(links.length, 1);
  assert.equal(links[0].href, '#template-claim/halcyon-a');
});

test('a reading with an estimate but no claim available shows no claim link', async () => {
  const p = page(() => ({build: {...approved, readings: [readingOf('halcyon-c', agreement), readingOf('halcyon-a', {...agreement, claim: {available: false, case: 'halcyon-a'}})]}}));
  await p.ui.run(p.root, 'tb_7a01');
  assert.equal(claimLinks(p.root).length, 0);
  assert.equal(named(p.root, 'Read this contract with the approved template'), undefined, 'already read: its reading is shown instead');
});

test('the read terms are said in version 3 shapes: a schedule of tiers and durations in the contract\'s unit', () => {
  const values = {availability_target_percent: '99.95', measurement_period: 'calendar_month',
    credit_schedule: [{below_percent: 'commitment', credit_percent: '10'}, {below_percent: '99.5', credit_percent: '25'}],
    credit_cap_percent: '30', claim_window: {value: '30', unit: 'days'}, maintenance_notice: {value: '1', unit: 'business_days'}, credit_application: 'next_invoice'};
  assert.equal(TC.termsLine(values), 'Terms read: commitment 99.95%; below the commitment: 10% credit; below 99.5%: 25% credit; cap 30%; claim within 30 days; maintenance notice 1 business day.');
  assert.equal(TC.termsLine({}), null);
  assert.match(TC.readingLines({...reading, values}).join(' '), /Terms read: commitment 99\.95%/);
});
