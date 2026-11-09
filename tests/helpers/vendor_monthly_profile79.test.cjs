'use strict';
// Authored DOM control; the actual durable queue is exercised in Python tests.
// Decision 97 (D05) replaced the phase 79 operator profile select: the client never names a rule family.
const test = require('node:test');
const assert = require('node:assert/strict');
const {Element, document} = require('./companion_dom.cjs');
const {create} = require('../../web/v4_ui.js');

test('the rule family is selected by the server; any source edit revokes exact request confirmation', async () => {
  const root = new Element('main'), sent = [];
  const ui = create({document, reviewForms:true, getAccess:() => ({canDraft:true}), api:async (path,body) => {
    if (body === undefined && path === '/api/vendors') return {vendors:[]};
    sent.push({path,body});
    if (path.endsWith('/proposal-access')) return {outcome:'NOT_SUBMITTED', selected:null, review_requirements:[],
      offline:{accepted:false, reason:'NOT_CANONICAL'}, families:[
        {family:'monthly-availability/1', label:'Monthly availability', enabled:true, job:null, state:null, refusal:null},
        {family:'resource-month/1', label:'Resource month', enabled:true, job:null, state:null, refusal:null}]};
    throw new Error('Unexpected generation or mutation');
  }});
  await ui.render(root,'vendors');
  const box = root.all('div').find(n => String(n.className).split(' ').includes('v4-generator'));
  const fields = Object.fromEntries([...box.all('input'),...box.all('textarea'),...box.all('select')].map(n => [n.name,n]));
  assert.equal(fields.profile, undefined, 'no operator profile control exists');
  Object.assign(fields.vendor_id,{value:'juniper-reach'});
  fields.name.value='Authored monthly source'; fields.uri.value='urn:authored:phase79';
  fields.classification.value='synthetic_public'; fields.text.value='Public source\r\n';
  const button = name => root.all('button').find(n => n.textContent === name);
  await button('Check generation access').listeners.click();
  assert.equal(button('Generate proposals').disabled,false);
  assert.equal(sent[0].body.profile,'auto');
  fields.text.value='Public source changed\r\n'; fields.text.listeners.input();
  assert.equal(button('Generate proposals').disabled,true);
  await button('Generate proposals').listeners.click();
  assert.equal(sent.length,1);
  await button('Check generation access').listeners.click();
  assert.equal(sent[1].body.profile,'auto');
  assert.equal(sent[1].body.document.text,'Public source changed\r\n');
  assert.deepEqual(Object.keys(sent[1].body).sort(),['attempt_nonce','document','profile']);
  assert.equal(button('Generate proposals').disabled,false);
  assert.match(root.textContent, /Monthly availability/);
  assert.match(root.textContent, /Resource month/);
});
