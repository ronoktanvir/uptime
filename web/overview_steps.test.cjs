'use strict';
// The Overview shows a decision's recorded steps one at a time, and its figures move only as each step appears.
const test = require('node:test');
const assert = require('node:assert/strict');
const {create, actorTag, leadIn, newSteps, stagedView} = require('./workspace_ui.js');
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
const OPS = [['approve-claim', 'Approve January claim', 'PERSON'], ['submit-claim', 'File January claim', 'APPROVED_OPERATION'],
  ['receive-denial', 'Receive vendor response', 'EVENT_INTAKE', 'northwind-2026-01-vendor'], ['receive-artifact', 'Attach requested log', 'EVENT_INTAKE', 'northwind-2026-01-customer'],
  ['receive-verification', 'Verify supplied log', 'EVENT_INTAKE', 'northwind-2026-01-status']];
const step = ([operation, label, kind, subject], i) => ({seq: i + 1, operation, label, class: 'INTAKE', state: 'COMPLETED', at: '2026-03-01T12:00:00+00:00', intent_id: 'action-' + (i + 1),
  authority: kind === 'PERSON' ? {kind, actor: 'scripted-test-reviewer'} : kind === 'APPROVED_OPERATION' ? {kind, actor: 'scripted-test-reviewer', approved_at: '2026-03-01T12:00:00+00:00'} : {kind, event_id: 'e' + i, source_subject: subject}});
const stages = claimed => [{stage: 'estimated', label: 'Estimated', amount: '2400.00', status: 'recorded'}, {stage: 'claimed', label: 'Claimed', amount: claimed ? '2400.00' : null, status: claimed ? 'recorded' : 'not yet'},
  {stage: 'awarded', label: 'Awarded', amount: null, status: 'not yet'}];
const workflow = (n, enabled = true) => ({vendor: 'Northwind Cloud', claim: {id: 'inbox-northwind-2026-01', month: '2026-01', state: n ? 'NEEDS_EVIDENCE' : 'DRAFTED'},
  ledger: {destination: 'Local ledger', currency: 'USD', bill: {}}, finance: {stages: stages(n > 1), bill: {}, attention: [{owner: 'reviewer', title: n ? 'Approve the response' : 'Approve the claim'}]}, months: [], audit: [],
  next_actions: [{id: n ? 'approve-response' : 'approve-claim', label: n ? 'Approve response' : 'Approve January claim'}],
  automation: {enabled, state: 'PAUSED', pause: {reason: 'APPROVAL_REQUIRED'}, counts: {person_decisions: n ? 1 : 0, automatic_steps: Math.max(0, n - 1)}, steps: OPS.slice(0, n).map(step)}});
function harness(stored = {}, enabled = true) {
  const queue = [], requests = [], root = new Element('main');
  let reads = 0;
  const ui = create({document, storage: {getItem: k => (k in stored ? stored[k] : null), setItem: (k, v) => { stored[k] = v; }},
    reducedMotion: () => false, schedule: (fn, ms) => queue.push({fn, ms}),
    api: async (path, body) => { requests.push(body === undefined ? path : 'POST ' + path); if (body !== undefined) return {}; return {workflow: workflow(reads++ ? 5 : 0, enabled)}; }});
  return {ui, root, queue, requests, stored};
}
const recovery = root => root.all('section').find(s => s.id === 'finance-recovery');
const actions = root => recovery(root).all('div').find(d => d.className === 'actions');
const claimed = root => root.all('li').find(li => String(li.className).startsWith('lifecycle-step') && li.children[0].textContent === 'Claimed');
const feedRows = root => recovery(root).all('li').filter(li => !li.hidden && /overview-(step|lead)/.test(li.className)).map(li => li.className.includes('overview-lead') ? 'lead: ' + li.textContent : li.children[0].children[0].textContent);
const statusText = root => recovery(root).all('p').find(p => p.attrs.role === 'status').textContent;

test('three plain actors: the reviewer, Uptime automatic steps, and the vendor or the named source', () => {
  const steps = OPS.map(step);
  assert.deepEqual(steps.map(s => actorTag(s).label), ['Reviewer decision', 'Uptime · automatic', 'Vendor', 'Customer source', 'Status source']);
  assert.equal(actorTag({authority: {kind: 'EVENT_INTAKE', source_subject: 'northwind-2026-01-billing'}}).label, 'Billing source');
  assert.equal(actorTag({authority: {kind: 'EVENT_INTAKE'}}).label, 'Received event');
  assert.equal(actorTag({authority: {kind: 'COORDINATOR'}}), null);
  for (const s of steps) assert.doesNotMatch(actorTag(s).label, /\bAI\b|model|Claude/i);
  assert.deepEqual(steps.slice(1).map(leadIn), ['Filing the claim with the vendor…', 'Receiving the vendor’s reply…', 'Attaching the requested service log…', 'Matching the service log to the request…']);
  assert.equal(leadIn({operation: 'unknown-op', label: 'Something recorded'}), 'Something recorded…');
});

test('a decision’s new steps are those after the last one already shown; held stages wait for the step that recorded them', () => {
  const before = workflow(0), after = workflow(5);
  assert.deepEqual(newSteps(before, after).map(s => s.operation), OPS.map(o => o[0]));
  assert.deepEqual(newSteps(workflow(2), after).map(s => s.seq), [3, 4, 5]);
  const pending = newSteps(before, after);
  const held = stagedView(before, after, pending.slice(1));
  assert.equal(held.finance.stages.find(r => r.stage === 'claimed').status, 'not yet');
  assert.equal(held.claim.state, 'DRAFTED');
  const moved = stagedView(before, after, pending.slice(2));
  assert.equal(moved.finance.stages.find(r => r.stage === 'claimed').amount, '2400.00');
  assert.equal(stagedView(before, after, []), after);
});

test('after a decision the Overview shows each recorded step in order, the figures move with them, and the next decision waits', async () => {
  const h = harness();
  await h.ui.render(h.root);
  assert.equal(claimed(h.root).children[2].textContent, 'Not yet');
  await actions(h.root).children[0].listeners.click();
  assert.deepEqual(h.requests, ['/api/workspace/workflow', 'POST /api/workspace/workflow/actions/approve-claim', '/api/workspace/workflow']);
  assert.equal(actions(h.root).hidden, true);
  assert.equal(statusText(h.root), 'Recorded: Approve January claim.');
  assert.ok(recovery(h.root).textContent.includes('Steps recorded after “Approve January claim”, shown in order'));
  assert.equal(claimed(h.root).children[2].textContent, 'Not yet', 'the claim is not shown as filed before its step appears');
  const attention = () => h.root.all('section').find(s => s.id === 'finance-attention').all('h3').map(n => n.textContent);
  assert.deepEqual(attention(), ['Approve the claim'], 'what needs attention updates only when the steps have been shown');
  const frames = [feedRows(h.root)];
  const claimedAt = [];
  while (h.queue.length) { const {fn, ms} = h.queue.shift(); assert.ok(ms === 500 || ms === 900); fn(); frames.push(feedRows(h.root)); claimedAt.push(claimed(h.root).children[2].textContent); }
  assert.deepEqual(frames.slice(0, 4), [['Approve January claim'], ['Approve January claim', 'lead: Filing the claim with the vendor…'],
    ['Approve January claim', 'File January claim'], ['Approve January claim', 'File January claim', 'lead: Receiving the vendor’s reply…']]);
  assert.equal(claimedAt[0], 'Not yet'); assert.equal(claimedAt[1], 'Recorded');
  assert.deepEqual(frames.at(-1), OPS.map(o => o[1]));
  const tags = recovery(h.root).all('li').filter(li => li.className.includes('overview-step')).map(li => li.children[0].children[1].textContent);
  assert.deepEqual(tags, ['Reviewer decision', 'Uptime · automatic', 'Vendor', 'Customer source', 'Status source']);
  assert.ok(recovery(h.root).textContent.includes('Run automatically under the approval recorded by scripted-test-reviewer'));
  assert.equal(actions(h.root).hidden, false);
  assert.deepEqual(attention(), ['Approve the response']);
  assert.equal(statusText(h.root), 'Recorded: Approve January claim. Next: Approve response.');
  assert.equal(h.requests.length, 3, 'the replay makes no request');
  assert.equal(h.stored['uptime.steps.replay.seen'], 'action-1', 'Activity does not replay the same decision again');
});

test('turned off, or in a step-by-step workspace, the Overview shows the result at once', async () => {
  const off = harness({'uptime.steps.replay': 'off'});
  await off.ui.render(off.root); await actions(off.root).children[0].listeners.click();
  assert.equal(off.queue.length, 0); assert.notEqual(actions(off.root).hidden, true);
  assert.equal(claimed(off.root).children[2].textContent, 'Recorded');
  assert.equal(statusText(off.root), 'Recorded: Approve January claim. Next: Approve response.');
  const box = recovery(off.root).all('input').find(i => i.type === 'checkbox');
  assert.equal(box.checked, false);
  assert.ok(recovery(off.root).textContent.includes('Show the steps one at a time after each decision'));
  const manual = harness({}, false);
  await manual.ui.render(manual.root); await actions(manual.root).children[0].listeners.click();
  assert.equal(manual.queue.length, 0);
});

test('turning the control off mid-way shows every step and the next decision at once', async () => {
  const h = harness();
  await h.ui.render(h.root); await actions(h.root).children[0].listeners.click();
  h.queue.shift().fn();
  const box = recovery(h.root).all('input').find(i => i.type === 'checkbox');
  box.checked = false; box.listeners.change();
  assert.equal(h.stored['uptime.steps.replay'], 'off');
  assert.deepEqual(feedRows(h.root), OPS.map(o => o[1]));
  assert.equal(actions(h.root).hidden, false);
  assert.equal(claimed(h.root).children[2].textContent, 'Recorded');
  while (h.queue.length) h.queue.shift().fn();
  assert.deepEqual(feedRows(h.root), OPS.map(o => o[1]), 'a stopped replay adds nothing more');
});
