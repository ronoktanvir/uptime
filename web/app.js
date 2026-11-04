/* Uptime browser client. Authorization and financial calculations belong to the server. */
(function () {
  'use strict';
  const list = value => Array.isArray(value) ? value : [];
  const display = value => value == null ? 'Not provided' : typeof value === 'object' ? JSON.stringify(value) : String(value);
  const title = value => String(value).replace(/_/g, ' ').replace(/^./, c => c.toUpperCase());
  function safeURL(value) {
    try { if (typeof value === 'string' && /^fixture:pricing\/agreement\.json(?:#|$)/.test(value)) return '/fixtures/pricing/agreement.json' + (value.split('#')[1] ? '#' + value.split('#')[1] : '');
      if (typeof value === 'string' && /^\/fixtures\/other_obligations\/agreement\.txt(?:#|$)/.test(value)) return value;
      const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : null; } catch { return null; }
  }
  // Compare decimal strings without rounding large balances through binary floats.
  function compareDecimal(a, b) {
    const parse = v => { const m = /^(-?)(\d+)(?:\.(\d+))?$/.exec(String(v)); return m && {negative: !!m[1], whole: m[2].replace(/^0+(?=\d)/, ''), fraction: m[3] || ''}; };
    const x = parse(a), y = parse(b);
    if (!x || !y) return x ? -1 : y ? 1 : 0;
    if (x.negative !== y.negative) return x.negative ? -1 : 1;
    const size = Math.max(x.fraction.length, y.fraction.length);
    const left = x.whole + x.fraction.padEnd(size, '0'), right = y.whole + y.fraction.padEnd(size, '0');
    const result = x.whole.length - y.whole.length || (left < right ? -1 : left > right ? 1 : 0);
    return x.negative ? -result : result;
  }
  function money(amount, currency) {
    if (amount == null || amount === '') return 'Not determined';
    const raw = String(amount);
    if (!/^-?\d+(\.\d+)?$/.test(raw)) return `${display(currency)} ${raw}`;
    const [whole, fraction] = raw.split('.');
    return `${currency === 'USD' ? '$' : `${display(currency)} `}${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}${fraction === undefined ? '' : `.${fraction}`}`;
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {compareDecimal, money, safeURL};
  if (typeof document === 'undefined') return;
  const $ = selector => document.querySelector(selector);
  const content = $('#content'), notice = $('#notice'), dialog = $('#inspector');
  let view = 'dashboard', generation = 0, caseGeneration = 0, activeCase = null, busy = false;
  const filters = {query: '', status: '', sort: 'value-desc'};
  function el(tag, className, text) { const node = document.createElement(tag); if (className) node.className = className; if (text != null) node.textContent = display(text); return node; }
  function add(parent, ...children) { children.flat().filter(Boolean).forEach(child => parent.append(child)); return parent; }
  function button(label, handler, className = '') { const node = el('button', className, label); node.type = 'button'; node.addEventListener('click', handler); return node; }
  function sources(values) {
    const node = el('div', 'sources');
    if (!list(values).length) return add(node, el('span', 'missing-source', 'Source not provided'));
    list(values).forEach(value => node.append(el('span', 'source', display(value))));
    return node;
  }
  function badge(value) { const text = display(value); return el('span', /pending|draft|shadow|review|insufficient|submitted/i.test(text) ? 'pill pending' : 'pill', text); }
  function heading(name, detail) { return add(el('div', 'page-head'), add(el('div'), el('h1', '', name), el('p', '', detail))); }
  function panel(name) { return add(el('section', 'panel'), el('h2', '', name)); }
  function empty(text) { return el('p', 'empty', text); }
  function announce(text) { notice.className = 'notice'; notice.textContent = text; }
  async function api(path, payload) {
    return window.uptimeAPI(path, payload);
  }
  function account() {
    if (dialog.open) dialog.close();
    content.replaceChildren(window.uptimeAuth.signInForm(navigate));
  }
  function showError(target, error, retry) { target.replaceChildren(add(el('section', 'panel error'), el('h2', '', 'Unable to load this view'), el('p', '', error.message || 'Connection unavailable. Check that the local demo server is running.'), button('Try again', retry, 'quiet'))); }
  function timeline(items, history = false) {
    const node = el('ol', 'activity');
    list(items).forEach(item => { const row = el('li'); if (typeof item === 'string') add(row, el('span', '', item), sources([])); else add(row, el('time', '', item.at), el('span', '', item.event), item.case_id ? el('div', 'help', `Case ${item.case_id}`) : null, sources(item.sources)); node.append(row); });
    return node.children.length ? node : empty(history ? 'No history returned by the server.' : 'No events returned by the server.');
  }
  // Unknown policy/integration fields remain read-only; source arrays are never renamed or inferred.
  function record(value) {
    if (value == null || typeof value !== 'object') return el('span', '', display(value));
    if (Array.isArray(value)) { const node = el('div'); value.forEach(item => node.append(add(el('div', 'record'), record(item)))); return node; }
    const node = el('dl', 'record');
    Object.entries(value).forEach(([key, val]) => {
      if (key === 'sources') { add(node, el('dt', '', 'Sources'), add(el('dd'), sources(val))); return; }
      add(node, el('dt', '', title(key)), add(el('dd'), typeof val === 'object' && val !== null ? record(val) : el('span', '', display(val))));
    });
    return node;
  }
  function renderDashboard(data) {
    const head = heading('Contract ledger', 'Unpaid invoice exposure and the current recovery case. Each figure belongs to a separate financial stage.');
    head.append(el('div', 'as-of', `${data.mode === "replay" ? "Offline replay" : "Sandbox capture · " + display(data.as_of)}`));
    const metrics = el('section', 'metrics'); metrics.setAttribute('aria-label', 'Financial stages');
    list(data.metrics).forEach(metric => metrics.append(add(el('article', 'metric'), el('h2', '', metric.label), el('div', 'metric-value', metric.value), el('p', '', metric.note), sources(metric.sources))));
    if (!metrics.children.length) metrics.append(empty('No financial metrics returned.'));
    const ledger = el('section', 'panel ledger'), controls = el('div', 'filters');
    const search = el('input'); search.type = 'search'; search.placeholder = 'Vendor or case'; search.value = filters.query;
    const status = el('select'); add(status, new Option('All statuses', '')); [...new Set(list(data.cases).map(c => c.stage).filter(Boolean))].sort().forEach(s => status.add(new Option(s, s))); status.value = filters.status;
    if (status.value !== filters.status) filters.status = '';
    const sort = el('select'); [['value-desc','Value: high to low'],['value-asc','Value: low to high'],['status','Status']].forEach(([value, label]) => sort.add(new Option(label, value))); sort.value = filters.sort;
    add(controls, add(el('label', '', 'Search'), search), add(el('label', '', 'Status'), status), add(el('label', '', 'Sort'), sort));
    const count = el('p', 'help'); count.setAttribute('aria-live', 'polite');
    const table = el('table'), body = el('tbody'); add(table, add(el('thead'), add(el('tr'), ...['Case / vendor','Eligibility','Stage','Value / sources'].map(s => { const th = el('th', '', s); th.scope = 'col'; return th; }))), body);
    function rows() {
      const cases = list(data.cases).filter(c => (!filters.status || c.stage === filters.status) && [c.id,c.vendor,c.title].join(' ').toLowerCase().includes(filters.query.toLowerCase()));
      cases.sort((a,b) => filters.sort === 'status' ? display(a.stage).localeCompare(display(b.stage)) : (a.amount == null ? 1 : b.amount == null ? -1 : compareDecimal(a.amount,b.amount) * (filters.sort === 'value-asc' ? 1 : -1)));
      body.replaceChildren();
      cases.forEach(c => body.append(add(el('tr'), add(el('td'), button(c.vendor || c.id, () => openCase(c.id), 'case-link'), el('div', 'case-subtitle', c.title), el('div', 'help', c.id)), add(el('td'), badge(c.outcome)), add(el('td'), badge(c.stage)), add(el('td', 'amount'), el('div', '', money(c.amount,c.currency)), sources(c.sources)))));
      if (!cases.length) { const td = el('td', 'empty', 'No cases match these filters. Clear search or select all statuses.'); td.colSpan = 4; body.append(add(el('tr'), td)); }
      count.textContent = `${cases.length} of ${list(data.cases).length} cases. Values are server-provided; no stages are added together.`;
    }
    search.addEventListener('input', () => { filters.query = search.value; rows(); }); status.addEventListener('change', () => { filters.status = status.value; rows(); }); sort.addEventListener('change', () => { filters.sort = sort.value; rows(); });
    add(ledger, add(el('div', 'ledger-head'), el('h2', '', 'Case ledger'), controls, count), add(el('div', 'table-scroll'), table)); rows();
    const audit = panel('Activity & provenance'); audit.append(timeline(data.audit));
    const ramp = panel('Ramp connection'); ramp.append(record(data.ramp || {status: 'Not provided'}));
    const current = window.uptimeAuth.session();
    if (current) $('#account').textContent = 'Sign out · ' + current.subject;
    content.replaceChildren(head, metrics, ledger, add(el('div', 'section-grid'), audit, ramp));
    $('#workspace-name').textContent = typeof data.workspace === 'string' ? data.workspace : 'Contract operations';
  }
  function actions(items, path, reload) {
    const node = el('div', 'actions');
    list(items).forEach(action => { if (!action.id) return; node.append(button(action.label || action.id, async event => {
      if (busy) return; busy = true; const trigger = event.currentTarget; node.querySelectorAll('button').forEach(b => b.disabled = true); announce('Sending action for server authorization…');
      try { await api(`${path}/${encodeURIComponent(action.id)}`, {}); announce('Action recorded. The latest server state is shown below.'); await reload(); }
      catch (error) { announce(`${error.message || 'Connection interrupted.'} The action outcome may be unknown; refresh state before retrying.`); }
      finally { busy = false; node.querySelectorAll('button').forEach(b => b.disabled = false); if (trigger.isConnected) trigger.focus(); }
    })); });
    if (!node.children.length) node.append(el('p', 'help', 'No actions are available in the current server state.'));
    return node;
  }
  async function openCase(id) {
    const token = ++caseGeneration; activeCase = id;
    const target = $('#case-content'); target.replaceChildren(el('h1', '', 'Loading case…')); target.firstChild.id = 'case-title';
    if (!dialog.open) dialog.showModal();
    try { const data = await api(`/api/cases/${encodeURIComponent(id)}`); if (token !== caseGeneration || !dialog.open) return; renderCase(data, id); }
    catch (error) { if (token === caseGeneration) { showError(target,error,() => openCase(id)); target.querySelector('h2').id = 'case-title'; } }
  }
  function localSource(link, url) {
    if (!url.startsWith('/fixtures/')) return;
    link.addEventListener('click', async event => {
      event.preventDefault();
      const current = window.uptimeAuth.session();
      if (!current) return account();
      try {
        const response = await fetch(url.split('#')[0], {headers:{Authorization:'Bearer '+current.token},
          credentials:'omit', redirect:'error', cache:'no-store'});
        if (!response.ok) throw new Error('Unable to read the local source');
        const details = el('details', 'record');
        add(details, el('summary', '', 'Source text'), el('pre', '', await response.text()));
        details.open = true; link.after(details);
      } catch (error) { announce(error.message); }
    });
  }
  function renderCase(data, id) {
    const name = el('h1', '', data.title || data.vendor || id); name.id = 'case-title';
    const target = $('#case-content'); target.replaceChildren(name, el('p', 'help', `${display(data.vendor)} / ${id}`), add(el('div', 'case-meta'), badge(data.outcome), badge(data.stage)), sources(data.sources));
    const financials = panel('Financial stages'); list(data.financials).forEach(f => financials.append(add(el('div', 'record'), el('h3', '', f.label), el('div', 'metric-value', f.value), sources(f.sources)))); if (!list(data.financials).length) financials.append(empty('No financial stages returned.'));
    const clauses = panel('Governing clauses'); list(data.clauses).forEach(c => { const url = safeURL(c.uri); const item = el(url ? 'a' : 'span', 'record', c.label); if (url) { item.href = url; item.target = '_blank'; item.rel = 'noopener noreferrer'; localSource(item, url); } clauses.append(add(el('p'), item)); }); if (!list(data.clauses).length) clauses.append(empty('No governing clauses returned.'));
    const evidence = panel('Evidence'); list(data.evidence).forEach(e => evidence.append(add(el('article', 'record'), el('h3', '', e.label), el('p', '', e.detail), sources(e.sources)))); if (!list(data.evidence).length) evidence.append(empty('No evidence returned.'));
    const trace = panel('Decision trace'); trace.append(add(el('ol', 'trace'), ...list(data.trace).map(t => el('li', '', t))));
    const history = panel('Case timeline'); history.append(timeline(data.timeline));
    const available = panel('Available actions'); add(available, el('p', 'help', 'Only actions offered by the server appear here. The server verifies this session’s permissions on every request.'), actions(data.actions, `/api/cases/${encodeURIComponent(id)}/actions`, async () => { await openCase(id); await load(); }));
    add(target, financials, add(el('div', 'section-grid'), clauses, evidence), trace, history, available, guide(id));
  }
  function guide(id) {
    const node = panel('Contextual guide'); node.append(el('p', 'help', 'Ask about this case’s evidence, calculation or next step. The guide is read-only and cannot perform actions.'));
    const form = el('form', 'guide-form'), input = el('textarea'); input.required = true; input.maxLength = 2000; input.placeholder = 'What evidence supports this case?';
    const submit = el('button', '', 'Ask guide'); submit.type = 'submit'; const answer = el('div', 'guide-answer'); answer.setAttribute('aria-live', 'polite');
    add(form, add(el('label', '', 'Question about this case'), input), submit); form.addEventListener('submit', async event => { event.preventDefault(); if (!input.value.trim()) return; submit.disabled = true; answer.textContent = 'Reading case context…'; try { const data = await api('/api/guide', {case_id:id,question:input.value.trim()}); answer.replaceChildren(el('p', '', data.answer), sources(data.sources)); } catch(error) { answer.textContent = error.message || 'Guide unavailable. Check your local connection and try again.'; } finally { submit.disabled = false; } });
    return add(node, form, answer);
  }
  function renderOnboarding(data) {
    const overview = panel(display(data.vendor)); add(overview, el('div', 'lab-state', display(data.state)), el('p', 'help', `Version ${display(data.version)}`), sources(data.sources), actions(data.actions, '/api/onboarding/actions', load));
    const checks = panel('Validation & shadow checks'); list(data.checks).forEach(check => { const passed = check.passed === true; add(checks, add(el('div', 'check'), el('span', passed ? 'pill valid' : 'pill pending', passed ? 'Passed' : check.passed === false ? 'Not passed' : 'Pending'), el('strong', '', check.label), el('p', '', check.detail), check.sources ? sources(check.sources) : null)); }); if (!list(data.checks).length) checks.append(empty('No validation results returned.'));
    const history = panel('Candidate history'); add(history, el('p', 'help', 'Each transition is recorded against the candidate version and reviewer.'), timeline(data.audit || data.history, true));
    const terms=panel('Governing sources');terms.append(el('p','',data.scope || 'Candidate scope unavailable.'));
    list(data.clauses).forEach(c=>{
      const url=safeURL(c.uri); if(!url) return;
      const link=el('a','record',c.label);link.href=url;link.target='_blank';link.rel='noopener noreferrer';localSource(link,url);terms.append(link);
    });
    const limits=panel('Coverage limits');
    list(data.limits).forEach(limit=>limits.append(el('p','help',limit)));
    const detail=el('details','panel');add(detail,el('summary','','Inspect generated rules and customer overlay'),record({template:data.template,overlay:data.overlay,sources:data.sources}));
    content.replaceChildren(heading('Vendor onboarding','Review the generated adapter, its shadow evaluations and the authority required to activate it.'),overview,add(el('div','section-grid'),checks,history),add(el('div','section-grid'),terms,limits),detail);
  }
  function renderPolicy(data) {
    const rules = panel('Execution policy');
    add(rules, badge(data.mode), el('p', '', data.scope), el('p','help',data.reviewer_controls), sources(data.sources));
    if (data.can_configure) {
      const mode = el('select');
      for (const option of data.available_modes) mode.add(new Option(option.replaceAll('_',' '),option));
      mode.value = data.mode;
      const cap=el('input'); cap.value=data.cap; cap.inputMode='decimal'; cap.maxLength=12;
      const save=button('Save local policy',async () => {
        save.disabled=true;
        try {
          renderPolicy(await api('/api/policy',{mode:mode.value,cap:cap.value}));
          announce('Local policy saved.');
        } catch(error) { announce(error.message); save.disabled=false; }
      },'primary');
      add(rules,add(el('div','filters'),add(el('label','','Mode'),mode),add(el('label','','USD ceiling'),cap),save));
    }
    const history=panel('Policy changes');
    if (!list(data.history).length) history.append(empty('Default assisted mode. No policy changes recorded.'));
    else history.append(timeline(data.history.map(r=>({at:r.at,event:r.actor+' selected '+r.mode+' · USD '+r.cap,sources:data.sources}))));
    content.replaceChildren(heading('Policies','Role: '+data.role+'. Only local simulated work is eligible for automation.'),rules,history);
  }

  function renderIntegrations(data) {
    const ramp=data.ramp, publicData=data.public_evidence, model=data.model;
    const bills=panel('Ramp Bill Pay');
    add(bills,el('p','',ramp.note),sources(ramp.sources));
    if (ramp.observed_at) bills.append(el('p','help','Retrieved '+ramp.observed_at));
    if (ramp.ui_url) {
      const link=el('a','case-link','Open Ramp sandbox'); link.href='https://demo.ramp.com'; link.target='_blank';link.rel='noopener noreferrer';bills.append(link);
    }
    for (const [name,obj] of Object.entries(ramp.capabilities || {})) {
      bills.append(el('p','help',name+' · '+(obj.state || 'checked')+' · granted '+(list(obj.granted).join(', ') || 'none')));
    }
    for (const b of ramp.bills) {
      const row=el('div','record'); const amount=b.amount ? b.amount.currency+' '+b.amount.amount : 'Amount unavailable';
      add(row,el('strong','',amount+' · '+b.approval_status),el('p','help',b.id),sources(ramp.sources));
      if(ramp.ui_url) row.append(button('Inspect bill mapping',()=>openCase('ramp-'+b.id),'quiet'));
      bills.append(row);
    }
    const feed=panel('Twilio status evidence');
    add(feed,el('p','',publicData.items.length+' captured incident leads. Customer impact and claimable fees require separate proof.'),sources(publicData.sources));
    list(publicData.items).slice(0,3).forEach(item=>add(feed,add(el('div','record'),el('strong','',item.label),el('p','help',item.detail),el('p','help',item.ref))));
    const extraction=panel('Verified model run');
    add(extraction,el('strong','',model.model),el('p','',model.note),el('p','help','Input SHA-256 · '+model.input_digest),sources(model.sources));
    content.replaceChildren(heading('Integrations','Provider observations, evidence sources and verified model provenance.'),bills,add(el('div','section-grid'),feed,extraction));
  }
  async function load() {
    const token = ++generation; const route = view; content.setAttribute('aria-busy', 'true');
    try { const data = await api(`/api/${route}`); if (token !== generation) return; if (route === 'dashboard') renderDashboard(data); else if (route === 'onboarding') renderOnboarding(data); else if (route === 'policy') renderPolicy(data); else renderIntegrations(data); }
    catch (error) { if (token === generation) { if (error.status === 401) account(); else showError(content,error,load); } }
    finally { if (token === generation) content.setAttribute('aria-busy', 'false'); }
  }
  function navigate() { const requested = location.hash.slice(1); view = ['dashboard','onboarding','policy','integrations'].includes(requested) ? requested : 'dashboard'; document.querySelectorAll('[data-view]').forEach(link => { if (link.dataset.view === view) link.setAttribute('aria-current','page'); else link.removeAttribute('aria-current'); }); content.replaceChildren(empty('Loading server state…')); announce(''); load(); }
  $('#close-inspector').addEventListener('click', () => dialog.close()); dialog.addEventListener('close', () => { caseGeneration++; activeCase = null; });
  $('#refresh').addEventListener('click', () => { announce(''); load(); if (dialog.open && activeCase) openCase(activeCase); });
  $('#account').addEventListener('click', () => {
    const current = window.uptimeAuth.session();
    if (current) window.uptimeAuth.signOut();
    else account();
  });
  window.addEventListener('hashchange', navigate); navigate();
})();
