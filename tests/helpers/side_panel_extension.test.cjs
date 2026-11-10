const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const DIR = path.join(__dirname, '..', '..', 'extension');
const {billFromUrl, routeFor, frameUrl, labelFor, latestOnly, openRequest, appUrl, openApp, allowedRoute, OPEN_TYPE, statusRequest, setBadge, STATUS_TYPE} = require(path.join(DIR, 'panel.js'));
const app = require(path.join(__dirname, '..', '..', 'web', 'app.js'));
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
  assert.equal(routeFor(null, config), 'ramp-bill');
  assert.equal(frameUrl(BILL, config), 'http://127.0.0.1:8776/#ramp-bill/' + BILL);
  assert.equal(frameUrl(null, config), 'http://127.0.0.1:8776/#ramp-bill');
  assert.equal(labelFor(BILL), 'Ramp bill f74ba12c…');
  assert.equal(labelFor(null), 'No Ramp bill open');
  const origin = new URL(config.origin);
  assert.equal(origin.protocol, 'http:');
  assert.equal(origin.hostname, '127.0.0.1');
  assert.deepEqual(config.rampHosts, HOSTS);
});

test('when tab lookups finish out of order, only the most recent one moves the panel', async () => {
  const delivered = [];
  const waits = [40, 5, 20];
  let call = 0;
  const refresh = latestOnly(() => { const mine = call++; return new Promise(done => setTimeout(() => done('tab ' + mine), waits[mine])); },
    value => delivered.push(value));
  await Promise.all([refresh(), refresh(), refresh()]);
  assert.deepEqual(delivered, ['tab 2']);
  await refresh();
  assert.deepEqual(delivered, ['tab 2', 'tab 3']);
});

test('the manifest asks for the side panel, Ramp tab addresses and the Uptime app\'s own tab addresses only, and its key pins one ID', () => {
  assert.equal(manifest.manifest_version, 3);
  assert.deepEqual(manifest.permissions, ['sidePanel']);
  // Demo line: the app's own origin is added so that a tab on Uptime itself can be recognised.
  assert.deepEqual(manifest.host_permissions, [...config.rampHosts.map(host => `https://${host}/*`), config.origin + '/*']);
  assert.equal(new URL(config.origin).origin, config.origin);
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
    /innerHTML/, /insertAdjacentHTML/, /document\.write/, /\beval\s*\(/, /new Function/, /postMessage/, /document\.cookie/,
    /chrome\.runtime/, /externally_connectable/])
    assert.equal(banned.test(source), false, String(banned));
  const html = fs.readFileSync(path.join(DIR, 'panel.html'), 'utf8');
  assert.equal(/<script(?![^>]*\ssrc=)/.test(html), false);
  assert.equal(/\son[a-z]+\s*=/.test(html), false);
  assert.equal(/style\s*=/.test(html), false);
  assert.deepEqual(Array.from(html.matchAll(/src="([^"]+)"/g), m => m[1]), ['config.js', 'panel.js']);
});

// ---- Opening the full app from the panel ----
const ORIGIN = config.origin;
const frameWindow = {name: 'the framed app'};
const message = (data, extra = {}) => ({origin: ORIGIN, source: frameWindow, data, ...extra});

test('the shell accepts only {type, route} from the framed window on the configured origin', () => {
  assert.equal(OPEN_TYPE, 'uptime-open-app');
  assert.equal(openRequest(message({type: OPEN_TYPE, route: 'records'}), config, frameWindow), 'records');
  assert.equal(openRequest(message({route: 'overview', type: OPEN_TYPE}), config, frameWindow), 'overview');
  for (const [why, event] of [
    ['another origin', message({type: OPEN_TYPE, route: 'records'}, {origin: 'https://demo.ramp.com'})],
    ['the origin with a trailing slash', message({type: OPEN_TYPE, route: 'records'}, {origin: ORIGIN + '/'})],
    ['the same origin but another window', message({type: OPEN_TYPE, route: 'records'}, {source: {}})],
    ['no source window', message({type: OPEN_TYPE, route: 'records'}, {source: null})],
    ['another type', message({type: 'open', route: 'records'})],
    ['an extra key', message({type: OPEN_TYPE, route: 'records', url: 'https://evil.example/'})],
    ['a missing route', message({type: OPEN_TYPE})],
    ['a string', message('uptime-open-app records')],
    ['an array', message([OPEN_TYPE, 'records'])],
    ['null', message(null)],
    ['an object with another prototype', message(Object.assign(Object.create({inherited: true}), {type: OPEN_TYPE, route: 'records'}))],
    ['a route off the list', message({type: OPEN_TYPE, route: 'ramp-bill/f74ba12c-95d0-582d-9f62-26d8057d1d37'})],
  ]) assert.equal(openRequest(event, config, frameWindow), null, why);
  assert.equal(openRequest(message({type: OPEN_TYPE, route: 'records'}), config, null), null, 'no frame');
  assert.equal(openRequest(undefined, config, frameWindow), null);
});

test('only overview, records, recovery, cases and one case by a plain id may be opened, on the configured origin only', () => {
  for (const route of ['overview', 'records', 'recovery', 'cases', 'cases/inbox-1', 'cases/A.b_c-9', 'cases/' + 'a'.repeat(64)])
    assert.equal(allowedRoute(route), true, route);
  for (const route of ['', 'activity', 'agreements', 'ramp', 'ramp/bill-1', 'ramp-bill', 'ramp-bill/x', 'cases/', 'cases/-x', 'cases/.x',
    'cases/a/b', 'cases/a%2Fb', 'cases/a?b', 'cases/a#b', 'cases/' + 'a'.repeat(65), 'records ', ' records', 'RECORDS', 'records/x',
    'overview\n', '//evil.example', 'https://evil.example/#records', 'javascript:alert(1)', null, undefined, 7, ['records'], {}])
    assert.equal(allowedRoute(route), false, String(route));
  assert.equal(appUrl('records', config), 'http://127.0.0.1:8776/#records');
  assert.equal(appUrl('cases/inbox-1', config), 'http://127.0.0.1:8776/#cases/inbox-1');
  assert.equal(appUrl('activity', config), null);
  // The app asks with the same pattern and the same message shape, and asks for nothing else.
  assert.equal(String(app.PANEL_OPEN_ROUTE), String(/^(?:overview|records|recovery|cases|cases\/[A-Za-z0-9][A-Za-z0-9._-]{0,63})$/));
  assert.equal(app.PANEL_MESSAGE_TYPE, OPEN_TYPE);
  assert.deepEqual(app.panelMessage('records'), {type: OPEN_TYPE, route: 'records'});
  assert.equal(openRequest(message(app.panelMessage('cases/inbox-1')), config, frameWindow), 'cases/inbox-1');
  for (const route of ['activity', 'ramp/x', 'https://evil.example/']) assert.equal(app.panelMessage(route), null, route);
});

function fakeTabs(closed = []) {
  const calls = [];
  let next = 40;
  return {calls,
    tabs: {query: async filter => { calls.push(['query', filter]); return []; },
      update: async (id, change) => { calls.push(['update', id, change]); if (closed.includes(id)) throw new Error('No tab with id'); return {id, windowId: 6}; },
      create: async props => { calls.push(['create', props]); return {id: next++, windowId: 6}; }},
    windows: {update: async (id, change) => { calls.push(['focus', id, change]); }}};
}

test('the first press opens one tab; later presses focus that same tab and set the route; a closed tab is replaced', async () => {
  const remembered = {tabId: null};
  const f = fakeTabs([40]);
  await openApp('records', config, f.tabs, f.windows, remembered);
  assert.deepEqual(f.calls, [['create', {url: ORIGIN + '/#records', active: true}]]);
  assert.equal(remembered.tabId, 40);
  const g = fakeTabs();
  await openApp('overview', config, g.tabs, g.windows, remembered);
  assert.deepEqual(g.calls, [['update', 40, {url: ORIGIN + '/#overview', active: true}], ['focus', 6, {focused: true}]]);
  // The person closed that tab: a new one opens and is remembered instead.
  await openApp('cases', config, f.tabs, f.windows, remembered);
  assert.deepEqual(f.calls.slice(1), [['update', 40, {url: ORIGIN + '/#cases', active: true}], ['create', {url: ORIGIN + '/#cases', active: true}]]);
  assert.equal(remembered.tabId, 41);
  // No tab is ever searched for, and a route off the list does nothing at all.
  assert.equal([...f.calls, ...g.calls].some(([kind]) => kind === 'query'), false);
  const refused = fakeTabs();
  assert.equal(await openApp('ramp/bill-1', config, refused.tabs, refused.windows, remembered), null);
  assert.deepEqual(refused.calls, []);
});

test('the shell listens for messages only through its one handler and never sends one', () => {
  const source = fs.readFileSync(path.join(DIR, 'panel.js'), 'utf8');
  assert.equal(source.match(/addEventListener\('message'/g).length, 1);
  assert.match(source, /openRequest\(event, config, frame\.contentWindow\)/);
});

// ---- Demo line: the toolbar badge ----
test('the shell accepts the bill-status message only in its one shape, from its own frame on the configured origin', () => {
  assert.equal(STATUS_TYPE, 'uptime-bill-status');
  const ok = {type: STATUS_TYPE, bill: BILL, state: 'match'};
  assert.deepEqual(statusRequest(message(ok), config, frameWindow), {bill: BILL, state: 'match'});
  assert.deepEqual(statusRequest(message({...ok, state: 'none'}), config, frameWindow), {bill: BILL, state: 'none'});
  for (const [why, event] of [
    ['another origin', message(ok, {origin: 'https://demo.ramp.com'})],
    ['another window', message(ok, {source: {}})],
    ['an extra key', message({...ok, text: '9'})],
    ['a missing state', message({type: STATUS_TYPE, bill: BILL})],
    ['another state', message({...ok, state: 'credit'})],
    ['an upper-case bill', message({...ok, bill: BILL.toUpperCase()})],
    ['a malformed bill', message({...ok, bill: 'f74ba12c'})],
    ['the open message', message({type: OPEN_TYPE, route: 'records'})],
    ['an array', message([STATUS_TYPE, BILL, 'match'])],
  ]) assert.equal(statusRequest(event, config, frameWindow), null, why);
  // The two shapes never overlap.
  assert.equal(openRequest(message(ok), config, frameWindow), null);
});

test('the badge is set for one tab on a match and cleared otherwise, and needs no permission', async () => {
  const calls = [];
  const action = {setBadgeText: async v => calls.push(['text', v]), setBadgeBackgroundColor: async v => calls.push(['color', v])};
  await setBadge(action, 7, true);
  await setBadge(action, 7, false);
  await setBadge(action, null, true);
  await setBadge(undefined, 7, true);
  assert.deepEqual(calls, [['color', {tabId: 7, color: '#4353e0'}], ['text', {tabId: 7, text: '$'}], ['text', {tabId: 7, text: ''}]]);
  assert.deepEqual(manifest.permissions, ['sidePanel']);
  assert.ok(manifest.action, 'chrome.action needs the manifest action key, which is present');
  const source = fs.readFileSync(path.join(DIR, 'panel.js'), 'utf8');
  assert.match(source, /status\.bill === current\) setBadge\(action, currentTab/);
});

// ---- Demo line, round three: where the active tab is, the tracking list and the app tab ----
const {placeFor, placeRoute, placeLabel, openBillRequest, billUrl, BILL_TYPE} = require(path.join(DIR, 'panel.js'));

test('the active tab decides the panel: one bill, the tracking list on any other Ramp page, nothing elsewhere, and Uptime itself', () => {
  const at = (url, id = 3, appTabId = null) => placeFor(url, id, config, appTabId);
  assert.deepEqual(at(`https://demo.ramp.com/bill-pay/bills/list/${BILL}`), {kind: 'bill', bill: BILL});
  for (const url of ['https://demo.ramp.com/bill-pay/bills/list', 'https://demo.ramp.com/home', 'https://demo.ramp.com/'])
    assert.deepEqual(at(url), {kind: 'list'}, url);
  for (const url of ['https://evil.example/bill-pay/bills/list', 'http://demo.ramp.com/home', 'https://demo.ramp.com.evil.example/', undefined, null, 'nope'])
    assert.deepEqual(at(url), {kind: 'none'}, String(url));
  assert.deepEqual(at(ORIGIN + '/#overview'), {kind: 'app'});
  assert.deepEqual(at(ORIGIN + '/'), {kind: 'app'});
  assert.deepEqual(at(undefined, 9, 9), {kind: 'app'}, 'the tab the panel opened, even without its address');
  assert.deepEqual(at('http://127.0.0.1:8777/', 3, 9), {kind: 'none'});
  assert.equal(placeRoute({kind: 'bill', bill: BILL}, config), 'ramp-bill/' + BILL);
  assert.equal(placeRoute({kind: 'list'}, config), 'ramp-bills');
  assert.equal(placeRoute({kind: 'none'}, config), 'ramp-bill');
  assert.deepEqual([placeLabel({kind: 'app'}), placeLabel({kind: 'list'}), placeLabel({kind: 'none'}), placeLabel({kind: 'bill', bill: BILL})],
    ['Uptime', 'Ramp, no single bill open', 'No Ramp bill open', 'Ramp bill f74ba12c…']);
});

test('the panel page has a quiet You\'re in Uptime state, hidden until the active tab is Uptime', () => {
  const html = fs.readFileSync(path.join(DIR, 'panel.html'), 'utf8');
  assert.match(html, /<section id="in-uptime" hidden>\s*<p class="mark">Uptime<\/p>\s*<h1>You're in Uptime<\/h1>\s*<p>You may close this panel\.<\/p>/);
  const source = fs.readFileSync(path.join(DIR, 'panel.js'), 'utf8');
  // That state hides the frame without changing its address, and clears the tab's badge first.
  const appBranch = source.slice(source.indexOf("if (place.kind === 'app')"), source.indexOf('inUptime.hidden = true'));
  assert.match(appBranch, /frame\.hidden = true; inUptime\.hidden = false;\s*return;/);
  assert.doesNotMatch(appBranch, /location|src/);
});

test('the open-bill message moves only to Ramp\'s own bill address, from the framed app in its one shape', () => {
  assert.equal(BILL_TYPE, 'uptime-open-bill');
  assert.equal(openBillRequest(message({type: BILL_TYPE, bill: BILL}), config, frameWindow), BILL);
  for (const [why, event] of [
    ['another origin', message({type: BILL_TYPE, bill: BILL}, {origin: 'https://demo.ramp.com'})],
    ['another window', message({type: BILL_TYPE, bill: BILL}, {source: {}})],
    ['an extra key', message({type: BILL_TYPE, bill: BILL, url: 'https://evil.example/'})],
    ['an upper-case bill', message({type: BILL_TYPE, bill: BILL.toUpperCase()})],
    ['a path', message({type: BILL_TYPE, bill: '../../x'})],
    ['the status message', message({type: STATUS_TYPE, bill: BILL, state: 'match'})],
  ]) assert.equal(openBillRequest(event, config, frameWindow), null, why);
  assert.equal(openRequest(message({type: BILL_TYPE, bill: BILL}), config, frameWindow), null);
  assert.equal(statusRequest(message({type: BILL_TYPE, bill: BILL}), config, frameWindow), null);
  assert.equal(billUrl(BILL, config), 'https://demo.ramp.com/bill-pay/bills/list/' + BILL);
  const source = fs.readFileSync(path.join(DIR, 'panel.js'), 'utf8');
  assert.match(source, /if \(bill && active === 'list' && Number\.isInteger\(currentTab\)\) chrome\.tabs\.update\(currentTab, \{url: billUrl\(bill, config\)\}\)/);
});
