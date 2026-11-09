const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const DIR = path.join(__dirname, '..', '..', 'extension');
const {billFromUrl, routeFor, frameUrl, labelFor} = require(path.join(DIR, 'panel.js'));
const config = require(path.join(DIR, 'config.js'));
const manifest = JSON.parse(fs.readFileSync(path.join(DIR, 'manifest.json'), 'utf8'));
const BILL = 'f74ba12c-95d0-582d-9f62-26d8057d1d37';
const HOSTS = ['demo.ramp.com'];

test('a Ramp bill address gives Ramp\'s own bill ID, lower-cased, and nothing else does', () => {
  assert.equal(billFromUrl(`https://demo.ramp.com/bill-pay/bills/list/${BILL}`, HOSTS), BILL);
  assert.equal(billFromUrl(`https://demo.ramp.com/bill-pay/bills/${BILL.toUpperCase()}`, HOSTS), BILL);
  assert.equal(billFromUrl(`https://demo.ramp.com/bill-pay/bills/list/${BILL}/details?tab=activity#notes`, HOSTS), BILL);
  for (const other of [
    `http://demo.ramp.com/bill-pay/bills/list/${BILL}`,
    `https://demo.ramp.com.evil.example/bill-pay/bills/list/${BILL}`,
    `https://evil.example/bill-pay/bills/list/${BILL}`,
    `https://app.ramp.com/bill-pay/bills/list/${BILL}`,
    `http://127.0.0.1:8776/bill-pay/bills/list/${BILL}`,
    `https://evil.example/?next=https://demo.ramp.com/bill-pay/bills/list/${BILL}`,
    `https://demo.ramp.com/bill-pay/bills/list/${BILL.slice(0, -1)}`,
    `https://demo.ramp.com/bill-pay/bills/list/${BILL}0`,
    'https://demo.ramp.com/bill-pay/bills/list',
    'https://demo.ramp.com/vendors/' + BILL,
    'chrome-extension://kibophanbmnepbmhpampfagpjfhjfcnl/panel.html',
    'not a url', '', null, undefined, 42,
  ]) assert.equal(billFromUrl(other, HOSTS), null, String(other));
  assert.equal(billFromUrl(`https://demo.ramp.com/bill-pay/bills/list/${BILL}`, []), null);
  assert.equal(billFromUrl(`https://demo.ramp.com/bill-pay/bills/list/${BILL}`, undefined), null);
});

test('the panel opens the bill page for a bill and the home page otherwise, only on the configured origin', () => {
  assert.equal(routeFor(BILL, config), 'ramp-bill/' + BILL);
  assert.equal(routeFor(null, config), 'records');
  assert.equal(frameUrl(BILL, config), 'http://127.0.0.1:8776/#ramp-bill/' + BILL);
  assert.equal(frameUrl(null, config), 'http://127.0.0.1:8776/#records');
  assert.equal(labelFor(BILL), 'Ramp bill f74ba12c…');
  assert.equal(labelFor(null), 'No Ramp bill open');
  const origin = new URL(config.origin);
  assert.equal(origin.protocol, 'http:');
  assert.equal(origin.hostname, '127.0.0.1');
  assert.deepEqual(config.rampHosts, HOSTS);
});

test('the manifest asks for the side panel and Ramp tab addresses only, and its key pins one ID', () => {
  assert.equal(manifest.manifest_version, 3);
  assert.deepEqual(manifest.permissions, ['sidePanel']);
  assert.deepEqual(manifest.host_permissions, config.rampHosts.map(host => `https://${host}/*`));
  for (const key of ['content_scripts', 'optional_permissions', 'optional_host_permissions', 'externally_connectable',
    'web_accessible_resources', 'content_security_policy', 'oauth2', 'chrome_url_overrides', 'declarative_net_request'])
    assert.equal(manifest[key], undefined, key);
  assert.deepEqual(manifest.side_panel, {default_path: 'panel.html'});
  assert.deepEqual(manifest.background, {service_worker: 'background.js'});
  const digest = crypto.createHash('sha256').update(Buffer.from(manifest.key, 'base64')).digest('hex').slice(0, 32);
  const id = Array.from(digest, c => String.fromCharCode(97 + parseInt(c, 16))).join('');
  assert.equal(id, 'kibophanbmnepbmhpampfagpjfhjfcnl');
});

test('the extension is a thin shell: no requests, storage, scripting of other pages or injected markup', () => {
  const files = fs.readdirSync(DIR).sort();
  assert.deepEqual(files, ['README.md', 'background.js', 'config.js', 'manifest.json', 'panel.css', 'panel.html', 'panel.js']);
  const source = ['background.js', 'config.js', 'panel.js'].map(name => fs.readFileSync(path.join(DIR, name), 'utf8')).join('\n');
  for (const banned of [/\bfetch\s*\(/, /XMLHttpRequest/, /WebSocket/, /sendBeacon/, /localStorage/, /sessionStorage/, /indexedDB/,
    /chrome\.storage/, /chrome\.scripting/, /chrome\.cookies/, /chrome\.webRequest/, /chrome\.debugger/, /executeScript/,
    /innerHTML/, /insertAdjacentHTML/, /document\.write/, /\beval\s*\(/, /new Function/, /postMessage/, /document\.cookie/])
    assert.equal(banned.test(source), false, String(banned));
  const html = fs.readFileSync(path.join(DIR, 'panel.html'), 'utf8');
  assert.equal(/<script(?![^>]*\ssrc=)/.test(html), false);
  assert.equal(/\son[a-z]+\s*=/.test(html), false);
  assert.equal(/style\s*=/.test(html), false);
  assert.deepEqual(Array.from(html.matchAll(/src="([^"]+)"/g), m => m[1]), ['config.js', 'panel.js']);
});
