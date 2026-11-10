/* Where your local Uptime workspace is served, and which pages the panel opens in it.

   origin     the address the workspace printed when it started; change the port to match yours.
   homeRoute  shown when no Ramp bill is open in the active tab: the app's "No Ramp bill open" page.
   billRoute  shown for a Ramp bill; {bill} is Ramp's own bill ID, taken from the tab's address.
   listRoute  shown for any other Ramp page: the bills Uptime is tracking.
   rampHosts  the Ramp sites whose bill addresses are followed; keep in step with host_permissions
              in manifest.json.
   If you change origin, change its entry in host_permissions in manifest.json to match: the panel
   uses it only to recognise a tab on the Uptime app itself. */
globalThis.UPTIME_PANEL_CONFIG = {
  origin: 'http://127.0.0.1:8776',
  homeRoute: 'ramp-bill',
  billRoute: 'ramp-bill/{bill}',
  listRoute: 'ramp-bills',
  rampHosts: ['demo.ramp.com'],
};
if (typeof module !== 'undefined' && module.exports) module.exports = globalThis.UPTIME_PANEL_CONFIG;
