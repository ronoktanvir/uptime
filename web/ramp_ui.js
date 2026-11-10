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
  function create({api, document: doc = global.document, onNavigate = () => {}}) {
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
      const head = add(el('div', null, 'page-head'), add(el('div'), el('p', 'Read from Ramp', 'eyebrow'), el('h1', 'Ramp records'),
        el('p', 'What Uptime has read from Ramp, with the time of each read and how complete it was. Ramp stays the system of record.', 'lead')));
      const status = data.snapshot_status;
      const coverage = add(el('details', null, 'panel ramp-details'), el('summary', 'Record coverage'));
      add(coverage, record(status && typeof status === 'object' ? {...status, freshness: FRESHNESS[status.freshness] || status.freshness} : status));
      const resources = el('div', null, 'ramp-resources');
      list(data.resources).forEach(r => resources.append(add(el('article', null, 'ramp-resource'), el('h3', RESOURCE[r.name] || r.name), el('span', listStatus(r.status), 'pill'), note(`Records kept: ${shown(r.count)} · Complete: ${r.complete === true ? 'yes' : r.complete === false ? 'no' : 'unknown'}`), record(r.issues))));
      add(coverage, resources);
      // The worklist is its own titled section, with when it was read and what is missing from it always in view.
      const ledger = add(el('section', null, 'panel ramp-worklist'), el('h2', 'Ramp worklist'),
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
      add(panel, el('h3','Ramp discussion'), ...discussion(ctx, 'No comments read on this bill.'),
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
      add(panel, el('h3','Ramp discussion'), ...(notes.length ? notes : [note('No comments read on this record.')]),
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
    return {render,unmount:() => {epoch++;}};
  }
  const exported={create,providerURL,matches,hypothetical,clean};
  if(typeof module!=='undefined' && module.exports) module.exports=exported;
  global.UptimeRamp=exported;
})(typeof window === 'undefined' ? globalThis : window);
