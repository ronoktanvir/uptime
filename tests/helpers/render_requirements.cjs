'use strict';
// Renders a vendor card from recorded server JSON with the real web/v4_ui.js, opens "Show review requirements"
// and prints what a reviewer would read. Usage: node render_requirements.cjs <payload.json>
const fs = require('node:fs');
const {Element, document} = require('./companion_dom.cjs');
const {create} = require('../../web/v4_ui.js');
(async () => {
  const {vendor_id, detail, requirements} = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const base = '/api/vendors/' + encodeURIComponent(vendor_id), calls = [];
  const api = async (path, body) => {
    calls.push({path, method:body === undefined ? 'GET' : 'POST'});
    if (body !== undefined) throw new Error('No write is expected: ' + path);
    if (path === '/api/vendors') return {vendors:[{vendor_id, state:detail.state}]};
    if (path === base) return detail;
    if (path === base + '/requirements') return requirements;
    throw new Error('Unexpected request ' + path);
  };
  const root = new Element('main');
  const ui = create({document, getAccess:() => ({canWrite:false}), api});
  await ui.render(root, 'vendors');
  const open = root.all('button').find(b => b.textContent === 'Show review requirements');
  if (!open) throw new Error('No review requirements control');
  await open.listeners.click();
  const card = root.all('div').find(n => String(n.className).split(' ').includes('v4-requirements-card'));
  process.stdout.write(JSON.stringify({text:card ? card.textContent : null, calls,
    blockquotes:card ? card.all('blockquote').map(q => q.textContent) : [],
    markup:root.all('img').length + root.all('script').length}));
})().catch(error => { console.error(error); process.exit(1); });
