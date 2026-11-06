/* Uptime V4 extension. No fetch, identity assignment, enrollment, or service credential handling.
 * Integration (lead owns app.js/index.html/server static routes):
 * 1. Serve /v4_ui.js and /v4_style.css locally; load stylesheet after style.css and script
 *    before app.js with defer. No inline handlers/styles, CDN, or CSP relaxation required.
 * 2. const v4 = window.UptimeV4.create({
 *      api: (path, body) => signedApi(path, body), // absent body = GET; body = POST
 *      getAccess: () => ({identity, enrollment, gate, canWrite}),
 *      onCase: id => openCase(id)
 *    });
 *    getAccess is a projection of SERVER auth-helper state, never user input. canWrite
 *    must be true only after enrollment and security gate pass. Default is read-only.
 *    The injected client MUST enforce reviewer signing and same-origin checks itself.
 * 3. In existing navigation loader: await v4.render(content, 'vendors'|'disputes');
 *    Existing onboarding/replay can remain a separate route. For dashboard:
 *    v4.render(comparisonSlot, 'portfolio', {portfolio: serverPortfolio, seeded: serverSeeded});
 *    Each cohort supplies {label, sources, metrics, cases}; never infer cohorts by title.
 * 4. In openCase: v4.render(caseSlot, 'case', serverCase). To inspect correspondence:
 *    await v4.inspect(caseSlot, claimId). Call v4.unmount(content) before V3 takes over
 *    that root, and rerender after auth state changes. Multiple roots are supported.
 * 5. api responses: /api/vendors -> array or {vendors:[]}; /api/correspondence/claims
 *    -> array or {claims:[]}. Catalog summaries are expanded with GET /api/vendors/{id}.
 *    Detail objects render exact provenance and structured
 *    records. Vendor objects expose vendor_id (or id), revision and actions:[{id,label}].
 *    Only returned action IDs are offered. Test POST carries revision, tests; action
 *    POST carries {}. evaluate POST carries facts. Claim creation carries claim_id,scope.
 *    Inbound /events is deliberately NOT called: provisioned services ingest through
 *    CLI. UI refreshes authenticated claim detail to show event/receipt evidence.
 * 6. Public proposal generation uses POST /api/vendors/{id}/proposal-access (permission
 *    check, no model call), POST .../proposal-jobs (explicit reservation), GET
 *    .../proposal-jobs/{job} (read-only status) and POST .../proposal-jobs/{job}/candidate
 *    ({overlay} only). Source text is posted exactly as entered. Optional
 *    options.schedule(callback, ms) replaces setTimeout for read-only status polling.
 * Consequential tradeoff for lead review: write UI requires explicit canWrite=true
 * AND server-returned actions; this is defense in depth, not authorization. Forms use
 * typed JSON for facts/tests/private overlay to preserve exact B/C schema and money;
 * blank fields and unsupported/missing source states never acquire sample defaults.
 */
(function (global) {
  'use strict';
  const list = value => Array.isArray(value) ? value : [];
  const shown = value => value === null || value === undefined || value === '' ? 'Not provided' : String(value);
  const label = key => key.replaceAll('_', ' ');
  const hidden = /secret|token|password|authorization|cookie|credential|private_key|service_key|signature/i;
  function parseJSON(text, kind) {
    let value;
    try { value = JSON.parse(text); } catch (_) { throw new Error('Enter valid JSON for ' + kind + '.'); }
    if (kind === 'tests' ? !Array.isArray(value) || !value.length : !value || typeof value !== 'object' || Array.isArray(value)) {
      throw new Error(kind === 'tests' ? 'Tests must be a non-empty JSON array.' : kind + ' must be a JSON object.');
    }
    return value;
  }
  function create(options = {}) {
    const doc = options.document || global.document;
    const mounts = new Map();
    let busy = false;
    // A mutation with a lost response may have committed. Reconcile before retrying.
    let uncertain = false;
    const access = () => typeof options.getAccess === 'function' ? options.getAccess() || {} : {};
    const writable = (draft = false) => (access().canWrite === true || draft && access().canDraft === true) && !busy && !uncertain;
    const el = (tag, text, cls) => { const n = doc.createElement(tag); if (text !== undefined) n.textContent = shown(text); if (cls) n.className = cls; return n; };
    const add = (node, ...children) => { children.filter(Boolean).forEach(child => node.append(child)); return node; };
    const section = title => add(el('section', undefined, 'v4-panel'), el('h2', title));
    const note = text => el('p', text, 'v4-note');
    const button = (text, handler) => { const n = el('button', text); n.type = 'button'; n.addEventListener('click', handler); return n; };
    function provenance(sources) {
      const refs = list(sources).filter(s => s && typeof s === 'object' && (s.ref || s.title || s.uri));
      const n = el('div', undefined, 'v4-sources');
      refs.forEach(s => n.append(el('span', s.ref || s.title || s.uri, 'v4-source')));
      if (!list(sources).length) n.append(note('Source references not provided.'));
      return n;
    }
    function record(value, depth = 0) {
      if (value === null || typeof value !== 'object') return el('span', shown(value));
      if (depth > 12) return note('Nested record omitted; inspect the server record.');
      if (Array.isArray(value)) {
        if (!value.length) return note('No records returned.');
        return add(el('div', undefined, 'v4-records'), ...value.map(v => record(v, depth + 1)));
      }
      const n = el('dl', undefined, 'v4-record');
      Object.entries(value).forEach(([key, val]) => {
        if (hidden.test(key) || ['source_mode','data_provenance','classification'].includes(key) || key === 'mode' && /replay|simulat|demo/i.test(String(val))) return; // Do not display accidentally included authentication fields.
        add(n, el('dt', label(key)), add(el('dd'), key === 'sources' ? provenance(val) : record(val, depth + 1)));
      });
      return n;
    }
    function details(title, value) { return add(el('details', undefined, 'v4-detail'), el('summary', title), record(value)); }
    function identity() {
      const a = access();
      const n = section('Identity & approval gate');
      add(n, record({identity:a.identity, enrollment:a.enrollment, gate:a.gate}), note(a.canWrite === true ? 'Reviewer requests use the authenticated API client. The server checks each action.' : a.canDraft === true ? 'Signed local draft intake, independent tests and previews are available. Promotion and financial actions require their separate authorization.' : 'Read-only. An enrolled reviewer can sign in here to stage a local draft. After a page reload, sign out and sign in again to restore signing.'));
      return n;
    }
    function field(form, name, title, type = 'text', required = true) {
      const input = el(Array.isArray(type) ? 'select' : type === 'textarea' ? 'textarea' : 'input');
      if (Array.isArray(type)) {
        const blank = el('option', 'Choose document origin'); blank.value = ''; input.append(blank);
        type.forEach(value => { const option = el('option', ({public:'Public document',synthetic_public:'Authored document'})[value] || value); option.value = value; input.append(option); });
      } else if (type !== 'textarea') input.type = type;
      input.name = name; input.required = required; input.autocomplete = 'off';
      input.setAttribute('aria-label', title);
      if (type === 'textarea') { input.rows = 5; input.spellcheck = false; }
      form.append(add(el('label', undefined, 'v4-field'), el('span', title), input));
      return input;
    }
    function sync() {
      mounts.forEach(m => {
        (m.writes || []).forEach(n => { n.disabled = !writable(n.draftAllowed === true); });
        (m.syncs || []).forEach(update => update());
      });
    }
    async function request(path, body) {
      if (typeof options.api !== 'function') throw new Error('Authenticated API client is not connected.');
      return body === undefined ? options.api(path) : options.api(path, body);
    }
    function status(m, message) { m.status.textContent = message; }
    async function mutate(m, path, body, onSuccess, draft = false) {
      if (!writable(draft) || mounts.get(m.root) !== m) return;
      busy = true; sync(); status(m, 'Submitting for server authorization…');
      let recorded = false, generatedCase = null;
      try {
        const result = await request(path, body);
        recorded = true;
        if (path.endsWith('/evaluate') && typeof result?.id === 'string') generatedCase = result.id;
        uncertain = true;
        if (mounts.get(m.root) !== m) return;
        status(m, 'Server recorded the request. Refresh to inspect current state.');
        m.result.replaceChildren(details('Server response', result));
        if (path.endsWith('/evaluate') && typeof result?.id === 'string' && typeof options.onCase === 'function') {
          m.result.append(button('Inspect generated case ' + result.id, () => options.onCase(result.id)));
        }
        if (onSuccess) onSuccess(result);
      } catch (_) {
        uncertain = true;
        status(m, 'Request did not complete reliably. Its outcome may be unknown. Refresh server state before another change.');
      } finally {
        busy = false; sync();
        if (recorded && options.reloadAfterMutation && mounts.get(m.root) === m) {
          if (m.claimId) await inspect(m.root,m.claimId);
          else if (typeof options.onRefresh === 'function') await options.onRefresh(m.view);
          if (generatedCase && typeof options.onCase === 'function') options.onCase(generatedCase);
        }
      }
    }
    function form(m, title, fields, submitLabel, build, path, draft = false) {
      const panel = section(title), node = el('form', undefined, 'v4-form'), inputs = {};
      fields.forEach(([name, text, type, required]) => { inputs[name] = field(node, name, text, type, required); });
      const preview = el('div', undefined, 'v4-review');
      let reviewed = null;
      const submit = el('button', submitLabel); submit.type = 'submit'; submit.draftAllowed = draft; m.writes.push(submit);
      node.addEventListener('submit', async event => {
        event.preventDefault();
        if (!writable(draft) || !node.reportValidity()) return;
        try {
          const values = Object.fromEntries(Object.entries(inputs).map(([k, v]) => [k, v.value.trim()]));
          const body = build(values);
          const destination = typeof path === 'function' ? path(values) : path;
          const exact = JSON.stringify({destination,body});
          if (options.reviewForms && reviewed !== exact) {
            reviewed = exact;
            preview.replaceChildren(el('h3','Review exact local request'), record({destination,body}),
              note('This signed request records local review work. It does not establish entitlement or external delivery. Source text is untrusted data.'));
            submit.textContent = 'Confirm ' + submitLabel.toLowerCase();
            status(m,'Review the request below, then confirm. Editing any field requires another review.');
            return;
          }
          await mutate(m, destination, body, undefined, draft);
        } catch (error) { status(m, error.message); }
      });
      node.addEventListener('input', () => { reviewed = null; preview.replaceChildren(); submit.textContent = submitLabel; });
      add(node, preview, submit); panel.append(node); return panel;
    }
    function actions(m, data, base) {
      const n = el('div', undefined, 'v4-actions');
      list(data.actions).forEach(action => {
        const id = typeof action === 'string' ? action : action.id;
        if (typeof id !== 'string' || !id) return;
        const b = button(typeof action === 'string' ? label(action) : (action.label === 'Replay shadow checks' ? 'Run shadow checks' : action.label) || label(id), () => mutate(m, base + '/actions/' + encodeURIComponent(id), {}));
        m.writes.push(b); n.append(b);
      });
      if (!n.children.length) n.append(note('No approved action is available in the returned server state.'));
      return n;
    }
    function inspector(m, data, correspondence = false) {
      const n = section(correspondence ? 'Correspondence case' : 'Case evidence & financial references');
      const refs = {case_id:data.case_id ?? data.claim_id ?? data.id, receipt_id:data.receipt_id, packet_id:data.packet_id,
        memo_id:data.memo_id, credit_id:data.credit_id, bill_id:data.bill_id, application_id:data.application_id};
      add(n, record(refs), provenance(data.sources));
      for (const [title, value] of [['Decision & unknowns', {outcome:data.outcome, state:data.state ?? data.stage, unknowns:data.unknowns, missing:data.missing ?? data.preflight?.missing, owner:data.owner, filing_cutoff:data.filing_cutoff, next_contact:data.next_contact, financials:data.financials}], ['Event timeline', data.timeline ?? data.events], ['Evidence & receipts', {evidence:data.evidence, receipts:data.receipts, submissions:data.submissions, replies:data.replies}], ['Current and historical evaluation', {evaluation:data.evaluation ?? data.preflight, history:data.history, trace:data.trace}]]) {
        add(n, el('h3', title), record(value));
      }
      add(n, details('Complete server case record', data));
      if (correspondence) {
        if (typeof data.interpretation_review_url === 'string' && /^\/static\/interpretation\.html\?claim=inbox-[a-zA-Z0-9._-]+$/.test(data.interpretation_review_url)) {
          const review = el('a', 'Review unfamiliar vendor wording'); review.href = data.interpretation_review_url;
          n.append(review, note('The review page uses your enrolled identity. Meaning review alone cannot file, close a denial or change money.'));
        }
        const id = data.claim_id ?? data.id;
        if (typeof id === 'string' && id) n.append(actions(m, data, '/api/correspondence/claims/' + encodeURIComponent(id)));
      }
      return n;
    }
    function vendor(m, data) {
      const id = data.vendor_id ?? data.id;
      const n = section(shown(data.name ?? data.vendor ?? id));
      add(n, provenance(data.sources), record({vendor_id:id, revision:data.revision, state:data.state, active_version:data.active_version, reviewer:data.reviewer}), details('Rules, overlay, tests and reviewer versions', data));
      if (typeof id !== 'string' || !id) { n.append(note('Vendor ID missing; actions unavailable.')); return n; }
      const base = '/api/vendors/' + encodeURIComponent(id);
      if (data.detail_unavailable) { n.append(note('Vendor details unavailable. Refresh before reviewing or changing this version.')); return n; }
      n.append(actions(m, data, base));
      if (data.revision !== undefined && data.revision !== null) {
        if (data.semantic_review_requirements) {
          n.append(note('Before pricing, a named reviewer must check the complete source, conditions, overrides, exact evidence representations and customer scope. Existing tests or approvals do not supply this review.'));
          n.append(form(m, 'Source meaning and evidence bindings', [['review','Explicit semantic review (JSON object; source pins, every block and literal selection)','textarea']], 'Record semantic review', v => ({revision:data.revision,review:parseJSON(v.review,'review')}), base + '/semantic-bindings'));
        }
        if (data.semantic_binding) n.append(form(m, 'Revoke source meaning review', [], 'Revoke semantic binding', () => ({revision:data.revision}), base + '/semantic-bindings/revoke'));
        n.append(form(m, 'Independent tests & shadow evidence', [ ['tests','Test cases (JSON array: name, facts, expected)', 'textarea'] ], 'Submit independent tests', v => ({revision:data.revision,tests:parseJSON(v.tests,'tests')}), base + '/tests', true));
        n.append(form(m, 'Local shadow preview', [['facts','Shadow facts (JSON object)','textarea']], 'Preview candidate', v => ({revision:data.revision,facts:parseJSON(v.facts,'facts')}), base + '/shadow-preview', true));
      }
      n.append(form(m, 'Evaluate the active adapter', [['facts','Contract-scoped facts (JSON object)', 'textarea']], 'Evaluate into a case', v => ({facts:parseJSON(v.facts,'facts')}), base + '/evaluate'));
      n.append(note('Facts require agreement, account, product, plan, month, eligible_downtime_minutes, monitor_source, month_complete, exclusions_removed, monthly_fee_cents, fee_line_ref, received_at, monitor_ref and fee_ref. Use observed values and explicit provenance.'));
      n.append(note('Evaluation uses the current server-approved adapter. Rollback affects new dispatch; historical cases retain their recorded version.'));
      return n;
    }
    // ---- Public proposal generation (proposal-generator) ----
    // Source text is sent exactly as entered: never trimmed or normalized here. Generation permission comes only
    // from the server's access answer for these exact fields, and any edit invalidates it. Job status is read with
    // GET only; a lost reservation response is recovered by an explicit access recheck, never by a second POST.
    const PROFILES = [['monthly','Monthly availability terms'],
      ['monthly-propositions','Monthly terms with prose interpretation'],
      ['resource-month','Resource or service-month terms (interpretation review required)']];
    const REASONS = {PROPOSAL_SERVICE_UNCONFIGURED:'proposal generation is not configured in this deployment',
      PROVIDER_UNCONFIGURED:'no public proposal provider is configured', NOT_SUCCEEDED:'the job has not succeeded',
      exact_request_not_approved:'this exact document request needs operator approval',
      proposal_validation_failed:'the returned proposal did not pass source validation',
      approval_unavailable_before_dispatch:'source permission was unavailable when the job was ready',
      provider_timeout:'the model did not finish within the allowed time',
      provider_outcome_unknown:'the model outcome could not be confirmed',
      restart_before_dispatch:'the pending job was cancelled when the service restarted',
      restart_after_dispatch:'the service restarted after the model call began',
      RESULT_INTEGRITY:'the stored result failed its integrity pins',
      STALE_CONTEXT:'the source, profile or evaluator semantics changed after generation',
      REQUEST_CHANGED:'the configured transport changed after generation'};
    const reasonText = code => typeof code === 'string' && code ? (REASONS[code] || code) : 'no reason returned';
    const JOB_MESSAGES = {
      QUEUED:'Queued. The server calls the configured model once for this approved request; this page only reads status.',
      RUNNING:'Running. This page only reads status and never resends the request.',
      SUCCEEDED:'Validated against the exact public source. The proposal is unreviewed and not approved.',
      REFUSED:'Source validation refused the model output. No candidate can be created from it. A retry needs a new attempt identifier and its own approval.',
      CANCELLED:'Cancelled before completion. A retry needs a new attempt identifier and its own approval.',
      UNCERTAIN:'The outcome is uncertain, for example after an interrupted run. It is never retried automatically.'};
    const schedule = typeof options.schedule === 'function' ? options.schedule : (callback, ms) => global.setTimeout(callback, ms);
    function generator(m) {
      const panel = section('Generate a public proposal');
      panel.append(note('Paste the exact public contract text. The server builds the complete request, requires a separate operator approval for those exact bytes, and calls the configured model at most once per approved request. A proposal is not a candidate, a test result or an approval.'));
      const box = el('div', undefined, 'v4-form v4-generator');
      box.setAttribute('role','group'); box.setAttribute('aria-label','Public proposal request');
      const inputs = {vendor_id:field(box, 'vendor_id', 'Proposal vendor identifier'), name:field(box, 'name', 'Public document name'),
        uri:field(box, 'uri', 'Public document URI', 'url'),
        classification:field(box, 'classification', 'Public document origin', ['public','synthetic_public'])};
      const profile = el('select');
      const blank = el('option', 'Choose extraction profile'); blank.value = ''; profile.append(blank);
      PROFILES.forEach(([value, text]) => { const option = el('option', text); option.value = value; profile.append(option); });
      profile.name = 'profile'; profile.required = true; profile.setAttribute('aria-label', 'Extraction profile');
      box.append(add(el('label', undefined, 'v4-field'), el('span', 'Extraction profile'), profile));
      inputs.profile = profile;
      inputs.attempt_nonce = field(box, 'attempt_nonce', 'Attempt identifier (change only for a separately approved retry)');
      inputs.attempt_nonce.value = 'initial';
      inputs.text = field(box, 'text', 'Exact public source text (sent exactly as entered)', 'textarea');
      inputs.text.rows = 12;
      const sourceFile = field(box, 'source_file', 'Import UTF-8 source file (optional)', 'file', false);
      sourceFile.accept = '.txt,text/plain';
      let fileText = null, fileDisplay = null;
      const state = {token:0, inflight:0, confirmed:null, lost:false, job:null, shown:null, polls:0};
      const accessOut = el('div', undefined, 'v4-review'), jobOut = el('div', undefined, 'v4-review');
      const live = () => mounts.get(m.root) === m;
      const values = () => {
        // Textareas normalize line endings. Keep imported text separately until an explicit edit.
        if (fileText !== null && inputs.text.value !== fileDisplay) fileText = null;
        return {...Object.fromEntries(Object.entries(inputs).map(([key, input]) => [key, input.value])),
          text:fileText === null ? inputs.text.value : fileText};
      };
      const payload = v => ({document:{name:v.name, uri:v.uri, classification:v.classification, text:v.text},
        profile:v.profile, attempt_nonce:v.attempt_nonce});
      const exact = v => JSON.stringify([v.vendor_id, payload(v)]);
      const vendorPath = id => '/api/vendors/' + encodeURIComponent(id);
      function problem(v) {
        if (Object.values(v).some(value => typeof value !== 'string' || value === '')) return 'Complete every proposal field. Source text is sent exactly as entered.';
        if (!/^[a-z0-9][a-z0-9_-]{0,79}$/.test(v.vendor_id)) return 'Use a lowercase vendor identifier of letters, digits, hyphens or underscores.';
        return '';
      }
      const check = button('Check generation access', () => checkAccess());
      const generate = button('Generate proposal', () => submitJob());
      const refresh = button('Refresh proposal status', () => { state.polls = 0; return loadJob(); });
      function update() {
        const can = live() && writable(true) && state.inflight === 0, c = state.confirmed;
        check.disabled = !can;
        generate.disabled = !(can && c && c.enabled === true && !c.existing && !state.lost && !state.job && c.key === exact(values()));
        refresh.disabled = !(live() && state.job && state.inflight === 0);
      }
      function invalidate() {
        state.token++; state.confirmed = null; state.lost = false; state.job = null; state.shown = null; state.polls = 0;
        accessOut.replaceChildren(); jobOut.replaceChildren(); update();
      }
      function edited() {
        const had = state.confirmed || state.job || state.lost || state.inflight;
        invalidate();
        if (had) status(m, 'The proposal fields changed. Check generation access again before generating.');
      }
      Object.values(inputs).forEach(input => {
        const change = () => {
          if (input === inputs.text && fileText !== null) {
            fileText = null;
            edited();
            status(m, 'Text edited. This is a new source request; check generation access again.');
          } else edited();
        };
        input.addEventListener('input', change); input.addEventListener('change', change);
      });
      sourceFile.addEventListener('change', async () => {
        const file = sourceFile.files && sourceFile.files[0];
        fileText = null; fileDisplay = null; inputs.text.value = ''; invalidate();
        if (!file) return;
        const token = state.token; state.inflight++; update();
        try {
          if (file.size > 200000) throw new Error('Source too large');
          const text = new TextDecoder('utf-8', {fatal:true, ignoreBOM:true}).decode(await file.arrayBuffer());
          if (token !== state.token || !live()) return;
          if (!text || text.length > 50000) throw new Error('Source too large');
          fileText = text; inputs.text.value = text; fileDisplay = inputs.text.value;
          status(m, 'Source file loaded. Original line endings are retained until you edit the text. Check generation access before sending.');
        } catch (_) {
          if (token === state.token && live()) status(m, 'Choose a valid UTF-8 text file within the source limit. Nothing was sent.');
        } finally { state.inflight--; update(); }
      });
      function accessView(answer) {
        const n = add(el('div', undefined, 'v4-access'), el('h3', 'Server generation access'),
          record({enabled:answer.enabled, reason:answer.reason, request_sha256:answer.request_sha256, context_sha256:answer.context_sha256}));
        if (answer.disclosure && typeof answer.disclosure === 'object') add(n, el('h3', 'Exact public transmission'), record(answer.disclosure));
        n.append(note('Only this server-computed request can be transmitted, and only after a separate operator approval of these exact bytes. The private customer overlay is never part of it. Hashes or labels shown here do not authorize transmission.'));
        return n;
      }
      function candidate(vendor, job) {
        const n = el('div', undefined, 'v4-form v4-candidate');
        n.setAttribute('role','group'); n.setAttribute('aria-label','Attach private customer overlay');
        const overlay = field(n, 'overlay', 'Private customer overlay for this proposal (JSON object; never sent for extraction)', 'textarea');
        const preview = el('div', undefined, 'v4-review');
        const path = vendorPath(vendor) + '/proposal-jobs/' + encodeURIComponent(job.job_id) + '/candidate';
        let reviewed = null;
        const attach = button('Review shadow candidate request', async () => {
          if (!writable(true) || !live()) return;
          let body;
          try { body = {overlay:parseJSON(overlay.value, 'overlay')}; } catch (error) { status(m, error.message); return; }
          const exactBody = JSON.stringify([path, body]);
          if (reviewed !== exactBody) {
            reviewed = exactBody;
            preview.replaceChildren(el('h3', 'Review exact candidate request'), record({destination:path, body}),
              note('The server attaches this private overlay to the immutable public proposal of job ' + job.job_id + ' and stages a normal SHADOW candidate. Nothing is sent to the model. Independent tests, any source-meaning review and named approval remain required.'));
            attach.textContent = 'Confirm shadow candidate';
            status(m, 'Review the candidate request, then confirm. Editing the overlay requires another review.');
            return;
          }
          await mutate(m, path, body, undefined, true);
        });
        attach.draftAllowed = true; attach.disabled = !writable(true); m.writes.push(attach);
        overlay.addEventListener('input', () => { reviewed = null; preview.replaceChildren(); attach.textContent = 'Review shadow candidate request'; });
        return add(n, preview, attach);
      }
      function proposal(vendor, job) {
        const p = job.proposal && typeof job.proposal === 'object' ? job.proposal : {};
        const n = add(el('div', undefined, 'v4-proposal'), el('h3', 'Proposed public clauses'),
          record({profile:p.profile, attempt_nonce:p.attempt_nonce, source_sha256:p.source_sha256, proposal_sha256:p.proposal_sha256,
            model:p.model, session:p.session, document:p.document}));
        const rows = el('ol', undefined, 'v4-clauses');
        list(p.clauses).forEach(clause => {
          if (!clause || typeof clause !== 'object') return;
          rows.append(add(el('li', undefined, 'v4-clause'),
            el('span', typeof clause.field === 'string' ? label(clause.field) : 'unlabeled', 'v4-clause-field'),
            el('blockquote', typeof clause.quote === 'string' ? clause.quote : null, 'v4-quote'),
            el('pre', clause.value === undefined ? null : JSON.stringify(clause.value, null, 2), 'v4-value')));
        });
        if (!rows.children.length) rows.append(el('li', 'No validated clauses returned.'));
        n.append(rows, note('Quotes are exact slices of the public source and remain untrusted text. This proposal is unreviewed: it has no tests, approval or customer scope.'));
        if (job.candidate_available === true) n.append(candidate(vendor, job));
        else n.append(note('A candidate cannot be created from this result: ' + reasonText(job.refusal) + '.'));
        return n;
      }
      function show(vendor, job) {
        const displayed = [job.job_id, job.status, job.candidate_available === true].join(':');
        if (state.shown === displayed) return; // Keep an overlay being typed for an already displayed result.
        state.shown = displayed;
        const n = add(el('div', undefined, 'v4-job'), el('h3', 'Proposal job'),
          record({job_id:job.job_id, status:job.status, reason:job.reason, request_sha256:job.request_sha256, context_sha256:job.context_sha256}),
          note(JOB_MESSAGES[job.status] || 'Unrecognized job status. No action is available.'));
        if (job.status === 'SUCCEEDED') n.append(proposal(vendor, job));
        jobOut.replaceChildren(n);
      }
      function poll(job) {
        if (!['QUEUED','RUNNING'].includes(job.status) || state.polls >= 60) return;
        state.polls++;
        const token = state.token, id = job.job_id;
        schedule(() => token === state.token && live() && state.job && state.job.job_id === id ? loadJob() : undefined, 2500);
      }
      function adopt(vendor, job) {
        state.job = {vendor, job_id:job.job_id};
        show(vendor, job); poll(job);
      }
      async function loadJob() {
        if (!live() || !state.job) return;
        const {vendor, job_id} = state.job, token = state.token;
        try {
          const job = await request(vendorPath(vendor) + '/proposal-jobs/' + encodeURIComponent(job_id));
          if (token !== state.token || !live() || !state.job || state.job.job_id !== job_id) return;
          if (!job || typeof job !== 'object' || job.job_id !== job_id) throw new Error('Mismatched proposal job.');
          show(vendor, job); poll(job);
        } catch (_) {
          if (token === state.token && live()) status(m, 'Proposal status is unavailable. Use Refresh proposal status; nothing was resent.');
        }
      }
      async function checkAccess() {
        if (check.disabled || !live()) return;
        const v = values(), message = problem(v);
        if (message) { status(m, message); return; }
        invalidate();
        const token = state.token, key = exact(v), body = payload(v);
        state.inflight++; update();
        status(m, 'Checking server generation access for these exact fields. Nothing is generated by this check.');
        try {
          const answer = await request(vendorPath(v.vendor_id) + '/proposal-access', body);
          if (token !== state.token || !live()) return;
          if (!answer || typeof answer !== 'object' || typeof answer.enabled !== 'boolean') throw new Error('Malformed access state.');
          const existing = !!answer.existing_job && typeof answer.existing_job === 'object' && typeof answer.existing_job.job_id === 'string';
          state.confirmed = {key, body, vendor:v.vendor_id, enabled:answer.enabled, existing};
          accessOut.replaceChildren(accessView(answer));
          if (existing) {
            adopt(v.vendor_id, answer.existing_job);
            status(m, 'This exact request already has a proposal job. Showing it; no new model call is requested.');
          } else status(m, answer.enabled ? 'Generation is permitted for this exact request. Review what will be transmitted, then choose Generate proposal.'
            : 'Generation is not available for this exact request: ' + reasonText(answer.reason) + '.');
        } catch (_) {
          if (token !== state.token || !live()) return;
          accessOut.replaceChildren();
          status(m, 'Generation access could not be confirmed. Nothing was generated. Check the connection, then check access again.');
        } finally { state.inflight--; update(); }
      }
      async function submitJob() {
        if (generate.disabled || !live()) return;
        const c = state.confirmed;
        if (!c || c.key !== exact(values()) || c.enabled !== true || c.existing || state.lost || state.job) {
          invalidate(); status(m, 'The request changed after its access check. Check generation access again.'); return;
        }
        const token = state.token;
        state.inflight++; update();
        status(m, 'Reserving one proposal job for this exact approved request…');
        try {
          const job = await request(vendorPath(c.vendor) + '/proposal-jobs', c.body);
          if (token !== state.token || !live()) return;
          if (!job || typeof job !== 'object' || typeof job.job_id !== 'string' || !job.job_id) throw new Error('Malformed proposal job.');
          state.confirmed = {...c, existing:true};
          adopt(c.vendor, job);
          status(m, 'Proposal job ' + job.job_id + ' is ' + shown(job.status) + '. Status is read-only from here.');
        } catch (_) {
          if (token !== state.token || !live()) return;
          state.lost = true;
          status(m, 'The generation request did not complete reliably and may have been queued. Choose Check generation access to recover any existing job; nothing is resent automatically.');
        } finally { state.inflight--; update(); }
      }
      add(box, add(el('div', undefined, 'v4-actions'), check, generate, refresh), accessOut, jobOut);
      panel.append(box);
      m.syncs.push(update); update();
      return panel;
    }
    async function vendors(m, data) {
      const summaries = Array.isArray(data) ? data : list(data.vendors);
      const items = await Promise.all(summaries.map(async item => {
        const id = item.vendor_id ?? item.id;
        if (Array.isArray(item.actions) || typeof id !== 'string' || !id) return item;
        try { return await request('/api/vendors/' + encodeURIComponent(id)); }
        catch (_) { return {...item, detail_unavailable:true}; }
      }));
      if (mounts.get(m.root) !== m) return;
      m.body.append(generator(m));
      m.body.append(form(m, 'Local deterministic intake', [
        ['vendor_id','Vendor identifier'], ['name','Document name'], ['uri','Public source URI','url'],
        ['classification','Document origin',['public','synthetic_public']], ['text','Public contract excerpt or full text','textarea'],
        ['overlay','Private customer overlay (JSON object)','textarea']
      ], 'Stage local candidate', v => ({document:{name:v.name,uri:v.uri,classification:v.classification,text:v.text},overlay:parseJSON(v.overlay,'overlay')}), v => '/api/vendors/' + encodeURIComponent(v.vendor_id) + '/candidates', true));
      m.body.append(note('Local intake validates supported wording with the built-in deterministic parser. It does not call a model.'));
      m.body.append(note('Public terms and private customer scope remain separate. Unsupported clauses and missing evidence must remain explicit in the server decision.'));
      m.body.append(note('Overlay fields: agreement, account, product, plan, effective_from, effective_until, fee_line_ref and currency. Include only customer scope supported by the governing agreement.'));
      items.forEach(item => m.body.append(vendor(m, item)));
      if (!items.length) m.body.append(note('No vendors returned. No example vendor has been selected.'));
    }
    function disputes(m, data) {
      m.body.append(form(m, 'Set up a correspondence case', [ ['claim_id','Claim identifier (inbox- prefix)'], ...['account','vendor','contract','service','component','invoice','incident','currency','month','region'].map(k => [k,label(k)]) ], 'Create scoped case', v => {
        const {claim_id, ...scope} = v; return {claim_id,scope};
      }, '/api/correspondence/claims'));
      m.body.append(note('Provisioned services deliver messages and evidence through CLI ingestion. Refresh to inspect receipts and available reviewer actions. Service credentials never belong in this browser.'));
      const items = Array.isArray(data) ? data : list(data.claims);
      items.forEach(item => {
        const id = typeof item === 'string' ? item : item.claim_id ?? item.id;
        const n = section(shown(id));
        if (typeof item === 'object') add(n, provenance(item.sources), record(item));
        if (typeof id === 'string' && id) n.append(button('Inspect case ' + id, () => inspect(m.root, id)));
        m.body.append(n);
      });
      if (!items.length) m.body.append(note('No correspondence cases returned.'));
    }
    function portfolio(m, data) {
      m.body.append(note('Portfolio and seeded comparison are separate server-declared cohorts. A seeded scenario is not a portfolio total.'));
      const grid = el('div', undefined, 'v4-grid');
      for (const [key, title] of [['portfolio','Portfolio'],['seeded','Seeded comparison']]) {
        const cohort = data[key]; const n = section(title);
        if (!cohort) n.append(note('Cohort not provided.'));
        else {
          add(n, note(shown(cohort.label)), provenance(cohort.sources), record(cohort.metrics));
          list(cohort.cases).forEach(c => {
            const row = add(el('div', undefined, 'v4-case'), record(c));
            if (typeof c.id === 'string' && typeof options.onCase === 'function') row.append(button('Inspect ' + c.id, () => options.onCase(c.id)));
            n.append(row);
          });
        }
        grid.append(n);
      }
      m.body.append(grid);
    }
    function catalog(m, data) {
      m.body.append(note('Review vendor terms, correspondence and financial reconciliation.'));
      const nav = el('nav', undefined, 'v4-grid'); nav.setAttribute('aria-label','Companion workflow catalog');
      for (const [route,title,description] of [
        ['ramp','Matched Ramp evidence','Inspect native records, governing terms, evidence and read-only workflow plans.'],
        ['vendors','Source-grounded vendor intake','Review public source text separately from customer scope; inspect candidate tests, shadow checks and version actions.'],
        ['disputes','Onboarding & disputes','Create a provisioned correspondence case, inspect untrusted inbound evidence and current reviewer actions.'],
        ['dashboard','Evidence ledger','Inspect case financial stages and clause-cited evaluation traces.'],
        ['lab','Onboarding lab','Preserved onboarding and shadow evaluation workflow.'],
        ['regression','Regression comparison','Compare the portfolio with a separate reference cohort.']]) {
        const panel = section(title), link = el('a','Open ' + title); link.href = '#' + route;
        add(panel,note(description),link); nav.append(panel);
      }
      m.body.append(nav,section('Observed integrity & reconciliation'));
      m.body.append(record({as_of:data.as_of,snapshot_status:data.snapshot_status,
        credit_sync:data.credit_sync,terms:data.terms ?? data.terms_status ?? data.terms_metrics ?? 'Terms verification metrics not returned by this backend',
        quarantine:data.quarantine ?? data.quarantine_metrics ?? 'Quarantine metrics not returned by this backend'}));
      m.body.append(note('Missing verification or quarantine counts are unknown, not zero. A checksum or source signature alone does not establish entitlement.'));
    }
    async function render(root, view, supplied) {
      if (!root || typeof root.replaceChildren !== 'function') throw new Error('A DOM root is required.');
      if (['portfolio','case','catalog'].includes(view) && supplied === undefined) throw new Error('Server projection is required for this view.');
      if (!['vendors','disputes','portfolio','case','catalog'].includes(view)) throw new Error('Unknown Uptime V4 view.');
      const m = {root,view,writes:[],syncs:[],status:el('p', '', 'v4-status'),result:el('div'),body:el('div')};
      m.status.setAttribute('role','status'); m.status.setAttribute('aria-live','polite');
      mounts.set(root,m);
      const wrap = el('div', undefined, 'uptime-v4');
      const title = {vendors:'Vendor intake & versions',disputes:'Correspondence & disputes',portfolio:'Portfolio comparison',case:'Case inspector',catalog:'Advanced companion workflows'}[view];
      const refresh = button('Refresh server state', async () => {
        if (busy) return;
        // Supplied projections must be refreshed by their owner, not reclassified as current.
        if (supplied !== undefined) {
          if (typeof options.onRefresh === 'function') options.onRefresh(view);
          else status(m,'Refresh the parent dashboard to load the latest server state.');
          return;
        }
        await render(root,view);
      });
      add(wrap, el('h2',title), identity(), refresh, m.status, m.result, m.body); root.replaceChildren(wrap);
      try {
        const data = supplied === undefined ? await request(view === 'vendors' ? '/api/vendors' : view === 'disputes' ? '/api/correspondence/claims' : '') : supplied;
        if (mounts.get(root) !== m) return;
        if (data === null || data === undefined) throw new Error('No state');
        if (supplied === undefined) uncertain = false;
        if (view === 'vendors') await vendors(m,data);
        else if (view === 'disputes') disputes(m,data);
        else if (view === 'portfolio') portfolio(m,data);
        else if (view === 'catalog') catalog(m,data);
        else m.body.append(inspector(m,data));
        if (mounts.get(root) !== m) return;
        status(m,'');
      } catch (_) { status(m,'State unavailable. Check identity, enrollment and the API connection, then refresh. Changes remain unavailable in this view.'); }
      sync();
      return m;
    }
    async function inspect(root, id) {
      const marker = {};
      mounts.set(root,marker);
      root.replaceChildren(note('Loading correspondence case…'));
      try {
        const data = await request('/api/correspondence/claims/' + encodeURIComponent(id));
        if (mounts.get(root) !== marker) return;
        const m = await render(root,'case',data);
        if (!m || mounts.get(root) !== m) return;
        m.claimId = id;
        m.body.replaceChildren(inspector(m,data,true));
        m.body.prepend(button('Back to correspondence', () => render(root,'disputes')), button('Refresh case receipts', () => inspect(root,id)));
        uncertain = false; sync();
      } catch (_) {
        if (mounts.get(root) === marker) root.replaceChildren(note('Case unavailable. No changes were sent.'), button('Back to correspondence', () => render(root,'disputes')));
      }
    }
    return Object.freeze({render, inspect, unmount: root => mounts.delete(root), refreshAccess: sync});
  }
  const api = Object.freeze({create, parseJSON});
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (global) global.UptimeV4 = api;
})(typeof window !== 'undefined' ? window : globalThis);
