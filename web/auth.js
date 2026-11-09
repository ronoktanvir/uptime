/* The read token is scoped to this origin and tab. Only the page that proved a named
   account can sign a fresh write challenge. No credential is sent as a cookie or URL. */
(function () {
  'use strict';
  const storageKey = 'uptime-v4-session';
  const encoder = new TextEncoder();
  let signingKey = null;
  const hex = bytes => Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, '0')).join('');
  function session() {
    try { return JSON.parse(sessionStorage.getItem(storageKey)) || null; } catch { return null; }
  }
  async function send(path, payload, token, proof = {}) {
    if (new URL(path, location.origin).origin !== location.origin || !path.startsWith('/api/'))
      throw new Error('Local API route required');
    const headers = {Accept:'application/json', ...proof};
    if (token) headers.Authorization = 'Bearer ' + token;
    const options = {method:'GET', credentials:'omit', cache:'no-store', redirect:'error', headers};
    if (payload !== undefined) {
      options.method = 'POST';
      options.body = JSON.stringify(payload);
      headers['Content-Type'] = 'application/json';
      headers['X-Uptime-Action'] = '1';
    }
    const response = await fetch(path, options);
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(typeof data.detail === 'string' ? data.detail : 'Request rejected. Review the latest workspace state.');
      error.status = response.status;
      throw error;
    }
    return data;
  }
  async function sign(key, challenge) {
    if (challenge.algorithm !== 'ES256') throw new Error('Unsupported reviewer proof');
    return hex(await crypto.subtle.sign({name:'ECDSA', hash:'SHA-256'}, key, encoder.encode(challenge.message)));
  }
  async function login(subject, file) {
    if (!file || file.size > 16384) throw new Error('Choose your enrolled reviewer credential file.');
    const credential = JSON.parse(await file.text());
    const key = await crypto.subtle.importKey('jwk', credential, {name:'ECDSA', namedCurve:'P-256'}, false, ['sign']);
    // Name the login path and empty body hash explicitly; the local review guard rejects omitted fields.
    const challenge = await send('/api/auth/challenge', {subject, path:'/api/auth/login', body_sha256:''});
    const data = await send('/api/auth/login', {challenge:challenge.challenge, proof:await sign(key, challenge)});
    signingKey = key;
    sessionStorage.setItem(storageKey, JSON.stringify(data));
  }
  async function api(path, payload) {
    const current = session();
    if (!current || !current.token) {
      const error = new Error('Sign in to this local workspace.'); error.status = 401; throw error;
    }
    const headers = {};
    // Read-only guide questions use the read session; they cannot change workspace state.
    if (payload !== undefined && path !== '/api/guide' && path !== '/api/workspace/guide') {
      if (!signingKey) {
        const e = new Error('Sign in again to authorize changes from this page.'); e.status = 401; throw e;
      }
      const bodyHash = hex(await crypto.subtle.digest('SHA-256', encoder.encode(JSON.stringify(payload))));
      const challenge = await send('/api/auth/challenge', {subject:current.subject, path, body_sha256:bodyHash}, current.token);
      headers['X-Uptime-Challenge'] = challenge.challenge;
      headers['X-Uptime-Proof'] = await sign(signingKey, challenge);
    }
    return send(path, payload, current.token, headers);
  }
  function signInForm(onSuccess) {
    const form = document.createElement('form');
    form.className = 'panel';
    const heading = document.createElement('h1'); heading.textContent = 'Sign in to Uptime';
    const note = document.createElement('p');
    note.textContent = 'Use your named account for this local workspace. Workspace setup prints the account name and where its credential file was saved. Choose that file, or drag it onto this form. It is used only in this page to prove your identity and is never uploaded.';
    const feedback = document.createElement('p'); feedback.setAttribute('role','status');
    function field(title, type, auto) {
      const label = document.createElement('label'); label.textContent = title;
      const input = document.createElement('input'); input.type = type; input.required = true; input.autocomplete = auto;
      label.append(input); form.append(label); return input;
    }
    form.append(heading, note);
    const subject = field('Account name', 'text', 'username'), credential = field('Credential file', 'file', 'off');
    credential.accept = '.json,.jwk,application/json,application/jwk+json';
    // A dropped file is held only in this form until sign-in; the account name of an expired session is prefilled.
    credential.required = false;
    let dropped = null;
    const previous = session();
    if (previous && typeof previous.subject === 'string') subject.value = previous.subject;
    form.addEventListener('dragover', event => { event.preventDefault(); });
    form.addEventListener('drop', event => {
      event.preventDefault();
      const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
      if (file) { dropped = file; feedback.textContent = 'Credential file selected: ' + file.name; }
    });
    credential.addEventListener('change', () => { dropped = null; });
    const submit = document.createElement('button'); submit.type = 'submit'; submit.textContent = 'Sign in';
    form.append(submit, feedback);
    form.addEventListener('submit', async event => {
      event.preventDefault(); submit.disabled = true;
      try {
        const file = (credential.files && credential.files[0]) || dropped;
        if (!file) throw new Error('Choose the credential file named in the setup output, or drag it here.');
        await login(subject.value, file); credential.value=''; dropped = null; onSuccess();
      }
      catch (error) { credential.value=''; dropped = null; feedback.textContent = error.message; }
      finally { submit.disabled = false; }
    });
    return form;
  }
  async function signOut() {
    const current = session();
    try { if (current) await send('/api/auth/logout', {}, current.token); }
    finally { signingKey = null; sessionStorage.removeItem(storageKey); location.reload(); }
  }
  window.uptimeAPI = api;
  // True only while this page holds the in-memory signing key; a reload keeps the read session but not the key.
  function canSign() { return signingKey !== null; }
  window.uptimeAuth = {session, signInForm, signOut, canSign};
})();
