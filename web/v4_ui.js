/* Uptime V4 extension. No fetch, identity assignment, enrollment, or service credential handling.
 * Integration (lead owns app.js/index.html/server static routes):
 * 1. Serve /v4_ui.js and /v4_style.css locally; load stylesheet after style.css and script
 *    before app.js with defer. No inline handlers/styles, CDN, or CSP relaxation required.
 * 2. const v4 = window.UptimeV4.create({
 *      api: (path, body) => signedApi(path, body), // absent body = GET; body = POST
 *      getAccess: () => ({identity, enrollment, gate, canWrite}),
 *      onCase: id => openCase(id), onUnauthorized: () => showSignIn()
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
 * 6. Public proposal generation sends profile "auto" (Uptime selects the rule family) to
 *    POST /api/vendors/{id}/proposal-access (selection and permission, no model call), POST
 *    .../proposal-jobs (explicit reservation of every family evaluation), GET
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
  // Plain wording for server dispute codes; unknown codes are shown as lower-case words, never guessed.
  const CATEGORY = {MISSING_EVIDENCE:'missing evidence', CONTRACTUAL_DENIAL:'contractual denial',
    INCORRECT_FACTUAL_ASSERTION:'incorrect factual assertion', UNRESOLVED_DENIAL:'unresolved denial',
    PARTIAL_AWARD:'partial award', AWARD_REPORTED:'award reported', CHANGED_SCOPE:'changed scope', AMBIGUOUS_GROUNDS:'ambiguous grounds'};
  const DISPOSITION = {PREPARE_CLAIM:'prepare the claim', AWAIT_RESPONSE:'awaiting the vendor response',
    AWAIT_CURE_EVIDENCE:'awaiting the requested evidence', AWAIT_EVIDENCE:'awaiting evidence',
    DENIAL_SUBSTANTIATED:'denial ground substantiated; accepting it is a separate step', ACCEPT_DENIAL:'denial accepted',
    AWARD_RECORDED:'award recorded', PARTIAL_AWARD_RECORDED:'partial award recorded', ESCALATE:'needs a reviewer'};
  const CHECKS = {governing_evaluation:'Governing evaluation', original_filing_within_window:'Original filing within the window',
    follow_ups_preserve_original_filing:'Follow-ups keep the original filing', month_coverage_basis:'Month coverage basis',
    timely_independent_maintenance_notice:'Timely independent maintenance notice', verified_measurement:'Verified measurement',
    denial_ground_substantiated:'Denial ground substantiated', explicit_denial_acceptance:'Explicit denial acceptance',
    award_not_above_claim:'Award not above the claim', contradicting_deliveries_unresolved:'Unresolved contradicting deliveries',
    status_origin:'Status record origin'};
  // Results whose true/false does not mean pass/fail.
  const RESULTS = {contradicting_deliveries_unresolved:{true:'yes, review needed', false:'none'},
    status_origin:{ENROLLED_SOURCE_NOT_ORIGIN_VERIFIED:'enrolled source; origin not verified', NO_STATUS_RECORD:'no status record'}};
  const NEXT = {'accept-denial':'Accept denial', 'interpretation-review':'Review vendor wording'};
  const plain = (map, value) => value == null ? 'Not determined' : map[value] || String(value).replaceAll('_', ' ').toLowerCase();
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
    let uncertain = false, authRequired = false;
    const active = m => mounts.get(m.root) === m;
    const access = () => typeof options.getAccess === 'function' ? options.getAccess() || {} : {};
    const writable = (draft = false) => (access().canWrite === true || draft && access().canDraft === true) && !busy && !uncertain && !authRequired;
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
        (m.writes || []).forEach(n => { n.disabled = !writable(n.draftAllowed === true) || (typeof n.stillCurrent === 'function' && !n.stillCurrent()); });
        (m.syncs || []).forEach(update => update());
      });
    }
    function disable(root) {
      for (const child of root?.children || []) {
        if (['button','input','select','textarea'].includes(String(child.tagName).toLowerCase())) child.disabled = true;
        disable(child);
      }
    }
    function unmount(root) { disable(root); mounts.delete(root); }
    async function request(m, path, body) {
      if (typeof options.api !== 'function') throw new Error('Authenticated API client is not connected.');
      try {
        const result = await (body === undefined ? options.api(path) : options.api(path, body));
        if (body === undefined && active(m)) authRequired = false;
        return result;
      } catch (error) {
        if (error?.status === 401 && active(m)) {
          authRequired = true;
          const roots = [...mounts.keys()];
          roots.forEach(unmount);
          roots.forEach(root => root.replaceChildren(note('Sign in again to load current server state. Nothing is retried automatically.')));
          if (typeof options.onUnauthorized === 'function') options.onUnauthorized();
        }
        throw error;
      }
    }
    function status(m, message) { if (active(m)) m.status.textContent = message; }
    async function mutate(m, path, body, onSuccess, draft = false) {
      if (!writable(draft) || mounts.get(m.root) !== m) return;
      busy = true; sync(); status(m, 'Submitting for server authorization…');
      let recorded = false, generatedCase = null;
      try {
        const result = await request(m, path, body);
        recorded = true;
        if (path.endsWith('/evaluate') && typeof result?.id === 'string') generatedCase = result.id;
        if (!active(m)) return;
        uncertain = true;
        status(m, 'Server recorded the request. Refresh to inspect current state.');
        m.result.replaceChildren(details('Server response', result));
        if (path.endsWith('/evaluate') && typeof result?.id === 'string' && typeof options.onCase === 'function') {
          m.result.append(button('Inspect generated case ' + result.id, () => active(m) && options.onCase(result.id)));
        }
        if (onSuccess) onSuccess(result);
      } catch (_) {
        if (!active(m)) return;
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
        if (!active(m) || !writable(draft) || !node.reportValidity()) return;
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
        if (action && typeof action === 'object' && action.route === 'denial-acceptance') {
          // The generic action route refuses this; the offer is bound to the exact denial basis the server showed.
          if (typeof action.basis_digest !== 'string' || !/^[a-f0-9]{64}$/.test(action.basis_digest)) return;
          const accept = button('Accept denial', () => acceptDenial(m, base, action.basis_digest));
          m.writes.push(accept);
          n.append(accept, note('Closes this claim on the substantiated denial ground. No further follow-up is sent and no credit is recorded.'));
          return;
        }
        const b = button(typeof action === 'string' ? label(action) : (action.label === 'Replay shadow checks' ? 'Run shadow checks' : action.label) || label(id), () => mutate(m, base + '/actions/' + encodeURIComponent(id), {}));
        m.writes.push(b); n.append(b);
      });
      if (!n.children.length) n.append(note('No approved action is available in the returned server state.'));
      return n;
    }
    async function acceptDenial(m, base, digest) {
      if (!writable() || mounts.get(m.root) !== m) return;
      busy = true; sync(); status(m, 'Submitting for server authorization…');
      let reload = false;
      try {
        const result = await request(m, base + '/denial-acceptance', {basis_digest:digest});
        if (!active(m)) return;
        reload = true;
        status(m, 'The server recorded the denial acceptance at stage ' + shown(result?.stage) + '.');
      } catch (error) {
        if (!active(m)) return;
        if (error?.status === 409) {
          reload = true;
          status(m, 'The denial basis changed since this page loaded. Nothing was accepted. Showing the current offer.');
        } else {
          uncertain = true;
          status(m, 'Request did not complete reliably. Its outcome may be unknown. Refresh server state before another change.');
        }
      } finally {
        busy = false; sync();
        if (reload && mounts.get(m.root) === m && m.claimId) {
          const message = m.status?.textContent;
          await inspect(m.root, m.claimId);
          const current = mounts.get(m.root);
          if (current && message) status(current, message);
        }
      }
    }
    // Records a source sent for another account or resource. A blocking one stops every case action until a person reviews it.
    function contradictions(items) {
      const rows = list(items).filter(item => item && typeof item === 'object');
      if (!rows.length) return null;
      const blocking = rows.some(item => item.blocking === true);
      const n = add(el('div', undefined, 'v4-review v4-contradictions'), el('h4', blocking ? 'Review needed: conflicting source record' : 'Conflicting source records'),
        note(blocking ? 'A source sent a record for another account or resource. A person must review it; this case offers no action until then.'
          : 'A source sent a record for another account or resource. It is recorded and does not block this case.'));
      const ul = el('ul');
      rows.forEach(item => ul.append(el('li', [shown(item.kind), shown(item.subject ?? item.source), shown(item.received_at), shown(item.reason)].join(' · ')
        + (item.blocking === true ? ' · blocking' : ''))));
      return add(n, ul);
    }
    function disputeRecord(m, url) {
      const n = add(el('div', undefined, 'v4-review v4-dispute-record'), el('h3', 'Dispute record'));
      const out = el('div'); out.setAttribute('aria-live', 'polite');
      const load = button('Show dispute record', async () => {
        if (!active(m)) return;
        load.disabled = true; out.replaceChildren(note('Loading the read-only dispute record…'));
        try {
          const t = await request(m, url);
          if (!active(m)) return;
          const facts = el('dl', undefined, 'v4-record');
          for (const [k, v] of [['Disposition', plain(DISPOSITION, t.disposition)], ['Category', plain(CATEGORY, t.category)],
            ['Final', t.final === true ? 'Yes' : 'No'], ['Claimed', t.ledger?.claimed], ['Awarded', t.ledger?.awarded]]) add(facts, el('dt', k), el('dd', v));
          out.replaceChildren(facts);
          if (t.stale_denial_review === true) out.append(note('The denial basis changed after review. This claim needs a reviewer again before any acceptance.'));
          const conflicts = contradictions(t.contradicting_deliveries);
          if (conflicts) out.append(conflicts);
          list(t.correspondence).forEach(reply => {
            const row = add(el('div', undefined, 'v4-dispute-reply'), el('strong', 'Vendor reply · ' + shown(reply.received_at)),
              note('Ground: ' + shown(reply.ground) + ' · Category: ' + plain(CATEGORY, reply.category)), el('blockquote', reply.text));
            const quote = reply.interpretation?.source?.quote;
            if (typeof quote === 'string' && quote) row.append(note('Relied-on passage'), el('blockquote', quote));
            out.append(row);
          });
          const checks = el('ul', undefined, 'v4-checks');
          list(t.deterministic_checks).forEach(c => {
            const special = RESULTS[c.check] && RESULTS[c.check][String(c.result)];
            checks.append(el('li', plain(CHECKS, c.check) + ': '
              + (special || (c.result === true ? 'pass' : c.result === false ? 'fail' : plain({}, c.result)))));
          });
          if (checks.children.length) out.append(el('h4', 'Deterministic checks'), checks);
          const next = list(t.permitted_next_actions).map(id => NEXT[id] || label(String(id)));
          out.append(note('Permitted next actions: ' + (next.length ? next.join(', ') : 'none') + '.'), note(shown(t.authority)));
        } catch (error) {
          if (active(m)) out.replaceChildren(note(error?.status === 401 ? 'Sign in again to read the dispute record.' : 'Dispute record unavailable. Nothing was changed.'));
        } finally { load.disabled = false; }
      });
      return add(n, note('A read-only summary of the replies, checks and permitted next actions. It grants no approval or closure.'), load, out);
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
        const conflicts = contradictions(data.contradicting_deliveries);
        if (conflicts) n.append(conflicts);
        if (typeof id === 'string' && id) n.append(actions(m, data, '/api/correspondence/claims/' + encodeURIComponent(id)));
        if (typeof id === 'string' && id && data.trace_url === '/api/correspondence/claims/' + id + '/trace')
          n.append(disputeRecord(m, '/api/correspondence/claims/' + encodeURIComponent(id) + '/trace'));
      }
      return n;
    }
    // Who recorded each lifecycle revision. Preparation scripts are never presented as a person's decision.
    function reviewHistory(data) {
      const rows = list(data.audit).filter(row => row && typeof row === 'object');
      if (!rows.length) return null;
      const box = add(el('div', undefined, 'v4-review'), el('h3', 'Review history'));
      const current = data.state === 'REVOKED' && !data.active_version ? 'Rolled back. No version is active.'
        : data.state === 'ACTIVE' && data.active_version ? 'Active version ' + shown(data.active_version) + '.'
        : 'Current state: ' + shown(data.state) + (data.active_version ? '; active version ' + shown(data.active_version) : '') + '.';
      box.append(note(current));
      const items = el('ol', undefined, 'v4-history');
      rows.forEach(row => items.append(add(el('li'), el('strong', 'Revision ' + shown(row.revision) + ' · ' + shown(row.kind)),
        note(shown(row.at) + ' · ' + (/^scripted-/.test(String(row.actor)) ? 'Scripted preparation (' + row.actor + ')' : 'Recorded under account ' + shown(row.actor))))));
      return add(box, items);
    }
    function vendor(m, data) {
      const id = data.vendor_id ?? data.id;
      const n = section(shown(data.name ?? data.vendor ?? id));
      add(n, provenance(data.sources), record({vendor_id:id, revision:data.revision, state:data.state, active_version:data.active_version, reviewer:data.reviewer}), reviewHistory(data), details('Rules, overlay, tests and reviewer versions', data));
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
    // Uptime selects the rule family (decision 97, D05). The client sends profile "auto" with the exact public
    // source and never names a family. Selection, proposals and candidates are not tests or approvals.
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
      STALE_CONTEXT:'the source or evaluator semantics changed after generation',
      REQUEST_CHANGED:'the configured transport changed after generation',
      NOT_CANONICAL:'not a canonical monthly source', RESOURCE_LANGUAGE_PRESENT:'contains resource-family language'};
    const reasonText = code => typeof code === 'string' && code ? (REASONS[code] || code) : 'no reason returned';
    const JOB_MESSAGES = {
      QUEUED:'Queued. The server calls the configured model once for this approved request; this page only reads status.',
      RUNNING:'Running. This page only reads status and never resends the request.',
      SUCCEEDED:'Validated against the exact public source. The proposal is unreviewed and not approved.',
      REFUSED:'Source validation refused the model output. No candidate can be created from it. A retry needs a new attempt identifier and its own approval.',
      CANCELLED:'Cancelled before completion. A retry needs a new attempt identifier and its own approval.',
      UNCERTAIN:'The outcome is uncertain, for example after an interrupted run. It is never retried automatically.'};
    const OUTCOMES = {
      SELECTED:'Uptime selected one rule family from the source. It can be staged as a SHADOW candidate; independent tests and a person’s approval remain required.',
      AMBIGUOUS:'More than one supported rule family fits this source. Uptime does not choose between readings, so no candidate can be staged.',
      NO_SUPPORTED_FAMILY:'No supported rule family represents this source. No candidate can be staged.',
      INCOMPLETE:'Selection is incomplete, so no candidate can be staged yet.',
      PENDING:'Family evaluations are running. This page only reads their status.',
      NOT_SUBMITTED:'Every family request for this exact source is approved and none has run yet.',
      APPROVAL_REQUIRED:'An operator must approve each family request for these exact bytes before any evaluation starts.',
      PROVIDER_UNCONFIGURED:'Proposal generation is not configured, and the offline parser cannot select a family for this source.'};
    const FAMILY_STATES = {VALIDATED:'validated the complete source', REFUSED_STRUCTURAL:'refused by a deterministic finding about the source',
      REFUSED_READING:'its reading of the source was refused', NOT_EVALUATED:'produced no grounded reading, so it was not evaluated',
      INCONCLUSIVE:'ended without a conclusive result', PENDING:'still running'};
    const RUNNING_STATES = ['QUEUED', 'RUNNING'];
    const schedule = typeof options.schedule === 'function' ? options.schedule : (callback, ms) => global.setTimeout(callback, ms);
    function generator(m) {
      const panel = section('Generate a public proposal');
      panel.append(note('Paste the exact public contract text. Uptime selects the rule family from the source itself. A canonical monthly source is recognized by the deterministic parser with no model call. Otherwise every supported family is evaluated by its own server-built request, each needing a separate operator approval of its exact bytes and called at most once. A proposal is not a candidate, a test result or an approval.'));
      const box = el('div', undefined, 'v4-form v4-generator');
      box.setAttribute('role','group'); box.setAttribute('aria-label','Public proposal request');
      const inputs = {vendor_id:field(box, 'vendor_id', 'Proposal vendor identifier'), name:field(box, 'name', 'Public document name'),
        uri:field(box, 'uri', 'Public document URI', 'url'),
        classification:field(box, 'classification', 'Public document origin', ['public','synthetic_public'])};
      inputs.attempt_nonce = field(box, 'attempt_nonce', 'Attempt identifier (change only for a separately approved retry)');
      inputs.attempt_nonce.value = 'initial';
      inputs.text = field(box, 'text', 'Exact public source text (sent exactly as entered)', 'textarea');
      inputs.text.rows = 12;
      const sourceFile = field(box, 'source_file', 'Import UTF-8 source file (optional)', 'file', false);
      sourceFile.accept = '.txt,text/plain';
      let fileText = null, fileDisplay = null;
      const state = {token:0, read:0, inflight:0, confirmed:null, lost:false, job:null, shown:null, polls:0,
        running:{}, selectedJob:null, offline:false, progress:null, round:0};
      const accessOut = el('div', undefined, 'v4-review'), jobOut = el('div', undefined, 'v4-review');
      const live = () => mounts.get(m.root) === m;
      const values = () => {
        // Textareas normalize line endings. Keep imported text separately until an explicit edit.
        if (fileText !== null && inputs.text.value !== fileDisplay) fileText = null;
        return {...Object.fromEntries(Object.entries(inputs).map(([key, input]) => [key, input.value])),
          text:fileText === null ? inputs.text.value : fileText};
      };
      const payload = v => ({document:{name:v.name, uri:v.uri, classification:v.classification, text:v.text},
        profile:'auto', attempt_nonce:v.attempt_nonce});
      const exact = v => JSON.stringify([v.vendor_id, payload(v)]);
      const vendorPath = id => '/api/vendors/' + encodeURIComponent(id);
      const valid = answer => !!answer && typeof answer === 'object' && typeof answer.outcome === 'string' && Array.isArray(answer.families);
      function problem(v) {
        if (Object.values(v).some(value => typeof value !== 'string' || value === '')) return 'Complete every proposal field. Source text is sent exactly as entered.';
        if (!/^[a-z0-9][a-z0-9_-]{0,79}$/.test(v.vendor_id)) return 'Use a lowercase vendor identifier of letters, digits, hyphens or underscores.';
        return '';
      }
      const check = button('Check generation access', () => checkAccess());
      const generate = button('Generate proposals', () => submitJob());
      const refresh = button('Refresh proposal status', () => checkAccess(true));
      function update() {
        const can = live() && writable(true) && state.inflight === 0, c = state.confirmed;
        check.disabled = !can;
        generate.disabled = !(can && c && c.outcome === 'NOT_SUBMITTED' && !state.lost && c.key === exact(values()));
        refresh.disabled = !(can && c && c.key === exact(values()));
      }
      function invalidate() {
        state.token++; state.confirmed = null; state.lost = false; state.job = null; state.shown = null; state.polls = 0;
        state.running = {}; state.selectedJob = null; state.offline = false; state.progress = null; state.round++;
        accessOut.replaceChildren(); disable(jobOut); jobOut.replaceChildren(); update();
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
        if (!live()) return;
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
      // The selection view's per-family refusal summary (codes, fixed explanations, exact passages, missing terms).
      // It is not the job projection's public-refusal-diagnostic/1 record; every value renders as text.
      function familyRefusal(value) {
        if (!value || typeof value !== 'object') return null;
        const box = add(el('div', undefined, 'v4-review v4-refusal'), el('h4', 'Why this family was refused'));
        list(value.explanations).filter(t => typeof t === 'string' && t).forEach(t => box.append(el('p', t)));
        list(value.passages).filter(t => typeof t === 'string' && t).forEach(t => box.append(el('blockquote', t), note('Public source passage')));
        const missing = list(value.missing_terms).filter(t => typeof t === 'string' && t);
        if (missing.length) box.append(note('Required terms not established by the source: ' + missing.join(', ') + '.'));
        return box;
      }
      function renderProgress() {
        if (!state.progress) return;
        const items = Object.entries(state.running);
        state.progress.replaceChildren(...items.map(([id, value]) => el('li', 'Proposal job ' + id + ': ' + shown(value))));
      }
      function selectionView(answer) {
        const selected = answer.selected && typeof answer.selected === 'object' ? answer.selected : null;
        const offline = answer.offline && typeof answer.offline === 'object' ? answer.offline : {};
        const n = add(el('div', undefined, 'v4-access v4-selection'), el('h3', 'Automatic rule-family selection'),
          el('p', OUTCOMES[answer.outcome] || 'Unrecognized selection outcome. No action is available.', 'v4-note v4-outcome'),
          record({outcome:answer.outcome, selected_family:selected ? selected.family : null,
            selection_method:selected ? selected.method : null,
            offline_parser:offline.accepted === true ? 'accepted the complete source' : reasonText(offline.reason),
            source_sha256:answer.source_sha256, selection_sha256:answer.selection_sha256}));
        const requirements = list(answer.review_requirements).filter(t => typeof t === 'string' && t);
        if (requirements.length) {
          const items = el('ul', undefined, 'v4-requirements');
          requirements.forEach(t => items.append(el('li', t)));
          add(n, el('h4', 'Review requirements'), items);
        }
        list(answer.families).filter(f => f && typeof f === 'object').forEach(f => {
          const job = f.job && typeof f.job === 'object' ? f.job : null;
          const row = add(el('div', undefined, 'v4-review v4-family'), el('h4', shown(f.label)),
            record({family:f.family, evaluation:f.state ? FAMILY_STATES[f.state] || f.state : 'not evaluated',
              request:f.enabled === true ? 'approved for these exact bytes' : reasonText(f.approval_reason),
              job_id:job ? job.job_id : null, job_status:job ? job.status : null, attempts:f.attempts}));
          if (f.disclosure && typeof f.disclosure === 'object') add(row, el('h4', 'Exact public transmission'), record(f.disclosure));
          // The verified per-family diagnostic carries exact offsets and SHA-256; the summary is the fallback.
          add(row, refusalDiagnostic(f.public_diagnostic, 'Why this family was refused') || familyRefusal(f.refusal));
          n.append(row);
        });
        state.progress = el('ul', undefined, 'v4-progress');
        n.append(state.progress, note('Each family request is built by the server and transmitted only after a separate operator approval of its exact bytes. The private customer overlay is never part of it. Selection grants no approval.'));
        return n;
      }
      function outcomeStatus(answer) {
        const first = list(answer.review_requirements).find(t => typeof t === 'string' && t);
        if (answer.outcome === 'NOT_SUBMITTED') return 'Generation is permitted for this exact request. Every supported rule family will be evaluated; review what will be transmitted, then choose Generate proposals.';
        if (answer.outcome === 'APPROVAL_REQUIRED' || answer.outcome === 'PROVIDER_UNCONFIGURED') return 'Generation is not available for this exact request: ' + (first || reasonText(answer.outcome));
        if (answer.outcome === 'PENDING') return 'Family evaluations are running. Status is read-only from here.';
        if (answer.outcome === 'SELECTED') {
          const chosen = list(answer.families).find(f => f && answer.selected && f.family === answer.selected.family);
          return 'Uptime selected the ' + shown(chosen ? chosen.label : answer.selected && answer.selected.family) + ' family. Review it, then stage it as a SHADOW candidate.';
        }
        return 'Selection outcome: ' + shown(answer.outcome) + '. No candidate can be staged; see the review requirements.';
      }
      function offlineCandidate(vendor, documentValue) {
        const n = el('div', undefined, 'v4-form v4-candidate');
        n.setAttribute('role','group'); n.setAttribute('aria-label','Attach private customer overlay');
        n.append(note('The deterministic parser established the monthly availability family from this exact source with no model call.'));
        const overlay = field(n, 'overlay', 'Private customer overlay for this proposal (JSON object; never sent for extraction)', 'textarea');
        const preview = el('div', undefined, 'v4-review');
        const path = vendorPath(vendor) + '/candidates';
        let reviewed = null;
        const token = state.token;
        const stillLive = () => live() && token === state.token && state.offline === true && state.confirmed?.outcome === 'SELECTED';
        const attach = button('Review shadow candidate request', async () => {
          if (!writable(true) || !stillLive()) return;
          let body;
          try { body = {document:documentValue, overlay:parseJSON(overlay.value, 'overlay')}; } catch (error) { status(m, error.message); return; }
          const exactBody = JSON.stringify([path, body]);
          if (reviewed !== exactBody) {
            reviewed = exactBody;
            preview.replaceChildren(el('h3', 'Review exact candidate request'), record({destination:path, overlay:body.overlay,
              document:{name:documentValue.name, uri:documentValue.uri, source_characters:documentValue.text.length}}),
              note('The server compiles this exact source with the deterministic parser, attaches the private overlay and stages a normal SHADOW candidate. Nothing is sent to a model. Independent tests and named approval remain required.'));
            attach.textContent = 'Confirm shadow candidate';
            status(m, 'Review the candidate request, then confirm. Editing the overlay requires another review.');
            return;
          }
          await mutate(m, path, body, undefined, true);
        });
        attach.draftAllowed = true; attach.stillCurrent = stillLive; attach.disabled = !writable(true); m.writes.push(attach);
        overlay.addEventListener('input', () => { reviewed = null; preview.replaceChildren(); attach.textContent = 'Review shadow candidate request'; });
        return add(n, preview, attach);
      }
      function candidate(vendor, job) {
        const n = el('div', undefined, 'v4-form v4-candidate');
        n.setAttribute('role','group'); n.setAttribute('aria-label','Attach private customer overlay');
        const overlay = field(n, 'overlay', 'Private customer overlay for this proposal (JSON object; never sent for extraction)', 'textarea');
        const preview = el('div', undefined, 'v4-review');
        const path = vendorPath(vendor) + '/proposal-jobs/' + encodeURIComponent(job.job_id) + '/candidate';
        let reviewed = null;
        const token = state.token;
        const candidateLive = () => live() && token === state.token && state.job?.job_id === job.job_id && state.selectedJob === job.job_id
          && state.shown === [job.job_id, 'SUCCEEDED', true].join(':');
        const attach = button('Review shadow candidate request', async () => {
          if (!writable(true) || !candidateLive()) return;
          let body;
          try { body = {overlay:parseJSON(overlay.value, 'overlay')}; } catch (error) { status(m, error.message); return; }
          const exactBody = JSON.stringify([path, body]);
          if (reviewed !== exactBody) {
            reviewed = exactBody;
            preview.replaceChildren(el('h3', 'Review exact candidate request'), record({destination:path, body}),
              note('The server attaches this private overlay to the immutable public proposal of job ' + job.job_id + ', which automatic selection chose, and stages a normal SHADOW candidate. Nothing is sent to the model. Independent tests, any source-meaning review and named approval remain required.'));
            attach.textContent = 'Confirm shadow candidate';
            status(m, 'Review the candidate request, then confirm. Editing the overlay requires another review.');
            return;
          }
          await mutate(m, path, body, undefined, true);
        });
        attach.draftAllowed = true; attach.stillCurrent = candidateLive; attach.disabled = !writable(true); m.writes.push(attach);
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
        if (job.candidate_available === true && job.job_id === state.selectedJob) n.append(candidate(vendor, job));
        else if (job.candidate_available === true) n.append(note('Automatic selection did not choose this job, so no candidate can be staged from it.'));
        else n.append(note('A candidate cannot be created from this result: ' + reasonText(job.refusal) + '.'));
        return n;
      }
      // A verified diagnostic from the server: fixed explanations, exact public passages and missing terms.
      // Every value is rendered as text. A refusal stays a refusal; nothing here offers a candidate.
      function refusalDiagnostic(value, heading = 'Why this proposal was refused') {
        if (!value || typeof value !== 'object' || value.schema !== 'public-refusal-diagnostic/1') return null;
        const box = add(el('div', undefined, 'v4-review v4-refusal'), el('h4', heading));
        list(value.issues).filter(issue => issue && typeof issue === 'object').forEach(issue => {
          const row = add(el('div', undefined, 'v4-refusal-issue'), el('p', shown(issue.explanation)));
          if (typeof issue.quote === 'string' && issue.quote) {
            row.append(el('blockquote', issue.quote),
              note('Public source passage' + (issue.block != null ? ' · block ' + shown(issue.block) : '')
                + (issue.start != null && issue.end != null ? ' · characters ' + shown(issue.start) + '–' + shown(issue.end) : '')
                + (issue.block_sha256 ? ' · SHA-256 ' + shown(issue.block_sha256) : '')));
          }
          box.append(row);
        });
        const missing = list(value.missing_terms).filter(term => typeof term === 'string' && term);
        if (missing.length) box.append(note('Required terms not established by the source: ' + missing.join(', ') + '.'));
        const doc = value.document && typeof value.document === 'object' ? value.document : {};
        box.append(note('Source: ' + shown(doc.name) + ' · ' + shown(doc.uri) + ' · SHA-256 ' + shown(value.source_sha256)),
          note('This refusal created no candidate, test or approval. A new attempt needs its own approval.'));
        return box;
      }
      function show(vendor, job) {
        const displayed = [job.job_id, job.status, job.candidate_available === true].join(':');
        if (state.shown === displayed) return; // Keep an overlay being typed for an already displayed result.
        state.shown = displayed;
        status(m, 'Proposal job ' + job.job_id + ' is ' + shown(job.status) + '. Status is read-only from here.');
        const n = add(el('div', undefined, 'v4-job'), el('h3', 'Proposal job'),
          record({job_id:job.job_id, status:job.status, reason:job.reason, request_sha256:job.request_sha256, context_sha256:job.context_sha256}),
          note(JOB_MESSAGES[job.status] || 'Unrecognized job status. No action is available.'));
        if (job.status === 'SUCCEEDED') n.append(proposal(vendor, job));
        if (job.status === 'REFUSED') { const d = refusalDiagnostic(job.public_diagnostic); if (d) n.append(d); }
        disable(jobOut); jobOut.replaceChildren(n);
      }
      function poll(job) {
        if (!RUNNING_STATES.includes(job.status) || state.polls >= 60) return;
        state.polls++;
        const token = state.token, id = job.job_id;
        schedule(() => token === state.token && live() && state.job && state.job.job_id === id ? loadJob() : undefined, 2500);
      }
      // Family evaluations are read with GET only. When all have finished, the person refreshes the selection.
      function pollFamilies(vendor, round = state.round) {
        if (round !== state.round) return;
        renderProgress();
        const ids = Object.keys(state.running).filter(id => RUNNING_STATES.includes(state.running[id]));
        if (!ids.length) {
          if (Object.keys(state.running).length) status(m, 'Every family evaluation has finished. Choose Refresh proposal status to see the selection; nothing is resent.');
          return;
        }
        if (state.polls >= 60) return;
        state.polls++;
        const token = state.token;
        schedule(async () => {
          if (token !== state.token || round !== state.round || !live()) return;
          for (const id of ids) {
            try {
              const job = await request(m, vendorPath(vendor) + '/proposal-jobs/' + encodeURIComponent(id));
              if (token !== state.token || round !== state.round || !live()) return;
              if (job && typeof job === 'object' && job.job_id === id && typeof job.status === 'string') state.running[id] = job.status;
            } catch (_) {
              if (token === state.token && live()) status(m, 'Proposal status is unavailable. Use Refresh proposal status; nothing was resent.');
              return;
            }
          }
          pollFamilies(vendor, round);
        }, 2500);
      }
      function follow(vendor, answer, body) {
        state.round++; state.running = {};
        list(answer.families).forEach(f => { if (f && f.job && typeof f.job.job_id === 'string') state.running[f.job.job_id] = f.job.status; });
        const selected = answer.selected && typeof answer.selected === 'object' ? answer.selected : null;
        if (answer.outcome === 'SELECTED' && selected?.method === 'deterministic_document_parser') {
          state.offline = true;
          jobOut.replaceChildren(offlineCandidate(vendor, body.document));
        } else if (answer.outcome === 'SELECTED' && selected?.method === 'public_proposal_job' && typeof selected.job_id === 'string') {
          state.selectedJob = selected.job_id; state.job = {vendor, job_id:selected.job_id};
          renderProgress();
          return loadJob();
        } else if (answer.outcome === 'PENDING') pollFamilies(vendor);
        else renderProgress();
      }
      async function loadJob() {
        if (!live() || !state.job) return;
        const {vendor, job_id} = state.job, token = state.token, read = ++state.read;
        try {
          const job = await request(m, vendorPath(vendor) + '/proposal-jobs/' + encodeURIComponent(job_id));
          if (token !== state.token || read !== state.read || !live() || !state.job || state.job.job_id !== job_id) return;
          if (!job || typeof job !== 'object' || job.job_id !== job_id) throw new Error('Mismatched proposal job.');
          show(vendor, job); poll(job);
        } catch (_) {
          if (token === state.token && read === state.read && live()) status(m, 'Proposal status is unavailable. Use Refresh proposal status; nothing was resent.');
        }
      }
      // A refresh of the same confirmed request re-reads the selection (read-only) without discarding a displayed
      // selected result or an overlay under review. Any field edit or a fresh check starts over.
      async function checkAccess(refreshing = false) {
        if ((refreshing ? refresh : check).disabled || !live()) return;
        const v = values(), message = problem(v);
        if (message) { status(m, message); return; }
        const key = exact(v), body = payload(v);
        const keep = refreshing && !!state.confirmed && state.confirmed.key === key;
        if (!keep) invalidate();
        const token = state.token;
        state.inflight++; update();
        if (!keep) status(m, 'Checking rule-family selection and generation access for these exact fields. Nothing is generated by this check.');
        try {
          const answer = await request(m, vendorPath(v.vendor_id) + '/proposal-access', body);
          if (token !== state.token || !live()) return;
          if (!valid(answer)) throw new Error('Malformed selection state.');
          const prior = state.confirmed;
          state.confirmed = {key, body, vendor:v.vendor_id, outcome:answer.outcome};
          accessOut.replaceChildren(selectionView(answer));
          const chosen = answer.outcome === 'SELECTED' && answer.selected && typeof answer.selected === 'object' ? answer.selected : null;
          const unchanged = keep && prior && prior.outcome === 'SELECTED' && chosen
            && (state.offline ? chosen.method === 'deterministic_document_parser' : state.selectedJob && chosen.job_id === state.selectedJob);
          if (unchanged) {
            renderProgress();
            if (state.selectedJob) await loadJob();
            return;
          }
          if (keep) { state.job = null; state.shown = null; state.selectedJob = null; state.offline = false; disable(jobOut); jobOut.replaceChildren(); }
          status(m, outcomeStatus(answer));
          await follow(v.vendor_id, answer, body);
        } catch (_) {
          if (token !== state.token || !live()) return;
          if (!keep) accessOut.replaceChildren();
          status(m, keep ? 'Proposal status is unavailable. Use Refresh proposal status; nothing was resent.'
            : 'Generation access could not be confirmed. Nothing was generated. Check the connection, then check access again.');
        } finally { state.inflight--; update(); }
      }
      async function submitJob() {
        if (generate.disabled || !live()) return;
        const c = state.confirmed;
        if (!c || c.key !== exact(values()) || c.outcome !== 'NOT_SUBMITTED' || state.lost) {
          invalidate(); status(m, 'The request changed after its access check. Check generation access again.'); return;
        }
        const token = state.token;
        state.inflight++; update();
        status(m, 'Reserving one proposal job per supported rule family for this exact approved request…');
        try {
          const answer = await request(m, vendorPath(c.vendor) + '/proposal-jobs', c.body);
          if (token !== state.token || !live()) return;
          if (!valid(answer)) throw new Error('Malformed selection state.');
          state.confirmed = {...c, outcome:answer.outcome};
          accessOut.replaceChildren(selectionView(answer));
          status(m, outcomeStatus(answer));
          await follow(c.vendor, answer, c.body);
        } catch (_) {
          if (token !== state.token || !live()) return;
          state.lost = true;
          status(m, 'The generation request did not complete reliably and may have been queued. Choose Check generation access to recover any existing jobs; nothing is resent automatically.');
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
        try { return await request(m, '/api/vendors/' + encodeURIComponent(id)); }
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
        // Decision D04-C: leave fields that do not apply blank; they are omitted, never sent as empty or null.
        const {claim_id, ...scope} = v; return {claim_id,scope:Object.fromEntries(Object.entries(scope).filter(([, x]) => x !== ''))};
      }, '/api/correspondence/claims'));
      m.body.append(note('Provisioned services deliver messages and evidence through CLI ingestion. Refresh to inspect receipts and available reviewer actions. Service credentials never belong in this browser.'));
      const items = Array.isArray(data) ? data : list(data.claims);
      items.forEach(item => {
        const id = typeof item === 'string' ? item : item.claim_id ?? item.id;
        const n = section(shown(id));
        if (typeof item === 'object') add(n, provenance(item.sources), record(item));
        if (typeof id === 'string' && id) n.append(button('Inspect case ' + id, () => active(m) && inspect(m.root, id)));
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
            if (typeof c.id === 'string' && typeof options.onCase === 'function') row.append(button('Inspect ' + c.id, () => active(m) && options.onCase(c.id)));
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
      unmount(root); mounts.set(root,m);
      const wrap = el('div', undefined, 'uptime-v4');
      const title = {vendors:'Vendor intake & versions',disputes:'Correspondence & disputes',portfolio:'Portfolio comparison',case:'Case inspector',catalog:'Advanced companion workflows'}[view];
      const refresh = button('Refresh server state', async () => {
        if (busy || !active(m)) return;
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
        const data = supplied === undefined ? await request(m, view === 'vendors' ? '/api/vendors' : view === 'disputes' ? '/api/correspondence/claims' : '') : supplied;
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
      const marker = {root};
      unmount(root); mounts.set(root,marker);
      root.replaceChildren(note('Loading correspondence case…'));
      try {
        const data = await request(marker, '/api/correspondence/claims/' + encodeURIComponent(id));
        if (mounts.get(root) !== marker) return;
        const m = await render(root,'case',data);
        if (!m || mounts.get(root) !== m) return;
        m.claimId = id;
        m.body.replaceChildren(inspector(m,data,true));
        m.body.prepend(button('Back to correspondence', () => active(m) && render(root,'disputes')), button('Refresh case receipts', () => active(m) && inspect(root,id)));
        uncertain = false; sync();
      } catch (_) {
        if (mounts.get(root) === marker) root.replaceChildren(note('Case unavailable. No changes were sent.'), button('Back to correspondence', () => active(marker) && render(root,'disputes')));
      }
    }
    return Object.freeze({render, inspect, unmount, refreshAccess: sync});
  }
  const api = Object.freeze({create, parseJSON});
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (global) global.UptimeV4 = api;
})(typeof window !== 'undefined' ? window : globalThis);
