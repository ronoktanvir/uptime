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
  const when = iso => typeof iso === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(iso) ? iso.slice(0,16).replace('T',' ') + ' UTC' : 'time not recorded';
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
  const shown = value => value == null ? 'Not provided' : typeof value === 'object' ? JSON.stringify(clean(value)) : CODES[value] || String(value);
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
    function worklist(root, data) {
      const head = add(el('div', null, 'page-head'), add(el('div'), el('h1', 'Ramp worklist'), note('Review bills, contract findings and supporting evidence.')),
        el('div', `Updated ${shown(data.as_of)} · ${shown(data.snapshot_status?.freshness)}`, 'as-of'));
      const captured = coverageText(data.capture);
      if (captured) add(head, el('p', captured, 'help ramp-capture'));
      const coverage = add(el('details', null, 'panel ramp-details'), el('summary', 'Record coverage'));
      add(coverage, record(data.snapshot_status));
      const resources = el('div', null, 'ramp-resources');
      list(data.resources).forEach(r => resources.append(add(el('article', null, 'ramp-resource'), el('h3', r.name), el('span', r.status, 'pill'), note(`Records: ${shown(r.count)} · Complete: ${r.complete === true ? 'yes' : r.complete === false ? 'no' : 'unknown'}`), record(r.issues))));
      add(coverage, resources);
      const ledger = section('Financial records'), controls = el('div', null, 'filters');
      const select = el('select'); select.setAttribute('aria-label', 'Record filter');
      [['unpaid','Unpaid bills'],['bills','All bills'],['transactions','Transactions'],['purchase_orders','Purchase orders'],['hypothetical','Contract scenarios'],['all','All records']].forEach(([value,label]) => { const o = el('option', label); o.value=value; select.append(o); }); select.value = filters.kind;
      const search = el('input'); search.type='search'; search.value=filters.query; search.placeholder='Vendor, title or native ID'; search.setAttribute('aria-label','Search Ramp records');
      add(controls, add(el('label','Show'),select), add(el('label','Search'),search));
      const count = note(''); count.setAttribute('aria-live','polite');
      const table = el('table'), body = el('tbody');
      add(table, add(el('thead'), add(el('tr'), ...['Record / native ID','Native status','Ramp amount','Contract finding','Finding amount'].map(t => { const n=el('th',t); n.scope='col'; return n; }))),body);
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
          body.append(add(el('tr'), add(el('td'), link, el('div',TITLES[r.title] || r.title,'case-subtitle'), note(identity), open),
            add(el('td'), el('span',shown(r.native_status),'pill'), note(`Approval: ${shown(r.native_approval_status)}`), ctx?.status_summary ? note(`Ramp status: ${shown(ctx.status_summary)}`) : null),
            add(el('td'), el('strong',r.native_amount?.amount != null ? `${shown(r.native_amount.currency)} ${shown(r.native_amount.amount)}` : 'Amount unavailable')),
            add(el('td'), el('strong',shown(r.outcome)), note(shown(r.stage)), sources(r.sources)),
            add(el('td'), el('span',withheld(r) ? 'Withheld: no agreement is bound to this Ramp record' : r.amount == null ? 'Not determined' : `${shown(r.currency)} ${shown(r.amount)}`))));
        });
        if (!selected.length) { const td=el('td','No matching records. Choose All records to inspect other types or unknown statuses.','empty'); td.colSpan=5; body.append(add(el('tr'),td)); }
        count.textContent=`${selected.length} of ${list(data.records).length} records · Page ${filters.page+1} of ${pages} · Up to 25 rows per page`;
        previous.disabled=filters.page===0; next.disabled=filters.page===pages-1;
      }
      select.addEventListener('change', () => { filters.kind=select.value; filters.page=0; rows(); });
      search.addEventListener('input', () => { filters.query=search.value; filters.page=0; rows(); });
      add(ledger, controls, count, add(el('div',null,'table-scroll'),table), add(el('div',null,'actions'), previous,next)); rows();
      const authority=add(el('details', null, 'panel ramp-details'), el('summary', 'Agreements & permission'));
      add(authority, note('No verified agreement or action grant is established by this worklist. Inspect each case’s evidence and current server plan. A provider record or hypothetical cap does not establish legal entitlement.'),
        record({comment:data.writeback?.comment,blank_canvas:data.writeback?.blank_canvas,scope_receipt_at:data.writeback?.scope_receipt_at}),
        note('Delivery receipts apply only to their exact object, operation and authoritative readback. Accepted delivery does not prove approval execution or cash recovery.'));
      const gaps = list(data.resources).filter(r => r.complete !== true);
      const warning = gaps.length ? note('Incomplete resource coverage: ' + gaps.map(r => `${shown(r.name)} (${shown(r.status)})`).join(', ') + '. Listed records are not a complete portfolio.') : null;
      const verified = verifiedPanel(data.verified_record);
      root.replaceChildren(head, ...(warning ? [warning] : []), ...(verified ? [verified] : []), ledger, coverage, authority,
        details('Credit reconciliation',data.credit_sync),
        details('Writeback evidence',data.writeback),note(data.portfolio_note || 'No portfolio note returned.'));
    }
    function verifiedPanel(v) {
      if (!v || !v.ramp_context) return null;
      const ctx = v.ramp_context, panel = section('Verified Ramp record');
      const started = v.started_by === 'PERSON' ? ', started by a person' : '';
      add(panel, note(`Saved record read from Ramp ${when(v.capture?.observed_at)}${started}. Not a live read.`));
      if (v.excerpt === true) add(panel, note('Only this bill’s records are kept here; the full read stays private and is referenced by its checksum.'));
      const url = providerURL(ctx.ramp_link?.url);
      if (url) { const open = el('a', 'Open this bill in Ramp', 'ramp-native-link'); open.href = url; open.target = '_blank'; open.rel = 'noopener noreferrer'; add(panel, open, note(LINK_BASIS[ctx.ramp_link.basis] || 'Link basis not recorded')); }
      const evidenceGap = v.finding?.outcome === 'INSUFFICIENT_EVIDENCE';
      add(panel, record({business:ctx.business_id, vendor:ctx.vendor_name || 'Name not captured', vendor_id:ctx.vendor_id, bill:ctx.object_id,
        invoice:ctx.invoice_number || 'Not captured', amount:ctx.amount ? `${ctx.amount.currency} ${ctx.amount.amount}` : 'Amount unavailable',
        status:ctx.status, ramp_status:ctx.status_summary, approval:ctx.approval_status,
        finding:evidenceGap ? 'Evidence gap: the governing agreement or usage evidence is missing' : shown(v.finding?.outcome),
        contract_terms:'No contract terms are attached to this bill', vendor_credits:ctx.credit_links ? ctx.credit_links.status : 'Not read'}));
      const notes = list(ctx.discussion).map(d => note(`${ATTRIBUTION[d.attribution] || 'Comment in Ramp'} · ${when(d.created_at)} · Comment ID: ${shown(d.comment_id)}`));
      add(panel, el('h3','Ramp discussion'), ...(notes.length ? notes : [note('No comments read on this bill.')]),
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
        vendor_credits:ctx.credit_links ? ctx.credit_links.status : 'Not read for this record'}));
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
      add(finding,sources(c.sources),record({outcome:c.outcome,stage:c.stage,amount:hide ? 'Withheld: no agreement is bound to this Ramp record' : c.amount,currency:hide ? null : c.currency,finding_type:c.finding_kind === 'SYNTHETIC_INVOICE_CAP' ? 'Price cap review' : c.finding_type || 'Contract review',finding_digest:c.finding_digest}));
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
