'use strict';
// Behavioral DOM check: who recorded each adapter revision, and the plain final state.
const test = require('node:test');
const assert = require('node:assert/strict');
const {create} = require('./v4_ui.js');
class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.listeners = {}; this.attrs = {}; this.value = ''; this._text = ''; }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text + this.children.map(n => n.textContent).join(' '); }
  append(...nodes) { this.children.push(...nodes); }
  prepend(...nodes) { this.children.unshift(...nodes); }
  replaceChildren(...nodes) { this._text = ''; this.children = nodes; }
  setAttribute(k,v) { this.attrs[k] = v; }
  addEventListener(k,f) { this.listeners[k] = f; }
  all(tag) { return this.children.flatMap(n => [...(n.tagName === tag ? [n] : []), ...n.all(tag)]); }
  reportValidity() { return true; }
}
const document = {createElement: tag => new Element(tag)};
const kinds = ['Imported public document and separate tenant overlay','Validated source coverage, typed thresholds and governing dates',
  'Shadow only; waiting for independent reviewer cases','Named pre-pricing source and literal evidence binding review',
  'Executed reviewer-authored scenarios in shadow','Accept source interpretation for this review','Approve reviewed tests',
  'Activate for local evaluation','Roll back activation'];
const audit = kinds.map((kind, i) => ({revision:i + 1, kind, at:`t${i + 1}`, actor:i < 5 ? 'scripted-test-reviewer' : 'reviewer-account'}));
async function render(vendor) {
  const root = new Element('main');
  // The list returns a summary; the client then reads the detail route, as with the real server.
  const ui = create({document, getAccess:() => ({canWrite:false}), api:async path =>
    path === '/api/vendors' ? {vendors:[{vendor_id:vendor.vendor_id, state:vendor.state}]} : vendor});
  await ui.render(root, 'vendors');
  return root;
}
const count = (text, pattern) => (text.match(pattern) || []).length;
test('a rolled-back adapter says nothing is active and separates scripted preparation from account actions', async () => {
  const root = await render({vendor_id:'calyxquay', name:'CalyxQuay', revision:9, state:'REVOKED', active_version:null, reviewer:null, audit});
  const text = root.textContent;
  assert.ok(text.includes('Review history'));
  assert.ok(text.includes('Rolled back. No version is active.'));
  for (let i = 1; i <= 5; i++) assert.ok(text.includes(`Revision ${i} · ${kinds[i - 1]}`));
  // Every revision row names who recorded it: five scripted, four under an account.
  const history = root.all('ol').find(n => n.className === 'v4-history').textContent;
  assert.equal(count(history, /Scripted preparation \(scripted-test-reviewer\)/g), 5);
  assert.equal(count(history, /Recorded under account reviewer-account/g), 4);
  // The summary in view names each once, with the number of steps it recorded, and nothing else on the page does.
  const who = root.all('ul').find(n => n.className === 'v4-actors').all('li').map(n => n.textContent);
  assert.deepEqual(who, ['Scripted preparation (scripted-test-reviewer) 5 steps', 'Recorded under account reviewer-account 4 steps']);
  assert.equal(count(text, /Scripted preparation \(scripted-test-reviewer\)/g), 6);
  assert.equal(count(text, /Recorded under account reviewer-account/g), 5);
  assert.ok(text.includes('Revision 9 · Roll back activation'));
  assert.ok(!text.includes('Active version'));
  assert.ok(text.includes('Not in force.') && !text.includes('In force in this workspace.'));
});
test('an active adapter names its version; other states are stated plainly', async () => {
  const active = (await render({vendor_id:'v', revision:8, state:'ACTIVE', active_version:'abc123', audit:audit.slice(0, 8)})).textContent;
  assert.ok(active.includes('Active version abc123.') && active.includes('In force in this workspace.'));
  const shadow = (await render({vendor_id:'v', revision:5, state:'SHADOW', active_version:null, audit:audit.slice(0, 5)})).textContent;
  assert.ok(shadow.includes('Current state: SHADOW.') && shadow.includes('Not in force.'));
  assert.ok(!(await render({vendor_id:'v', revision:1, state:'DRAFT'})).textContent.includes('Review history'));
});
