const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const TB = require('./template_builder_ui.js');

class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.listeners = {}; this.attrs = {}; this._text = ''; this.className = ''; this.disabled = false; }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text + this.children.map(c => ' ' + c.textContent).join(''); }
  append(...c) { this.children.push(...c); }
  replaceChildren(...c) { this._text = ''; this.children = c; }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener(k, f) { this.listeners[k] = f; }
  all(pred) { return this.children.flatMap(c => [...(pred(c) ? [c] : []), ...c.all(pred)]); }
  tag(t) { return this.all(c => c.tagName === t); }
  cls(name) { return this.all(c => String(c.className).split(' ').includes(name)); }
}
const document = {createElement: t => new Element(t)};
const text = node => node.textContent.replace(/\s+/g, ' ');
const buttonNamed = (root, name) => root.tag('button').find(b => b._text === name);

const T0 = '2026-11-10T13:02:11Z', NOW = Date.parse('2026-11-10T13:02:20.5Z');
const sample = {id: 'halcyon-availability-addendum', title: 'Halcyon Grid: Platform Availability Addendum', vendor: 'Halcyon Grid Services',
  document: {id: 'halcyon-a', title: 'Addendum A', chars: 5120, text_url: '/fixtures/template_builder_demo/halcyon-a.txt'},
  next_documents: [{id: 'halcyon-c', title: 'Addendum C', vendor: 'Halcyon Grid Services', chars: 5033, text_url: '/fixtures/template_builder_demo/halcyon-c.txt'}]};
const STEP_IDS = [['classify', 'JEV', 'Which contract type is this?', 'jev-1.13.0'], ['reader-1', 'CLAUDE', 'Reader 1', 'claude-opus-5-5'],
  ['reader-2', 'CLAUDE', 'Reader 2', 'claude-opus-5-5'], ['reader-3', 'CLAUDE', 'Reader 3', 'claude-opus-5-5'],
  ['build', 'CLAUDE', 'Template builder', 'claude-opus-5-5'], ['checks', 'UPTIME', 'Checks', null], ['review', 'REVIEWER', 'Reviewer approval', null]];
function steps(states, extra = {}) {
  return STEP_IDS.map(([id, actor, label, model]) => ({id, actor, label, model, state: states[id] || 'PENDING', started_at: null, finished_at: null,
    seconds: null, summary: null, detail: {}, ...(extra[id] || {})}));
}
const term = (field, label, value, display, status, jev = {yes: true, probability: '0.98', model: 'jev-1.13.0'}) => ({field, label, type: 'percent', value, display,
  quote: 'The sentence for ' + label + '.', readers: [1, 2, 3].map(r => ({reader: r, value, quote_found: true})), agreement: {agree: 3, of: 3},
  rule: {pattern: label.replace(/ /g, '\\s') + '\\s(\\d+)', group: 1}, rule_value: value, second_document_value: value, second_document_ok: true, jev, status});
const TERMS = [term('availability_target_percent', 'Availability commitment', '99.95', '99.95%', 'PASS'),
  term('claim_window_days', 'Claim window', '30', '30 days', 'REVIEW', {yes: true, probability: '0.875', model: 'jev-1.13.0'})];
const CHECKS = [
  {id: 'quotes', label: 'Every quote is in the contract, word for word', passed: 6, total: 6, ok: true, blocking: true, by: 'UPTIME'},
  {id: 'agreement', label: 'The three readers agree', passed: 2, total: 2, ok: true, blocking: false, by: 'UPTIME'},
  {id: 'reproduce', label: 'The template returns every term from this contract', passed: 2, total: 2, ok: true, blocking: true, by: 'UPTIME'},
  {id: 'second_document', label: 'The template reads a second contract of the same form', passed: 2, total: 2, ok: true, blocking: true, by: 'UPTIME'},
  {id: 'jev', label: 'Jev: each term is supported by its sentence', passed: 1, total: 2, ok: false, blocking: false, by: 'JEV', threshold: '0.90', lowest: '0.875', ran: true}];
const TEMPLATE = {id: 'halcyon-availability-addendum/1', sha256: 'a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90', rules: 2, state: 'PROPOSED', approved_by: null, approved_at: null};
const DONE = {state: 'DONE', started_at: T0, seconds: '11.2'};
const allDone = {classify: 'DONE', 'reader-1': 'DONE', 'reader-2': 'DONE', 'reader-3': 'DONE', build: 'DONE', checks: 'DONE'};
const doneExtra = {classify: {...DONE, seconds: '0.8', summary: 'No template on file matches'}, 'reader-1': {...DONE, summary: '2 terms, 2 quotes found in the contract'},
  'reader-2': {...DONE, seconds: '12.9'}, 'reader-3': {...DONE, seconds: '10.4'}, build: {...DONE, seconds: '14.0', summary: '2 extraction rules written'},
  checks: {...DONE, seconds: '0.1', summary: '4 of 5 checks passed'}, review: {summary: 'Waiting for a reviewer'}};
const base = {id: 'tb_3f9a2c', sample_id: sample.id, started_at: T0, updated_at: T0, finished_at: null, terms: [], checks: [], template: null, error: null};
const BUILDS = {
  queued: {...base, state: 'QUEUED', steps: steps({})},
  reading: {...base, state: 'READING', steps: steps({classify: 'DONE', 'reader-1': 'RUNNING', 'reader-2': 'RUNNING', 'reader-3': 'DONE'},
    {classify: doneExtra.classify, 'reader-1': {started_at: '2026-11-10T13:02:12Z'}, 'reader-2': {started_at: '2026-11-10T13:02:12Z'}, 'reader-3': doneExtra['reader-3']})},
  readerFailed: {...base, state: 'READING', steps: steps({classify: 'DONE', 'reader-1': 'DONE', 'reader-2': 'FAILED', 'reader-3': 'RUNNING'},
    {classify: doneExtra.classify, 'reader-2': {summary: 'Claude did not answer within the allowed time.'}, 'reader-3': {started_at: '2026-11-10T13:02:12Z'}})},
  ready: {...base, state: 'READY_FOR_REVIEW', steps: steps(allDone, doneExtra), terms: TERMS, checks: CHECKS, template: TEMPLATE},
  blocked: {...base, state: 'READY_FOR_REVIEW', steps: steps(allDone, doneExtra), terms: TERMS, template: TEMPLATE,
    checks: CHECKS.map(c => c.id === 'second_document' ? {...c, passed: 1, ok: false} : c)},
  noJev: {...base, state: 'READY_FOR_REVIEW', steps: steps({...allDone, classify: 'FAILED'}, {...doneExtra, classify: {summary: 'Jev could not be reached, so the contract type was not decided by Jev.'}}),
    terms: TERMS.map(t => ({...t, jev: null, status: 'PASS'})), template: TEMPLATE,
    checks: CHECKS.map(c => c.id === 'jev' ? {id: 'jev', label: c.label, passed: null, total: null, ok: false, blocking: false, by: 'JEV', ran: false} : c)},
  failed: {...base, state: 'FAILED', steps: steps({classify: 'DONE', 'reader-1': 'FAILED', 'reader-2': 'FAILED', 'reader-3': 'FAILED'}, {classify: doneExtra.classify}),
    error: {sentence: 'No reader returned a reading, so no template was written.'}},
};
BUILDS.approved = {...BUILDS.ready, state: 'APPROVED', template: {...TEMPLATE, state: 'APPROVED', approved_by: 'scripted-reviewer', approved_at: '2026-11-10T13:05:00Z'},
  steps: steps({...allDone, review: 'DONE'}, {...doneExtra, review: {summary: 'Approved by scripted-reviewer'}})};
const READING = {document: {id: 'halcyon-c', title: 'Addendum C', vendor: 'Halcyon Grid Services'}, read_by: 'TEMPLATE',
  template: {id: TEMPLATE.id, sha256: TEMPLATE.sha256}, model_calls: 0, milliseconds: '3.4', found: 1, total: 2, read_at: '2026-11-10T13:06:00Z',
  terms: [{field: 'availability_target_percent', label: 'Availability commitment', type: 'percent', value: '99.9', display: '99.9%', quote: 'Availability will be 99.9%.'},
    {field: 'claim_window_days', label: 'Claim window', type: 'days', value: null, display: null, quote: null}]};
const LIST = {enabled: true, reason: null, samples: [sample], builds: [], templates: []};

function setup(answers, listAnswer = LIST) {
  const requests = [], routes = [], timers = [], root = new Element('main');
  let unauthorized = 0;
  const ui = TB.create({document, now: () => NOW, setTimeout: fn => { timers.push(fn); return timers.length; }, clearTimeout: () => {},
    setInterval: () => 1, clearInterval: () => {}, onNavigate: r => routes.push(r), onUnauthorized: () => { unauthorized++; },
    api: async (path, body) => {
      requests.push(body === undefined ? [path] : [path, body]);
      if (path === '/api/template-builds' && body === undefined) return listAnswer;
      const answer = answers(path, body);
      if (answer instanceof Error) throw answer;
      return answer;
    }});
  return {ui, root, requests, routes, timers, get unauthorized() { return unauthorized; }};
}
const stepCards = root => root.cls('tb-step');

test('the first answer draws all seven steps waiting, polls again, and names who is orchestrating', async () => {
  const s = setup(() => ({build: BUILDS.queued}));
  await s.ui.run(s.root, 'tb_3f9a2c');
  const t = text(s.root);
  assert.equal(stepCards(s.root).length, 7);
  assert.equal(s.root.cls('tb-parallel').length, 1);
  assert.equal(s.root.cls('tb-parallel')[0].cls('tb-step').length, 3);
  assert.match(t, /Uptime started one Jev decision, three Claude readers in parallel and one Claude template builder\./);
  assert.match(t, /Halcyon Grid Services/); assert.match(t, /Halcyon Grid: Platform Availability Addendum/);
  for (const actor of ['Jev', 'Claude', 'Uptime · fixed rules', 'Reviewer']) assert.ok(s.root.cls('tb-actor').some(a => a._text === actor), actor);
  assert.equal(stepCards(s.root).filter(c => /Waiting/.test(text(c))).length, 7);
  assert.equal(s.timers.length, 1, 'polls again while the run is not finished');
  assert.deepEqual(s.requests, [['/api/template-builds'], ['/api/template-builds/tb_3f9a2c']]);
  assert.equal(s.root.cls('tb-terms').length, 0); assert.equal(s.root.cls('tb-approval').length, 0);
});

test('working readers count up from their own start; a finished step shows its seconds and summary', async () => {
  const s = setup(() => ({build: BUILDS.reading}));
  await s.ui.run(s.root, 'tb_3f9a2c');
  const [classify, r1, r2, r3] = stepCards(s.root);
  assert.match(text(classify), /Done in 0\.8 s/); assert.match(text(classify), /No template on file matches/); assert.match(text(classify), /jev-1\.13\.0/);
  for (const r of [r1, r2]) { assert.match(text(r), /Working/); assert.match(text(r), /8\.5 s/); assert.equal(r.cls('tb-working').length, 1); assert.equal(r.attrs['aria-busy'], 'true'); }
  assert.match(text(r3), /Done in 10\.4 s/); assert.equal(r3.cls('tb-working').length, 0);
  assert.match(text(s.root), /Claude readers are reading the contract/);
});

test('one failed reader shows its sentence while the others carry on', async () => {
  const s = setup(() => ({build: BUILDS.readerFailed}));
  await s.ui.run(s.root, 'tb_3f9a2c');
  const r2 = stepCards(s.root)[2];
  assert.match(r2.className, /tb-failed/); assert.match(text(r2), /Failed/); assert.match(text(r2), /Claude did not answer within the allowed time\./);
  assert.match(text(stepCards(s.root)[3]), /Working/);
  assert.equal(s.timers.length, 1);
});

test('polling follows the run, stops at READY_FOR_REVIEW and stops when the view is left', async () => {
  const sequence = [BUILDS.queued, BUILDS.reading, BUILDS.ready];
  const s = setup(() => ({build: sequence.shift()}));
  await s.ui.run(s.root, 'tb_3f9a2c');
  await s.timers.shift()(); assert.match(text(s.root), /Claude readers are reading/);
  await s.timers.shift()(); assert.match(text(s.root), /Ready for a reviewer/);
  assert.equal(s.timers.length, 0, 'no further poll once ready for review');
  const left = setup(() => ({build: BUILDS.queued}));
  await left.ui.run(left.root, 'tb_3f9a2c');
  left.ui.unmount(); left.root.replaceChildren(new Element('p'));
  await left.timers.shift()();
  assert.equal(left.requests.length, 2, 'a poll scheduled before leaving sends nothing');
});

test('READY_FOR_REVIEW: terms with agreement, Jev percentage and a term marked for the reviewer; rows open to the sentence and rule', async () => {
  const s = setup(() => ({build: BUILDS.ready}));
  await s.ui.run(s.root, 'tb_3f9a2c');
  const rows = s.root.cls('tb-term');
  assert.equal(rows.length, 2);
  assert.match(text(rows[0]), /Availability commitment 99\.95% 3 of 3 Yes · 98% Passed/);
  assert.match(rows[1].className, /tb-term-review/); assert.match(text(rows[1]), /Yes · 87\.5% For the reviewer/);
  assert.match(text(s.root.cls('tb-terms')[0]), /1 term for the reviewer/);
  assert.equal(s.root.tag('blockquote').length, 0);
  buttonNamed(rows[1], 'Show sentence').listeners.click();
  assert.equal(s.root.tag('blockquote')[0]._text, 'The sentence for Claim window.');
  assert.match(text(s.root.cls('tb-term-detail')[0]), /Claim\\swindow\\s\(\\d\+\)/);
  const checks = s.root.cls('tb-check');
  assert.equal(checks.length, 5);
  assert.match(text(checks[0]), /Every quote is in the contract, word for word Uptime’s code · blocks approval if it fails 6 of 6 Pass/);
  assert.match(text(checks[4]), /Jev · advisory 1 of 2 lowest 87\.5%, threshold 90% Fail/);
  const approval = s.root.cls('tb-approval')[0];
  assert.match(text(approval), /halcyon-availability-addendum\/1/); assert.match(text(approval), /a1b2c3d4e5f6\b/); assert.doesNotMatch(text(approval), /a1b2c3d4e5f60/);
  assert.equal(buttonNamed(s.root, 'Approve this template').disabled, false);
  assert.equal(s.timers.length, 0);
});

test('a failed blocking check disables approval and says why in words', async () => {
  const s = setup(() => ({build: BUILDS.blocked}));
  await s.ui.run(s.root, 'tb_3f9a2c');
  const approve = buttonNamed(s.root, 'Approve this template');
  assert.equal(approve.disabled, true);
  assert.match(text(s.root.cls('tb-approval')[0]), /Approval is not possible: The template reads a second contract of the same form failed\./);
  assert.match(text(s.root.cls('tb-check')[3]), /1 of 2 Fail/);
  assert.deepEqual(TB.blockingFailures(BUILDS.blocked).map(c => c.id), ['second_document']);
});

test('when Jev did not run, no Jev figure is shown anywhere and the page says Jev could not be reached', async () => {
  const s = setup(() => ({build: BUILDS.noJev}));
  await s.ui.run(s.root, 'tb_3f9a2c');
  const t = text(s.root);
  assert.match(t, /Jev could not be reached/);
  assert.match(text(stepCards(s.root)[0]), /Failed/);
  buttonNamed(s.root.cls('tb-term')[0], 'Show sentence').listeners.click();
  const terms = text(s.root.cls('tb-terms')[0]);
  assert.doesNotMatch(terms, /Jev: supported|Yes ·|No ·|Jev model|jev-1/);
  assert.deepEqual(terms.match(/\d+(\.\d+)?%/g), ['99.95%']);
  assert.equal(s.root.cls('tb-jev').length, 0);
  const jevRow = s.root.cls('tb-check')[4];
  assert.match(text(jevRow), /Jev could not be reached/); assert.match(text(jevRow), /Not run/);
  assert.doesNotMatch(text(jevRow), /of|lowest|threshold|Pass|Fail/);
  assert.equal(buttonNamed(s.root, 'Approve this template').disabled, false, 'Jev is advisory');
});

test('approving POSTs the exact SHA-256, then shows who approved it and offers the next contract; the reading never guesses', async () => {
  const s = setup((path, body) => path.endsWith('/approve') ? {build: BUILDS.approved} : path.endsWith('/read') ? {reading: READING} : {build: BUILDS.ready});
  await s.ui.run(s.root, 'tb_3f9a2c');
  await buttonNamed(s.root, 'Approve this template').listeners.click();
  assert.deepEqual(s.requests[2], ['/api/template-builds/tb_3f9a2c/approve', {template_sha256: TEMPLATE.sha256}]);
  assert.match(text(s.root), /Approved by scripted-reviewer · Nov 10, 2026, 13:05 UTC/);
  assert.equal(buttonNamed(s.root, 'Approve this template'), undefined);
  await buttonNamed(s.root, 'Read the next contract with the template').listeners.click();
  assert.deepEqual(s.requests[3], ['/api/template-builds/tb_3f9a2c/read', {document_id: 'halcyon-c'}]);
  const reading = s.root.cls('tb-reading')[0];
  assert.match(text(reading), /Read by fixed rules · template halcyon-availability-addendum\/1 · 0 model calls · 3\.4 ms/);
  assert.match(text(reading), /1 of 2 terms found/);
  const missing = reading.cls('tb-not-found')[0];
  assert.match(text(missing), /Claim window Not found No sentence matched/);
  assert.doesNotMatch(text(missing), /30/);
});

test('a refused approval shows the server sentence and keeps the button', async () => {
  const s = setup(path => path.endsWith('/approve') ? Object.assign(new Error('The template hash is not this build’s.'), {status: 409}) : {build: BUILDS.ready});
  await s.ui.run(s.root, 'tb_3f9a2c');
  await buttonNamed(s.root, 'Approve this template').listeners.click();
  assert.match(text(s.root), /The template hash is not this build’s\./);
  assert.equal(buttonNamed(s.root, 'Approve this template').disabled, false);
});

test('a FAILED build shows its sentence and a way back to Agreements, and polling stops', async () => {
  const s = setup(() => ({build: BUILDS.failed}));
  await s.ui.run(s.root, 'tb_3f9a2c');
  assert.match(text(s.root), /No reader returned a reading, so no template was written\./);
  assert.match(text(s.root), /Failed/);
  buttonNamed(s.root, 'Back to Agreements').listeners.click();
  assert.deepEqual(s.routes, ['agreements']);
  assert.equal(s.timers.length, 0);
});

test('Agreements section: one card per sample, a start button that POSTs and opens the run', async () => {
  const s = setup(() => ({build: BUILDS.queued}));
  const node = await s.ui.section(s.root);
  assert.equal(s.root.children[0], node);
  const t = text(node);
  assert.match(t, /A contract type Uptime has not read before/); assert.match(t, /Halcyon Grid Services/); assert.match(t, /5,120 characters/);
  assert.equal(node.tag('a')[0].href, '/fixtures/template_builder_demo/halcyon-a.txt');
  await buttonNamed(node, 'Build a reader with Claude agents').listeners.click();
  assert.deepEqual(s.requests[1], ['/api/template-builds', {sample_id: sample.id}]);
  assert.deepEqual(s.routes, ['template-build/tb_3f9a2c']);
});

test('Agreements section: an existing build is opened instead of started; a disabled server shows its reason and no button', async () => {
  const s = setup(() => ({}), {...LIST, builds: [{...BUILDS.ready}], templates: [{...TEMPLATE, state: 'APPROVED', approved_by: 'scripted-reviewer', sample_id: sample.id}]});
  const node = await s.ui.section(s.root);
  assert.equal(buttonNamed(node, 'Build a reader with Claude agents'), undefined);
  buttonNamed(node, 'Open the run').listeners.click();
  assert.deepEqual(s.routes, ['template-build/tb_3f9a2c']);
  assert.match(text(node), /Template halcyon-availability-addendum\/1 approved by scripted-reviewer/);
  const off = setup(() => ({}), {enabled: false, reason: 'Template building needs the Claude Code CLI; start the server with --template-builder.', samples: [sample], builds: [], templates: []});
  const offNode = await off.ui.section(off.root);
  assert.match(text(offNode), /Template building needs the Claude Code CLI; start the server with --template-builder\./);
  assert.equal(offNode.tag('button').length, 0);
});

test('helpers: percentages shift decimal text, step states read plainly, and the page wording has no forbidden labels', () => {
  assert.equal(TB.percent('0.97'), '97%'); assert.equal(TB.percent('0.875'), '87.5%'); assert.equal(TB.percent('1'), '100%'); assert.equal(TB.percent('0.05'), '5%'); assert.equal(TB.percent(null), null);
  assert.equal(TB.stepState({state: 'RUNNING', started_at: T0}, Date.parse(T0) + 4200).elapsed, '4.2 s');
  assert.equal(TB.stepState({state: 'RUNNING', started_at: T0}, Date.parse(T0) - 1000).elapsed, '0.0 s');
  assert.equal(TB.stepState({state: 'DONE', seconds: null}).word, 'Done');
  assert.equal(TB.actorName('UPTIME'), 'Uptime · fixed rules');
  const source = fs.readFileSync(__dirname + '/template_builder_ui.js', 'utf8');
  const strings = source.match(/'[^'\n]*'/g).join(' ');
  assert.doesNotMatch(strings, /prototype|demo|beta|synthetic/i);
  assert.doesNotMatch(strings, /Uptime agent|code agent|rules agent/i);
  assert.doesNotMatch(source, /\bfetch\s*\(|innerHTML|localStorage/);
});

test('style: the template builder block sits before the side-panel block, which stays last', () => {
  const css = fs.readFileSync(__dirname + '/style.css', 'utf8');
  const tb = css.indexOf('/* 15c. Template builder'), side = css.indexOf('/* 16. Side panel');
  assert.ok(tb > 0 && side > tb);
  const html = fs.readFileSync(__dirname + '/index.html', 'utf8');
  assert.ok(html.indexOf('/static/template_builder_ui.js') > 0 && html.indexOf('/static/template_builder_ui.js') < html.indexOf('/static/app.js'));
});
