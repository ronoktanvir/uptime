/* Where your local Uptime workspace is served, and which pages the panel opens in it.

   origin     the address the workspace printed when it started; change the port to match yours.
   homeRoute  shown when no Ramp bill is open in the active tab.
   billRoute  shown for a Ramp bill; {bill} is Ramp's own bill ID, taken from the tab's address.
   rampHosts  the Ramp sites whose bill addresses are followed; keep in step with host_permissions
              in manifest.json. */
globalThis.UPTIME_PANEL_CONFIG = {
  origin: 'http://127.0.0.1:8776',
  homeRoute: 'records',
  billRoute: 'ramp-bill/{bill}',
  rampHosts: ['demo.ramp.com'],
};
if (typeof module !== 'undefined' && module.exports) module.exports = globalThis.UPTIME_PANEL_CONFIG;
