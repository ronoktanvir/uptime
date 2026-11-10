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
  // Server labels already name the financial stage and its destination (for example "Vendor awarded" or "Record
  // scoped simulated credit"). They are shown as sent: the browser never renames a state or hides where a record went.
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
  function companionPlan(value) {
      if (!value || typeof value !== 'object') return value;
      const {method, path: proposedPath, required_scope, ...rest} = value;
      return {...rest, server_status:value.status, status:value.object_type === 'bills' ? 'READ_ONLY_PROPOSAL' : 'UNSUPPORTED_ENTITY',
        delivery:value.delivery, note:'Plan inspection only. No browser dispatch is offered. The installed native binding supports bill comments only; exact independent permission and current provider grants are required.'};
  }
  // Primary destinations map onto existing views; every older route hash still works.
  const DESTINATIONS = {overview:'ramp', cases:'disputes', agreements:'vendors', activity:'activity'};
  function companionRoute(requested) {
    if (Object.prototype.hasOwnProperty.call(DESTINATIONS, requested)) return DESTINATIONS[requested];
    if (requested.startsWith('cases/')) return 'disputes/' + requested.slice(6);
    if (requested === 'rehearsal') return 'dashboard';
    if (requested === 'records') return 'records';
    // One Ramp bill by Ramp's own id, for the panel beside Ramp; with no id, the panel's "no bill open" page.
    if (requested.startsWith('ramp-bill/')) return 'ramp-bill';
    if (requested === 'ramp-bill') return 'ramp-bill-none';
    // A Ramp page that is not one bill: the bills Uptime is tracking.
    if (requested === 'ramp-bills') return 'ramp-bills';
    if (requested === 'ramp' || requested.startsWith('ramp/')) return 'ramp';
    return ['dashboard','onboarding','lab','regression','advanced','vendors','disputes','policy','integrations'].includes(requested) || requested.startsWith('disputes/') ? requested : 'ramp';
  }
  // ---- Panel mode ----
  // The server lets exactly one named browser extension frame this app (its side panel beside Ramp); every other
  // framing page is refused by the browser. So a framed page is the panel, and only a framed page is in panel mode.
  // Panel mode changes presentation only: a compact header, and one button that asks the panel to open the full app.
  function framed(win) {
    try { return !!win && win.self !== win.top; } catch { return true; }
  }
  // The routes the panel may ask to open in a full tab. The extension enforces the same pattern on its side.
  const PANEL_OPEN_ROUTE = /^(?:overview|records|recovery|cases|cases\/[A-Za-z0-9][A-Za-z0-9._-]{0,63})$/;
  const PANEL_MESSAGE_TYPE = 'uptime-open-app';
  // The extension page that frames this one, when the browser names it; the message is addressed to it alone.
  function panelParent(loc) {
    const origins = loc && loc.ancestorOrigins;
    const first = origins && origins.length === 1 ? origins[0] : null;
    return typeof first === 'string' && /^chrome-extension:\/\/[a-p]{32}$/.test(first) ? first : null;
  }
  function panelMessage(route) {
    return PANEL_OPEN_ROUTE.test(route) ? {type: PANEL_MESSAGE_TYPE, route} : null;
  }
  // Tells the panel whether the bill it shows is matched to an Uptime invoice, for the toolbar badge.
  const PANEL_STATUS_TYPE = 'uptime-bill-status';
  const RAMP_BILL = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
  // Asks the panel to move the Ramp tab to one bill from the tracking list.
  const PANEL_BILL_TYPE = 'uptime-open-bill';
  function openBillMessage(bill) {
    return typeof bill === 'string' && RAMP_BILL.test(bill) ? {type: PANEL_BILL_TYPE, bill} : null;
  }
  function billStatusMessage(bill, state) {
    return typeof bill === 'string' && RAMP_BILL.test(bill) && (state === 'match' || state === 'none') ? {type: PANEL_STATUS_TYPE, bill, state} : null;
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {compareDecimal, money, safeURL, companionPlan, companionRoute,
    framed, panelParent, panelMessage, PANEL_OPEN_ROUTE, PANEL_MESSAGE_TYPE, billStatusMessage, PANEL_STATUS_TYPE, openBillMessage, PANEL_BILL_TYPE};
  if (typeof document === 'undefined') return;
  const panelMode = framed(window);
  if (panelMode) document.documentElement?.classList?.add('panel-mode');
  // Asks the extension shell to open the full app at an allowed route. It sends a route and nothing else; when no
  // extension parent is named, it opens the route in a new tab itself.
  function openApp(route) {
    const message = panelMessage(route), parent = panelParent(window.location);
    if (!message) return;
    if (parent && window.parent && window.parent !== window) window.parent.postMessage(message, parent);
    else window.open('/#' + route, '_blank', 'noopener');
  }
  // Only inside the panel, and only to the one extension origin the browser names as the parent.
  function openBill(bill) {
    const message = openBillMessage(bill), parent = panelParent(window.location);
    if (message && parent && window.parent && window.parent !== window) window.parent.postMessage(message, parent);
  }
  function billState(bill, state) {
    const message = billStatusMessage(bill, state), parent = panelParent(window.location);
    if (message && parent && window.parent && window.parent !== window) window.parent.postMessage(message, parent);
  }
  const $ = selector => document.querySelector(selector);
  const content = $('#content'), notice = $('#notice'), dialog = $('#inspector');
  let view = 'ramp', generation = 0, caseGeneration = 0, activeCase = null, busy = false;
  let rampCase = null, rampScroll = 0, rampBill = null;
  // Which page a Ramp record was opened from: it stays the marked destination, and "Back" returns to it.
  let rampOrigin = 'ramp';
  let companion, companionAssets, signedPage = false, companionAccess = {};
  const ramp = window.UptimeRamp?.create({api, onNavigate: route => { history.pushState(null, '', '#' + (route === 'ramp' ? rampOrigin : route)); navigate(); },
    ...(panelMode ? {openApp, onBillState: billState, openBill} : {})});
  // The finance view disables actions when this page holds no signing key (for example after a reload).
  const workspaceWorkflow = window.UptimeWorkspace?.create({api,onUnauthorized:account,canAct:() => window.uptimeAuth?.canSign?.() !== false});
  const filters = {query: '', status: '', sort: 'value-desc'};
  function el(tag, className, text) { const node = document.createElement(tag); if (className) node.className = className; if (text != null) node.textContent = display(text); return node; }
  function add(parent, ...children) { children.flat().filter(Boolean).forEach(child => parent.append(child)); return parent; }
  function button(label, handler, className = '') { const node = el('button', className, label); node.type = 'button'; node.addEventListener('click', handler); return node; }
  function sources(values) {
    const node = el('div', 'sources');
    if (!list(values).length) node.append(el('span','missing-source','Source not provided'));
    list(values).filter(value => value && typeof value === 'object').forEach(value => {
      if (value.ref || value.title || value.uri) node.append(el('span', 'source', value.ref || value.title || value.uri));
    });
    return node;
  }
  function badge(value) { const text = display(value); return el('span', /pending|draft|shadow|review|insufficient|submitted/i.test(text) ? 'pill pending' : 'pill', text); }
  function heading(name, detail) { return add(el('div', 'page-head'), add(el('div'), el('h1', '', name), el('p', '', detail))); }
  function panel(name) { return add(el('section', 'panel'), el('h2', '', name)); }
  function empty(text) { return el('p', 'empty', text); }
  function announce(text) { notice.className = 'notice'; notice.textContent = text; }
  async function api(path, payload) {
    const data = await window.uptimeAPI(path, payload);
    // The legacy plan advertises provider paths beyond the mounted bill-only binding.
    if (payload === undefined && /^\/api\/ramp\/records\//.test(path)) {
      if (path.endsWith('/workflow')) return companionPlan(data);
      if (data.native_workflow) return {...data, native_workflow:companionPlan(data.native_workflow)};
    }
    return data;
  }
  // One workspace name on every route, whatever page is opened first: the company from the workflow projection,
  // read once per sign-in, or the product name when the workspace has no configured workflow.
  let workspaceName = null, workspaceNameRead = null;
  // Presentation only: up to two initials of a name, for the tile beside it.
  const initials = value => String(value || '').split(/[\s._-]+/).filter(Boolean).slice(0, 2).map(part => part[0].toUpperCase()).join('');
  function showAccount(subject) {
    const control = $('#account');
    control.textContent = 'Sign out · ' + subject;
    if (typeof control.setAttribute === 'function') control.setAttribute('data-initials', initials(subject));
  }
  function showWorkspaceName() {
    const name = workspaceName || 'Uptime';
    const slot = $('#workspace-name');
    slot.textContent = name;
    const tile = document.querySelector?.('.rail-avatar');
    if (tile) { tile.textContent = initials(name); tile.className = 'rail-avatar brand-' + String(name).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''); }
    // Without a workspace name the line under the brand would only repeat the product name.
    if (slot.parentElement) slot.parentElement.hidden = !workspaceName;
    document.title = workspaceName ? workspaceName + ' · Uptime' : 'Uptime';
  }
  function companyOf(workflow) {
    const company = workflow && typeof workflow === 'object' ? (workflow.company?.name || workflow.company) : null;
    return typeof company === 'string' && company ? company : null;
  }
  function readWorkspaceName() {
    if (!workspaceNameRead) {
      workspaceNameRead = api('/api/workspace/workflow')
        .then(projection => { const company = companyOf(projection && projection.workflow); if (company) workspaceName = company; })
        .catch(() => { workspaceNameRead = null; });
    }
    return workspaceNameRead;
  }
  function account() {
    generation++; signedPage = false; companionAccess = {}; workspaceName = null; workspaceNameRead = null;
    content.setAttribute('aria-busy', 'false');
    ramp?.unmount(); workspaceWorkflow?.unmount(); companion?.unmount(content);
    if (dialog.open) dialog.close();
    content.replaceChildren(window.uptimeAuth.signInForm(() => { signedPage = true; navigate(); }));
  }
  function showError(target, error, retry) { target.replaceChildren(add(el('section', 'panel error'), el('h2', '', 'Unable to load this view'), el('p', '', error.message || 'Connection unavailable. Check that the server is running.'), button('Try again', retry, 'quiet'))); }
  // Presentation only: an instant with an explicit offset is written as the other pages write it ("Nov 9, 2026,
  // 23:18 UTC"); the exact server value stays on the element. Anything else is shown as sent.
  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  function instant(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)) return null;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return null;
    return `${MONTHS[date.getUTCMonth()]} ${date.getUTCDate()}, ${date.getUTCFullYear()}, ${String(date.getUTCHours()).padStart(2, '0')}:${String(date.getUTCMinutes()).padStart(2, '0')} UTC`;
  }
  function moment(value) {
    const shown = instant(value), node = el('time', '', shown || value);
    if (shown) { node.setAttribute('datetime', value); node.title = value; }
    return node;
  }
  function timeline(items, history = false) {
    const node = el('ol', 'activity');
    list(items).forEach(item => { const row = el('li'); if (typeof item === 'string') add(row, el('span', '', item), sources([])); else add(row, moment(item.at), el('span', '', display(item.event)), item.case_id ? el('div', 'help', `Case ${item.case_id}`) : null, sources(item.sources)); node.append(row); });
    return node.children.length ? node : empty(history ? 'No history returned by the server.' : 'No events returned by the server.');
  }
  // Unknown policy/integration fields remain read-only; source arrays are never renamed or inferred.
  function record(value) {
    if (value == null || typeof value !== 'object') return el('span', '', display(value));
    if (Array.isArray(value)) { const node = el('div'); value.forEach(item => node.append(add(el('div', 'record'), record(item)))); return node; }
    const node = el('dl', 'record');
    Object.entries(value).forEach(([key, val]) => {
      if (['source_mode','data_provenance','classification'].includes(key) || key === 'mode' && /replay|simulat|demo/i.test(String(val))) return;
      if (key === 'sources') { add(node, el('dt', '', 'Sources'), add(el('dd'), sources(val))); return; }
      add(node, el('dt', '', title(key)), add(el('dd'), typeof val === 'object' && val !== null ? record(val) : el('span', '', display(val))));
    });
    return node;
  }
  function renderDashboard(data) {
    const head = heading('Evidence ledger', 'Unpaid invoice exposure and the current recovery case. Each figure belongs to a separate financial stage.');
    head.append(el('div', 'as-of', `Updated ${instant(data.as_of) || display(data.as_of)}`));
    const metrics = el('section', 'metrics'); metrics.setAttribute('aria-label', 'Financial stages');
    list(data.metrics).forEach(metric => metrics.append(add(el('article', 'metric'), el('h2', '', display(metric.label)), el('div', 'metric-value', metric.value), el('p', '', display(metric.note)), sources(metric.sources))));
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
      cases.forEach(c => body.append(add(el('tr'), add(el('td'), button(display(c.vendor || c.id), () => openCase(c.id), 'case-link'), el('div', 'case-subtitle', display(c.title)), el('div', 'help', c.id)), add(el('td'), badge(c.outcome)), add(el('td'), badge(c.stage)), add(el('td', 'amount'), el('div', '', money(c.amount,c.currency)), sources(c.sources)))));
      if (!cases.length) { const td = el('td', 'empty', 'No cases match these filters. Clear search or select all statuses.'); td.colSpan = 4; body.append(add(el('tr'), td)); }
      count.textContent = `${cases.length} of ${list(data.cases).length} cases. Values are server-provided; no stages are added together.`;
    }
    search.addEventListener('input', () => { filters.query = search.value; rows(); }); status.addEventListener('change', () => { filters.status = status.value; rows(); }); sort.addEventListener('change', () => { filters.sort = sort.value; rows(); });
    add(ledger, add(el('div', 'ledger-head'), el('h2', '', 'Case ledger'), controls, count), add(el('div', 'table-scroll'), table)); rows();
    const audit = panel('Activity'); audit.append(timeline(data.audit));
    const ramp = panel('Ramp connection'); ramp.append(record(data.ramp || {status: 'Not provided'}));
    const current = window.uptimeAuth.session();
    if (current) showAccount(current.subject);
    content.replaceChildren(head, metrics, ledger, add(el('div', 'section-grid'), audit, ramp));
    showWorkspaceName();
  }
  function actions(items, path, reload) {
    const node = el('div', 'actions');
    list(items).forEach(action => {
      if (!action.id) return;
      const trigger = button(display(action.label || action.id), async () => {
        if (busy) return;
        busy = true;
        document.querySelectorAll('[data-domain-action]').forEach(control => { control.disabled = true; });
        announce('Sending action for server authorization…');
        try {
          await api(`${path}/${encodeURIComponent(action.id)}`, {});
          await reload();
          announce('Action recorded.');
        } catch (error) {
          announce(`${error.message || 'Connection interrupted.'} Refresh to check the recorded outcome.`);
        } finally {
          busy = false;
          document.querySelectorAll('[data-domain-action]').forEach(control => { control.disabled = false; });
          if (trigger.isConnected) trigger.focus();
        }
      });
      trigger.dataset.domainAction = action.id;
      trigger.disabled = busy;
      node.append(trigger);
    });
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
    const name = el('h1', '', display(data.title || data.vendor || id)); name.id = 'case-title';
    const target = $('#case-content'); target.replaceChildren(name, el('p', 'help', `${display(data.vendor)} / ${id}`), add(el('div', 'case-meta'), badge(data.outcome), badge(data.stage)), sources(data.sources));
    const financials = panel('Financial stages'); list(data.financials).forEach(f => financials.append(add(el('div', 'record'), el('h3', '', display(f.label)), el('div', 'metric-value', f.value), sources(f.sources)))); if (!list(data.financials).length) financials.append(empty('No financial stages returned.'));
    if (list(data.financial_refs).length) {
      financials.append(el('h3', '', 'Linked records'));
      data.financial_refs.forEach(ref => {
        if (ref.id) financials.append(add(el('div', 'record'), el('strong', '', title(ref.kind)),
          el('code', '', ref.id), sources(ref.sources)));
      });
    }
    const clauses = panel('Governing clauses'); list(data.clauses).forEach(c => { const url = safeURL(c.uri); const item = el(url ? 'a' : 'span', 'record', c.label); if (url) { item.href = url; item.target = '_blank'; item.rel = 'noopener noreferrer'; localSource(item, url); } clauses.append(add(el('p'), item)); }); if (!list(data.clauses).length) clauses.append(empty('No governing clauses returned.'));
    const evidence = panel('Evidence'); list(data.evidence).forEach(e => evidence.append(add(el('article', 'record'), el('h3', '', display(e.label)), el('p', '', display(e.detail)), sources(e.sources)))); if (!list(data.evidence).length) evidence.append(empty('No evidence returned.'));
    const trace = panel('Decision trace'); trace.append(add(el('ol', 'trace'), ...list(data.trace).filter(t=>!/^Synthetic invoice only; no live Ramp bill bound\.$/.test(t)).map(t => el('li', '', String(t).replace(/^Synthetic line allocation/, 'Line allocation').replace(/^Replayed interval/, 'Evidence interval').replace(/^Simulated scoped,/, 'Scoped,').replace(/^Simulated receipt/, 'Receipt')))));
    const history = panel('Case timeline'); history.append(timeline(data.timeline));
    const available = panel('Available actions'); add(available, el('p', 'help', 'Only actions offered by the server appear here. The server verifies this session’s permissions on every request.'), actions(data.actions, `/api/cases/${encodeURIComponent(id)}/actions`, async () => { await openCase(id); await load(); }));
    if (id.startsWith('inbox-')) {
      const inbox = el('a','case-link','Inspect correspondence evidence & receipts');
      inbox.href = '#disputes/' + encodeURIComponent(id); target.append(inbox);
    }
    add(target, financials, add(el('div', 'section-grid'), clauses, evidence), trace, history, available, guide(id));
  }
  function guide(id) {
    const node = panel('Contextual guide'); node.append(el('p', 'help', 'Ask about this case’s evidence, calculation or next step. The guide is read-only and cannot perform actions.'));
    const form = el('form', 'guide-form'), input = el('textarea'); input.required = true; input.maxLength = 1000; input.placeholder = 'What evidence supports this case?';
    const submit = el('button', '', 'Ask guide'); submit.type = 'submit'; const answer = el('div', 'guide-answer'); answer.setAttribute('aria-live', 'polite');
    add(form, add(el('label', '', 'Question about this case'), input), submit); form.addEventListener('submit', async event => { event.preventDefault(); if (!input.value.trim()) return; submit.disabled = true; answer.textContent = 'Reading case context…'; try { const data = await api('/api/guide', {case_id:id,question:input.value.trim()}); answer.replaceChildren(el('p', '', data.answer), sources(data.sources)); } catch(error) { answer.textContent = error.message || 'Guide unavailable. Check your local connection and try again.'; } finally { submit.disabled = false; } });
    return add(node, form, answer);
  }
  function renderOnboarding(data) {
    const overview = panel(display(data.vendor)); add(overview, el('div', 'lab-state', display(data.state)), el('p', 'help', `Version ${display(data.version)}`), sources(data.sources), actions(data.actions, '/api/onboarding/actions', load));
    const checks = panel('Validation & shadow checks');
    if (data.checks_status) checks.append(add(el('div','record'),el('strong','','Current verification'),badge(data.checks_status)));
    if (list(data.recorded_checks).length) { const previous=el('details','record'); add(previous,el('summary','','Recorded checks'),record(data.recorded_checks)); checks.append(previous); }
    list(data.checks).forEach(check => { const passed = check.passed === true; add(checks, add(el('div', 'check'), el('span', passed ? 'pill valid' : 'pill pending', passed ? 'Passed' : check.passed === false ? 'Not passed' : 'Pending'), el('strong', '', check.label), el('p', '', check.detail), check.sources ? sources(check.sources) : null)); }); if (!list(data.checks).length) checks.append(empty('No validation results returned.'));
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
    content.replaceChildren(heading('Policies','Role: '+data.role+'. Review the execution scope and approval requirements.'),rules,history);
  }

  function renderIntegrations(data) {
    const ramp=data.ramp, publicData=data.public_evidence, model=data.model;
    const bills=add(el('section', 'panel'), el('h2', 'ramp-glyph', 'Ramp Bill Pay'));
    add(bills,el('p','',ramp.note),sources(ramp.sources));
    if (ramp.observed_at) bills.append(el('p','help','Retrieved '+(instant(ramp.observed_at) || ramp.observed_at)));
    if (ramp.ui_url) {
      const link=el('a','case-link','Open Ramp'); link.href='https://demo.ramp.com'; link.target='_blank';link.rel='noopener noreferrer';bills.append(link);
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
    content.replaceChildren(heading('Integrations','Connected records, evidence sources and model verification.'),bills,add(el('div','section-grid'),feed,extraction));
  }
  async function advanced() {
    if (!companionAssets) companionAssets = new Promise((resolve, reject) => {
      const css = document.createElement('link'); css.rel = 'stylesheet'; css.href = '/static/v4_style.css'; document.head.append(css);
      const script = document.createElement('script'); script.src = '/static/v4_ui.js';
      script.onload = resolve; script.onerror = () => { companionAssets = null; script.remove(); css.remove(); reject(new Error('Companion asset unavailable.')); };
      document.head.append(script);
    });
    await companionAssets;
    companion ||= window.UptimeV4.create({api, getAccess:() => companionAccess, onCase:openCase, onUnauthorized:account,
      reviewForms:true, onRefresh:load, reloadAfterMutation:true});
    return companion;
  }
  async function loadCompanion(route, token) {
    const ui = await advanced();
    const policy = await api('/api/policy');
    if (token !== generation) return;
    const session = window.uptimeAuth.session();
    if (session) showAccount(session.subject);
    companionAccess = {identity:session?.subject, enrollment:policy.role,
      gate:session?.approvals_enabled === true ? 'Deployment approvals enabled; server rechecks every request' : 'Read-only deployment',
      canWrite:signedPage && policy.role === 'reviewer' && session?.approvals_enabled === true,
      canDraft:signedPage && session?.role === 'reviewer' && session?.drafts_enabled === true};
    if (route === 'vendors' || route === 'disputes') return ui.render(content,route);
    if (route.startsWith('disputes/')) return ui.inspect(content,decodeURIComponent(route.slice(9)));
    if (route === 'regression') {
      const data = await api('/api/dashboard');
      if (token === generation) return ui.render(content,'portfolio',data.cohorts || {});
      return;
    }
    const data = await api('/api/ramp/workspace');
    if (token === generation) return ui.render(content,'catalog',data);
  }
  // Navigation is declared in index.html: four primary destinations and a secondary group.

  // Load responsive companion navigation styles on the primary worklist too.
  advanced().catch(() => {});
  async function load() {
    const token = ++generation; const route = view; content.setAttribute('aria-busy', 'true');
    // Overview and Activity read the workflow themselves; any other page reads the name once, after its own content.
    const readsWorkflow = route === 'activity' || (route === 'ramp' && !rampCase);
    // The one-bill page makes exactly one request, the saved Ramp workspace, so it does not read the workspace name.
    try { await renderRoute(); } finally {
      if (!readsWorkflow && route !== 'ramp-bill' && route !== 'ramp-bill-none' && route !== 'ramp-bills' && token === generation && !workspaceNameRead) readWorkspaceName().then(() => { if (token === generation) showWorkspaceName(); });
    }
    async function renderRoute() {
    try { if (['advanced','vendors','disputes','regression'].includes(route) || route.startsWith('disputes/')) { await loadCompanion(route, token); return; }
    if (route === 'activity') {
      const projection = await api('/api/workspace/workflow');
      if (token !== generation) return;
      if (projection && projection.workflow && typeof projection.workflow === 'object' && workspaceWorkflow) {
        workspaceName = companyOf(projection.workflow) || workspaceName; workspaceNameRead = Promise.resolve();
        await workspaceWorkflow.activity(content, projection.workflow);
      } else content.replaceChildren(heading('Activity', 'What happened in this workspace, in order.'), empty('No workflow activity is recorded in this workspace.'));
      showWorkspaceName();
      return;
    }
    // No Ramp bill is open in the tab beside the panel. Nothing is read: the page holds no data.
    if (route === 'ramp-bill-none') {
      if (!ramp) throw new Error('Ramp UI asset unavailable.');
      ramp.noBill(content);
      const current = window.uptimeAuth.session();
      if (current) showAccount(current.subject);
      return;
    }
    if (route === 'ramp-bills') {
      if (!ramp) throw new Error('Ramp UI asset unavailable.');
      await ramp.bills(content);
      if (token === generation) { const current = window.uptimeAuth.session(); if (current) showAccount(current.subject); }
      return;
    }
    if (route === 'ramp-bill') {
      if (!ramp) throw new Error('Ramp UI asset unavailable.');
      await ramp.bill(content, rampBill);
      if (token === generation) {
        window.scrollTo?.({top:0, behavior:'instant'});
        showWorkspaceName();
        const current = window.uptimeAuth.session();
        if (current) showAccount(current.subject);
      }
      return;
    }
    if (route === 'ramp' || route === 'records') {
      if (route === 'ramp' && !rampCase) {
        const projection = await api('/api/workspace/workflow');
        if (token !== generation) return;
        if (!Object.prototype.hasOwnProperty.call(projection, 'workflow')) throw new Error('Workspace workflow response unavailable.');
        workspaceNameRead = Promise.resolve();
        if (projection.workflow !== null) {
          if (!workspaceWorkflow || !projection.workflow || typeof projection.workflow !== 'object') throw new Error('Workspace workflow unavailable.');
          await workspaceWorkflow.render(content, projection.workflow);
          workspaceName = companyOf(projection.workflow) || workspaceName;
          showWorkspaceName();
          const current = window.uptimeAuth.session();
          if (current) showAccount(current.subject);
          return;
        }
      }
      if (!ramp) throw new Error('Ramp UI asset unavailable.');
      await ramp.render(content, rampCase);
      if (token === generation) {
        window.scrollTo?.({top:rampCase ? 0 : rampScroll, behavior:'instant'});
        showWorkspaceName();
        const current = window.uptimeAuth.session();
        if (current) showAccount(current.subject);
      }
      return;
    }
    const data = await api(`/api/${route === 'lab' ? 'onboarding' : route}`); if (token !== generation) return; if (route === 'dashboard') renderDashboard(data); else if ((route === 'onboarding' || route === 'lab')) renderOnboarding(data); else if (route === 'policy') renderPolicy(data); else renderIntegrations(data); }
    catch (error) { if (token === generation) { if (error.status === 401) account(); else showError(content,error,load); } }
    finally { if (token === generation) content.setAttribute('aria-busy', 'false'); }
    }
  }
  const narrow = () => typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 760px)').matches;
  function navigate() {
    const requested = location.hash.slice(1);
    if (requested === 'workspace') return; // Skip link is an in-page accessibility target.
    if (view === 'ramp' && !rampCase) rampScroll = window.scrollY || 0;
    if ((view === 'ramp' || view === 'records') && !rampCase) rampOrigin = view;
    ramp?.unmount();
    workspaceWorkflow?.unmount();
    companion?.unmount(content);
    if (dialog.open) dialog.close();
    rampCase = null; rampBill = null;
    if (requested.startsWith('ramp/')) {
      try { rampCase = decodeURIComponent(requested.slice(5)); } catch { rampCase = null; }
    }
    if (requested.startsWith('ramp-bill/')) {
      try { rampBill = decodeURIComponent(requested.slice(10)); } catch { rampBill = null; }
    }
    view = companionRoute(requested);
    // A page under a destination (one case under Cases) keeps that destination marked as the current one.
    // One Ramp record keeps the page it was opened from marked.
    const marked = rampCase ? rampOrigin : view === 'ramp-bill' || view === 'ramp-bill-none' || view === 'ramp-bills' ? 'records' : view;
    document.querySelectorAll('[data-view]').forEach(link => { if (link.dataset.view === marked || marked.startsWith(link.dataset.view + '/')) link.setAttribute('aria-current','page'); else link.removeAttribute('aria-current'); });
    // On a wide screen the group that holds the current page is opened. On a narrow one the header stays slim:
    // the group's own label is marked instead, and the list opens only when asked for.
    const more = document.querySelector?.('.rail-more');
    if (more && more.querySelector?.('[aria-current]') && !narrow()) more.open = true;
    if (!content.children.length) content.append(empty('Loading server state…')); announce(''); load();
  }
  // Updating route history explicitly prevents fragment scrolling during normal navigation.
  document.querySelectorAll('.rail a[href^="#"]').forEach(link => link.addEventListener('click', event => {
    if (event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    // In the panel the brand opens the full app in a tab instead of squeezing it into the panel.
    if (panelMode) { event.preventDefault(); openApp('overview'); return; }
    event.preventDefault(); history.pushState(null, '', link.getAttribute('href')); navigate();
    // A choice made from the narrow header's list closes the list, so the page it opened is in view.
    const group = link.closest?.('.rail-more');
    if (group && narrow()) group.open = false;
  }));
  $('#close-inspector').addEventListener('click', () => dialog.close()); dialog.addEventListener('close', () => { caseGeneration++; activeCase = null; });
  $('#refresh').addEventListener('click', () => { if (view === 'ramp' && !rampCase) rampScroll = window.scrollY || 0; announce(''); load(); if (dialog.open && activeCase) openCase(activeCase); });
  $('#account').addEventListener('click', () => {
    const current = window.uptimeAuth.session();
    if (current) window.uptimeAuth.signOut();
    else account();
  });
  window.addEventListener('hashchange', navigate); navigate();
})();
