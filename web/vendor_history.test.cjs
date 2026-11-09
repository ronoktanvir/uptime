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
  return root.textContent;
}
test('a rolled-back adapter says nothing is active and separates scripted preparation from account actions', async () => {
  const text = await render({vendor_id:'calyxquay', name:'CalyxQuay', revision:9, state:'REVOKED', active_version:null, reviewer:null, audit});
  assert.ok(text.includes('Review history'));
  assert.ok(text.includes('Rolled back. No version is active.'));
  for (let i = 1; i <= 5; i++) assert.ok(text.includes(`Revision ${i} · ${kinds[i - 1]}`));
  assert.equal((text.match(/Scripted preparation \(scripted-test-reviewer\)/g) || []).length, 5);
  assert.equal((text.match(/Recorded under account reviewer-account/g) || []).length, 4);
  assert.ok(text.includes('Revision 9 · Roll back activation'));
  assert.ok(!text.includes('Active version'));
});
test('an active adapter names its version; other states are stated plainly', async () => {
  assert.ok((await render({vendor_id:'v', revision:8, state:'ACTIVE', active_version:'abc123', audit:audit.slice(0, 8)})).includes('Active version abc123.'));
  assert.ok((await render({vendor_id:'v', revision:5, state:'SHADOW', active_version:null, audit:audit.slice(0, 5)})).includes('Current state: SHADOW.'));
  assert.ok(!(await render({vendor_id:'v', revision:1, state:'DRAFT'})).includes('Review history'));
});
