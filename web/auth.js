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
  async function loginDemo(subject, password) {
    // Demo workspaces only: exchange a name and any password for the same rehearsal key the credential file holds,
    // then prove it with a fresh challenge exactly as the file flow does. The server verifies every signature.
    const data = await send('/api/auth/demo-credential', {subject, password});
    const key = await crypto.subtle.importKey('jwk', data.credential, {name:'ECDSA', namedCurve:'P-256'}, false, ['sign']);
    const challenge = await send('/api/auth/challenge', {subject, path:'/api/auth/login', body_sha256:''});
    const result = await send('/api/auth/login', {challenge:challenge.challenge, proof:await sign(key, challenge)});
    signingKey = key;
    sessionStorage.setItem(storageKey, JSON.stringify(result));
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
    const make = (tag, className, text) => { const node = document.createElement(tag); if (className) node.className = className; if (text != null) node.textContent = text; return node; };
    const form = make('form', 'panel signin');
    // The product's own mark, served from this origin; the sign-in card is the whole page until an account is proven.
    const mark = make('img'); mark.src = '/static/favicon.svg'; mark.alt = ''; mark.width = 32; mark.height = 32;
    const brand = make('p', 'signin-brand'); brand.append(mark, make('span', 'signin-name', 'Uptime'), make('span', 'signin-for', 'for Ramp'));
    const heading = make('h1', null, 'Sign in to Uptime');
    const note = make('p', null, 'Use your named account for this local workspace. Workspace setup prints the account name and where its credential file was saved.');
    const hint = make('p', 'signin-hint', 'Choose that file, or drag it onto this form. It is used only in this page to prove your identity and is never uploaded.');
    const feedback = make('p'); feedback.setAttribute('role','status');
    const subjectLabel = make('label', null, 'Account name');
    const subject = document.createElement('input'); subject.type = 'text'; subject.required = true; subject.autocomplete = 'username';
    subjectLabel.append(subject);
    // The second field is the enrolled credential file; a demo workspace replaces it with a password.
    const secondLabel = make('label', null, 'Credential file');
    const credential = document.createElement('input'); credential.type = 'file'; credential.autocomplete = 'off';
    credential.accept = '.json,.jwk,application/json,application/jwk+json';
    secondLabel.append(credential);
    const submit = make('button'); submit.type = 'submit'; submit.textContent = 'Sign in';
    form.append(brand, heading, note, subjectLabel, secondLabel, hint, submit, feedback);
    // A dropped file is held only in this form until sign-in; the account name of an expired session is prefilled.
    let mode = 'file', password = null, dropped = null;
    const previous = session();
    if (previous && typeof previous.subject === 'string') subject.value = previous.subject;
    const dragging = on => { if (form.classList) form.classList.toggle('dragging', on); };
    form.addEventListener('dragover', event => { event.preventDefault(); dragging(true); });
    form.addEventListener('dragleave', () => dragging(false));
    form.addEventListener('drop', event => {
      event.preventDefault(); dragging(false);
      if (mode !== 'file') return;
      const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
      if (file) { dropped = file; feedback.textContent = 'Credential file selected: ' + file.name; }
    });
    credential.addEventListener('change', () => { dropped = null; });
    // A demo workspace offers a plain name + password sign-in, no file. Only a real browser asks the server;
    // the node sign-in harness (no document body) and the request-stubbed views never reach this.
    if (typeof document !== 'undefined' && document.body) {
      send('/api/auth/context').then(context => {
        if (!context || !context.demo_login || mode !== 'file') return;
        mode = 'demo';
        secondLabel.textContent = 'Password';
        password = document.createElement('input'); password.type = 'password'; password.required = true; password.autocomplete = 'off';
        secondLabel.append(password);
        note.textContent = 'Sign in to this demo workspace with your reviewer name and any password.';
        hint.textContent = 'Any password works here. Your name records which reviewer is deciding; no credential file is needed.';
        if (typeof context.subject === 'string' && context.subject && !subject.value) subject.value = context.subject;
      }).catch(() => {});
    }
    form.addEventListener('submit', async event => {
      event.preventDefault(); submit.disabled = true;
      try {
        if (mode === 'demo') await loginDemo(subject.value, password ? password.value : '');
        else {
          const file = (credential.files && credential.files[0]) || dropped;
          if (!file) throw new Error('Choose the credential file named in the setup output, or drag it here.');
          await login(subject.value, file); credential.value = ''; dropped = null;
        }
        onSuccess();
      }
      catch (error) { if (mode !== 'demo') { credential.value = ''; dropped = null; } feedback.textContent = error.message; }
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
