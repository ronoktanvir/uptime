/* Uptime side panel.

   The panel is a thin shell. It frames the real Uptime page and tells it which Ramp bill is open.
   It reads only the address of the active tab, and Chrome shows it that address only for the Ramp
   hosts named in the manifest. It does not read or change Ramp's page, holds no credential, stores
   nothing, and makes no request of its own. Sign-in happens inside the framed Uptime page, from
   Uptime's own origin, exactly as it does in an ordinary tab. */
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

  if (typeof module !== 'undefined' && module.exports) module.exports = {billFromUrl, routeFor, frameUrl, labelFor};
  if (typeof document === 'undefined') return;

  const config = globalThis.UPTIME_PANEL_CONFIG;
  const frame = document.getElementById('uptime');
  const label = document.getElementById('bill');
  let loaded = false;
  let current;

  function follow(tabUrl) {
    const bill = typeof tabUrl === 'string' ? billFromUrl(tabUrl, config.rampHosts) : null;
    if (loaded && bill === current) return;
    current = bill;
    label.textContent = labelFor(bill);
    const url = frameUrl(bill, config);
    if (!loaded) { frame.src = url; loaded = true; return; }
    // Only the fragment changes, so the framed page is kept and its in-memory signing key survives.
    frame.contentWindow.location.replace(url);
  }

  if (globalThis.chrome && chrome.tabs) {
    const refresh = async () => {
      const [tab] = await chrome.tabs.query({active: true, lastFocusedWindow: true});
      // A tab on any other site has no address visible to this extension; that reads as "no bill".
      follow(tab ? tab.url : null);
    };
    chrome.tabs.onActivated.addListener(refresh);
    chrome.tabs.onUpdated.addListener((id, change, tab) => {
      if (tab.active && (change.url !== undefined || change.status === 'loading')) refresh();
    });
    refresh();
  } else {
    follow(null);
  }
})();
