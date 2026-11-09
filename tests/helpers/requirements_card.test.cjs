'use strict';
// DOM contract for the read-only review requirements on a vendor card. Authored payloads; not a service proof.
const test = require('node:test');
const assert = require('node:assert/strict');
const {Element, document} = require('./companion_dom.cjs');
const {create} = require('../../web/v4_ui.js');

const ID = 'aster-cove', BASE = '/api/vendors/' + ID;
const DETAIL = {vendor_id:ID, name:'Aster Cove', revision:3, state:'SHADOW', active_version:null, reviewer:null, audit:[],
  manifest:{citations:[{id:4, quote:'Claims within 15 days <script>x()</script>'}]}};
const REQUIREMENTS = {vendor_id:ID, version:'v', revision:3, state:'SHADOW', authority:{approval_gate:false, dispatch_authorized:false},
  card:{schema:'adapter-requirements/1', family:'resource-month/1', supported:true, no_open_requirements:false, source_sha256:'a'.repeat(64),
    elements:[{element:'deadline', status:'PRESENT', citations:[4, 9], detail:{filing_days:15}, requirement:null},
      {element:'evidence', status:'REVIEW_REQUIRED', citations:[], detail:{}, requirement:'Name the <b>monitor</b> that establishes downtime.'},
      {element:'new_element', status:'SOMETHING_NEW', citations:[], detail:null, requirement:null}],
    review_requirements:['Resolve the evidence requirement before approval.']},
  drafts:{generated:false, reason:'The family is not supported for drafts', notice:null, scenarios:[]},
  draft_overlap:{tests_reusing_draft_facts:['copied case'], warning:'One submitted test reuses generated draft facts.'},
  family_selection:{outcome:'AMBIGUOUS', selected:null, review_requirements:['Two families fit; Uptime does not choose between readings.'],
    families:[{family:'monthly-availability/1', label:'Monthly availability', state:'VALIDATED', refusal:null},
      {family:'resource-month/1', label:'Resource month', state:'REFUSED_READING',
       refusal:{codes:['X'], explanations:['The reading was refused.'], passages:['Per resource <img src=x>'], missing_terms:['credit remedy']}}]}};
const button = (root, name) => root.all('button').find(b => b.textContent === name);

async function card(answer, detail = DETAIL) {
  const root = new Element('main'), calls = [];
  const api = async (path, body) => {
    calls.push({path, body});
    if (body !== undefined) throw new Error('no write expected');
    if (path === '/api/vendors') return {vendors:[{vendor_id:ID, state:detail.state}]};
    if (path === BASE) return detail;
    if (path === BASE + '/requirements') { if (answer instanceof Error) throw answer; return answer; }
    throw new Error('Unexpected request ' + path);
  };
  const ui = create({document, getAccess:() => ({canWrite:true}), api, onUnauthorized:() => {}});
  await ui.render(root, 'vendors');
  const open = button(root, 'Show review requirements');
  if (open) await open.listeners.click();
  return {root, calls, open};
}

test('elements, reviewer tasks, family choice, missing drafts and overlap render as text only', async () => {
  const {root, calls} = await card(REQUIREMENTS);
  const text = root.textContent;
  for (const expected of ['Claim deadline: stated in the source', 'Cited clauses 4, 9', 'Clause 9 text not returned.',
    'Evidence: review required', 'Name the <b>monitor</b> that establishes downtime.', 'New element: something new',
    'Resolve the evidence requirement before approval.', 'How the rule family was chosen', 'Outcome: ambiguous.',
    'Two families fit; Uptime does not choose between readings.', 'Monthly availability: validated', 'Resource month: refused reading',
    'Why this family was refused', 'The reading was refused.', 'Required terms not established by the source: credit remedy.',
    'No drafts were generated: The family is not supported for drafts.', 'One submitted test reuses generated draft facts.',
    'Tests reusing draft facts: copied case.', 'Read only. These requirements grant no approval, activation or dispatch.'])
    assert.ok(text.includes(expected), expected);
  assert.deepEqual(root.all('blockquote').map(q => q.textContent), ['Claims within 15 days <script>x()</script>', 'Per resource <img src=x>']);
  assert.equal(root.all('script').length + root.all('img').length + root.all('b').length, 0);
  assert.ok(calls.every(c => c.body === undefined));
  assert.equal(calls.filter(c => c.path === BASE + '/requirements').length, 1);
});

test('a non-automatic version, a 401 and a failed read each say so without inventing content', async () => {
  const manual = await card({...REQUIREMENTS, family_selection:{outcome:'NOT_AUTOMATIC', review_requirements:['Chosen by an operator profile.']}});
  assert.ok(manual.root.textContent.includes('This version was not chosen by automatic family selection.'));
  assert.ok(manual.root.textContent.includes('Chosen by an operator profile.'));
  const expired = await card(Object.assign(new Error('expired'), {status:401}));
  assert.ok(!expired.root.textContent.includes('Elements'));
  const failed = await card(new Error('boom'));
  assert.ok(failed.root.textContent.includes('Review requirements unavailable. Nothing was changed.'));
  assert.ok(!failed.root.textContent.includes('boom'));
});

test('no requirements control without a readable revision', async () => {
  const {open, calls} = await card(REQUIREMENTS, {...DETAIL, revision:null});
  assert.equal(open, undefined);
  assert.ok(!calls.some(c => c.path.endsWith('/requirements')));
});
