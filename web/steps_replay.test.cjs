'use strict';
// Steps in order: the legend and the display-only replay. A DOM harness; no browser-layout claims.
const test = require('node:test');
const assert = require('node:assert/strict');
const {create, recordedOrder, replayGroup, stepLegend} = require('./workspace_ui.js');
class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.listeners = {}; this.attrs = {}; this._text = ''; this.className = ''; }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(''); }
  append(...c) { this.children.push(...c); }
  replaceChildren(...c) { this._text = ''; this.children = c; }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener(k, f) { this.listeners[k] = f; }
  all(t) { return this.children.flatMap(c => [...(c.tagName === t ? [c] : []), ...c.all(t)]); }
}
const document = {createElement: t => new Element(t)};
// The eleven steps the Northwind walkthrough records, in the server's shape (labels, kinds and states as recorded).
const OPS = [['approve-claim', 'Approve January claim', 'PERSON'], ['submit-claim', 'File January claim', 'APPROVED_OPERATION'],
  ['receive-denial', 'Receive vendor response', 'EVENT_INTAKE'], ['receive-artifact', 'Attach requested log', 'EVENT_INTAKE'],
  ['receive-verification', 'Verify supplied log', 'EVENT_INTAKE'], ['approve-response', 'Approve response', 'PERSON'],
  ['submit-response', 'Send response', 'APPROVED_OPERATION'], ['receive-award', 'Receive credit decision', 'EVENT_INTAKE'],
  ['record-credit', 'Post to Local ledger', 'PERSON'], ['receive-invoice', 'Receive next invoice', 'EVENT_INTAKE'],
  ['apply-balance', 'Apply credit to eligible invoice', 'PERSON']];
const authority = kind => kind === 'PERSON' ? {kind, actor: 'scripted-test-reviewer'}
  : kind === 'APPROVED_OPERATION' ? {kind, actor: 'scripted-test-reviewer', approved_at: '2026-03-01T12:00:00+00:00'}
  : {kind, event_id: 'event-x', source_subject: 'northwind-2026-01-vendor'};
const steps = n => OPS.slice(0, n).map(([operation, label, kind], i) => ({seq: i + 1, operation, label, class: 'INTAKE', authority: authority(kind),
  state: 'COMPLETED', at: '2026-03-01T12:00:00+00:00', recorded_at: '2026-11-10T10:00:00+00:00', intent_id: 'action-' + (i + 1), detail: null, timing: null}));
const workflow = (n, counts) => ({vendor: 'Northwind Cloud', audit: [], next_actions: [], automation: {enabled: true, state: 'PAUSED',
  pause: {reason: 'APPROVAL_REQUIRED', detail: 'A reviewer approves the exact packet.'}, steps: steps(n), counts}});
function harness({stored = {}, still = false} = {}) {
  const queue = [], requests = [], root = new Element('main');
  const storage = {getItem: k => (k in stored ? stored[k] : null), setItem: (k, v) => { stored[k] = String(v); }};
  const ui = create({document, storage, reducedMotion: () => still, schedule: (fn, ms) => queue.push({fn, ms}),
    api: async (...args) => { requests.push(args); return {}; }});
  return {ui, root, queue, requests, stored};
}
const stepRows = root => root.all('li').filter(n => String(n.className).startsWith('automation-step'));
const visibleLabels = root => stepRows(root).filter(n => !n.hidden).map(n => n.children[1].children[0].textContent);
const button = (root, name) => root.all('button').find(b => b.textContent === name);
const toggle = root => root.all('input').find(i => i.type === 'checkbox');
const line = root => root.all('p').find(p => String(p.className).includes('replay-line'));

test('recorded order is the server sequence; the replay group is the latest reviewer decision and the steps after it', () => {
  const all = steps(8), shuffled = [all[5], all[0], all[7], all[2], all[1], all[6], all[4], all[3]];
  assert.deepEqual(recordedOrder(shuffled).map(s => s.seq), [1, 2, 3, 4, 5, 6, 7, 8]);
  // Without a sequence on every step, the order the server sent is kept.
  const unnumbered = [{label: 'b'}, {label: 'a'}];
  assert.deepEqual(recordedOrder(unnumbered).map(s => s.label), ['b', 'a']);
  const group = replayGroup(shuffled);
  assert.equal(group.decision.operation, 'approve-response');
  assert.deepEqual(group.before.map(s => s.seq), [1, 2, 3, 4, 5]);
  assert.deepEqual(group.replay.map(s => s.operation), ['approve-response', 'submit-response', 'receive-award']);
  assert.equal(replayGroup([{seq: 1, authority: {kind: 'EVENT_INTAKE'}}]), null);
});

test('the legend counts equal the recorded steps and agree with the server’s own counts', async () => {
  assert.deepEqual(stepLegend(steps(11), {person_decisions: 4, automatic_steps: 7}),
    {reviewer: 4, approved: 2, received: 5, other: 0, total: 11, agrees: true, server: {person_decisions: 4, automatic_steps: 7}});
  // A step that did not complete is not counted as automatic work, as the server counts; a difference is reported.
  const uncertain = steps(5); uncertain[4].state = 'UNCERTAIN';
  const legend = stepLegend(uncertain, {person_decisions: 1, automatic_steps: 4});
  assert.deepEqual([legend.reviewer, legend.approved, legend.received, legend.other, legend.agrees], [1, 1, 2, 1, false]);
  const h = harness(); await h.ui.activity(h.root, workflow(11, {person_decisions: 4, automatic_steps: 7}));
  const figures = h.root.all('dl').find(d => String(d.className).includes('step-legend')).children.map(d => d.textContent);
  assert.deepEqual(figures, ['Reviewer decisions4', 'Uptime · automatic2', 'Received from the vendor and other sources5']);
  assert.ok(h.root.textContent.includes('Uptime runs an automatic step only under an approval a reviewer already recorded. Those steps and the received events are the automatic steps the server counts.'));
  assert.ok(h.root.textContent.includes('4 reviewer decisions and 7 automatic steps recorded.'));
  assert.doesNotMatch(h.root.textContent, /differ from the steps listed/);
  const off = harness(); await off.ui.activity(off.root, {...workflow(5, {person_decisions: 1, automatic_steps: 4}), automation: {...workflow(5).automation, steps: uncertain, counts: {person_decisions: 1, automatic_steps: 4}}});
  assert.ok(off.root.textContent.includes('The server’s own counts differ from the steps listed: 1 reviewer decision and 4 automatic steps.'));
});

test('on by default on the demo line; turned off, every step shows at once, nothing is scheduled and no request is added', async () => {
  const on = harness(); await on.ui.activity(on.root, workflow(8, {person_decisions: 2, automatic_steps: 6}));
  assert.equal(toggle(on.root).checked, true); assert.equal(on.queue.length, 1); assert.equal(on.requests.length, 0);
  const h = harness({stored: {'uptime.steps.replay': 'off'}}); await h.ui.activity(h.root, workflow(8, {person_decisions: 2, automatic_steps: 6}));
  assert.equal(toggle(h.root).checked, false);
  assert.ok(button(h.root, 'Replay'));
  assert.equal(stepRows(h.root).filter(n => n.hidden).length, 0);
  assert.equal(h.queue.length, 0); assert.equal(h.requests.length, 0); assert.equal(line(h.root).hidden, true);
});

test('turned on, the next decision’s steps are shown one at a time in recorded order, then all remain', async () => {
  const h = harness({stored: {'uptime.steps.replay': 'off'}});
  await h.ui.activity(h.root, workflow(5, {person_decisions: 1, automatic_steps: 4}));
  toggle(h.root).checked = true; toggle(h.root).listeners.change();
  assert.equal(h.stored['uptime.steps.replay'], 'on');
  assert.equal(h.queue.length, 0, 'turning it on replays nothing already shown');
  // A reviewer decision is recorded (on the Overview); the page then shows Activity again.
  await h.ui.activity(h.root, workflow(8, {person_decisions: 2, automatic_steps: 6}));
  assert.equal(toggle(h.root).checked, true);
  const text = line(h.root).textContent;
  assert.equal(text, 'Replay: these steps ran when the reviewer decision “Approve response” was recorded. Shown one at a time so each can be read.');
  // The demo line names these steps Uptime · automatic; no step is ever attributed to a model or an AI, and nothing claims live work.
  assert.doesNotMatch(text, /\bAI\b|\bmodel\b|Claude|working|in progress|thinking/i);
  assert.ok(stepRows(h.root).every(n => !/\bAI\b|model|Claude/i.test(n.children[1].textContent)));
  const seen = [visibleLabels(h.root).slice(5)];
  while (h.queue.length) { const {fn, ms} = h.queue.shift(); assert.equal(ms, 1600); fn(); seen.push(visibleLabels(h.root).slice(5)); }
  assert.deepEqual(seen, [['Approve response'], ['Approve response', 'Send response'], ['Approve response', 'Send response', 'Receive credit decision']]);
  assert.deepEqual(visibleLabels(h.root), OPS.slice(0, 8).map(o => o[1]));
  assert.equal(line(h.root).textContent, 'Replay finished. These steps were recorded before the replay began; nothing ran during it.');
  assert.ok(stepRows(h.root).slice(5).every(n => n.className.includes('replay-reveal')));
  assert.equal(h.requests.length, 0);
  // The same decision is not replayed again when the page is drawn again.
  await h.ui.activity(h.root, workflow(8, {person_decisions: 2, automatic_steps: 6}));
  assert.equal(h.queue.length, 0); assert.equal(stepRows(h.root).filter(n => n.hidden).length, 0);
});

test('Replay shows the whole list in recorded order; skipping or turning it off shows every step at once', async () => {
  const h = harness({stored: {'uptime.steps.replay': 'off'}}); await h.ui.activity(h.root, workflow(11, {person_decisions: 4, automatic_steps: 7}));
  button(h.root, 'Replay').listeners.click();
  assert.equal(line(h.root).textContent, 'Replay: every step below has already run and been recorded. Shown one at a time so each can be read.');
  const order = [visibleLabels(h.root).at(-1)];
  while (h.queue.length) { h.queue.shift().fn(); order.push(visibleLabels(h.root).at(-1)); }
  assert.deepEqual(order, OPS.map(o => o[1]));
  button(h.root, 'Replay').listeners.click(); h.queue.shift().fn();
  assert.equal(visibleLabels(h.root).length, 2);
  button(h.root, 'Show every step now').listeners.click();
  assert.equal(visibleLabels(h.root).length, 11);
  const stale = h.queue.shift(); stale.fn(); assert.equal(h.queue.length, 0, 'a stopped replay schedules nothing more');
  // A new replay cancels an earlier one: only one timer chain runs.
  button(h.root, 'Replay').listeners.click(); const first = h.queue.shift();
  button(h.root, 'Replay').listeners.click(); first.fn();
  assert.equal(h.queue.length, 1);
});

test('reduced motion: the replay still goes one step at a time but adds no animation class', async () => {
  const h = harness({stored: {'uptime.steps.replay': 'on'}, still: true});
  await h.ui.activity(h.root, workflow(8, {person_decisions: 2, automatic_steps: 6}));
  while (h.queue.length) h.queue.shift().fn();
  assert.ok(stepRows(h.root).every(n => !n.className.includes('replay-reveal')));
  assert.equal(visibleLabels(h.root).length, 8);
});

test('browser storage that refuses leaves the setting in memory for this page', async () => {
  const root = new Element('main'), queue = [];
  const ui = create({document, storage: {getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); }},
    reducedMotion: () => false, schedule: fn => queue.push(fn), api: async () => ({})});
  await ui.activity(root, workflow(5, {person_decisions: 1, automatic_steps: 4}));
  assert.equal(queue.length, 1, 'on by default');
  toggle(root).checked = false; toggle(root).listeners.change();
  await ui.activity(root, workflow(8, {person_decisions: 2, automatic_steps: 6}));
  assert.equal(toggle(root).checked, false); assert.equal(queue.length, 1, 'turned off, nothing more is scheduled');
});
