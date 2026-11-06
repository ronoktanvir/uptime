'use strict';
// Authored DOM control; the actual durable queue is exercised in Python tests.
const test = require('node:test');
const assert = require('node:assert/strict');
const {Element, document} = require('./companion_dom.cjs');
const {create} = require('../../web/v4_ui.js');

test('monthly prose profile is explicit and changing it revokes exact request confirmation', async () => {
  const root = new Element('main'), sent = [];
  const ui = create({document, reviewForms:true, getAccess:() => ({canDraft:true}), api:async (path,body) => {
    if (body === undefined && path === '/api/vendors') return {vendors:[]};
    sent.push({path,body});
    if (path.endsWith('/proposal-access')) return {enabled:true,request_sha256:'a'.repeat(64),context_sha256:'b'.repeat(64),
      disclosure:{model:'claude-opus-5-5',tools:[]},existing_job:null};
    throw new Error('Unexpected generation or mutation');
  }});
  await ui.render(root,'vendors');
  const box = root.all('div').find(n => String(n.className).split(' ').includes('v4-generator'));
  const fields = Object.fromEntries([...box.all('input'),...box.all('textarea'),...box.all('select')].map(n => [n.name,n]));
  assert.deepEqual(fields.profile.all('option').map(n => n.value),['','monthly','monthly-propositions','resource-month']);
  assert.equal(fields.profile.value,'');
  Object.assign(fields.vendor_id,{value:'juniper-reach'});
  fields.name.value='Authored monthly source'; fields.uri.value='urn:authored:phase79';
  fields.classification.value='synthetic_public'; fields.text.value='Public source\r\n';
  fields.profile.value='monthly';
  const button = name => root.all('button').find(n => n.textContent === name);
  await button('Check generation access').listeners.click();
  assert.equal(button('Generate proposal').disabled,false);
  assert.equal(sent[0].body.profile,'monthly');
  fields.profile.value='monthly-propositions'; fields.profile.listeners.change();
  assert.equal(button('Generate proposal').disabled,true);
  await button('Generate proposal').listeners.click();
  assert.equal(sent.length,1);
  await button('Check generation access').listeners.click();
  assert.equal(sent[1].body.profile,'monthly-propositions');
  assert.equal(sent[1].body.document.text,'Public source\r\n');
  assert.deepEqual(Object.keys(sent[1].body).sort(),['attempt_nonce','document','profile']);
  assert.equal(button('Generate proposal').disabled,false);
});
