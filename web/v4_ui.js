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
  // Server timestamps are shown as dates and times in UTC at the rendering boundary.
  const at = value => {
    const d = typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value) ? new Date(value) : null;
    if (!d || Number.isNaN(d.getTime())) return value;
    const month = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][d.getUTCMonth()];
    return `${month} ${d.getUTCDate()}, ${d.getUTCFullYear()}, ${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')} UTC`;
  };
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
    // A 64-character fingerprint is shown by its first ten characters wherever the exact value sits one click away.
    const short = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value) ? value.slice(0, 10) + '…' : value;
    const MONTH = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const day = value => { const d = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value)); return d && MONTH[Number(d[2]) - 1] ? MONTH[Number(d[2]) - 1] + ' ' + Number(d[3]) + ', ' + d[1] : value; };
    // A closed section: forms, histories and raw records stay one click away. A section a person opened stays open
    // when the page is drawn again after an action.
    const opened = new Set();
    function fold(key, title, ...children) {
      const n = add(el('details', undefined, 'v4-fold'), el('summary', title), ...children);
      if (opened.has(key)) n.open = true;
      n.addEventListener('toggle', () => { if (n.open) opened.add(key); else opened.delete(key); });
      return n;
    }
    // Short facts as label over value; absent values are left out, never shown as placeholders.
    function facts(pairs) {
      const n = el('dl', undefined, 'v4-facts');
      pairs.filter(([, value]) => value !== undefined && value !== null && value !== '').forEach(([name, value]) =>
        n.append(add(el('div'), el('dt', name), typeof value === 'object' ? add(el('dd'), value) : el('dd', value))));
      return n;
    }
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
    // What this account may do here, as the page's access helper reports it. A read-only page says so at the top;
    // the identity, enrollment and gate sit in a closed section at the foot.
    function accessNote() {
      const a = access();
      return a.canWrite === true ? 'Reviewer requests use the authenticated API client. The server checks each action.' : a.canDraft === true ? 'Signed local draft intake, independent tests and previews are available. Promotion and financial actions require their separate authorization.' : 'Read-only. An enrolled reviewer can sign in here to stage a local draft. After a page reload, sign out and sign in again to restore signing.';
    }
    const readOnly = () => access().canWrite !== true && access().canDraft !== true;
    function identity() {
      const a = access();
      return fold('access', 'Your access on this page', record({identity:a.identity, enrollment:a.enrollment, gate:a.gate}), readOnly() ? null : note(accessNote()));
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
      if (correspondence) return caseView(m, data);
      const n = section('Case evidence & financial references');
      const refs = {case_id:data.case_id ?? data.claim_id ?? data.id, receipt_id:data.receipt_id, packet_id:data.packet_id,
        memo_id:data.memo_id, credit_id:data.credit_id, bill_id:data.bill_id, application_id:data.application_id};
      add(n, record(refs), provenance(data.sources));
      add(n, el('h3', 'Decision & unknowns'), record(decisionRecord(data)));
      // Receipts, digests and evaluator traces stay exact but collapsed, one click away.
      for (const [title, value] of caseRecords(data)) add(n, details(title, value));
      add(n, details('Complete server case record', data));
      return n;
    }
    const decisionRecord = data => ({outcome:data.outcome, state:data.state ?? data.stage, unknowns:data.unknowns, missing:data.missing ?? data.preflight?.missing,
      owner:data.owner, filing_cutoff:at(data.filing_cutoff), next_contact:at(data.next_contact), financials:data.financials});
    const caseRecords = data => [['Event timeline', data.timeline ?? data.events],
      ['Evidence & receipts', {evidence:data.evidence, receipts:data.receipts, submissions:data.submissions, replies:data.replies}],
      ['Current and historical evaluation', {evaluation:data.evaluation ?? data.preflight, history:data.history, trace:data.trace}]];
    // Plain words for a claim's outcome, the same as on the Overview; any other code is shown as lower-case words.
    const OUTCOME_WORDS = {ELIGIBLE:'Eligible', INELIGIBLE:'Ineligible', INSUFFICIENT_EVIDENCE:'Needs evidence', UNKNOWN:'Needs evidence'};
    const OUTCOME_TONE = {ELIGIBLE:'ok', INSUFFICIENT_EVIDENCE:'warn', UNKNOWN:'warn'};
    const words = value => String(value).replaceAll('_', ' ').toLowerCase();
    const outcomePill = value => value == null ? null : el('span', OUTCOME_WORDS[value] || words(value), 'pill' + (OUTCOME_TONE[value] ? ' ' + OUTCOME_TONE[value] : ''));
    const stagePill = value => value == null ? null : el('span', words(value), 'pill');
    // A decimal string is shown with separators and never passes through a number. An absent amount stays absent.
    function money(amount, currency) {
      if (amount == null || amount === '') return null;
      const raw = String(amount);
      if (!/^-?\d+(\.\d+)?$/.test(raw)) return (currency ? currency + ' ' : '') + raw;
      const [whole, fraction] = raw.split('.');
      return (currency === 'USD' ? '$' : currency ? currency + ' ' : '') + whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + (fraction === undefined ? '' : '.' + fraction);
    }
    const LONG_MONTH = ['January','February','March','April','May','June','July','August','September','October','November','December'];
    const monthName = value => { const d = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(String(value)); return d ? LONG_MONTH[Number(d[2]) - 1] + ' ' + d[1] : value; };
    // The claim's own record of what happened, in order: when, what, and the actor exactly as the server names it.
    // A vendor reply is quoted under the event that delivered it, joined by the server's event identifier.
    function caseTimeline(data) {
      const rows = list(data.timeline).filter(row => row && typeof row === 'object' && (row.event != null || row.at != null));
      if (!rows.length) return null;
      const replies = new Map(list(data.replies).filter(r => r && typeof r === 'object' && typeof r.event_id === 'string' && typeof r.text === 'string').map(r => [r.event_id, r]));
      const items = el('ol', undefined, 'v4-timeline');
      rows.forEach(row => {
        const reply = typeof row.event_id === 'string' ? replies.get(row.event_id) : null;
        const refs = [row.event_id ? 'Event ' + row.event_id : null, row.receipt ? 'Receipt ' + row.receipt : null].filter(Boolean);
        items.append(add(el('li', undefined, 'v4-step' + (reply ? ' v4-step-reply' : '')), el('time', shown(at(row.at))),
          add(el('div', undefined, 'v4-step-body'),
            add(el('p', undefined, 'v4-step-head'), el('strong', shown(row.event)), row.actor == null ? null : el('span', 'Actor: ' + row.actor, 'v4-actor')),
            refs.length ? el('p', refs.join(' · '), 'v4-note') : null,
            reply ? add(el('div', undefined, 'v4-reply'), el('p', 'Vendor reply, as received', 'v4-cited'), el('blockquote', reply.text)) : null)));
      });
      return items;
    }
    // One claim: where it stands, what a reviewer may do, and its correspondence in order. Receipts, digests,
    // evaluation traces and the complete server record are one click away.
    function caseView(m, data) {
      const out = el('div', undefined, 'v4-case-view');
      const id = data.claim_id ?? data.id, key = 'case:' + id;
      const base = typeof id === 'string' && id ? '/api/correspondence/claims/' + encodeURIComponent(id) : null;
      if (typeof data.interpretation_review_url === 'string' && /^\/static\/interpretation\.html\?claim=inbox-[a-zA-Z0-9._-]+$/.test(data.interpretation_review_url)) {
        const review = el('a', 'Review unfamiliar vendor wording', 'v4-cta'); review.href = data.interpretation_review_url;
        out.append(add(el('section', undefined, 'v4-panel v4-callout'), el('h2', 'Vendor wording to review'),
          note('The review page uses your enrolled identity. Meaning review alone cannot file, close a denial or change money.'), review));
      }
      const conflicts = contradictions(data.contradicting_deliveries);
      if (conflicts) out.append(add(el('section', undefined, 'v4-panel'), conflicts));
      const scope = data.scope && typeof data.scope === 'object' ? data.scope : {};
      const told = value => typeof value === 'string' || typeof value === 'number' ? value : null;
      const wanted = data.requested_artifact && typeof data.requested_artifact === 'object' ? data.requested_artifact : null;
      const standing = add(section('Where this claim stands'), facts([['Stage', stagePill(data.stage ?? data.state)], ['Outcome', outcomePill(data.outcome)],
        ['Claim amount', money(data.amount, data.currency)], ['Filing cutoff', at(data.filing_cutoff)], ['Next contact', at(data.next_contact)],
        ['Requested document', wanted ? [told(wanted.type) == null ? null : words(wanted.type), told(wanted.ref)].filter(value => value != null).join(' · ') : null],
        ['Service', told(scope.service)], ['Invoice', told(scope.invoice)], ['Incident', told(scope.incident)], ['Account', told(scope.account)],
        ['Contract', told(scope.contract)], ['Receipt', told(data.receipt_id)], ['Bill', told(data.bill_id)], ['Credit', told(data.credit_id)], ['Application', told(data.application_id)]]));
      // Amounts this claim's correspondence establishes. This record does not post or apply credit; those two stages
      // belong to the ledger and are shown on the Overview. The record's own six values stay exact one click away.
      const ledger = data.ledger && typeof data.ledger === 'object' ? data.ledger : null;
      if (ledger) {
        const amounts = facts([['Estimated', money(ledger.estimated, data.currency)], ['Claimed', money(ledger.claimed, data.currency)],
          ['Awarded', money(ledger.awarded, data.currency)], ['Disputed remainder', money(ledger.disputed_remainder, data.currency)]]);
        amounts.className = 'v4-facts v4-amounts';
        if (amounts.children.length) standing.append(amounts, note('One claim at each stage of its correspondence. The amounts are not added together.'));
      }
      // Only the actions the server offers for this claim; the server checks each one again when it is pressed.
      if (base) add(standing, el('h3', 'Reviewer actions'), actions(m, data, base));
      out.append(standing);
      const steps = caseTimeline(data);
      if (steps) out.append(add(section('Correspondence, in order'), note('Each step with the actor the server recorded for it. Vendor replies are quoted exactly as received.'), steps));
      if (base && data.trace_url === '/api/correspondence/claims/' + id + '/trace') out.append(add(el('section', undefined, 'v4-panel'), disputeRecord(m, base + '/trace')));
      const records = el('div', undefined, 'v4-fold-group');
      add(records, fold(key + ':decision', 'Decision, unknowns and amounts as recorded', provenance(data.sources), record(decisionRecord(data))));
      for (const [title, value] of caseRecords(data)) records.append(fold(key + ':' + title, title, record(value)));
      records.append(fold(key + ':record', 'Complete server case record', record(data)));
      out.append(records);
      return out;
    }
    // A rule family's refusal summary (codes, fixed explanations, exact passages, missing terms). It is not the job
    // projection's public-refusal-diagnostic/1 record; every value renders as text. Shared by the proposal
    // generator and the review requirements.
    function familyRefusal(value) {
      if (!value || typeof value !== 'object') return null;
      const box = add(el('div', undefined, 'v4-review v4-refusal'), el('h4', 'Why this family was refused'));
      list(value.explanations).filter(t => typeof t === 'string' && t).forEach(t => box.append(el('p', t)));
      list(value.passages).filter(t => typeof t === 'string' && t).forEach(t => box.append(el('blockquote', t), note('Public source passage')));
      const missing = list(value.missing_terms).filter(t => typeof t === 'string' && t);
      if (missing.length) box.append(note('Required terms not established by the source: ' + missing.join(', ') + '.'));
      return box;
    }
    // Read-only review requirements for an adapter version (decisions 90 and 97). Loaded on request; no action control.
    const ELEMENT_NAMES = {source_clauses:'Source clauses', eligible_fee:'Eligible fee', evidence:'Evidence',
      exclusions:'Exclusions', deadline:'Claim deadline', submission_channel:'Submission channel'};
    const ELEMENT_STATUS = {PRESENT:'stated in the source', FAMILY_DEFINED:'defined by the adapter family',
      NONE_STATED:'none stated in the source', REVIEW_REQUIRED:'review required'};
    const SELECTION_METHOD = {deterministic_document_parser:'deterministic document parser', public_proposal_job:'public proposal job'};
    const lower = value => value == null ? 'Not provided' : String(value).replaceAll('_', ' ').toLowerCase();
    const cents = value => Number.isSafeInteger(value) ? (value < 0 ? '-' : '') + 'USD ' + Math.trunc(Math.abs(value) / 100) + '.'
      + String(Math.abs(value) % 100).padStart(2, '0') : 'Not provided';
    function requirementsView(r, citations, key = 'requirements') {
      const card = r.card && typeof r.card === 'object' ? r.card : {};
      const quotes = new Map(list(citations).filter(c => c && typeof c === 'object').map(c => [c.id, c.quote]));
      const out = add(el('div', undefined, 'v4-requirements-card'), note('Read only. These requirements grant no approval, activation or dispatch.'));
      // What the source establishes, element by element: its status in words on the left, each cited clause on the
      // right, in view and untrimmed. Typed values, reviewer tasks, the family choice and fingerprints are one click away.
      const elements = el('ul', undefined, 'v4-elements'), typed = [];
      list(card.elements).filter(e => e && typeof e === 'object').forEach(e => {
        const fallback = label(String(e.element)), name = ELEMENT_NAMES[e.element] || fallback.charAt(0).toUpperCase() + fallback.slice(1);
        const term = add(el('div', undefined, 'v4-element-term'), el('strong', name + ': ' + (ELEMENT_STATUS[e.status] || lower(e.status))));
        if (typeof e.requirement === 'string' && e.requirement) term.append(el('p', e.requirement, 'v4-requirement'));
        const ids = list(e.citations).filter(id => id !== null && id !== undefined), cited = el('div', undefined, 'v4-element-quotes');
        if (ids.length) {
          term.append(el('p', 'Cited clauses ' + ids.map(String).join(', '), 'v4-cited'));
          ids.forEach(id => { const q = quotes.get(id); cited.append(typeof q === 'string' && q ? el('blockquote', q) : note('Clause ' + shown(id) + ' text not returned.')); });
        }
        if (e.detail && typeof e.detail === 'object' && Object.keys(e.detail).length) typed.push(add(el('div', undefined, 'v4-typed'), el('h4', name + ': typed values'), record(e.detail)));
        elements.append(add(el('li', undefined, 'v4-element v4-is-' + String(e.status).toLowerCase().replace(/[^a-z_]/g, '')), term, ids.length ? cited : null));
      });
      out.append(elements.children.length ? elements : note('No elements returned.'));
      const more = [record({family:card.family, supported:card.supported === true ? 'yes' : 'no',
        open_requirements:card.no_open_requirements === true ? 'none' : 'see below', source_sha256:card.source_sha256}), ...typed];
      const todo = list(card.review_requirements).filter(t => typeof t === 'string' && t);
      if (todo.length) { const items = el('ul', undefined, 'v4-requirements'); todo.forEach(t => items.append(el('li', t))); more.push(el('h4', 'What a reviewer must still do'), items); }
      const selection = r.family_selection && typeof r.family_selection === 'object' ? r.family_selection : null;
      if (selection) {
        const box = add(el('div', undefined, 'v4-review'), el('h4', 'How the rule family was chosen'));
        if (selection.outcome === 'NOT_AUTOMATIC') box.append(note('This version was not chosen by automatic family selection.'));
        else {
          const chosen = selection.selected && typeof selection.selected === 'object' ? selection.selected : null;
          box.append(note('Outcome: ' + lower(selection.outcome) + (chosen ? '. Selected ' + shown(chosen.family) + ' by '
            + (SELECTION_METHOD[chosen.method] || lower(chosen.method)) + '.' : '.')));
          list(selection.families).filter(f => f && typeof f === 'object').forEach(f => {
            box.append(add(el('div', undefined, 'v4-family'), el('strong', shown(f.label ?? f.family) + ': ' + lower(f.state)), familyRefusal(f.refusal)));
          });
        }
        const why = list(selection.review_requirements).filter(t => typeof t === 'string' && t);
        if (why.length) { const items = el('ul', undefined, 'v4-requirements'); why.forEach(t => items.append(el('li', t))); box.append(items); }
        more.push(box);
      }
      const drafts = r.drafts && typeof r.drafts === 'object' ? r.drafts : null;
      if (drafts) {
        const box = add(el('details', undefined, 'v4-detail v4-drafts'), el('summary', 'Generated drafts (not independent tests; placeholder fee)'));
        if (typeof drafts.notice === 'string' && drafts.notice) box.append(note(drafts.notice));
        if (drafts.generated !== true) box.append(note('No drafts were generated: ' + shown(drafts.reason) + '.'));
        else {
          const table = el('table'), body = el('tbody');
          add(table, add(el('thead'), add(el('tr'), ...['Scenario', 'Derived outcome', 'Derived amount', 'Placeholder fee', 'Clauses'].map(t => { const th = el('th', t); th.scope = 'col'; return th; }))), body);
          list(drafts.scenarios).filter(d => d && typeof d === 'object').forEach(d => body.append(add(el('tr'),
            add(el('td'), el('span', shown(d.name)), typeof d.derivation === 'string' ? note(d.derivation) : null),
            el('td', lower(d.derived?.outcome)), el('td', d.derived?.amount == null ? 'Not determined' : 'USD ' + shown(d.derived.amount)),
            el('td', cents(d.placeholder_fee_cents)), el('td', list(d.citations).map(String).join(', ') || 'None'))));
          box.append(add(el('div', undefined, 'v4-scroll'), table));
        }
        more.push(box);
      }
      const overlap = r.draft_overlap && typeof r.draft_overlap === 'object' ? r.draft_overlap : null;
      if (overlap && typeof overlap.warning === 'string' && overlap.warning) {
        const reused = list(overlap.tests_reusing_draft_facts).filter(t => typeof t === 'string' && t);
        more.push(add(el('div', undefined, 'v4-review v4-overlap'), el('h4', 'Draft overlap'), note(overlap.warning),
          reused.length ? note('Tests reusing draft facts: ' + reused.join(', ') + '.') : null));
      }
      return add(out, fold(key, 'Typed values, reviewer tasks and how the rule family was chosen', ...more));
    }
    // Shown on request only where a vendor's detail carries no source manifest; otherwise the requirements are read
    // with the vendor and shown on its card.
    function requirementsPanel(m, base, citations, key) {
      const n = add(el('div', undefined, 'v4-review'), el('h3', 'Review requirements'),
        note('What the source establishes for this adapter version, what a reviewer must still do, and how its rule family was chosen.'));
      const out = el('div'); out.setAttribute('aria-live', 'polite');
      const load = button('Show review requirements', async () => {
        if (!active(m)) return;
        load.disabled = true; out.replaceChildren(note('Loading review requirements…'));
        try {
          const r = await request(m, base + '/requirements');
          if (active(m)) out.replaceChildren(r && typeof r === 'object' ? requirementsView(r, citations, key) : note('Review requirements unavailable. Nothing was changed.'));
        } catch (error) {
          if (active(m)) out.replaceChildren(note(error?.status === 401 ? 'Sign in again to read the review requirements.' : 'Review requirements unavailable. Nothing was changed.'));
        } finally { load.disabled = false; }
      });
      return add(n, load, out);
    }
    // Who recorded each lifecycle revision, exactly as the server names the account. Preparation scripts are never
    // presented as a person's decision. The summary stays in view; every revision is one click away.
    const actorLabel = actor => /^scripted-/.test(String(actor)) ? 'Scripted preparation (' + actor + ')' : 'Recorded under account ' + shown(actor);
    function reviewSteps(data, key) {
      const rows = list(data.audit).filter(row => row && typeof row === 'object');
      if (!rows.length) return null;
      const box = add(el('div', undefined, 'v4-review v4-review-steps'), el('h3', 'Review steps'));
      const actors = new Map();
      rows.forEach(row => { const name = actorLabel(row.actor); actors.set(name, (actors.get(name) || 0) + 1); });
      const who = el('ul', undefined, 'v4-actors');
      actors.forEach((count, name) => who.append(add(el('li'), el('strong', name), el('span', count + (count === 1 ? ' step' : ' steps')))));
      const last = rows[rows.length - 1];
      const items = el('ol', undefined, 'v4-history');
      rows.forEach(row => items.append(add(el('li'), el('strong', 'Revision ' + shown(row.revision) + ' · ' + shown(row.kind)),
        note(shown(at(row.at)) + ' · ' + actorLabel(row.actor)))));
      return add(box, who, note('Latest: ' + shown(last.kind) + ' · ' + shown(at(last.at))),
        fold(key, 'Review history (' + rows.length + (rows.length === 1 ? ' step' : ' steps') + ')', items));
    }
    // Whether an agreement is in force, in plain words from two server fields: the state and the active version.
    function stateSentence(data) {
      const version = shown(short(data.active_version));
      return data.state === 'REVOKED' && !data.active_version ? 'Rolled back. No version is active.'
        : data.state === 'ACTIVE' && data.active_version ? 'Active version ' + version + '.'
        : 'Current state: ' + shown(data.state) + (data.active_version ? '; active version ' + version : '') + '.';
    }
    const STATE_TONE = {ACTIVE:'ok', APPROVED:'accent', SHADOW:'warn', REVIEW_REQUIRED:'warn'};
    // ---- A proposal job as the server reports it ----
    // In view: job id, state, reason, the model actually used and its times, each only when the server supplies it.
    // Every digest and the session sit in one closed "Request details" disclosure, exact and one click away.
    const compact = fields => { Object.keys(fields).forEach(key => { if (fields[key] === undefined || fields[key] === null || fields[key] === '') delete fields[key]; }); return fields; };
    const JOB_TONE = {SUCCEEDED:'ok', REFUSED:'bad', UNCERTAIN:'warn', QUEUED:'accent', RUNNING:'accent'};
    function jobFacts(job) {
      const provider = job.provider && typeof job.provider === 'object' ? job.provider : {};
      const proposal = job.status === 'SUCCEEDED' && job.proposal && typeof job.proposal === 'object' ? job.proposal : {};
      const n = facts([['Job', job.job_id],
        ['Status', job.status == null ? null : el('span', job.status, 'pill' + (JOB_TONE[job.status] ? ' ' + JOB_TONE[job.status] : ''))],
        ['Reason', job.reason], ['Model', provider.model || proposal.model],
        ['Submitted', at(job.submitted_at)], ['Started', at(job.started_at)], ['Finished', at(job.finished_at)]]);
      n.className = 'v4-facts v4-inline';
      return n;
    }
    function requestDetails(job) {
      const provider = job.provider && typeof job.provider === 'object' ? job.provider : {};
      const p = job.status === 'SUCCEEDED' && job.proposal && typeof job.proposal === 'object' ? job.proposal : {};
      return compact({request_sha256:job.request_sha256, context_sha256:job.context_sha256, profile:p.profile,
        attempt_nonce:p.attempt_nonce, source_sha256:p.source_sha256, proposal_sha256:p.proposal_sha256, proposal_model:p.model,
        session:p.session || provider.session});
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
    // Each proposed term beside its exact sentence and typed value. The document name and URI are shown as sent.
    function proposalView(job) {
      const p = job.proposal && typeof job.proposal === 'object' ? job.proposal : {};
      const doc = p.document && typeof p.document === 'object' ? p.document : {};
      const source = facts([['Document', doc.name], ['URI', doc.uri]]); source.className = 'v4-facts v4-inline';
      const n = add(el('div', undefined, 'v4-proposal'), el('h3', 'Proposed public clauses'), source);
      // A typed value on one line: the same JSON, with a space where pretty-printing would break the line.
      const typed = value => value === undefined ? null : JSON.stringify(value, null, 1).replace(/\n\s*/g, ' ');
      const rows = el('ol', undefined, 'v4-clauses');
      list(p.clauses).forEach(clause => {
        if (!clause || typeof clause !== 'object') return;
        rows.append(add(el('li', undefined, 'v4-clause'),
          el('span', typeof clause.field === 'string' ? label(clause.field) : 'unlabeled', 'v4-clause-field'),
          el('blockquote', typeof clause.quote === 'string' ? clause.quote : null, 'v4-quote'),
          el('pre', typed(clause.value), 'v4-value')));
      });
      if (!rows.children.length) rows.append(el('li', 'No validated clauses returned.'));
      const heads = add(el('p', undefined, 'v4-clause-head'), el('span', 'Term'), el('span', 'Exact sentence in the source'), el('span', 'Proposed value'));
      heads.setAttribute('aria-hidden', 'true');
      return add(n, heads, rows, note('Quotes are exact slices of the public source and remain untrusted text. This proposal is unreviewed: it has no tests, approval or customer scope.'));
    }
    function jobView(job, heading) {
      return add(el('div', undefined, 'v4-job'), el('h3', heading), jobFacts(job),
        el('p', JOB_MESSAGES[job.status] || 'Unrecognized job status. No action is available.', 'v4-note v4-job-message'),
        details('Request details', requestDetails(job)));
    }
    // One agreement: its name and state, whether it is in force, the proposal job behind it when there is one, what
    // its source establishes with each cited clause, and who performed the review steps. Forms, version actions and
    // the full record are one click away.
    function vendor(m, data, extras = {}) {
      const id = data.vendor_id ?? data.id;
      const n = el('section', undefined, 'v4-panel v4-vendor');
      const tone = STATE_TONE[data.state];
      n.append(add(el('div', undefined, 'v4-vendor-head'), el('h2', shown(data.name ?? data.vendor ?? id)),
        typeof data.state === 'string' && data.state ? el('span', data.state, 'pill' + (tone ? ' ' + tone : '')) : null));
      if (typeof data.state === 'string' && data.state) {
        const force = data.state === 'ACTIVE' && data.active_version ? 'In force in this workspace.'
          : data.active_version ? 'An earlier version is in force; this revision is not.' : 'Not in force.';
        n.append(add(el('p', undefined, 'v4-force' + (force === 'In force in this workspace.' ? ' v4-in-force' : '')), el('strong', force), el('span', stateSentence(data))));
      }
      const overlay = data.overlay && typeof data.overlay === 'object' ? data.overlay : {};
      const manifest = data.manifest && typeof data.manifest === 'object' ? data.manifest : {};
      const doc = manifest.document && typeof manifest.document === 'object' ? manifest.document : {};
      const extraction = data.extraction && typeof data.extraction === 'object' ? data.extraction : {};
      const told = value => typeof value === 'string' || typeof value === 'number' ? value : null;
      n.append(facts([['Agreement', told(overlay.agreement) ?? told(manifest.agreement)],
        ['Covers', [told(overlay.product), told(overlay.plan)].filter(value => value != null).join(' · ')],
        ['Account', told(overlay.account)],
        ['In effect', told(overlay.effective_from) == null ? null : day(overlay.effective_from) + (told(overlay.effective_until) == null ? '' : ' – ' + day(overlay.effective_until))],
        ['Source document', told(doc.name)],
        ['Source read by', told(extraction.method) == null ? null : lower(extraction.method) + (told(extraction.model) == null ? '' : ' · ' + extraction.model)],
        ['Revision', told(data.revision)],
        ['Reviewer', typeof data.reviewer === 'string' && data.reviewer ? data.reviewer + (typeof data.reviewer_kind === 'string' ? ' (' + lower(data.reviewer_kind) + ')' : '') : null]]));
      if (typeof id !== 'string' || !id) { n.append(note('Vendor ID missing; actions unavailable.')); return n; }
      const base = '/api/vendors/' + encodeURIComponent(id), key = 'vendor:' + id;
      if (data.detail_unavailable) { n.append(note('Vendor details unavailable. Refresh before reviewing or changing this version.')); return n; }
      // The proposal job this version was staged from, directly under the vendor.
      if (extras.job && typeof extras.job === 'object') {
        const card = jobView(extras.job, 'Model proposal job');
        if (extras.job.status === 'SUCCEEDED') card.append(proposalView(extras.job));
        if (extras.job.status === 'REFUSED') { const d = refusalDiagnostic(extras.job.public_diagnostic); if (d) card.append(d); }
        n.append(card);
      } else if (extras.jobUnavailable) n.append(note('The proposal job behind this version could not be read with this account. Nothing was changed.'));
      const cited = manifest.citations;
      if (extras.requirements && typeof extras.requirements === 'object')
        n.append(add(el('div', undefined, 'v4-establishes'), el('h3', 'What the source establishes'), requirementsView(extras.requirements, cited, key + ':requirements')));
      else if (extras.requirementsUnavailable) n.append(note('Review requirements unavailable. Nothing was changed.'));
      add(n, reviewSteps(data, key + ':history'));
      const tools = [provenance(data.sources)];
      if (!extras.requirements && !extras.requirementsUnavailable && data.revision != null) tools.push(requirementsPanel(m, base, cited, key + ':requirements'));
      tools.push(el('h3', 'Version actions'), actions(m, data, base));
      if (data.revision !== undefined && data.revision !== null) {
        if (data.semantic_review_requirements) {
          tools.push(note('Before pricing, a named reviewer must check the complete source, conditions, overrides, exact evidence representations and customer scope. Existing tests or approvals do not supply this review.'));
          tools.push(form(m, 'Source meaning and evidence bindings', [['review','Explicit semantic review (JSON object; source pins, every block and literal selection)','textarea']], 'Record semantic review', v => ({revision:data.revision,review:parseJSON(v.review,'review')}), base + '/semantic-bindings'));
        }
        if (data.semantic_binding) tools.push(form(m, 'Revoke source meaning review', [], 'Revoke semantic binding', () => ({revision:data.revision}), base + '/semantic-bindings/revoke'));
        tools.push(form(m, 'Independent tests & shadow evidence', [ ['tests','Test cases (JSON array: name, facts, expected)', 'textarea'] ], 'Submit independent tests', v => ({revision:data.revision,tests:parseJSON(v.tests,'tests')}), base + '/tests', true));
        tools.push(form(m, 'Local shadow preview', [['facts','Shadow facts (JSON object)','textarea']], 'Preview candidate', v => ({revision:data.revision,facts:parseJSON(v.facts,'facts')}), base + '/shadow-preview', true));
      }
      tools.push(form(m, 'Evaluate the active adapter', [['facts','Contract-scoped facts (JSON object)', 'textarea']], 'Evaluate into a case', v => ({facts:parseJSON(v.facts,'facts')}), base + '/evaluate'));
      tools.push(note('Facts require agreement, account, product, plan, month, eligible_downtime_minutes, monitor_source, month_complete, exclusions_removed, monthly_fee_cents, fee_line_ref, received_at, monitor_ref and fee_ref. Use observed values and explicit provenance.'));
      tools.push(note('Evaluation uses the current server-approved adapter. Rollback affects new dispatch; historical cases retain their recorded version.'));
      tools.push(details('Rules, overlay, tests and reviewer versions', data));
      n.append(fold(key + ':tools', 'Review tools, version actions and the full record', ...tools));
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
      // The shared proposal view, plus the one control this form adds: staging the job automatic selection chose.
      function proposal(vendor, job) {
        const n = proposalView(job);
        if (job.candidate_available === true && job.job_id === state.selectedJob) n.append(candidate(vendor, job));
        else if (job.candidate_available === true) n.append(note('Automatic selection did not choose this job, so no candidate can be staged from it.'));
        else n.append(note('A candidate cannot be created from this result: ' + reasonText(job.refusal) + '.'));
        return n;
      }
      function show(vendor, job) {
        const displayed = [job.job_id, job.status, job.candidate_available === true].join(':');
        if (state.shown === displayed) return; // Keep an overlay being typed for an already displayed result.
        state.shown = displayed;
        status(m, 'Proposal job ' + job.job_id + ' is ' + shown(job.status) + '. Status is read-only from here.');
        const n = jobView(job, 'Proposal job');
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
      // Each agreement is read once before the page is drawn, so nothing shifts in afterwards: its detail, then its
      // requirements when the detail carries a source manifest, then the proposal job it was staged from when it has
      // one. All three are read-only GETs.
      const items = await Promise.all(summaries.map(async item => {
        const id = item.vendor_id ?? item.id;
        let detail = item;
        if (!Array.isArray(item.actions) && typeof id === 'string' && id) {
          try { detail = await request(m, '/api/vendors/' + encodeURIComponent(id)); }
          catch (_) { return {detail:{...item, detail_unavailable:true}, extras:{}}; }
        }
        const extras = {};
        if (typeof id !== 'string' || !id || !detail || typeof detail !== 'object') return {detail, extras};
        const base = '/api/vendors/' + encodeURIComponent(id);
        if (detail.manifest && typeof detail.manifest === 'object' && detail.revision != null) {
          try { extras.requirements = await request(m, base + '/requirements'); } catch (_) { extras.requirementsUnavailable = true; }
        }
        const job = detail.extraction && typeof detail.extraction === 'object' ? detail.extraction.proposal_job : null;
        if (job && typeof job === 'object' && typeof job.job_id === 'string' && job.job_id) {
          try { extras.job = await request(m, base + '/proposal-jobs/' + encodeURIComponent(job.job_id)); } catch (_) { extras.jobUnavailable = true; }
        }
        return {detail, extras};
      }));
      if (mounts.get(m.root) !== m) return;
      const cards = items.map(item => vendor(m, item.detail, item.extras));
      // With more than one agreement, the first lines of the page name them all; each name moves to its card.
      if (cards.length > 1) {
        const index = el('nav', undefined, 'v4-index'); index.setAttribute('aria-label', 'Agreements on this page');
        cards.forEach((card, i) => {
          const detail = items[i].detail, heading = card.children[0].children[0];
          heading.tabIndex = -1;
          const jump = button(shown(detail.name ?? detail.vendor ?? detail.vendor_id ?? detail.id), () => {
            if (typeof card.scrollIntoView === 'function') card.scrollIntoView({block:'start'});
            if (typeof heading.focus === 'function') heading.focus();
          });
          if (typeof detail.state === 'string' && detail.state) jump.append(el('span', detail.state, 'pill' + (STATE_TONE[detail.state] ? ' ' + STATE_TONE[detail.state] : '')));
          index.append(jump);
        });
        m.body.append(index);
      }
      cards.forEach(card => m.body.append(card));
      if (!items.length) m.body.append(note('No vendors returned. No example vendor has been selected.'));
      // Adding an agreement: the model-assisted proposal form and the local deterministic intake, closed until wanted.
      m.body.append(fold('add', 'Add an agreement', generator(m), form(m, 'Local deterministic intake', [
        ['vendor_id','Vendor identifier'], ['name','Document name'], ['uri','Public source URI','url'],
        ['classification','Document origin',['public','synthetic_public']], ['text','Public contract excerpt or full text','textarea'],
        ['overlay','Private customer overlay (JSON object)','textarea']
      ], 'Stage local candidate', v => ({document:{name:v.name,uri:v.uri,classification:v.classification,text:v.text},overlay:parseJSON(v.overlay,'overlay')}), v => '/api/vendors/' + encodeURIComponent(v.vendor_id) + '/candidates', true),
        note('Local intake validates supported wording with the built-in deterministic parser. It does not call a model.'),
        note('Public terms and private customer scope remain separate. Unsupported clauses and missing evidence must remain explicit in the server decision.'),
        note('Overlay fields: agreement, account, product, plan, effective_from, effective_until, fee_line_ref and currency. Include only customer scope supported by the governing agreement.')));
    }
    // A table that reads as stacked rows on a narrow screen; explicit roles keep its meaning when the layout changes.
    function sheet(titles, numeric = []) {
      const table = el('table', undefined, 'stack'), head = el('thead'), headRow = el('tr'), body = el('tbody');
      table.setAttribute('role', 'table'); head.setAttribute('role', 'rowgroup'); headRow.setAttribute('role', 'row'); body.setAttribute('role', 'rowgroup');
      titles.forEach((title, index) => {
        // A column of links has no visible heading; it is named for assistive technology.
        const th = el('th', title || undefined, numeric.includes(index) ? 'num' : undefined); th.scope = 'col'; th.setAttribute('role', 'columnheader');
        if (!title) th.setAttribute('aria-label', 'Open');
        headRow.append(th);
      });
      add(table, add(head, headRow), body);
      const row = (...cells) => {
        const tr = el('tr'); tr.setAttribute('role', 'row');
        cells.forEach((cell, index) => { cell.setAttribute('role', 'cell'); if (index && titles[index]) cell.setAttribute('data-label', titles[index]); tr.append(cell); });
        body.append(tr);
      };
      return {table, row};
    }
    function disputes(m, data) {
      const items = Array.isArray(data) ? data : list(data.claims);
      if (items.length) {
        const cases = sheet(['Case', 'Service month', 'Stage', 'Outcome', 'Claim amount', ''], [4]);
        items.forEach(item => {
          const id = typeof item === 'string' ? item : item.claim_id ?? item.id;
          const claim = item && typeof item === 'object' ? item : {};
          const scope = claim.scope && typeof claim.scope === 'object' ? claim.scope : {};
          const usable = typeof id === 'string' && id;
          // The case opens by route, so the address names it and Back returns to this list.
          const link = (text, cls) => { const a = el('a', text, cls); a.href = '#cases/' + encodeURIComponent(id); return a; };
          const name = add(el('td'), usable ? link(shown(claim.title ?? id), 'v4-case-title') : el('span', shown(claim.title ?? id)),
            el('p', [claim.vendor, claim.title == null ? null : id].filter(value => value != null).join(' · '), 'v4-note'));
          // An ineligible claim owes no credit: a determined outcome, not an unknown amount.
          const amount = claim.amount == null && claim.outcome === 'INELIGIBLE' ? 'No credit' : money(claim.amount, claim.currency) ?? 'Not determined';
          const open = el('td', undefined, 'v4-open'); if (usable) { const go = link('Open case', 'v4-open-link'); go.setAttribute('aria-label', 'Open case ' + id); open.append(go); }
          cases.row(name, el('td', scope.month == null ? 'Not provided' : monthName(scope.month)), add(el('td', undefined, 'tag'), stagePill(claim.stage ?? claim.state) || el('span', 'Not provided')),
            add(el('td'), outcomePill(claim.outcome) || el('span', 'Not provided')), el('td', amount, 'num'), open);
        });
        m.body.append(add(el('section', undefined, 'v4-panel v4-cases'), add(el('div', undefined, 'v4-scroll'), cases.table)));
      } else m.body.append(note('No correspondence cases returned.'));
      const tools = el('div', undefined, 'v4-fold-group');
      tools.append(fold('cases:setup', 'Set up a correspondence case', form(m, 'Set up a correspondence case', [ ['claim_id','Claim identifier (inbox- prefix)'], ...['account','vendor','contract','service','component','invoice','incident','currency','month','region'].map(k => [k,label(k)]) ], 'Create scoped case', v => {
        // Decision D04-C: leave fields that do not apply blank; they are omitted, never sent as empty or null.
        const {claim_id, ...scope} = v; return {claim_id,scope:Object.fromEntries(Object.entries(scope).filter(([, x]) => x !== ''))};
      }, '/api/correspondence/claims'),
        note('Provisioned services deliver messages and evidence through CLI ingestion. Refresh to inspect receipts and available reviewer actions. Service credentials never belong in this browser.')));
      // The complete server record of each case (hashes, trace, evaluation), exact and one click away.
      const full = items.filter(item => item && typeof item === 'object');
      if (full.length) tools.append(fold('cases:records', 'Complete record of each case (' + full.length + ')', ...full.map(item =>
        add(el('details', undefined, 'v4-detail'), el('summary', shown(item.claim_id ?? item.id)), provenance(item.sources), record(item)))));
      m.body.append(tools);
    }
    // One figure of a cohort as the server labels it: its value and note in view, the whole record one click away.
    function figure(metric) {
      return add(el('div', undefined, 'v4-figure'), el('p', shown(metric.label ?? metric.key), 'v4-figure-label'),
        el('p', shown(metric.value), 'v4-figure-value'), metric.note == null ? null : note(metric.note), details('Full record', metric));
    }
    function portfolio(m, data) {
      const grid = el('div', undefined, 'v4-grid v4-cohorts');
      for (const [key, title] of [['portfolio','Portfolio'],['seeded','Seeded comparison']]) {
        const cohort = data[key]; const n = section(title);
        if (!cohort) n.append(note('Cohort not provided.'));
        else {
          add(n, note(shown(cohort.label)), provenance(cohort.sources));
          const metrics = cohort.metrics;
          // The server's list of labelled figures reads as a list; any other shape is shown as the record it is.
          if (Array.isArray(metrics) && metrics.length && metrics.every(x => x && typeof x === 'object' && !Array.isArray(x) && 'value' in x)) {
            n.append(add(el('div', undefined, 'v4-figures'), ...metrics.map(figure)));
          } else n.append(record(metrics));
          const cases = list(cohort.cases);
          if (cases.length) n.append(el('h3', 'Cases in this cohort (' + cases.length + ')'));
          cases.forEach(c => {
            const row = el('div', undefined, 'v4-case');
            if (c && typeof c === 'object' && !Array.isArray(c)) {
              // Stage and outcome are the server's own words; an absent amount is not a zero.
              add(row, add(el('div', undefined, 'v4-case-head'), el('strong', shown(c.title ?? c.id)),
                el('span', c.amount == null ? 'Not determined' : money(c.amount, c.currency) ?? shown(c.amount), 'v4-case-amount')),
                note([c.vendor, c.title == null ? null : c.id].filter(value => value != null).join(' · ')),
                add(el('div', undefined, 'v4-case-tags'), c.outcome == null ? null : el('span', c.outcome, 'pill'), c.stage == null ? null : el('span', c.stage, 'pill')),
                details('Full record', c));
            } else row.append(record(c));
            if (c && typeof c.id === 'string' && typeof options.onCase === 'function') {
              // The case is named on the line above; the control says what it does and names the case for a screen reader.
              const inspect = button('Inspect case', () => active(m) && options.onCase(c.id)); inspect.setAttribute('aria-label', 'Inspect case ' + c.id);
              row.append(inspect);
            }
            n.append(row);
          });
        }
        grid.append(n);
      }
      m.body.append(grid);
    }
    function catalog(m, data) {
      const nav = el('nav', undefined, 'v4-grid v4-catalog'); nav.setAttribute('aria-label','Companion workflow catalog');
      for (const [route,title,description] of [
        ['ramp','Matched Ramp evidence','Inspect native records, governing terms, evidence and read-only workflow plans.'],
        ['vendors','Source-grounded vendor intake','Review public source text separately from customer scope; inspect candidate tests, shadow checks and version actions.'],
        ['disputes','Onboarding & disputes','Create a provisioned correspondence case, inspect untrusted inbound evidence and current reviewer actions.'],
        ['dashboard','Evidence ledger','Inspect case financial stages and clause-cited evaluation traces.'],
        ['lab','Onboarding lab','Preserved onboarding and shadow evaluation workflow.'],
        ['regression','Regression comparison','Compare the portfolio with a separate reference cohort.']]) {
        const panel = section(title), link = el('a','Open ' + title, 'v4-open-link'); link.href = '#' + route;
        add(panel,note(description),link); nav.append(panel);
      }
      // What the server observed, inside its own card, with the limit of what it establishes stated beside it.
      const observed = section('Observed integrity & reconciliation');
      add(observed, note('Missing verification or quarantine counts are unknown, not zero. A checksum or source signature alone does not establish entitlement.'),
        record({as_of:data.as_of,snapshot_status:data.snapshot_status,
        credit_sync:data.credit_sync,terms:data.terms ?? data.terms_status ?? data.terms_metrics ?? 'Terms verification metrics not returned by this backend',
        quarantine:data.quarantine ?? data.quarantine_metrics ?? 'Quarantine metrics not returned by this backend'}));
      m.body.append(nav, observed);
    }
    async function render(root, view, supplied) {
      if (!root || typeof root.replaceChildren !== 'function') throw new Error('A DOM root is required.');
      if (['portfolio','case','catalog'].includes(view) && supplied === undefined) throw new Error('Server projection is required for this view.');
      if (!['vendors','disputes','portfolio','case','catalog'].includes(view)) throw new Error('Unknown Uptime V4 view.');
      const m = {root,view,writes:[],syncs:[],status:el('p', '', 'v4-status'),result:el('div'),body:el('div')};
      m.status.setAttribute('role','status'); m.status.setAttribute('aria-live','polite');
      unmount(root); mounts.set(root,m);
      const wrap = el('div', undefined, 'uptime-v4');
      // Each page says what it is in its first lines: a short context line, the title and one sentence.
      const [eyebrow, title, lead] = {
        vendors:['Vendor agreements & versions', 'Agreements', 'Each agreement Uptime reads in this workspace: whether it is in force, what its source establishes with the exact clauses, and who performed each review step.'],
        disputes:['Correspondence & disputes', 'Cases', 'Each claim filed with a vendor, its stage and its correspondence. Open a case to read every step in order.'],
        portfolio:['Regression comparison', 'Portfolio comparison', 'Portfolio and seeded comparison are separate server-declared cohorts. A seeded scenario is not a portfolio total.'],
        case:[null, 'Case inspector', null],
        catalog:['More tools', 'Advanced companion workflows', 'Review vendor terms, correspondence and financial reconciliation.']}[view];
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
      refresh.className = 'v4-refresh'; m.body.className = 'v4-body';
      m.head = add(el('div'), eyebrow ? el('p', eyebrow, 'eyebrow') : null, el('h1', title), lead ? el('p', lead, 'lead') : null);
      m.tools = add(el('div', undefined, 'v4-head-tools'), refresh);
      add(wrap, add(el('div', undefined, 'page-head'), m.head, m.tools),
        readOnly() ? el('p', accessNote(), 'v4-banner') : null, m.status, m.result, m.body, identity()); root.replaceChildren(wrap);
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
      // What is on screen stays, with its controls disabled, until the case is read; nothing blinks away and back.
      if (!root.children || !root.children.length) root.replaceChildren(note('Loading correspondence case…'));
      try {
        const data = await request(marker, '/api/correspondence/claims/' + encodeURIComponent(id));
        if (mounts.get(root) !== marker) return;
        const m = await render(root,'case',data);
        if (!m || mounts.get(root) !== m) return;
        m.claimId = id;
        // The page is titled by the claim; the way back is a route, so the address and the Back button agree.
        const scope = data && data.scope && typeof data.scope === 'object' ? data.scope : {};
        const back = el('a', 'All cases', 'v4-back'); back.href = '#cases';
        const context = [data.vendor, scope.month == null ? null : monthName(scope.month)].filter(value => typeof value === 'string' && value).join(' · ');
        m.head.replaceChildren(back, el('p', context || 'Correspondence case', 'eyebrow'), el('h1', shown(data.title ?? id)), el('p', shown(id), 'lead'));
        m.tools.replaceChildren(button('Refresh case receipts', () => active(m) && inspect(root,id)));
        m.body.replaceChildren(inspector(m,data,true));
        uncertain = false; sync();
      } catch (_) {
        if (mounts.get(root) === marker) root.replaceChildren(note('Case unavailable. No changes were sent.'), button('Back to all cases', () => active(marker) && render(root,'disputes')));
      }
    }
    return Object.freeze({render, inspect, unmount, refreshAccess: sync});
  }
  const api = Object.freeze({create, parseJSON});
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (global) global.UptimeV4 = api;
})(typeof window !== 'undefined' ? window : globalThis);
