'use strict';
// DOM contract for a case page's closed "Decision, unknowns and amounts as recorded" section (acceptance A2).
// The claim's own record does not track posting or application and sends a zero for both, so a zero there is not
// stated as an amount. Authored data; not a browser or service proof.
const test = require('node:test');
const assert = require('node:assert/strict');
const {Element, document} = require('./companion_dom.cjs');
const {create} = require('../../web/v4_ui.js');

const ID = 'inbox-a2';
const BASE = '/api/correspondence/claims/' + ID;
const SENTENCE = 'This record does not track posting or application; the Overview’s credit lifecycle shows them for the credit it follows.';
const row = (label, amount) => ({label, value:'USD ' + amount, sources:[]});
function claim(ledger) {
  return {claim_id:ID, id:ID, title:'Claim correspondence · A2', vendor:'Northwind Cloud', stage:'AWARDED', outcome:'ELIGIBLE', actions:[], sources:[],
    ledger, financials:ledger && [row('Estimated', ledger.estimated), row('Claimed', ledger.claimed), row('Awarded', ledger.awarded),
      row('Posted', ledger.posted), row('Applied', ledger.applied), row('Disputed Remainder', ledger.disputed_remainder)]};
}
async function sections(data) {
  const root = new Element('main'), calls = [];
  const api = async (path, body) => { calls.push({path, body}); if (body === undefined && path === BASE) return data; throw new Error('Unexpected request ' + path); };
  const ui = create({document, getAccess:() => ({canWrite:false}), api});
  await ui.inspect(root, ID);
  const folds = root.all('details').filter(n => n.children[0] && n.children[0].tagName === 'summary');
  const named = title => folds.find(n => n.children[0].textContent === title);
  assert.deepEqual(calls.map(c => c.path), [BASE], 'one read, no write');
  return {recorded:named('Decision, unknowns and amounts as recorded'), complete:named('Complete server case record'), page:root};
}

test('a zero for posting and application is not stated as an amount; the other four and the complete record are exact', async () => {
  const s = await sections(claim({estimated:'2400.00', claimed:'2400.00', awarded:'2400.00', posted:'0.00', applied:'0.00', disputed_remainder:'0.00'}));
  const text = s.recorded.textContent;
  for (const label of ['Estimated', 'Claimed', 'Awarded', 'Disputed Remainder']) assert.ok(text.includes(label), label + ' stays');
  assert.equal((text.match(/USD 2400\.00/g) || []).length, 3, 'estimated, claimed and awarded as the record sends them');
  assert.ok(text.includes('USD 0.00'), 'the disputed remainder the record does track is shown, zero or not');
  assert.equal((text.match(/USD 0\.00/g) || []).length, 1, 'only the tracked zero is stated');
  assert.ok(!/Posted|Applied/.test(text), 'no Posted or Applied row');
  assert.ok(text.includes(SENTENCE));
  // The raw record is the record: both fields and their zeros stay.
  assert.match(s.complete.textContent, /posted\s+0\.00/);
  assert.match(s.complete.textContent, /applied\s+0\.00/);
});

test('a non-zero posted or applied amount on the record is shown like the others', async () => {
  const one = await sections(claim({estimated:'2400.00', claimed:'2400.00', awarded:'2400.00', posted:'2400.00', applied:'0.00', disputed_remainder:'0.00'}));
  assert.ok(one.recorded.textContent.includes('Posted'));
  assert.equal((one.recorded.textContent.match(/USD 2400\.00/g) || []).length, 4);
  assert.ok(!one.recorded.textContent.includes('Applied'));
  assert.ok(one.recorded.textContent.includes('This record does not track application; the Overview’s credit lifecycle shows it for the credit it follows.'));
  const both = await sections(claim({estimated:'2400.00', claimed:'2400.00', awarded:'2400.00', posted:'2400.00', applied:'1200.00', disputed_remainder:'0.00'}));
  assert.ok(both.recorded.textContent.includes('Posted') && both.recorded.textContent.includes('Applied'));
  assert.ok(both.recorded.textContent.includes('USD 1200.00'));
  assert.ok(!both.recorded.textContent.includes('does not track'), 'nothing withheld, so no sentence');
});

test('a record without amounts states none and adds no sentence', async () => {
  const s = await sections(claim(undefined));
  assert.ok(!s.recorded.textContent.includes('does not track'));
  assert.ok(!/USD/.test(s.recorded.textContent));
});
