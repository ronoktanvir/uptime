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
  assert.match(text(checks[4]), /Jev · a term it does not support needs your acknowledgement 1 of 2 lowest 87\.5%, threshold 90% For the reviewer/);
  assert.match(text(checks[3]), /Pass/); assert.doesNotMatch(text(s.root.cls('tb-checks')[0]), /Fail/);
  assert.match(rows[1].cls('tb-jev')[0].children[0].children[0].className, /warn/);
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
  assert.deepEqual(s.requests[2], ['/api/template-builds/tb_3f9a2c/approve', {template_sha256: TEMPLATE.sha256, acknowledged: []}]);
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

test('engine additions: second contract named, rule error and rule match shown, a term Jev did not answer says No answer', async () => {
  const withSecond = {...LIST, samples: [{...sample, second_document: {id: 'halcyon-b', title: 'Addendum B', chars: 5001, text_url: '/fixtures/template_builder_demo/halcyon-b.txt'}}]};
  const b = {...BUILDS.ready, terms: [{...TERMS[0], rule_quote: 'The other sentence.', rule_error: null},
    {...TERMS[1], jev: null, status: 'PASS', rule_error: 'The rule matched nothing in this contract.', rule: {pattern: '(each calendar month)', group: 1, map: {'each calendar month': 'calendar_month'}}}],
    checks: CHECKS.map(c => c.id === 'jev' ? {...c, passed: 1, total: 2, lowest: null} : c)};
  const s = setup(() => ({build: b}), withSecond);
  await s.ui.run(s.root, 'tb_3f9a2c');
  const rows = s.root.cls('tb-term');
  assert.match(text(rows[1]), /No answer/); assert.doesNotMatch(text(rows[1]), /%/);
  assert.match(text(s.root.cls('tb-check')[3]), /Second contract: Addendum B/);
  assert.doesNotMatch(text(s.root.cls('tb-check')[4]), /lowest|threshold/);
  buttonNamed(rows[1], 'Show sentence').listeners.click();
  const detail = text(s.root.cls('tb-term-detail')[0]);
  assert.match(detail, /Rule error The rule matched nothing in this contract\./);
  assert.match(detail, /“each calendar month” → calendar_month/);
  buttonNamed(s.root.cls('tb-term')[0], 'Show sentence').listeners.click();
  assert.match(text(s.root.cls('tb-term-detail')[0]), /The rule matched The other sentence\./);
});

test('a REVIEW term is explained beside an enabled Approve; a refused start shows the server sentence', async () => {
  const s = setup(() => ({build: BUILDS.ready}));
  await s.ui.run(s.root, 'tb_3f9a2c');
  assert.match(text(s.root.cls('tb-approval')[0]), /Jev marked Claim window for you to read before approving\. Jev’s check is advisory/);
  assert.equal(buttonNamed(s.root, 'Approve this template').disabled, false);
  const busy = setup(() => Object.assign(new Error('Six template builds have run on this server; restart it to build more.'), {status: 429}));
  const node = await busy.ui.section(busy.root);
  await buttonNamed(node, 'Build a reader with Claude agents').listeners.click();
  assert.match(text(node), /Six template builds have run on this server; restart it to build more\./);
  assert.deepEqual(busy.routes, []);
  assert.equal(buttonNamed(node, 'Build a reader with Claude agents').disabled, false);
});

// ---- Version 2 (docs/demo/TEMPLATE-BUILDER.md, "Version 2"): canned objects in the interface page's shapes ----
const inputs = root => root.tag('input');
const checkboxes = root => root.tag('input').filter(i => i.type === 'checkbox');
const SOURCE = {kind: 'pasted', title: 'Meridian Relay: Uptime Schedule', vendor: 'Meridian Relay Ltd', chars: 6077};
const ROLE_STEPS = {'reader-1': {...DONE, model: 'claude-opus-5-5', detail: {role: 'clause_by_clause', terms: 9}},
  'reader-2': {...DONE, model: 'claude-opus-5-5', detail: {role: 'numbers_first', terms: 9}},
  'reader-3': {...DONE, model: 'claude-sonnet-5-5', detail: {role: 'sceptic', terms: 9}}};
const v2Term = (field, label, value, display, extra = {}) => ({...term(field, label, value, display, 'PASS'), value_in_sentence: true, needs_acknowledgement: false,
  second_readers: {agree: 3, of: 3, value: field === 'availability_target_percent' ? '99.9' : value}, second_document_value: field === 'availability_target_percent' ? '99.9' : value, ...extra});
const V2_TERMS = [v2Term('availability_target_percent', 'Availability commitment', '99.95', '99.95%'),
  v2Term('claim_window_days', 'Claim window', '30', '30 days', {status: 'REVIEW', needs_acknowledgement: true, jev: {yes: false, probability: '0.31', model: 'jev-1.13.0'}}),
  v2Term('maintenance_notice_hours', 'Maintenance notice', '72', '72 hours', {status: 'REVIEW', needs_acknowledgement: true, jev: null})];
// Deliberately out of order: the page draws the interface page's order.
const V2_CHECKS = [
  {id: 'jev', label: 'Jev: each term is supported by its sentence', passed: 1, total: 3, ok: false, blocking: false, by: 'JEV', threshold: '0.90', lowest: '0.31', ran: true},
  {id: 'quotes', label: 'Every quote is in the contract, word for word', passed: 9, total: 9, ok: true, blocking: true, by: 'UPTIME'},
  {id: 'agreement', label: 'The three readers agree', passed: 3, total: 3, ok: true, blocking: false, by: 'UPTIME'},
  {id: 'value_in_sentence', label: 'Each value is in its sentence', passed: 3, total: 3, ok: true, blocking: true, by: 'UPTIME'},
  {id: 'reproduce', label: 'The template returns every term from this contract', passed: 3, total: 3, ok: true, blocking: true, by: 'UPTIME'},
  {id: 'second_document', label: 'The template reads a second contract of the same form', passed: 3, total: 3, ok: true, blocking: true, by: 'UPTIME', document: {id: 'pasted-2', title: 'Meridian Relay: Uptime Schedule (EU)'}}];
const V2_BASE = {...base, sample_id: null, source: SOURCE, second: {provided: true, title: 'Meridian Relay: Uptime Schedule (EU)'}, matched_template: null, readings: []};
const v2Ready = {...V2_BASE, state: 'READY_FOR_REVIEW', steps: steps(allDone, {...doneExtra, ...ROLE_STEPS}), terms: V2_TERMS, checks: V2_CHECKS, template: {...TEMPLATE, rules: 3}};
const GUARDS = [{id: 'complete', label: 'Every rule found a value', ok: true, detail: '9 of 9'},
  {id: 'unambiguous', label: 'No rule matched two different values', ok: true, detail: null},
  {id: 'value_in_sentence', label: 'Each value is in the sentence its rule matched', ok: true, detail: '9 of 9'},
  {id: 'plausible', label: 'The values are plausible together', ok: true, detail: null},
  {id: 'template_match', label: 'Jev: this document follows the template', ok: true, detail: '0.94', advisory: false}];
const AGREEMENT = {agreement_id: 'HGS-PAA-2026-0518', state: 'SHADOW', read_by: 'template:halcyon-availability-addendum/1', month: '2026-10',
  availability_percent: '99.41', credit_percent: '25', monthly_fee: '8000.00', credit: {amount: '2000.00', currency: 'USD', stage: 'ESTIMATED'},
  inputs: [{label: 'Minutes unavailable', value: '254'}, {label: 'Minutes in the month', value: '44640'}],
  evaluation: 'Availability of 99.41% falls in the 25% tier, so the estimated credit is 25% of the monthly fee.'};
const V2_READING = {...READING, id: 'rd_4be1', status: 'ACCEPTED', found: 2, total: 2, guards: GUARDS,
  jev_template: {choice: TEMPLATE.id, probability: '0.94', model: 'jev-1.13.0'}, agreement: AGREEMENT,
  terms: [READING.terms[0], {field: 'claim_window_days', label: 'Claim window', type: 'days', value: '45', display: '45 days', quote: 'Claims must be made within 45 days.'}]};
const REFUSED = {...V2_READING, id: 'rd_9c0d', status: 'REFUSED', agreement: null,
  guards: GUARDS.map(g => g.id === 'unambiguous' ? {...g, ok: false, detail: 'Claim window matched in 2 places with different values'}
    : g.id === 'plausible' ? {...g, ok: false, detail: 'The second tier’s credit is not above the first'} : g)};
const matched = {...V2_BASE, state: 'MATCHED', matched_template: {id: TEMPLATE.id, sha256: TEMPLATE.sha256, probability: '0.93'},
  steps: steps({classify: 'DONE', 'reader-1': 'SKIPPED', 'reader-2': 'SKIPPED', 'reader-3': 'SKIPPED', build: 'SKIPPED', checks: 'DONE', review: 'SKIPPED'},
    {classify: {...DONE, seconds: '0.9', summary: 'Jev matched an approved template', detail: {choice: TEMPLATE.id, probability: '0.93'}},
      'reader-1': {summary: 'Not started: Jev matched an approved template'}, 'reader-2': {summary: 'Not started: Jev matched an approved template'},
      'reader-3': {summary: 'Not started: Jev matched an approved template'}, build: {summary: 'Not started: Jev matched an approved template'},
      review: {summary: 'Not started: Jev matched an approved template'}}),
  checks: GUARDS.map(g => ({...g, passed: null, total: null})), readings: [V2_READING]};
const needsReviewer = {...V2_BASE, state: 'NEEDS_REVIEWER', steps: steps({classify: 'FAILED'}, {classify: {summary: 'Jev could not be reached: the request timed out after 20 seconds.'}})};

test('MATCHED: no reader starts, the page leads with the reading and its guards, and says no Claude agent ran', async () => {
  const s = setup(() => ({build: matched}));
  await s.ui.run(s.root, 'tb_3f9a2c');
  const page = s.root.children[0];
  assert.match(page.children[1].className, /tb-matched/, 'the reading comes straight after the heading');
  assert.match(text(s.root), /Jev recognised an approved template, so no Claude agent ran/);
  assert.match(text(s.root), /No Claude agent ran\. Uptime’s fixed interpreter read the contract/);
  assert.match(text(s.root), /Read by an approved template/);
  assert.equal(s.timers.length, 0, 'MATCHED is final');
  const cards = stepCards(s.root);
  for (const c of cards.slice(1, 5)) { assert.match(text(c), /Not started/); assert.match(text(c), /Jev matched an approved template/); assert.doesNotMatch(text(c), /Not started: Jev/); }
  assert.match(text(cards[0]), /Matched approved template halcyon-availability-addendum\/1 \(93%\), so no reader started\./);
  assert.equal(s.root.cls('tb-stage-skipped').length, 3);
  const matchedPanel = s.root.cls('tb-matched')[0];
  assert.match(text(matchedPanel), /Jev · 93%/);
  assert.equal(matchedPanel.cls('tb-guard').length, 5);
  assert.match(text(matchedPanel.cls('tb-guard')[4]), /Pass Jev: this document follows the template Jev · 94% · jev-1\.13\.0/);
  assert.match(text(matchedPanel), /Values by fixed rules · Jev checked the document type · template halcyon-availability-addendum\/1 · 3\.4 ms/);
  assert.equal(s.root.cls('tb-terms').length, 0); assert.equal(s.root.cls('tb-approval').length, 0); assert.equal(s.root.cls('tb-checks').length, 0);
});

test('NEEDS_REVIEWER: nothing has started; "Build without Jev" POSTs /continue with {} and polling resumes', async () => {
  const running = {...V2_BASE, state: 'READING', steps: steps({classify: 'FAILED', 'reader-1': 'RUNNING', 'reader-2': 'RUNNING', 'reader-3': 'RUNNING'},
    {classify: {summary: 'Jev could not be reached.', detail: {reviewer_decision: {by: 'scripted-reviewer', at: T0}}},
      'reader-1': {started_at: T0}, 'reader-2': {started_at: T0}, 'reader-3': {started_at: T0}})};
  const s = setup(path => path.endsWith('/continue') ? {build: running} : {build: needsReviewer});
  await s.ui.run(s.root, 'tb_3f9a2c');
  assert.equal(s.timers.length, 0, 'nothing moves until the reviewer decides');
  const t = text(s.root);
  assert.match(t, /Jev could not be reached, so nothing has started/);
  assert.match(t, /Jev could not be reached: the request timed out after 20 seconds\./);
  assert.match(t, /Your choice is recorded on the run as a reviewer’s decision\./);
  assert.equal(s.root.tag('button').filter(b => b._text === 'Build without Jev').length, 1);
  await buttonNamed(s.root, 'Build without Jev').listeners.click();
  assert.deepEqual(s.requests[2], ['/api/template-builds/tb_3f9a2c/continue', {}]);
  assert.equal(s.timers.length, 1, 'polling resumes');
  assert.equal(buttonNamed(s.root, 'Build without Jev'), undefined);
  assert.match(text(stepCards(s.root)[0]), /the readers started on a reviewer’s decision \(scripted-reviewer\)/);
  const refused = setup(path => path.endsWith('/continue') ? Object.assign(new Error('Only a reviewer can continue a run.'), {status: 409}) : {build: needsReviewer});
  await refused.ui.run(refused.root, 'tb_3f9a2c');
  await buttonNamed(refused.root, 'Build without Jev').listeners.click();
  assert.match(text(refused.root), /Only a reviewer can continue a run\./);
  assert.equal(buttonNamed(refused.root, 'Build without Jev').disabled, false);
});

test('readers differ: each card shows its role in words and the model that answered; the Jev step says why they started', async () => {
  const s = setup(() => ({build: v2Ready}));
  await s.ui.run(s.root, 'tb_3f9a2c');
  const [classify, r1, r2, r3] = stepCards(s.root);
  assert.match(text(r1), /Reads clause by clause/); assert.match(text(r1), /claude-opus-5-5/);
  assert.match(text(r2), /Lists every number first/); assert.match(text(r2), /claude-opus-5-5/);
  assert.match(text(r3), /Looks for a conflicting second statement/); assert.match(text(r3), /claude-sonnet-5-5/); assert.doesNotMatch(text(r3), /opus/);
  assert.match(text(classify), /No approved template matched, so the readers started\./);
  assert.equal(TB.routeLine({...v2Ready, steps: steps(allDone, {classify: {detail: {choice: 'northwind-cloud-sla', probability: '0.62'}}})}),
    'Jev’s closest template, northwind-cloud-sla at 62%, was not a confident match, so the readers started.');
  assert.match(text(s.root), /Meridian Relay Ltd/); assert.match(text(s.root), /Meridian Relay: Uptime Schedule/);
  assert.match(text(s.root), /Pasted contract · 6,077 characters · Second contract: Meridian Relay: Uptime Schedule \(EU\)/);
});

test('checks: six in the interface page order; a failing value-in-sentence check blocks approval', async () => {
  const s = setup(() => ({build: v2Ready}));
  await s.ui.run(s.root, 'tb_3f9a2c');
  const checks = s.root.cls('tb-check');
  assert.deepEqual(checks.map(c => c.children[0].children[0]._text), ['Every quote is in the contract, word for word', 'Each value is in its sentence',
    'The three readers agree', 'The template returns every term from this contract', 'The template reads a second contract of the same form', 'Jev: each term is supported by its sentence']);
  assert.match(text(checks[4]), /Second contract: Meridian Relay: Uptime Schedule \(EU\)/);
  assert.match(text(checks[4]), /No answer key: three fresh Claude readers read the second contract/);
  const bad = {...v2Ready, checks: V2_CHECKS.map(c => c.id === 'value_in_sentence' ? {...c, passed: 2, ok: false} : c),
    terms: V2_TERMS.map(t => t.field === 'availability_target_percent' ? {...t, value_in_sentence: false} : t)};
  const b = setup(() => ({build: bad}));
  await b.ui.run(b.root, 'tb_3f9a2c');
  assert.match(text(b.root.cls('tb-check')[1]), /Each value is in its sentence Uptime’s code · blocks approval if it fails 2 of 3 Fail/);
  assert.match(text(b.root.cls('tb-approval')[0]), /Approval is not possible: Each value is in its sentence failed\./);
  assert.equal(buttonNamed(b.root, 'Approve this template').disabled, true);
  assert.match(text(b.root.cls('tb-term')[0].cls('tb-in-sentence')[0]), /No/);
  assert.match(b.root.cls('tb-term')[0].cls('tb-in-sentence')[0].children[0].className, /bad/);
});

test('the second-contract check that did not run is neither a pass nor a failure, and approval stays possible', async () => {
  const none = {...v2Ready, second: {provided: false, title: null}, terms: V2_TERMS.map(t => ({...t, second_readers: null, second_document_value: null, second_document_ok: null})),
    checks: V2_CHECKS.map(c => c.id === 'second_document' ? {id: c.id, label: c.label, passed: null, total: null, ok: false, blocking: false, by: 'UPTIME', ran: false} : c)};
  const s = setup(() => ({build: none}));
  await s.ui.run(s.root, 'tb_3f9a2c');
  const row = s.root.cls('tb-check')[4];
  assert.match(text(row), /the template was not checked on a second contract/);
  assert.match(text(row), /Not checked/);
  assert.doesNotMatch(text(row), /Pass|Fail|For the reviewer|of 3/);
  assert.match(row.className, /tb-check-off/);
  assert.deepEqual(TB.blockingFailures(none), []);
  assert.match(text(s.root.cls('tb-approval')[0]), /This template was not checked on a second contract\./);
  assert.match(text(s.root.cls('tb-terms')[0]), /No second contract given|Not given/);
  assert.match(text(s.root), /No second contract given/);
});

test('terms show the second contract’s readers and the value in its sentence; approval waits for every acknowledgement and sends them', async () => {
  const approvedBuild = {...v2Ready, state: 'APPROVED', template: {...TEMPLATE, rules: 3, state: 'APPROVED', approved_by: 'scripted-reviewer', approved_at: '2026-11-10T13:05:00Z'},
    steps: steps({...allDone, review: 'DONE'}, {...doneExtra, ...ROLE_STEPS, review: {summary: 'Approved', detail: {acknowledged: ['claim_window_days', 'maintenance_notice_hours']}}})};
  const s = setup(path => path.endsWith('/approve') ? {build: approvedBuild} : {build: v2Ready});
  await s.ui.run(s.root, 'tb_3f9a2c');
  const rows = s.root.cls('tb-term');
  assert.match(text(rows[0]), /Availability commitment 99\.95% 3 of 3 3 of 3 · 99\.9% Yes Yes · 98% Passed/);
  assert.match(text(rows[1]), /To acknowledge/);
  assert.match(text(s.root.cls('tb-terms')[0]), /2 terms need your acknowledgement/);
  assert.equal(s.root.cls('tb-detail-row').length, 2, 'terms to acknowledge open by themselves');
  const approve = () => buttonNamed(s.root, 'Approve this template');
  assert.equal(approve().disabled, true);
  assert.match(text(s.root.cls('tb-approval')[0]), /2 of 2 terms still to acknowledge: Claim window, Maintenance notice/);
  assert.match(text(s.root.cls('tb-approval')[0]), /2 still to acknowledge/);
  const detail = text(s.root.cls('tb-term-detail')[0]);
  assert.match(detail, /Jev says this sentence does not support the value \(31% yes\)\./);
  assert.match(detail, /I have read this sentence and the value is right/);
  assert.match(text(s.root.cls('tb-term-detail')[1]), /Jev did not answer for this term\./);
  let boxes = checkboxes(s.root);
  assert.equal(boxes.length, 2);
  boxes[0].checked = true; boxes[0].listeners.change();
  assert.equal(approve().disabled, true);
  assert.match(text(s.root.cls('tb-approval')[0]), /1 of 2 terms still to acknowledge: Maintenance notice/);
  boxes = checkboxes(s.root); assert.equal(boxes[0].checked, true, 'the tick survives the redraw');
  boxes[1].checked = true; boxes[1].listeners.change();
  assert.equal(approve().disabled, false);
  assert.match(text(s.root.cls('tb-terms')[0]), /All 2 acknowledged/);
  await approve().listeners.click();
  assert.deepEqual(s.requests[2], ['/api/template-builds/tb_3f9a2c/approve', {template_sha256: TEMPLATE.sha256, acknowledged: ['claim_window_days', 'maintenance_notice_hours']}]);
  assert.match(text(s.root.cls('tb-approval')[0]), /The reviewer acknowledged Claim window, Maintenance notice\./);
  assert.equal(checkboxes(s.root.cls('tb-terms')[0]).length, 0);
  const refused = setup(path => path.endsWith('/approve') ? Object.assign(new Error('Acknowledge exactly the terms Jev did not support.'), {status: 409}) : {build: v2Ready});
  await refused.ui.run(refused.root, 'tb_3f9a2c');
  checkboxes(refused.root).forEach((b, i) => { checkboxes(refused.root)[i].checked = true; checkboxes(refused.root)[i].listeners.change(); });
  await buttonNamed(refused.root, 'Approve this template').listeners.click();
  assert.match(text(refused.root), /Acknowledge exactly the terms Jev did not support\./);
  assert.equal(buttonNamed(refused.root, 'Approve this template').disabled, false);
});

test('a REFUSED reading says so with each failed guard’s reason, marks what was found as not accepted, and shows no agreement', async () => {
  const approved = {...v2Ready, sample_id: sample.id, state: 'APPROVED', template: {...TEMPLATE, state: 'APPROVED', approved_by: 'scripted-reviewer'}, readings: [], terms: V2_TERMS.map(t => ({...t, needs_acknowledgement: false}))};
  const s = setup(path => path.endsWith('/read') ? {reading: REFUSED} : {build: approved});
  await s.ui.run(s.root, 'tb_3f9a2c');
  await buttonNamed(s.root, 'Read the next contract with the template').listeners.click();
  const reading = s.root.cls('tb-reading')[0];
  assert.match(reading.className, /tb-reading-refused/);
  assert.match(text(reading), /Refused/);
  assert.match(text(reading), /This reading was refused, so nothing from it is used/);
  const reasons = reading.cls('tb-refused-reasons')[0].children.map(li => li._text);
  assert.deepEqual(reasons, ['No rule matched two different values: Claim window matched in 2 places with different values', 'The values are plausible together: The second tier’s credit is not above the first']);
  assert.equal(reading.cls('tb-guard').length, 5);
  assert.equal(reading.cls('tb-guard-bad').length, 2);
  assert.match(text(reading), /What the rules found · not accepted/);
  assert.match(text(reading), /Found \(not accepted\)/);
  assert.equal(reading.cls('tb-money').length, 0);
  assert.doesNotMatch(text(reading), /\$|2,000/);
});

test('an accepted reading with an agreement shows the money link exactly as sent; credit null shows the evaluation and no amount', async () => {
  const approved = {...v2Ready, state: 'APPROVED', template: {...TEMPLATE, state: 'APPROVED', approved_by: 'scripted-reviewer'}, readings: [V2_READING],
    terms: V2_TERMS.map(t => ({...t, needs_acknowledgement: false}))};
  const s = setup(() => ({build: {...approved, sample_id: sample.id}}));
  await s.ui.run(s.root, 'tb_3f9a2c');
  assert.equal(s.root.cls('tb-next-doc')[0].cls('tb-money').length, 1, 'the server’s reading is drawn under its listed document');
  const money = s.root.cls('tb-money')[0];
  assert.ok(money, 'the reading from the server is drawn under its document');
  const t = text(money);
  assert.match(t, /HGS-PAA-2026-0518/); assert.match(t, /In shadow/);
  assert.match(t, /Contract read by fixed rules · template halcyon-availability-addendum\/1/);
  assert.equal(money.cls('tb-money-amount')[0]._text, '$2,000.00');
  assert.match(t, /Estimated · not claimed/);
  assert.match(t, /Service month October 2026/); assert.match(t, /Availability 99\.41%/); assert.match(t, /Credit percent 25%/); assert.match(t, /Monthly fee \$8,000\.00/);
  assert.match(t, /Minutes unavailable 254/);
  assert.match(t, /Availability of 99\.41% falls in the 25% tier/);
  const link = money.tag('a')[0];
  assert.equal(link.href, '#overview'); link.listeners.click({preventDefault() {}});
  assert.deepEqual(s.routes, ['overview']);
  assert.match(text(s.root.cls('tb-reading')[0]), /Accepted Values by fixed rules · Jev checked the document type/);
  const noUsage = {...approved, readings: [{...V2_READING, agreement: {...AGREEMENT, credit: null, evaluation: 'Needs usage evidence', availability_percent: null, credit_percent: null}}]};
  const n = setup(() => ({build: noUsage}));
  await n.ui.run(n.root, 'tb_3f9a2c');
  const card = n.root.cls('tb-money')[0];
  assert.equal(card.cls('tb-money-amount').length, 0);
  assert.equal(card.cls('tb-money-missing')[0]._text, 'Needs usage evidence');
  assert.match(text(card), /Availability Not known/);
  assert.doesNotMatch(text(card), /2,000|Estimated credit|\$0/);
});

test('after approval a next contract can be pasted and read; its body carries the text and consent', async () => {
  const approved = {...v2Ready, state: 'APPROVED', template: {...TEMPLATE, state: 'APPROVED', approved_by: 'scripted-reviewer'}, terms: V2_TERMS.map(t => ({...t, needs_acknowledgement: false}))};
  const s = setup(path => path.endsWith('/read') ? {reading: {...V2_READING, id: 'rd_77', document: {id: 'pasted-3', title: 'Meridian Relay: Schedule B', vendor: 'Meridian Relay Ltd'}}} : {build: approved});
  await s.ui.run(s.root, 'tb_3f9a2c');
  const form = s.root.cls('tb-next-paste')[0];
  const go = buttonNamed(form, 'Read this contract with the template');
  assert.equal(go.disabled, true);
  const [title, vendor] = form.tag('input'); const area = form.tag('textarea')[0];
  title.value = 'Meridian Relay: Schedule B'; title.listeners.input(); vendor.value = 'Meridian Relay Ltd'; vendor.listeners.input();
  area.value = 'Schedule B. Availability will be 99.9%.'; area.listeners.input();
  assert.equal(go.disabled, true, 'consent is still needed');
  const consent = checkboxes(form)[0]; consent.checked = true; consent.listeners.change();
  assert.equal(go.disabled, false);
  await go.listeners.click();
  assert.deepEqual(s.requests[2], ['/api/template-builds/tb_3f9a2c/read', {contract: {title: 'Meridian Relay: Schedule B', vendor: 'Meridian Relay Ltd', text: 'Schedule B. Availability will be 99.9%.'}, consent: true}]);
  assert.match(text(s.root.cls('tb-next')[0]), /Meridian Relay: Schedule B/);
  assert.equal(s.root.cls('tb-money').length, 1);
});

test('Paste a contract: disabled until the text is there and consent is ticked; POSTs the pasted shape; shows the server sentence', async () => {
  const s = setup((path, body) => ({build: {...V2_BASE, ...BUILDS.queued, id: 'tb_pasted'}}));
  const node = await s.ui.section(s.root);
  const card = node.cls('tb-paste')[0];
  assert.match(text(card), /Paste a contract/);
  const consentLabel = card.cls('tb-consent')[0];
  assert.match(text(consentLabel), /will be sent to Claude and to Jev/);
  const go = buttonNamed(card, 'Build a reader from this contract');
  assert.equal(go.disabled, true);
  assert.match(text(card), /Paste the contract text to start\./);
  const [title, vendor, secondTitle] = card.tag('input').filter(i => i.type === 'text');
  const [area, secondArea] = card.tag('textarea');
  title.value = '  Meridian Relay: Uptime Schedule '; title.listeners.input();
  vendor.value = 'Meridian Relay Ltd'; vendor.listeners.input();
  area.value = 'Uptime Schedule. Availability will be 99.95%.'; area.listeners.input();
  assert.equal(go.disabled, true, 'text without consent');
  assert.match(text(card), /Tick the box above to send the text\./);
  const consent = checkboxes(card)[0];
  consent.checked = true; consent.listeners.change();
  assert.equal(go.disabled, false);
  area.value = '   '; area.listeners.input();
  assert.equal(go.disabled, true, 'blank text');
  area.value = 'Uptime Schedule. Availability will be 99.95%.'; area.listeners.input();
  await go.listeners.click();
  assert.deepEqual(s.requests[1], ['/api/template-builds', {contract: {title: 'Meridian Relay: Uptime Schedule', vendor: 'Meridian Relay Ltd', text: 'Uptime Schedule. Availability will be 99.95%.'}, second_contract: null, consent: true}]);
  assert.deepEqual(s.routes, ['template-build/tb_pasted']);
  secondTitle.value = 'Schedule (EU)'; secondTitle.listeners.input(); secondArea.value = 'Second text.'; secondArea.listeners.input();
  await go.listeners.click();
  assert.deepEqual(s.requests[2][1].second_contract, {title: 'Schedule (EU)', text: 'Second text.'});
  for (const [status, sentence] of [[409, 'A build for this contract is already running.'], [404, 'That sample is not shipped.'], [429, 'Six template builds have run on this server; restart it to build more.'], [422, 'The contract text is over 60,000 characters.']]) {
    const e = setup(() => Object.assign(new Error(sentence), {status}));
    const n = await e.ui.section(e.root);
    const c = n.cls('tb-paste')[0];
    c.tag('textarea')[0].value = 'Some text'; c.tag('textarea')[0].listeners.input();
    checkboxes(c)[0].checked = true; checkboxes(c)[0].listeners.change();
    await buttonNamed(c, 'Build a reader from this contract').listeners.click();
    assert.match(text(c), new RegExp(sentence.replace(/[.()]/g, '\\$&')), String(status));
    assert.equal(buttonNamed(c, 'Build a reader from this contract').disabled, false);
    assert.deepEqual(e.routes, []);
  }
  const off = setup(() => ({}), {enabled: false, reason: 'Off.', samples: [], builds: [], templates: []});
  assert.equal((await off.ui.section(off.root)).cls('tb-paste').length, 0, 'no form when the server has building off');
});

test('read_by is worded for a person: a template read is "Fixed rules · template <id>"', () => {
  assert.equal(TB.readByWords('template:halcyon-availability-addendum/1'), 'Fixed rules · template halcyon-availability-addendum/1');
  assert.equal(TB.money('2000.00', 'USD'), '$2,000.00'); assert.equal(TB.money('1234567.5', 'EUR'), '1,234,567.5 EUR'); assert.equal(TB.money(null, 'USD'), null);
  assert.equal(TB.monthLabel('2026-10'), 'October 2026');
  assert.equal(TB.withUnit({field: 'claim_window_days'}, '30'), '30 days'); assert.equal(TB.withUnit({type: 'percent'}, '99.9'), '99.9%');
  const ramp = fs.readFileSync(__dirname + '/ramp_ui.js', 'utf8'), workspace = fs.readFileSync(__dirname + '/workspace_ui.js', 'utf8');
  assert.ok(ramp.includes("'Fixed rules · template '"), 'ramp_ui.js words a template read'); assert.ok(workspace.includes("' · Fixed rules · template '"), 'workspace_ui.js words a template read');
});

test('as the engine built it: Jev not asked with no template on file, the sceptic’s conflict, second readers, reasons and blank-term errors', async () => {
  const notAsked = {...v2Ready, steps: steps(allDone, {...doneExtra, ...ROLE_STEPS, classify: {...DONE, model: null, seconds: '0.0',
    summary: 'No approved template is on file, so there was nothing for Jev to match; reading the contract', detail: {choice: 'unrecognised', probability: null, options: ['unrecognised'], asked: false}}}),
    terms: V2_TERMS.map(t => t.field === 'claim_window_days' ? {...t, conflict: 'Claims are due within forty-five days.', rule_places: 2} : t),
    checks: V2_CHECKS.map(c => c.id === 'second_document' ? {...c, basis: 'Three fresh readers read the second contract; a value counts when two agree.',
      readers: [{reader: 1, role: 'clause_by_clause', model: 'claude-opus-5-5', seconds: '9.1', ok: true}, {reader: 3, role: 'sceptic', model: 'claude-sonnet-5-5', seconds: '8.0', ok: false, summary: 'No answer in time'}]} : c)};
  const s = setup(() => ({build: notAsked}));
  await s.ui.run(s.root, 'tb_3f9a2c');
  const classify = stepCards(s.root)[0];
  assert.match(text(classify), /No approved template is on file, so Jev was not asked and the readers started\./);
  assert.doesNotMatch(text(classify), /%|jev-1/);
  const detail = text(s.root.cls('tb-term-detail')[0]);
  assert.match(detail, /Reader 3 found a conflict Claims are due within forty-five days\./);
  assert.match(detail, /Places the rule matched 2, all with the same value/);
  const second = text(s.root.cls('tb-check-second_document')[0]);
  assert.match(second, /a value counts when two agree/);
  assert.match(second, /Reader 1 · reads clause by clause · claude-opus-5-5 · 9\.1 s/);
  assert.match(second, /Reader 3 · looks for a conflicting second statement · claude-sonnet-5-5 · 8\.0 s · No answer in time/);
  const approved = {...v2Ready, sample_id: sample.id, state: 'APPROVED', template: {...TEMPLATE, state: 'APPROVED'}, terms: V2_TERMS.map(t => ({...t, needs_acknowledgement: false})),
    readings: [{...REFUSED, reasons: ['Claim window matched in two places with different values.'],
      terms: [{...REFUSED.terms[1], value: null, display: null, quote: null, error: 'The rule matched 30 and 45.', failed_guards: ['unambiguous']}]}]};
  const r = setup(() => ({build: approved}));
  await r.ui.run(r.root, 'tb_3f9a2c');
  const reading = r.root.cls('tb-reading')[0];
  assert.deepEqual(reading.cls('tb-refused-reasons')[0].children.map(li => li._text), ['Claim window matched in two places with different values.']);
  assert.match(text(reading), /The rule matched 30 and 45\./);
  const noted = setup(() => ({build: {...approved, readings: [{...V2_READING, agreement: null, agreement_note: 'No usage evidence is on file for this vendor.'}]}}));
  await noted.ui.run(noted.root, 'tb_3f9a2c');
  assert.match(text(noted.root.cls('tb-reading')[0]), /No usage evidence is on file for this vendor\./);
});
