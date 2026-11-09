// Runs the real web/auth.js sign-in form up to its first request and prints that request as JSON,
// plus the file types the credential picker accepts.
// Usage: node tests/helpers/browser_sign_in_challenge.cjs <account name>
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function element(tag) {
  return {tagName: tag, children: [], listeners: {}, value: '', files: [], disabled: false,
    append(...nodes) { this.children.push(...nodes); }, setAttribute() {},
    addEventListener(kind, fn) { this.listeners[kind] = fn; }};
}

(async () => {
  const subject = process.argv[2];
  const pair = await crypto.subtle.generateKey({name: 'ECDSA', namedCurve: 'P-256'}, true, ['sign', 'verify']);
  const jwk = JSON.stringify(await crypto.subtle.exportKey('jwk', pair.privateKey));
  const inputs = [];
  let captured = null;
  const context = {
    window: {}, crypto, TextEncoder, URL,
    location: {origin: 'http://127.0.0.1:8777'},
    sessionStorage: {getItem: () => null, setItem() {}, removeItem() {}},
    document: {createElement(tag) { const node = element(tag); if (tag === 'input') inputs.push(node); return node; }},
    fetch: async (url, options) => { captured = {url, method: options.method, headers: options.headers, body: options.body};
      throw new Error('stop after the first request'); },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', '..', 'web', 'auth.js'), 'utf8'), context);
  const form = context.window.uptimeAuth.signInForm(() => {});
  const [account, credential] = inputs;
  account.value = subject;
  credential.files = [{size: jwk.length, text: async () => jwk}];
  await form.listeners.submit({preventDefault() {}});
  if (!captured) throw new Error('The sign-in form sent no request');
  process.stdout.write(JSON.stringify({...captured, credential_accept: credential.accept}));
})().catch(error => { console.error(error); process.exit(1); });
