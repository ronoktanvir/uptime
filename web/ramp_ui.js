/* Read-only Ramp companion. Provider observations and authority belong to the server. */
(function (global) {
  'use strict';
  const list = value => Array.isArray(value) ? value : [];
  const hidden = /secret|token|password|authorization|cookie|credential|private|raw|signature|signed_payload|api_key|bank_account|routing_number|card_number|ssn/i;
  function clean(value) {
    if (Array.isArray(value)) return value.map(clean);
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).filter(([key]) => !hidden.test(key)).map(([key, val]) => [key, clean(val)]));
    return value;
  }
  // Ordinary wording for a few source-classification codes. The meaning is kept: a saved capture is not live,
  // a scenario is not a finding and a local counterparty is not a vendor. The API values are unchanged.
  const CODES = {HISTORICAL_REPLAY:'Saved capture (not live)', SIMULATION_ONLY:'Scenario only, not a finding',
    SIMULATED_VENDOR:'Local counterparty, not a vendor', SYNTHETIC_INVOICE_CAP:'Hypothetical invoice cap'};
  const TITLES = {'Synthetic gross invoice cap rehearsal':'Invoice cap review'};
  // Ramp context wording. Identity and money come from the server unchanged; these only label them.
  const LINK_BASIS = {PROVIDER_DEEP_LINK:'Link supplied by Ramp for this record',
    OPERATOR_OBSERVED_URL:'Exact URL observed in Ramp by a person and confirmed against this bill by API read'};
  const ATTRIBUTION = {PERSON_POSTED_VERIFIED_READBACK:'Posted by a person in Ramp; Uptime read it back on this bill',
    UNATTRIBUTED:'Comment in Ramp; author not verified'};
  const RESOURCE = {bills:'Bills', transactions:'Card transactions', purchase_orders:'Purchase orders', vendors:'Vendors',
    credits:'Vendor credits', comments:'Bill comments', agreements:'Agreements', approvals:'Approvals'};
  const when = iso => instant(iso) || 'time not recorded';
  function coverageText(capture) {
    if (!capture) return null;
    const partial = list(capture.resources).filter(r => list(capture.incomplete_lists).includes(r.name));
    const source = capture.custody === 'packaged_receipt' ? 'Saved worklist from an earlier Ramp demo installation; its Ramp business is not recorded in this capture. '
      : capture.business_id ? `Ramp business ${capture.business_id}. ` : '';
    const read = `${source}Read from Ramp ${when(capture.observed_at)}.`;
    if (capture.account_complete === true) return `${read} Every bill, transaction and purchase-order list in this capture was read to the end.`;
    const parts = partial.map(r => `${RESOURCE[r.name] || r.name}: ${r.retained} kept of ${r.listed == null ? 'an unknown number' : r.listed} listed${r.has_next ? ', more remain in Ramp' : ''}`);
    return `${read} Partial capture. ${parts.join('; ')}. This is not the complete account.`;
  }
  function withheld(row) {
    const ctx = row.ramp_context;
    return !!ctx && row.amount != null && ctx.finding_attachable !== true && ctx.agreement_binding?.status !== 'HYPOTHETICAL';
  }
  // Instants render as "Nov 5, 2026, 00:36 UTC" everywhere on this page; the API values are unchanged.
  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const INSTANT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d{1,9})?)?(Z|[+-]\d{2}:\d{2})$/;
  function instant(value) {
    if (typeof value !== 'string' || !INSTANT.test(value)) return null;
    const date = new Date(value.replace(/(\.\d{3})\d+/, '$1'));
    if (Number.isNaN(date.getTime())) return null;
    const two = n => String(n).padStart(2, '0');
    return `${MONTHS[date.getUTCMonth()]} ${date.getUTCDate()}, ${date.getUTCFullYear()}, ${two(date.getUTCHours())}:${two(date.getUTCMinutes())} UTC`;
  }
  const shown = value => value == null ? 'Not provided' : typeof value === 'object' ? JSON.stringify(clean(value)) : CODES[value] || instant(value) || String(value);
  // Plain words for read-status codes, keeping their exact meaning: partial stays partial,
  // and a list that was not requested is never described as empty.
  const LIST_STATUS = {COMPLETE:'complete list', EMPTY:'complete list, none in Ramp', TRUNCATED:'partial list',
    PARTIAL:'partial list, some reads failed', UNAVAILABLE:'not read, unavailable', FORBIDDEN:'not read, not permitted',
    NOT_REQUESTED:'not requested'};
  const CREDIT_STATUS = {NO_APPLIED_CREDITS:'No credits applied to this bill',
    VERIFIED_APPLICATIONS:'Credits applied, confirmed on both the bill and the credit',
    REVIEW_REQUIRED:'Credit records disagree; needs review', UNKNOWN:'Credit status unknown from this read'};
  const FRESHNESS = {FRESH:'read within the last 24 hours', STALE:'older than 24 hours'};
  const listStatus = value => LIST_STATUS[value] || shown(value);
  const creditStatus = links => links ? CREDIT_STATUS[links.status] || shown(links.status) : 'Not read';
  function providerURL(value) {
    if (typeof value !== 'string' || !(value === 'https://demo.ramp.com' || value.startsWith('https://demo.ramp.com/'))) return null;
    try {
      const url = new URL(value);
      return url.origin === 'https://demo.ramp.com' && !url.username && !url.password && ![...url.searchParams.keys()].some(k => hidden.test(k)) ? url.href : null;
    } catch { return null; }
  }
  function hypothetical(row) {
    return /SYNTHETIC|HYPOTHETICAL|SIMULAT/i.test([row.finding_kind, ...list(row.sources)].join(' '));
  }
  function matches(row, filter, query) {
    const kind = row.provider_object_type;
    const bills = ['bills', 'bill', 'draft-bills', 'draft_bill'].includes(kind);
    const unpaid = /^(UNPAID|OPEN|DRAFT|PENDING|AWAITING_APPROVAL|APPROVED|SCHEDULED|AWAITING_PAYMENT)$/i.test(row.native_status || '');
    const included = filter === 'all' || (filter === 'unpaid' && bills && unpaid) || (filter === 'bills' && bills) ||
      (filter === 'transactions' && ['transactions', 'transaction'].includes(kind)) ||
      (filter === 'purchase_orders' && ['purchase-orders', 'purchase_orders', 'purchase_order'].includes(kind)) ||
      (filter === 'hypothetical' && hypothetical(row));
    return included && [row.id,row.provider_id,row.vendor,row.title,row.native_status].join(' ').toLowerCase().includes(query.toLowerCase());
  }
  function create({api, document: doc = global.document, onNavigate = () => {}, openApp = null, onBillState = null, openBill = null}) {
    let epoch = 0;
    const filters = {kind:'unpaid', query:'', page:0};
    const el = (tag, text, cls) => { const n = doc.createElement(tag); if (text != null) n.textContent = shown(text); if (cls) n.className = cls; return n; };
    const add = (node, ...children) => { children.filter(Boolean).forEach(c => node.append(c)); return node; };
    const note = text => el('p', text, 'help');
    const section = title => add(el('section', null, 'panel'), el('h2', title));
    const button = (text, fn, cls = 'quiet') => { const n = el('button', text, cls); n.type = 'button'; n.addEventListener('click', fn); return n; };
    function record(value, depth = 0) {
      if (depth > 10) return note('Further nested evidence omitted.');
      if (value == null || typeof value !== 'object') return el('span', shown(value));
      if (Array.isArray(value) && value.every(v => typeof v === 'string')) return el('span', value.length ? value.map(v => shown(v)).join(', ') : 'None');
      if (Array.isArray(value)) return value.length ? add(el('div'), ...value.map(v => add(el('div', null, 'record'), record(v, depth + 1)))) : note('No records returned.');
      const node = el('dl', null, 'record');
      Object.entries(value).filter(([k,v]) => !hidden.test(k) && !['sources','source_mode','data_provenance','classification'].includes(k) && !(k === 'mode' && /replay|simulat|demo/i.test(String(v)))).forEach(([k,v]) => add(node, el('dt', k.replaceAll('_',' ')), add(el('dd'), record(v, depth + 1))));
      return node;
    }
    const details = (name, value) => add(el('details', null, 'panel ramp-details'), el('summary', name), record(value));
    function sources(values) {
      const n=el('div',null,'sources');
      list(values).filter(v=>v && typeof v === 'object' && (v.ref || v.title || v.uri)).forEach(v=>n.append(el('span',v.ref || v.title || v.uri,'source')));
      return n;
    }
    function nativeLink(uri) {
      const url = providerURL(uri);
      if (!url) return note('Native destination unavailable. No provider URL has been verified.');
      const link = el('a', 'Open record in Ramp', 'ramp-native-link'); link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer'; return link;
    }
    function loadError(root, error, retry) {
      if (error.status === 401) throw error;
      root.replaceChildren(add(section('Ramp state unavailable'), note('The authenticated server could not return this record. No delivery or financial outcome is inferred.'), button('Try again', retry)));
    }
    // Short facts as label over value. An absent value is left out; a value the server marks as not captured is said so.
    function fields(pairs, cls) {
      const node = el('dl', null, 'northwind-fields' + (cls ? ' ' + cls : ''));
      pairs.filter(([, value]) => value != null && value !== '').forEach(([name, value]) => node.append(add(el('div', null, 'northwind-field'), el('dt', name), el('dd', value))));
      return node;
    }
    // A row the server marks as a scenario is never a finding on the Ramp record beside it.
    const isScenario = row => row.stage === 'SIMULATION_ONLY' || hypothetical(row);
    const COLUMNS = ['Record / native ID','Native status','Ramp amount','Contract finding','Finding amount'];
    // Plain words for a row's outcome and stage, keeping their meaning. Any other code is shown as sent, and the
    // record page keeps every exact value.
    const OUTCOME_WORDS = {ELIGIBLE:'Eligible', INELIGIBLE:'Ineligible', INSUFFICIENT_EVIDENCE:'Needs evidence'};
    const STAGE_WORDS = {PREPAYMENT_REVIEW:'Review before payment', RETROSPECTIVE_REVIEW:'Review after payment', NEEDS_REVIEW:'Needs review'};
    const outcomeWords = value => OUTCOME_WORDS[value] || shown(value), stageWords = value => STAGE_WORDS[value] || shown(value);
    function worklist(root, data) {
      const verified = verifiedPanel(data.verified_record);
      const tile = el('span', null, 'page-tile tile-ramp'); tile.setAttribute('aria-hidden', 'true');
      const head = add(el('div', null, 'page-head'), tile, add(el('div'), el('p', 'Read from Ramp', 'eyebrow ramp-glyph'), el('h1', 'Ramp records')));
      const status = data.snapshot_status;
      const coverage = add(el('details', null, 'panel ramp-details'), el('summary', 'Record coverage'));
      add(coverage, record(status && typeof status === 'object' ? {...status, freshness: FRESHNESS[status.freshness] || status.freshness} : status));
      const resources = el('div', null, 'ramp-resources');
      list(data.resources).forEach(r => resources.append(add(el('article', null, 'ramp-resource'), el('h3', RESOURCE[r.name] || r.name), el('span', listStatus(r.status), 'pill'), note(`Records kept: ${shown(r.count)} · Complete: ${r.complete === true ? 'yes' : r.complete === false ? 'no' : 'unknown'}`), record(r.issues))));
      add(coverage, resources);
      // The worklist is its own titled section, with when it was read and what is missing from it always in view.
      const ledger = add(el('section', null, 'panel ramp-worklist'), el('h2', 'Ramp worklist', 'ramp-glyph'),
        el('p', `Updated ${data.as_of ? when(data.as_of) : 'time not recorded'} · ${FRESHNESS[data.snapshot_status?.freshness] || shown(data.snapshot_status?.freshness)}`, 'as-of'));
      const captured = coverageText(data.capture);
      if (captured) ledger.append(el('p', captured, 'help ramp-capture'));
      const gaps = list(data.resources).filter(r => r.complete !== true);
      if (gaps.length) ledger.append(note('Not every list in this read is complete. ' + gaps.map(r => `${RESOURCE[r.name] || shown(r.name)}: ${listStatus(r.status)}`).join('; ') + '. Listed records are not a complete portfolio.'));
      const controls = el('div', null, 'filters');
      const select = el('select'); select.setAttribute('aria-label', 'Record filter');
      [['unpaid','Unpaid bills'],['bills','All bills'],['transactions','Transactions'],['purchase_orders','Purchase orders'],['hypothetical','Contract scenarios'],['all','All records']].forEach(([value,label]) => { const o = el('option', label); o.value=value; select.append(o); }); select.value = filters.kind;
      const search = el('input'); search.type='search'; search.value=filters.query; search.placeholder='Vendor, title or native ID'; search.setAttribute('aria-label','Search Ramp records');
      add(controls, add(el('label','Show'),select), add(el('label','Search'),search));
      const count = note(''); count.setAttribute('aria-live','polite');
      const table = el('table', null, 'stack stack-blocks'), body = el('tbody');
      add(table, add(el('thead'), add(el('tr'), ...COLUMNS.map((t, i) => { const n=el('th',t, i === 2 || i === 4 ? 'num' : null); n.scope='col'; return n; }))),body);
      const previous = button('Previous page', () => { filters.page--; rows(); });
      const next = button('Next page', () => { filters.page++; rows(); });
      function rows() {
        const selected = list(data.records).filter(r => matches(r,filters.kind,filters.query));
        const pages = Math.max(1,Math.ceil(selected.length / 25)); filters.page=Math.max(0,Math.min(filters.page,pages-1));
        body.replaceChildren();
        selected.slice(filters.page*25,filters.page*25+25).forEach(r => {
          const ctx = r.ramp_context;
          const name = ctx ? (ctx.vendor_name || 'Vendor name not captured') : (r.vendor || r.title || r.id);
          const link=button(name, () => onNavigate('ramp/'+encodeURIComponent(r.id)), 'case-link');
          const native = providerURL(ctx?.ramp_link?.url) || providerURL(r.provider_uri);
          let open = null;
          if (native) { open = el('a', 'Open in Ramp', 'ramp-row-link'); open.href = native; open.target = '_blank'; open.rel = 'noopener noreferrer'; open.setAttribute('aria-label', `Open ${shown(ctx?.vendor_name || r.vendor || r.title || r.provider_id)} in Ramp`); }
          const identity = ctx ? `Invoice: ${shown(ctx.invoice_number || 'not captured')} · Vendor ID: ${shown(ctx.vendor_id)} · Native ID: ${shown(r.provider_id)}` : `${shown(r.provider_object_type)} · Native ID: ${shown(r.provider_id)}`;
          const amount = withheld(r) ? 'Withheld: no agreement is bound to this Ramp record' : r.amount == null ? 'Not determined' : `${shown(r.currency)} ${shown(r.amount)}`;
          const scenario = isScenario(r);
          // A scenario row leads with that fact in words, before its outcome or amount, and neither is set as a finding.
          const finding = scenario
            ? add(el('td', null, 'ramp-scenario'), el('span', CODES.SIMULATION_ONLY, 'pill warn'), note(`Scenario outcome: ${outcomeWords(r.outcome)}`),
                r.stage === 'SIMULATION_ONLY' ? null : note(stageWords(r.stage)), sources(r.sources))
            : add(el('td'), el('strong',outcomeWords(r.outcome)), note(stageWords(r.stage)), sources(r.sources));
          const figure = scenario ? add(el('td', null, 'num ramp-scenario'), note('Scenario amount'), el('span', amount)) : add(el('td', null, 'num'), el('span', amount));
          const cells = [add(el('td'), link, el('div',TITLES[r.title] || r.title,'case-subtitle'), note(identity), open),
            add(el('td'), el('span',shown(r.native_status),'pill'), note(`Approval: ${shown(r.native_approval_status)}`), ctx?.status_summary ? note(`Ramp status: ${shown(ctx.status_summary)}`) : null),
            add(el('td', null, 'num'), el('strong',r.native_amount?.amount != null ? `${shown(r.native_amount.currency)} ${shown(r.native_amount.amount)}` : 'Amount unavailable')),
            finding, figure];
          cells.forEach((cell, i) => { if (i) cell.setAttribute('data-label', COLUMNS[i]); });
          body.append(add(el('tr', null, scenario ? 'scenario' : null), ...cells));
        });
        if (!selected.length) { const td=el('td','No matching records. Choose All records to inspect other types or unknown statuses.','empty'); td.colSpan=5; body.append(add(el('tr'),td)); }
        count.textContent=`${selected.length} of ${list(data.records).length} records · Page ${filters.page+1} of ${pages} · Up to 25 rows per page`;
        previous.disabled=filters.page===0; next.disabled=filters.page===pages-1;
      }
      select.addEventListener('change', () => { filters.kind=select.value; filters.page=0; rows(); });
      search.addEventListener('input', () => { filters.query=search.value; filters.page=0; rows(); });
      // Beside a verified record the worklist's rows stay closed until asked for, so no row is read as that record's finding.
      const records = add(el('details', null, 'ramp-list'), el('summary', 'Records in this worklist'), controls, count, add(el('div',null,'table-scroll'),table), add(el('div',null,'actions'), previous,next));
      if (!verified) records.open = true;
      ledger.append(records); rows();
      const authority=add(el('details', null, 'panel ramp-details'), el('summary', 'Agreements & permission'));
      add(authority, note('No verified agreement or action grant is established by this worklist. Inspect each case’s evidence and current server plan. A provider record or hypothetical cap does not establish legal entitlement.'),
        record({comment:data.writeback?.comment,blank_canvas:data.writeback?.blank_canvas,scope_receipt_at:data.writeback?.scope_receipt_at}),
        note('Delivery receipts apply only to their exact object, operation and authoritative readback. Accepted delivery does not prove approval execution or cash recovery.'));
      root.replaceChildren(head, ...(verified ? [verified] : []), ledger,
        add(el('div', null, 'fold-group'), coverage, authority, details('Credit reconciliation',data.credit_sync), details('Writeback evidence',data.writeback)),
        note(data.portfolio_note || 'No portfolio note returned.'));
    }
    // What Ramp holds for one bill, as it was read: identity, amount and Ramp's own statuses.
    function billFacts(ctx) {
      return [fields([['Vendor', ctx.vendor_name || 'Name not captured'], ['Invoice', ctx.invoice_number || 'Not captured'],
        ['Amount', ctx.amount ? `${ctx.amount.currency} ${ctx.amount.amount}` : 'Amount unavailable'],
        ['Status', shown(ctx.status)], ['Ramp status', shown(ctx.status_summary)], ['Approval', shown(ctx.approval_status)],
        ['Vendor credits', creditStatus(ctx.credit_links)]], 'ramp-bill'),
        fields([['Business', ctx.business_id], ['Vendor ID', ctx.vendor_id], ['Bill', ctx.object_id]], 'ramp-ids')];
    }
    const discussion = (ctx, empty) => { const notes = list(ctx.discussion).map(d => note(`${ATTRIBUTION[d.attribution] || 'Comment in Ramp'} · ${when(d.created_at)} · Comment ID: ${shown(d.comment_id)}`)); return notes.length ? notes : [note(empty)]; };
    function verifiedPanel(v) {
      if (!v || !v.ramp_context) return null;
      const ctx = v.ramp_context, panel = el('section', null, 'panel ramp-verified');
      const started = v.started_by === 'PERSON' ? ', started by a person' : '';
      const url = providerURL(ctx.ramp_link?.url);
      let open = null;
      if (url) { open = el('a', 'Open this bill in Ramp', 'ramp-native-link'); open.href = url; open.target = '_blank'; open.rel = 'noopener noreferrer'; }
      add(panel, add(el('div', null, 'panel-head'), el('h2', 'Verified Ramp record'), open),
        note(`Saved record read from Ramp ${when(v.capture?.observed_at)}${started}. Not a live read.`),
        v.excerpt === true ? note('Only this bill’s records are kept here; the full read stays private and is referenced by its checksum.') : null,
        el('h3', 'The bill, as read from Ramp'), ...billFacts(ctx),
        url ? note('Ramp link: ' + (LINK_BASIS[ctx.ramp_link.basis] || 'Link basis not recorded')) : null);
      const evidenceGap = v.finding?.outcome === 'INSUFFICIENT_EVIDENCE';
      add(panel, el('h3', 'What Uptime found for this bill'), fields([['Finding', evidenceGap ? 'Evidence gap: the governing agreement or usage evidence is missing' : shown(v.finding?.outcome)],
        ['Contract terms', 'No contract terms are attached to this bill']], 'ramp-finding'));
      add(panel, el('h3','Ramp discussion','ramp-glyph'), ...discussion(ctx, 'No comments read on this bill.'),
        note('Uptime has made no write to Ramp. A local ledger entry is never shown here as a Ramp confirmation.'));
      return panel;
    }
    function rampRecord(ctx) {
      const panel=section('Ramp record');
      const basis=ctx.ramp_link ? LINK_BASIS[ctx.ramp_link.basis] || 'Link basis not recorded' : 'No verified Ramp link for this record';
      add(panel, record({business:ctx.business_id || 'Not verified for this capture', vendor:ctx.vendor_name || 'Name not captured',
        vendor_id:ctx.vendor_id, entity_id:ctx.entity_id, bill:ctx.object_id, invoice:ctx.invoice_number || 'Not captured',
        amount:ctx.amount ? `${ctx.amount.currency} ${ctx.amount.amount}` : 'Amount unavailable',
        status:ctx.status, ramp_status:ctx.status_summary, approval:ctx.approval_status,
        read_from_ramp:when(ctx.observed_at), ramp_link:basis,
        agreement:ctx.agreement_binding?.status === 'BOUND' ? ctx.agreement_binding.contract_id : ctx.agreement_binding?.status === 'HYPOTHETICAL' ? 'Hypothetical terms only' : 'No agreement bound to this record',
        vendor_credits:ctx.credit_links ? creditStatus(ctx.credit_links) : 'Not read for this record'}));
      const notes=list(ctx.discussion).map(d => note(`${ATTRIBUTION[d.attribution] || 'Comment in Ramp'} · ${when(d.created_at)} · Comment ID: ${shown(d.comment_id)}`));
      add(panel, el('h3','Ramp discussion','ramp-glyph'), ...(notes.length ? notes : [note('No comments read on this record.')]),
        note('Uptime reads this record from Ramp. A local ledger entry is never shown here as a Ramp confirmation.'));
      return panel;
    }
    function detail(root, response, id, token) {
      const c=response.case || response;
      const back=button('Back to Ramp worklist', () => onNavigate('ramp'));
      // The native route back to Ramp leads the record so its workflow stays in Ramp.
      const ctx=response.ramp_context || c.ramp_context;
      const header=add(el('div',null,'page-head'),add(el('div'),el('h1',TITLES[c.title] || c.title || ctx?.vendor_name || c.vendor || 'Ramp record'),note(`${shown(ctx?.vendor_name || c.vendor)} · Native ID: ${shown(c.provider_id)} · ${shown(c.provider_object_type)}`)),nativeLink(ctx?.ramp_link?.url || response.provider_uri || c.provider_uri));
      const context=ctx ? rampRecord(ctx) : null;
      const finding=section('Contract finding');
      const hide=withheld({...c,ramp_context:ctx});
      if (ctx && ctx.finding_attachable !== true && ctx.agreement_binding?.status === 'NONE') add(finding, note('No agreement is bound to this Ramp record, so no contract amount is shown on it.'));
      // A scenario leads with that fact, before its outcome or amount: it is not a finding on this Ramp record.
      const scenario = isScenario(c);
      if (scenario) add(finding, el('span', CODES.SIMULATION_ONLY, 'pill warn'));
      const amount = hide ? 'Withheld: no agreement is bound to this Ramp record' : c.amount, currency = hide ? null : c.currency;
      const kind = c.finding_kind === 'SYNTHETIC_INVOICE_CAP' ? 'Price cap review' : c.finding_type || 'Contract review';
      add(finding,sources(c.sources),record(scenario ? {stage:c.stage,scenario_outcome:c.outcome,scenario_amount:amount,currency,finding_type:kind,finding_digest:c.finding_digest}
        : {outcome:c.outcome,stage:c.stage,amount,currency,finding_type:kind,finding_digest:c.finding_digest}));
      const native=section('Native Ramp status');
      add(native,record({native_status:c.native_status,native_approval_status:c.native_approval_status,native_amount:c.native_amount}));
      const workflow=section('Finding workflow');
      add(workflow,note('Inspect the current plan and its permission requirements.'),
        note('An accepted receipt is authoritative only for its scoped provider readback. It is not proof of a payment, entitlement or recovered cash.'));
      const plan=el('div'); plan.setAttribute('aria-live','polite');
      const inspect=button('Inspect finding plan',async () => {
        if (token !== epoch || inspect.disabled) return;
        inspect.disabled=true; plan.replaceChildren(note('Loading current server plan…'));
        try { const result=await api(`/api/ramp/records/${encodeURIComponent(id)}/workflow`); if(token===epoch) plan.replaceChildren(record(result)); }
        catch(error) { if(token===epoch) plan.replaceChildren(note(error.status===401 ? 'Session expired. Sign in again to inspect the plan.' : 'Plan unavailable. No action was sent.')); }
        finally { inspect.disabled=false; }
      });
      add(workflow,inspect,plan);
      const evidence=response.evidence ?? c.evidence;
      root.replaceChildren(back,header,...(context ? [context] : []),finding,native,workflow,
        details('Evidence & governing agreements',evidence ?? {status:'No evidence returned; agreement and entitlement are unverified.'}),
        details('Deterministic trace',c.trace),
        details('Governing terms & scenario', {clauses:c.clauses,agreement:c.agreement,agreements:c.agreements,scenario:c.scenario,cap:c.cap,evaluation:c.evaluation,limitations:c.limitations}),
        details('Native workflow & scoped receipts',response.native_workflow ?? c.native_workflow ?? {status:'Not provided; inspect the current plan.'}),
        details('Ramp record fields',response.native_projection ?? c.native_projection ?? {status:'Not provided'}),
        details('Financial stages & source references', {financials:c.financials,actual_recovery:c.actual_recovery,actual_money_prevented:c.actual_money_prevented,data_provenance:c.data_provenance,observed_at:c.observed_at,snapshot_status:c.snapshot_status,mode:c.mode}));
    }
    async function render(root, id) {
      const token=++epoch;
      // Keep the current layout while reading to avoid collapsing the scroll position.
      if (!root.children.length) root.append(note(id ? 'Loading Ramp record…' : 'Loading Ramp worklist…'));
      try {
        const data=await api(id ? `/api/ramp/records/${encodeURIComponent(id)}` : '/api/ramp/workspace');
        if(token!==epoch) return;
        if(id) detail(root,data,id,token); else worklist(root,data);
      } catch(error) { if(token===epoch) loadError(root,error,()=>render(root,id)); }
    }
    // ---- One Ramp bill, by Ramp's own bill id: a compact page for a narrow panel beside Ramp ----
    // It reads the same saved workspace as Ramp records, with one GET and nothing else, and shows only what that read
    // holds for this bill. It never shows a claim, credit or price finding from an agreement that is not bound to it.
    const BINDING = {NONE:'No agreement on file for this bill.', HYPOTHETICAL:'Hypothetical terms only; no agreement on file for this bill.',
      CONFLICT:'Agreement records for this bill conflict; needs review.'};
    const sameId = (a, b) => typeof a === 'string' && typeof b === 'string' && a !== '' && a.toLowerCase() === b.toLowerCase();
    function bindingWords(ctx) {
      const binding = ctx.agreement_binding && typeof ctx.agreement_binding === 'object' ? ctx.agreement_binding : {};
      return binding.status === 'BOUND' ? `Agreement on file: ${shown(binding.contract_id)}.` : BINDING[binding.status] || 'Agreement binding not recorded for this bill.';
    }
    const attachWords = ctx => ctx.finding_attachable === true ? 'A contract finding can be attached to this bill.' : 'No contract finding is attached to this bill.';
    const link = (text, href, cls = 'case-link') => { const a = el('a', text, cls); a.href = href; return a; };
    function billHead(ctx, context) {
      return add(el('div', null, 'page-head'), add(el('div'), el('p', context, 'eyebrow'), el('h1', ctx.vendor_name || 'Vendor name not captured'),
        el('p', ctx.invoice_number ? `Invoice ${ctx.invoice_number}` : 'Invoice not captured', 'lead')));
    }
    // Amount and Ramp's own statuses, exactly as read.
    function billSummary(ctx, statement) {
      return add(el('section', null, 'panel ramp-bill-card'), el('h2', 'In Ramp', 'ramp-glyph'),
        fields([['Amount', ctx.amount ? `${ctx.amount.currency} ${ctx.amount.amount}` : 'Amount unavailable'], ['Status', shown(ctx.status)],
          ['Ramp status', shown(ctx.status_summary)], ['Approval', shown(ctx.approval_status)]], 'ramp-bill'),
        fields([['Bill', ctx.object_id]], 'ramp-ids'), statement ? note(statement) : null);
    }
    // The way into the full app from this page. In the side panel (openApp given) it is the page's one primary button,
    // which asks the panel to open the full app in a browser tab; in an ordinary tab it stays a link on this page.
    const RAMP_BILL_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    function intoApp(route, label, href) {
      if (typeof openApp === 'function') return add(el('div', null, 'panel-open-app'), button('Open Uptime', () => openApp(route), 'panel-open-app-button'));
      return add(el('p', null, 'help recovery-links'), link(label, href));
    }
    // The bill view's states, in order: the verified record; the saved worklist; [reserved, not built: a Ramp bill that
    // matches an invoice in Uptime's own workspace]; no saved record. Each state is one function returning the page.
    function verifiedBill(v) {
      const ctx = v.ramp_context, started = v.started_by === 'PERSON' ? ', started by a person' : '';
      const found = add(el('section', null, 'panel'), el('h2', 'What Uptime found for this bill'));
      const evidenceGap = v.finding?.outcome === 'INSUFFICIENT_EVIDENCE';
      add(found, el('p', evidenceGap ? 'Evidence gap: the governing agreement or usage evidence is missing' : shown(v.finding?.outcome), 'ramp-finding-line'));
      const missing = list(v.finding?.missing).filter(item => typeof item === 'string' && item);
      if (missing.length) add(found, add(el('ul', null, 'ramp-missing'), ...missing.map(item => el('li', item))));
      add(found, note(bindingWords(ctx)), note(attachWords(ctx)), note(creditStatus(ctx.credit_links) + '.'));
      const talk = add(el('section', null, 'panel'), el('h2', 'Note in Ramp', 'ramp-glyph'), ...discussion(ctx, 'No comments read on this bill.'),
        note('Uptime has made no write to Ramp. A local ledger entry is never shown here as a Ramp confirmation.'));
      return [billHead(ctx, 'Verified Ramp record'),
        billSummary(ctx, `Saved record read from Ramp ${when(v.capture?.observed_at)}${started}. Not a live read.`), found, talk,
        intoApp('records', 'Open the full record', '#records')];
    }
    // A bill found only in the earlier saved worklist. Beside a Ramp bill this page states no outcome and lists no
    // scenario: it names the bill's own records and their stage, and says how many scenarios are kept elsewhere.
    function worklistBill(data, matches) {
      const ctx = matches[0].ramp_context;
      const own = matches.filter(r => !isScenario(r)), scenarios = matches.length - own.length;
      const found = add(el('section', null, 'panel'), el('h2', 'In the saved worklist'), note(bindingWords(ctx)), note(attachWords(ctx)),
        note(creditStatus(ctx.credit_links) + '.'));
      if (own.length) {
        const rows = el('ul', null, 'ramp-bill-records');
        own.forEach(r => rows.append(add(el('li'), el('strong', TITLES[r.title] || shown(r.title || r.id)), note(stageWords(r.stage)),
          typeof openApp === 'function' ? null : link('Open this record', '#ramp/' + encodeURIComponent(r.id)))));
        add(found, rows);
      }
      if (scenarios) add(found, note(`${scenarios === 1 ? 'One contract scenario about this bill is' : `${scenarios} contract scenarios about this bill are`} kept in Ramp records. A scenario is not a finding on this bill.`));
      return [billHead(ctx, 'Ramp bill in the saved worklist'), billSummary(ctx, coverageText(data.capture)), found,
        intoApp('records', 'Open Ramp records', '#records')];
    }
    // ---- A Ramp bill matched to an invoice in Uptime's own workspace (demo line) ----
    // Everything here is the server's: the match, its basis, the credit and its stage, the agreement, the inputs, the
    // balance and the notes. The browser formats amounts as strings (no arithmetic) and never adds stages together.
    const STAGES = [['ESTIMATED','Estimated'],['CLAIMED','Claimed'],['AWARDED','Awarded'],['POSTED','Posted'],['APPLIED','Applied']];
    const BASIS = {vendor_name:'vendor', invoice_number:'invoice number', amount:'amount'};
    const OPEN_ROUTE = /^(?:overview|records|recovery|agreements|cases|cases\/[A-Za-z0-9][A-Za-z0-9._-]{0,63})$/;
    const NOTE_KIND = {possible_credit:'Possible service credit', credit_applied:'Credit applied'};
    function money(amount, currency) {
      if (amount == null || amount === '') return 'Not determined';
      const raw = String(amount);
      if (!/^-?\d+(\.\d+)?$/.test(raw)) return `${shown(currency)} ${raw}`;
      const [whole, fraction] = raw.replace(/^-/, '').split('.');
      const sign = raw.startsWith('-') ? '-' : '';
      return `${sign}${currency === 'USD' ? '$' : `${shown(currency)} `}${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}${fraction === undefined ? '' : `.${fraction}`}`;
    }
    const FULL_MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
    function monthWords(value) {
      const m = /^(\d{4})-(\d{2})$/.exec(typeof value === 'string' ? value : '');
      return m && +m[2] >= 1 && +m[2] <= 12 ? `${FULL_MONTHS[+m[2] - 1]} ${m[1]}` : null;
    }
    function joinWords(words) { return words.length < 2 ? words.join('') : `${words.slice(0, -1).join(', ')} and ${words[words.length - 1]}`; }
    const obj = value => value && typeof value === 'object' && !Array.isArray(value) ? value : {};
    // How the record was read: a live read names its time and can be refreshed; a saved one says it is not live.
    function readParts(v, ctx, rerender) {
      const live = v.read && typeof v.read === 'object' && v.read.live === true;
      if (!live) return [note(`Saved record read from Ramp ${when(v.capture?.observed_at)}. Not a live read.`)];
      const status = el('p', null, 'help match-refresh-result'); status.setAttribute('role', 'status');
      const refresh = button('Refresh from Ramp', async () => {
        if (refresh.disabled) return;
        refresh.disabled = true; status.textContent = 'Reading the bill from Ramp…';
        try { await api('/api/ramp/refresh', {}); status.textContent = ''; if (typeof rerender === 'function') await rerender(); }
        catch (error) {
          if (error.status === 404) { refresh.hidden = true; status.textContent = ''; return; }
          status.textContent = typeof error.message === 'string' && error.message ? error.message : 'Ramp could not be read.';
        } finally { refresh.disabled = false; }
      }, 'link-button match-refresh');
      return [add(el('div', null, 'match-read'), note(`Read from Ramp just now · ${when(v.read.at)}`), refresh), status];
    }
    function matchedBill(v, data, rerender) {
      const ctx = v.ramp_context, match = obj(v.match), credit = obj(match.credit), invoice = obj(match.invoice), agreement = obj(match.agreement), balance = obj(match.balance);
      const price = match.kind === 'price_exception', exception = obj(match.exception), rampCredit = obj(match.ramp_credit);
      const confirmed = !price && rampCredit.status === 'APPLIED_CONFIRMED';
      const mode = data && typeof data.notes_mode === 'string' ? data.notes_mode : null;
      let stage = STAGES.findIndex(([code]) => code === credit.stage);
      if (confirmed) stage = STAGES.length - 1;
      const applied = credit.stage === 'APPLIED' || confirmed;
      const route = typeof match.route === 'string' && OPEN_ROUTE.test(match.route) ? match.route : 'overview';
      const month = monthWords(credit.service_month);
      // The headline: what may be recovered on this bill, how much, and where it stands.
      const hero = price
        ? add(el('section', null, 'panel match-hero match-price'), el('p', 'Price check', 'eyebrow'),
            el('h2', `This bill is above the contracted price by ${money(exception.amount, exception.currency || invoice.currency)}`),
            el('p', money(exception.amount, exception.currency || invoice.currency), 'match-amount'),
            fields([['Billed', money(exception.billed, exception.currency || invoice.currency)], ['Expected', money(exception.expected, exception.currency || invoice.currency)]], 'match-price-figures'),
            exception.basis != null ? note(`Basis: ${shown(exception.basis)}`) : null,
            exception.state != null ? note(`State: ${shown(exception.state)}`) : null)
        : add(el('section', null, 'panel match-hero'), el('p', 'Service credit', 'eyebrow'),
            el('h2', confirmed ? 'A service credit was applied to this bill in Ramp' : 'A service credit may apply to this bill'),
            el('p', money(credit.amount, credit.currency || invoice.currency), 'match-amount'),
            note(`${month ? `For service in ${month}` : 'Service month not recorded'} · ${confirmed ? 'Applied in Ramp' : stage >= 0 ? STAGES[stage][1] : 'Stage not recorded'}`));
      const estimateOnly = !price && match.route === 'agreements';
      const primaryWords = price ? 'Review in Uptime' : estimateOnly ? 'Review the estimate in Uptime' : stage <= 0 ? 'Review and file the claim' : 'Open the case in Uptime';
      const primary = button(primaryWords, () => (typeof openApp === 'function' ? openApp(route) : onNavigate(route)), 'match-primary');
      const next = match.next_action && typeof match.next_action.label === 'string' ? note(`Next in Uptime: ${match.next_action.label}`) : null;
      const result = el('p', null, 'help match-note-result'); result.setAttribute('role', 'status');
      const noteKind = applied ? 'credit_applied' : 'possible_credit';
      const notesList = el('ul', null, 'match-notes');
      const noWrite = note('Uptime has made no write to Ramp. A local ledger entry is never shown here as a Ramp confirmation.');
      // The note button: offered for a service credit when notes are manual (or the mode is not stated); in auto mode
      // Uptime posts the notes itself, and when notes are off there is nothing to offer.
      const offerNote = !price && (mode === null || mode === 'manual');
      const noteButton = offerNote ? button('Add a note to this bill in Ramp', async () => {
        if (noteButton.disabled) return;
        noteButton.disabled = true; result.textContent = 'Posting the note to Ramp…';
        try {
          const answer = await api('/api/ramp/notes', {bill_id: ctx.object_id, kind: noteKind});
          if (answer && answer.status === 'POSTED') {
            result.textContent = `Note posted to Ramp · ${when(answer.at)}`;
            notesList.append(noteRow({id: answer.comment_id, at: answer.at, by: 'UPTIME', kind: noteKind}));
            noWrite.remove?.(); noWrite.hidden = true;
          } else { result.textContent = 'Ramp did not confirm the note. Nothing is shown as posted.'; noteButton.disabled = false; }
        } catch (error) {
          if (error.status === 404) { noteButton.hidden = true; result.textContent = ''; return; }
          result.textContent = typeof error.message === 'string' && error.message ? error.message : 'The note was not posted.';
          noteButton.disabled = false;
        }
      }, 'quiet match-note-button') : null;
      add(hero, add(el('div', null, 'match-actions'), primary, noteButton), next, result);
      // The bill in Ramp and how it was matched.
      const basis = list(match.basis).map(b => BASIS[b]).filter(Boolean);
      const billCard = add(el('section', null, 'panel match-bill'), el('h2', 'The bill in Ramp', 'ramp-glyph'),
        fields([['Vendor', ctx.vendor_name || 'Name not captured'], ['Invoice', ctx.invoice_number || 'Not captured'],
          ['Amount', ctx.amount ? money(ctx.amount.amount, ctx.amount.currency) : 'Amount unavailable'], ['Status', shown(ctx.status_summary || ctx.status)]], 'ramp-bill'),
        note(`Matched to Uptime's invoice ${shown(invoice.id)}${basis.length ? ` by ${joinWords(basis)}` : ''}`),
        ...readParts(v, ctx, rerender));
      // The evidence: the agreement, its clause quoted exactly, and the inputs.
      const evidence = add(el('section', null, 'panel match-evidence'), el('h2', 'The evidence'),
        fields([['Agreement', agreement.id || 'Not provided'], ...(typeof agreement.read_by === 'string' && agreement.read_by ? [['Contract read by', /^claude/i.test(agreement.read_by) ? 'Claude (' + agreement.read_by + ')' : agreement.read_by.startsWith('template:') ? 'Fixed rules · template ' + agreement.read_by.slice(9) : 'Fixed rules (' + agreement.read_by.replace(/_/g, ' ') + ')']] : [])]),
        typeof agreement.clause === 'string' && agreement.clause ? el('blockquote', agreement.clause) : note('No clause quoted.'),
        typeof agreement.citation === 'string' && agreement.citation ? el('p', agreement.citation, 'help match-citation') : null,
        list(match.inputs).length ? fields(list(match.inputs).filter(i => i && typeof i === 'object').map(i => [shown(i.label), shown(i.value)]), 'match-inputs') : null);
      // The money, as the server states it. The figures are not added together here.
      const currency = credit.currency || exception.currency || invoice.currency;
      const moneyCard = price && !v.match.balance ? null : add(el('section', null, 'panel match-money'), el('h2', 'The money'),
        fields([['Invoice', money(balance.invoice, currency)], ['Credit applied so far', money(balance.credit_applied, currency)],
          ['Remaining', money(balance.remaining, currency)]], 'match-balance'),
        confirmed ? el('p', `Credit applied in Ramp · ${money(rampCredit.amount, currency)} · confirmed on the bill and the credit`, 'match-confirmed') : null);
      // Where the credit stands: five stages, the current one marked in words.
      let standing = null;
      if (!price) {
        const steps = el('ol', null, 'match-stages');
        STAGES.forEach(([code, label], i) => {
          const last = i === STAGES.length - 1;
          const state = confirmed && last ? 'Confirmed in Ramp' : stage < 0 ? 'Not recorded' : i < stage ? 'Recorded' : i === stage ? 'Current stage' : 'Not yet';
          const cls = confirmed ? 'done' : i < stage ? 'done' : i === stage ? 'current' : 'pending';
          const item = add(el('li', null, 'match-stage ' + cls + (confirmed && last ? ' confirmed' : '')), el('span', label, 'step-label'), el('span', state, 'step-state'));
          if (i === stage) item.setAttribute('aria-current', 'step');
          steps.append(item);
        });
        standing = add(el('section', null, 'panel match-standing'), el('h2', 'Where the credit stands'), steps);
      }
      // Notes on the bill: who posted each one.
      function noteRow(n) {
        if (mode === 'auto' && n.by === 'UPTIME') return add(el('li', null, 'match-note'), el('strong', `Uptime added a note to this bill in Ramp · ${when(n.at)}`));
        const who = n.by === 'UPTIME' ? 'Posted by Uptime' : n.by === 'RAMP' ? 'Posted in Ramp' : 'Author not recorded';
        return add(el('li', null, 'match-note'), el('strong', who), note([NOTE_KIND[n.kind], when(n.at)].filter(Boolean).join(' · ')));
      }
      const notes = Array.isArray(v.notes) ? v.notes.filter(n => n && typeof n === 'object') : null;
      if (notes) notes.forEach(n => notesList.append(noteRow(n)));
      // The no-write statement stands only while nothing shows Uptime writing to Ramp or a credit applied there.
      const wrote = (notes && notes.some(n => n.by === 'UPTIME')) || confirmed;
      const talk = add(el('section', null, 'panel match-notes-card'), el('h2', 'Notes on this bill in Ramp', 'ramp-glyph'),
        ...(notes ? (notes.length ? [] : [note('No notes read on this bill.')]) : discussion(ctx, 'No comments read on this bill.')), notesList,
        wrote ? null : noWrite);
      return [billHead(ctx, 'Matched to an Uptime invoice'), hero, billCard, evidence, moneyCard, standing, talk].filter(Boolean);
    }
    // One line of what Uptime found for a bill in the list.
    function findingLine(v) {
      if (!isMatch(v)) return v.ramp_context?.agreement_binding?.status === 'BOUND' ? 'No money found to recover' : 'No agreement on file';
      const m = v.match, currency = obj(m.invoice).currency;
      if (m.kind === 'price_exception') return `Above contracted price · ${money(obj(m.exception).amount, obj(m.exception).currency || currency)}`;
      return `Service credit may apply · ${money(obj(m.credit).amount, obj(m.credit).currency || currency)}`;
    }
    // Every bill Uptime is tracking, matched ones first, for a Ramp page that is not one bill.
    function billsView(root, data) {
      const records = list(data && data.verified_records).filter(v => v && v.ramp_context);
      if (!records.length && data && data.verified_record && data.verified_record.ramp_context) records.push(data.verified_record);
      const ordered = [...records.filter(isMatch), ...records.filter(v => !isMatch(v))];
      const matched = ordered.filter(isMatch).length;
      const count = matched === 1 ? '1 bill may have money to recover' : matched ? `${matched} bills may have money to recover` : 'No tracked bill shows money to recover';
      const rows = el('ul', null, 'track-list');
      ordered.forEach(v => {
        const ctx = v.ramp_context, id = typeof ctx.object_id === 'string' ? ctx.object_id.toLowerCase() : '';
        const body = [add(el('span', null, 'track-top'), el('strong', ctx.vendor_name || 'Vendor name not captured'),
            el('span', ctx.amount ? money(ctx.amount.amount, ctx.amount.currency) : 'Amount unavailable', 'track-amount')),
          el('span', ctx.invoice_number ? `Invoice ${ctx.invoice_number}` : 'Invoice not captured', 'track-invoice'),
          el('span', findingLine(v), 'track-finding' + (isMatch(v) ? ' found' : ''))];
        let row;
        if (typeof openBill === 'function' && RAMP_BILL_ID.test(id)) row = add(button('', () => openBill(id), 'track-row'), ...body);
        else { row = add(el('a', null, 'track-row'), ...body); row.href = '#ramp-bill/' + encodeURIComponent(id); }
        rows.append(add(el('li'), row));
      });
      root.replaceChildren(add(el('div', null, 'page-head'), add(el('div'), el('p', 'Ramp', 'eyebrow'), el('h1', 'Bills Uptime is tracking'),
          el('p', ordered.length ? count : 'Uptime is not tracking any Ramp bill yet.', 'lead track-count'))),
        ...(ordered.length ? [add(el('section', null, 'panel track-panel'), rows)] : []), intoApp('overview', 'Open Ramp records', '#records'));
    }
    // Looks a bill up by Ramp's id: the list of verified records first, then the single verified record.
    function verifiedFor(data, id) {
      const found = list(data && data.verified_records).find(r => r && r.ramp_context && sameId(r.ramp_context.object_id, id));
      if (found) return found;
      const v = data && data.verified_record;
      return v && v.ramp_context && sameId(v.ramp_context.object_id, id) ? v : null;
    }
    const isMatch = v => !!(v && v.match && typeof v.match === 'object' && !Array.isArray(v.match));
    function noRecord(id) {
      const known = typeof id === 'string' && RAMP_BILL_ID.test(id);
      return [add(el('div', null, 'page-head'), add(el('div'), el('p', 'Ramp bill', 'eyebrow'), el('h1', 'No saved record for this bill'),
        el('p', 'This workspace has no saved record for this Ramp bill.', 'lead'))),
        add(el('section', null, 'panel ramp-bill-empty'), note('Uptime shows a bill here only when it holds a saved read of it from Ramp. Nothing about this bill is inferred.'),
          known ? fields([['Bill', id.toLowerCase()]], 'ramp-ids') : null),
        intoApp('overview', 'Open Ramp records', '#records')];
    }
    function billView(root, data, id) {
      const v = verifiedFor(data, id);
      if (typeof onBillState === 'function' && typeof id === 'string' && RAMP_BILL_ID.test(id)) onBillState(id.toLowerCase(), isMatch(v) ? 'match' : 'none');
      if (isMatch(v)) return root.replaceChildren(...matchedBill(v, data, () => bill(root, id)));
      if (v) return root.replaceChildren(...verifiedBill(v));
      const matches = list(data && data.records).filter(r => r && r.ramp_context && sameId(r.ramp_context.object_id, id));
      if (matches.length) {
        // The bill's own record first; a scenario about the same bill is never its finding.
        matches.sort((a, b) => Number(isScenario(a)) - Number(isScenario(b)));
        return root.replaceChildren(...worklistBill(data, matches));
      }
      root.replaceChildren(...noRecord(id));
    }
    // No Ramp bill is open in the tab beside the panel. It reads nothing and shows no record.
    function noBill(root) {
      epoch++;
      root.replaceChildren(add(el('div', null, 'page-head'), add(el('div'), el('p', 'This tab', 'eyebrow'), el('h1', 'No Ramp bill open'),
        el('p', 'Open a bill in Ramp, and Uptime shows here what it holds for that bill.', 'lead'))),
        intoApp('overview', 'Open Ramp records', '#records'));
    }
    async function bill(root, id) {
      const token=++epoch;
      if (!root.children.length) root.append(note('Loading the saved Ramp record…'));
      try {
        const data=await api('/api/ramp/workspace');
        if(token!==epoch) return;
        billView(root, data, typeof id === 'string' ? id : '');
      } catch(error) { if(token===epoch) loadError(root,error,()=>bill(root,id)); }
    }
    async function bills(root) {
      const token=++epoch;
      if (!root.children.length) root.append(note('Loading the bills Uptime is tracking…'));
      try {
        const data=await api('/api/ramp/workspace');
        if(token!==epoch) return;
        billsView(root, data);
      } catch(error) { if(token===epoch) loadError(root,error,()=>bills(root)); }
    }
    return {render,bill,bills,noBill,unmount:() => {epoch++;}};
  }
  const exported={create,providerURL,matches,hypothetical,clean};
  if(typeof module!=='undefined' && module.exports) module.exports=exported;
  global.UptimeRamp=exported;
})(typeof window === 'undefined' ? globalThis : window);
