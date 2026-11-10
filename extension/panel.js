/* Uptime side panel.

   The panel is a thin shell. It frames the real Uptime page and moves it to Uptime's page for the
   Ramp bill in the active tab.
   It reads only the address of the active tab, and Chrome shows it that address only for the Ramp
   hosts named in the manifest. It does not read or change Ramp's page, holds no credential, stores
   nothing, and makes no request of its own. Sign-in happens inside the framed Uptime page, from
   Uptime's own origin, exactly as it does in an ordinary tab.

   One message is accepted from the framed page: {type: 'uptime-open-app', route}, and only from the
   framed window on the configured app origin. It opens the full app at config.origin + '/#' + route
   in a browser tab, for a route on a fixed list; the tab this panel opened is reused while it is open.
   A second message, {type: 'uptime-bill-status', bill, state}, with the same sender checks, sets or
   clears a small badge on the toolbar button for the tab whose bill the panel shows. */
(function () {
  'use strict';
  const BILL = /\/bills\/(?:list\/)?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:\/|$)/i;

  // The bill ID in a Ramp bill address, or null for any other site, scheme or shape.
  function billFromUrl(value, hosts) {
    let url;
    try { url = new URL(value); } catch { return null; }
    if (url.protocol !== 'https:' || !Array.isArray(hosts) || !hosts.includes(url.hostname)) return null;
    const match = BILL.exec(url.pathname);
    return match ? match[1].toLowerCase() : null;
  }
  function routeFor(bill, config) {
    return bill ? config.billRoute.replace('{bill}', encodeURIComponent(bill)) : config.homeRoute;
  }
  function frameUrl(bill, config) { return config.origin + '/#' + routeFor(bill, config); }
  function labelFor(bill) { return bill ? 'Ramp bill ' + bill.slice(0, 8) + '…' : 'No Ramp bill open'; }
  // The routes the framed page may ask to open in a full tab. The app checks the same pattern before asking.
  const OPEN_ROUTE = /^(?:overview|records|cases|cases\/[A-Za-z0-9][A-Za-z0-9._-]{0,63})$/;
  const OPEN_TYPE = 'uptime-open-app';
  const allowedRoute = route => typeof route === 'string' && OPEN_ROUTE.test(route);
  // The route a message asks for, or null. It must come from the framed window, on the configured origin, and be
  // exactly {type, route}: a plain object with those two keys and no others.
  function openRequest(event, config, frameWindow) {
    if (!event || !config || event.origin !== config.origin || !frameWindow || event.source !== frameWindow) return null;
    const data = event.data;
    if (!data || typeof data !== 'object' || Array.isArray(data) || Object.getPrototypeOf(data) !== Object.prototype) return null;
    const keys = Object.keys(data).sort();
    if (keys.length !== 2 || keys[0] !== 'route' || keys[1] !== 'type' || data.type !== OPEN_TYPE) return null;
    return allowedRoute(data.route) ? data.route : null;
  }
  // The second message: whether the bill the panel shows is matched to an Uptime invoice. Same sender checks;
  // exactly {type, bill, state} with a Ramp bill id and state 'match' or 'none'.
  const STATUS_TYPE = 'uptime-bill-status';
  const BILL_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
  function statusRequest(event, config, frameWindow) {
    if (!event || !config || event.origin !== config.origin || !frameWindow || event.source !== frameWindow) return null;
    const data = event.data;
    if (!data || typeof data !== 'object' || Array.isArray(data) || Object.getPrototypeOf(data) !== Object.prototype) return null;
    const keys = Object.keys(data).sort();
    if (keys.length !== 3 || keys[0] !== 'bill' || keys[1] !== 'state' || keys[2] !== 'type' || data.type !== STATUS_TYPE) return null;
    if (typeof data.bill !== 'string' || !BILL_ID.test(data.bill) || (data.state !== 'match' && data.state !== 'none')) return null;
    return {bill: data.bill, state: data.state};
  }
  // A small badge on the toolbar button, for that one tab, while its bill is matched; cleared otherwise.
  async function setBadge(action, tabId, matched) {
    if (!action || !Number.isInteger(tabId)) return;
    if (matched) await action.setBadgeBackgroundColor({tabId, color: '#4353e0'});
    await action.setBadgeText({tabId, text: matched ? '$' : ''});
  }
  function appUrl(route, config) { return allowedRoute(route) ? config.origin + '/#' + route : null; }
  // Opens the full app in a browser tab. The tab this panel opened earlier is reused while it is still open, so a
  // second press focuses it and sets the route there instead of opening another. The extension has no permission
  // to read other tabs' addresses, so a tab opened some other way is not looked for; see README.md.
  async function openApp(route, config, tabs, windows, remembered) {
    const url = appUrl(route, config);
    if (!url) return null;
    if (remembered && Number.isInteger(remembered.tabId)) {
      try {
        const tab = await tabs.update(remembered.tabId, {url, active: true});
        if (tab && windows && Number.isInteger(tab.windowId)) await windows.update(tab.windowId, {focused: true});
        return tab;
      } catch { remembered.tabId = null; }
    }
    const tab = await tabs.create({url, active: true});
    if (remembered && tab && Number.isInteger(tab.id)) remembered.tabId = tab.id;
    return tab;
  }
  // Wraps an asynchronous lookup so that only the answer to the most recent call is delivered. Tab
  // events can arrive faster than their lookups finish; an older answer must not overwrite a newer one.
  function latestOnly(lookup, deliver) {
    let asked = 0;
    return async () => { const mine = ++asked; const value = await lookup(); if (mine === asked) deliver(value); };
  }

  if (typeof module !== 'undefined' && module.exports) module.exports = {billFromUrl, routeFor, frameUrl, labelFor, latestOnly,
    openRequest, appUrl, openApp, allowedRoute, OPEN_TYPE, statusRequest, setBadge, STATUS_TYPE};
  if (typeof document === 'undefined') return;

  const config = globalThis.UPTIME_PANEL_CONFIG;
  const frame = document.getElementById('uptime');
  const label = document.getElementById('bill');
  let loaded = false;
  let current, currentTab = null;
  const action = globalThis.chrome && chrome.action;

  function follow(tabUrl, tabId = null) {
    const bill = typeof tabUrl === 'string' ? billFromUrl(tabUrl, config.rampHosts) : null;
    if (loaded && bill === current && tabId === currentTab) return;
    // The tab's badge is cleared when the panel moves; the framed page sets it again for a matched bill.
    if (Number.isInteger(tabId) && (bill !== current || tabId !== currentTab)) setBadge(action, tabId, false).catch(() => {});
    currentTab = tabId;
    if (loaded && bill === current) return;
    current = bill;
    label.textContent = labelFor(bill);
    const url = frameUrl(bill, config);
    if (!loaded) { frame.src = url; loaded = true; return; }
    // Only the fragment changes, so the framed page is kept and its in-memory signing key survives.
    frame.contentWindow.location.replace(url);
  }

  if (globalThis.chrome && chrome.tabs) {
    const appTab = {tabId: null};
    globalThis.addEventListener('message', event => {
      const route = openRequest(event, config, frame.contentWindow);
      if (route) { openApp(route, config, chrome.tabs, chrome.windows, appTab).catch(() => {}); return; }
      const status = statusRequest(event, config, frame.contentWindow);
      // Only for the bill the panel is showing, on the tab it is showing it for.
      if (status && status.bill === current) setBadge(action, currentTab, status.state === 'match').catch(() => {});
    });
    const refresh = latestOnly(async () => {
      const [tab] = await chrome.tabs.query({active: true, lastFocusedWindow: true});
      // A tab on any other site has no address visible to this extension; that reads as "no bill".
      return tab ? {url: tab.url, id: tab.id} : null;
    }, tab => follow(tab ? tab.url : null, tab ? tab.id : null));
    chrome.tabs.onActivated.addListener(refresh);
    chrome.tabs.onUpdated.addListener((id, change, tab) => {
      if (tab.active && (change.url !== undefined || change.status === 'loading')) refresh();
    });
    refresh();
  } else {
    follow(null);
  }
})();
