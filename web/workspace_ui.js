/* Finance workflow projection. Amounts, actions, evidence and authority are server-owned. */
(function (global) {
  'use strict';
  const list = value => Array.isArray(value) ? value : [];
  const text = value => value == null || value === '' ? 'Not provided' : String(value);
  const names = {ELIGIBLE:'Eligible', INELIGIBLE:'Ineligible', INSUFFICIENT_EVIDENCE:'Needs evidence', UNKNOWN:'Needs evidence',
    SCRIPTED_REVIEWER:'Scripted reviewer', SCRIPTED:'Scripted reviewer', LOCAL_LEDGER:'Local ledger'};
  const reason = value => text(value).replace(/^Synthetic invoice only; no live Ramp bill bound\.;?\s*/, '').replace(/^Simulated scoped,/, 'Scoped,');
  const state = value => names[value] || text(value).replaceAll('_', ' ').toLowerCase();
  function money(value, currency = 'USD') {
    if (value == null || value === '') return 'Not determined';
    const raw = String(value);
    if (!/^-?\d+(\.\d+)?$/.test(raw)) return 'Not determined';
    const [whole, fraction] = raw.split('.');
    return `${currency === 'USD' ? '$' : text(currency) + ' '}${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}${fraction == null ? '' : '.' + fraction}`;
  }
  // Presentation-only formatting. Values keep their exact server form in the inspectors.
  const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  function parseInstant(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}/.test(value)) return null;
    const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? value + 'T00:00:00Z' : value);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  function day(value) {
    const date = parseInstant(value);
    return date ? `${MONTHS[date.getUTCMonth()].slice(0, 3)} ${date.getUTCDate()}, ${date.getUTCFullYear()}` : text(value);
  }
  // A period between two server dates, written once when both fall in the same year: "Apr 1 – May 1, 2026".
  function period(start, end) {
    const a = parseInstant(start), b = parseInstant(end);
    if (!a || !b) return day(start) + ' – ' + day(end);
    return a.getUTCFullYear() === b.getUTCFullYear()
      ? `${MONTHS[a.getUTCMonth()].slice(0, 3)} ${a.getUTCDate()} – ${day(end)}` : day(start) + ' – ' + day(end);
  }
  function when(value) {
    const date = parseInstant(value);
    if (!date) return text(value);
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return day(value);
    return `${day(value)}, ${String(date.getUTCHours()).padStart(2, '0')}:${String(date.getUTCMinutes()).padStart(2, '0')} UTC`;
  }
  function monthLabel(value) {
    const m = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(String(value));
    return m ? `${MONTHS[Number(m[2]) - 1]} ${m[1]}` : text(value);
  }
  const monthOnly = value => { const date = parseInstant(value) || parseInstant(String(value) + '-01'); return date ? MONTHS[date.getUTCMonth()] : null; };
  // An evaluator fraction such as 20000000/1000000% is shown as an exact percent. Only power-of-ten
  // denominators are converted, by moving the decimal point; no arithmetic changes.
  function rates(value) {
    return text(value).replace(/(-?)(\d+)\/1(0+)%/g, (_, sign, digits, zeros) => {
      const k = zeros.length, padded = digits.padStart(k + 1, '0');
      const whole = padded.slice(0, -k).replace(/^0+(?=\d)/, ''), fraction = padded.slice(-k).replace(/0+$/, '');
      return sign + whole + (fraction ? '.' + fraction : '') + '%';
    });
  }
  // A server instant inside a sentence (for example a filing cutoff) is shown as a date and time; the text is otherwise unchanged.
  const instants = value => text(value).replace(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})/g, match => when(match));
  const shortRef = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value) ? value.slice(0, 10) + '…' : text(value);
  // A 64-character fingerprint inside a sentence is shown by its first ten characters; the exact value stays in the inspectors.
  const fingerprints = value => text(value).replace(/\b[0-9a-f]{64}\b/g, match => match.slice(0, 10) + '…');
  const isZero = value => /^-?0*(\.0*)?$/.test(String(value));
  // Steps in order: pure readings of the server's recorded steps. Nothing here creates, reorders or invents a step.
  // The recorded order is the server's sequence number; without one on every step, the order the server sent.
  function recordedOrder(steps) {
    const rows = list(steps).filter(step => step && typeof step === 'object');
    if (!rows.every(step => Number.isInteger(step.seq))) return rows;
    return rows.map((step, index) => [step, index]).sort((a, b) => a[0].seq - b[0].seq || a[1] - b[1]).map(([step]) => step);
  }
  // The latest reviewer decision and every step recorded after it, in recorded order, with the steps before it.
  function replayGroup(steps) {
    const ordered = recordedOrder(steps);
    let at = -1;
    ordered.forEach((step, index) => { if (step.authority && step.authority.kind === 'PERSON') at = index; });
    if (at < 0) return null;
    return {decision: ordered[at], before: ordered.slice(0, at), replay: ordered.slice(at)};
  }
  // Who did what, counted from the recorded steps. An automatic step counts once it completed, as the server counts
  // it; the server's own two counts are compared, never replaced, and a difference is reported.
  function stepLegend(steps, counts) {
    const ordered = recordedOrder(steps), kind = step => step.authority && step.authority.kind, done = step => step.state === 'COMPLETED';
    const reviewer = ordered.filter(step => kind(step) === 'PERSON').length;
    const approved = ordered.filter(step => kind(step) === 'APPROVED_OPERATION' && done(step)).length;
    const received = ordered.filter(step => kind(step) === 'EVENT_INTAKE' && done(step)).length;
    const other = ordered.length - reviewer - approved - received;
    const c = counts && typeof counts === 'object' ? counts : {};
    const agrees = (c.person_decisions == null || c.person_decisions === reviewer) && (c.automatic_steps == null || c.automatic_steps === approved + received);
    return {reviewer, approved, received, other, total: ordered.length, agrees,
      server: {person_decisions: c.person_decisions == null ? null : c.person_decisions, automatic_steps: c.automatic_steps == null ? null : c.automatic_steps}};
  }
  const REPLAY_PACE_MS = 1600, REPLAY_KEY = 'uptime.steps.replay', REPLAY_SEEN_KEY = 'uptime.steps.replay.seen';
  // Who did the work, as three plain actors. The reviewer account decides; Uptime's agent runs a step under an approval
  // already recorded (fixed automation, not a model); a received event is named by the source the server names.
  const SOURCE_NAMES = {vendor:'Vendor', customer:'Customer source', status:'Status source', billing:'Billing source'};
  function actorTag(step) {
    const authority = step && step.authority && typeof step.authority === 'object' ? step.authority : {};
    if (authority.kind === 'PERSON') return {label:'Reviewer decision', cls:'accent tag-reviewer'};
    if (authority.kind === 'APPROVED_OPERATION') return {label:'Uptime agent', cls:'tag-agent'};
    if (authority.kind === 'EVENT_INTAKE') {
      const suffix = typeof authority.source_subject === 'string' ? authority.source_subject.split('-').pop() : null;
      return {label:SOURCE_NAMES[suffix] || 'Received event', cls:'tag-received' + (suffix === 'vendor' ? ' tag-vendor' : '')};
    }
    return null;
  }
  // The short line shown before a recorded step appears on the Overview. It names the step about to be shown.
  const LEAD_IN = {'submit-claim':'Filing the claim with the vendor', 'receive-denial':'Receiving the vendor’s reply',
    'receive-artifact':'Attaching the requested service log', 'receive-verification':'Matching the service log to the request',
    'submit-response':'Sending the response to the vendor', 'receive-award':'Receiving the vendor’s credit decision',
    'record-credit':'Posting the credit', 'receive-invoice':'Receiving the next invoice', 'apply-balance':'Applying the credit'};
  function leadIn(step) {
    const s = step && typeof step === 'object' ? step : {};
    return (LEAD_IN[s.operation] || (typeof s.label === 'string' && s.label ? s.label : 'Next recorded step')) + '…';
  }
  // The steps a decision added: those after the last step the page held before it, in recorded order.
  function newSteps(prior, next) {
    const before = recordedOrder(prior && prior.automation && prior.automation.steps), after = recordedOrder(next && next.automation && next.automation.steps);
    if (before.every(s => Number.isInteger(s.seq)) && after.every(s => Number.isInteger(s.seq))) {
      const last = before.reduce((max, s) => Math.max(max, s.seq), 0);
      return after.filter(s => s.seq > last);
    }
    return after.slice(before.length);
  }
  // What the Overview's figures show while a decision's steps are still being shown: the server's new projection, with
  // each credit stage (and the bill) held at its earlier recorded value until the step that recorded it is shown, and the
  // claim's stage held until the last one is. Display only; with nothing pending it is exactly the new projection.
  const STAGE_BY_OPERATION = {'submit-claim':'claimed', 'receive-award':'awarded', 'record-credit':'posted', 'apply-balance':'applied'};
  function stagedView(prior, next, pending) {
    const waiting = list(pending).filter(s => s && typeof s === 'object');
    if (!waiting.length || !prior || typeof prior !== 'object') return next;
    const held = new Set(waiting.map(s => STAGE_BY_OPERATION[s.operation]).filter(Boolean));
    const priorFinance = prior.finance && typeof prior.finance === 'object' ? prior.finance : {}, finance = next.finance && typeof next.finance === 'object' ? next.finance : {};
    const priorRows = list(priorFinance.stages);
    const stages = list(finance.stages).map(row => row && held.has(row.stage) ? priorRows.find(old => old && old.stage === row.stage) || row : row);
    const billHeld = waiting.some(s => s.operation === 'apply-balance' || s.operation === 'receive-invoice');
    return {...next, claim: prior.claim || next.claim, ledger: billHeld ? prior.ledger || next.ledger : next.ledger,
      finance: {...finance, stages, bill: billHeld ? priorFinance.bill : finance.bill}};
  }
  function create({api, document:doc = global.document, onRefresh = () => {}, onUnauthorized, canAct = () => true,
    storage, schedule = (callback, ms) => global.setTimeout(callback, ms), reducedMotion}) {
    // The replay setting lasts for this page's session. Browser storage may be absent or refuse; memory stands in.
    const memory = {};
    const session = (() => { if (storage !== undefined) return storage; try { return global.sessionStorage || null; } catch (_) { return null; } })();
    const readSetting = key => { try { const value = session ? session.getItem(key) : null; if (value != null) return value; } catch (_) { /* memory below */ } return memory[key] == null ? null : memory[key]; };
    const writeSetting = (key, value) => { memory[key] = value; try { if (session) session.setItem(key, value); } catch (_) { /* memory holds it */ } };
    const still = () => { if (typeof reducedMotion === 'function') return reducedMotion() === true;
      try { return typeof global.matchMedia === 'function' && global.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (_) { return false; } };
    // After a recorded action the page re-renders and focus moves to the recovery heading, never to the next
    // decision: a held or repeated Enter must not approve the next step. The status names what was recorded and what
    // comes next, one Tab away.
    let epoch = 0, busy = false, uncertain = false, focusNextStep = false, recordedLabel = null;
    // The projection this page last drew, the one a pressed decision leaves behind, and the running Overview replay's stop.
    let lastData = null, pendingReplay = null, stopReplay = null;
    const replayOn = () => readSetting(REPLAY_KEY) !== 'off';
    const el = (tag, value, cls) => { const n = doc.createElement(tag); if (value != null) n.textContent = text(value); if (cls) n.className = cls; return n; };
    const add = (n, ...children) => { children.filter(Boolean).forEach(c => n.append(c)); return n; };
    const note = value => el('p',value,'help');
    const SECTION_IDS = {agreement:'finance-agreement', recovery:'finance-recovery', months:'finance-months', price:'finance-price',
      bill:'finance-bill', coverage:'finance-coverage', ramp:'finance-ramp', attention:'finance-attention', guide:'finance-guide'};
    const panel = (title, key) => {
      const heading = el('h2', title), node = add(el('section', null, 'panel'), heading);
      if (key && SECTION_IDS[key]) { node.id = SECTION_IDS[key]; heading.tabIndex = -1; }
      return node;
    };
    // A closed section: the same content, one click away. Its summary takes focus when a link jumps to it.
    const fold = (title, key) => {
      const node = add(el('details', null, 'panel fold'), add(el('summary'), el('h2', title)));
      if (key && SECTION_IDS[key]) node.id = SECTION_IDS[key];
      return node;
    };
    // Move to a section without changing the route hash, which the shell uses for navigation.
    function jump(sectionId) {
      const target = typeof doc.getElementById === 'function' ? doc.getElementById(sectionId) : null;
      if (!target) return;
      // A section inside a closed disclosure is opened first, so its heading can be seen and take focus.
      for (let node = target; node && node.tagName; node = node.parentElement) if (node.tagName === 'DETAILS') node.open = true;
      if (typeof target.scrollIntoView === 'function') target.scrollIntoView({block:'start'});
      const heading = target.querySelector ? target.querySelector(target.tagName === 'DETAILS' ? 'summary' : 'h2') : null;
      if (heading && typeof heading.focus === 'function') heading.focus();
    }
    function jumpButton(text, sectionId) {
      const button = el('button', text, 'quiet link-button'); button.type = 'button';
      button.addEventListener('click', () => jump(sectionId)); return button;
    }
    const OWNERS = {reviewer:'Reviewer action', evidence:'Evidence needed', finance:'Finance check'};
    const SUGGESTED_QUESTIONS = ['What needs my attention?', 'How was the January credit calculated?',
      'Why is March undetermined?', 'Did the credit reach Ramp?'];
    const field = (label,value) => add(el('div',null,'northwind-field'),el('dt',label),el('dd',value));
    const fields = pairs => add(el('dl',null,'northwind-fields'),...pairs.map(([k,v])=>field(k,v)));
    function citations(items) {
      const refs = el('ul',null,'northwind-citations');
      list(items).forEach(c => {
        const row=add(el('li'),el('span',typeof c === 'string' ? c : c.label || c.title || c.ref),typeof c === 'object' && c.ref ? el('code',c.ref) : null);
        if(typeof c === 'object' && c.quote) row.append(add(el('details'),el('summary','Read clause'),el('blockquote',c.quote)));
        refs.append(row);
      });
      return refs.children.length ? refs : note('Source references not provided.');
    }
    // Long source lists and exact technical values stay one click away.
    function inspector(summary, ...children) { return add(el('details', null, 'workflow-evidence inspector'), el('summary', summary), ...children); }
    const clauseList = items => list(items).length ? inspector('Cited clauses (' + list(items).length + ')', citations(items)) : note('Source references not provided.');
    function monthEvidence(month) {
      const cell = el('td', null, 'basis'), lines = list(month.calculation);
      if (lines.length) cell.append(add(el('ol', null, 'trace'), ...lines.map(line => el('li', rates(line)))));
      else cell.append(note(rates(reason(month.reason))));
      const inputs = month.inputs || {};
      if (Object.keys(inputs).length) {
        const rows = [['Governing fee', inputs.governing_fee == null ? null : money(inputs.governing_fee, inputs.currency || month.currency || 'USD')],
          ['Fee reference', inputs.fee_version], ['Eligible downtime (minutes)', inputs.eligible_downtime_minutes],
          ['Completed increments', inputs.completed_steps], ['Credit rate', inputs.credit_percent == null ? null : inputs.credit_percent + '%'],
          ['Claim deadline', inputs.claim_cutoff == null ? null : when(inputs.claim_cutoff)], ['Usage record', inputs.monitor_ref]].filter(([, value]) => value != null);
        if (rows.length) cell.append(inspector('Calculation inputs', fields(rows)));
      }
      if (list(month.citations).length) cell.append(clauseList(month.citations));
      if (month.invoice || list(month.evidence).length || list(month.trace).length) {
        const detail=add(el('details',null,'workflow-evidence inspector'),el('summary','Inspect invoice & usage'));
        const invoice=month.invoice || {};
        if (month.invoice) detail.append(fields([['Invoice',invoice.id],['Issued',invoice.issued_at],['Service starts',invoice.service_start],['Service ends',invoice.service_end]]));
        list(month.evidence).forEach(item=>detail.append(add(el('article',null,'workflow-document'),el('h3',item.label),note(item.value == null ? 'Not provided' : item.value),item.ref ? el('code',item.ref) : null)));
        if(list(month.trace).length) detail.append(add(el('ol',null,'trace'),...month.trace.map(line=>el('li',rates(reason(line))))));
        cell.append(detail);
      }
      return cell;
    }
    const PRICE_STATUS = {PREPAYMENT_REVIEW:'Open · review before payment', RETROSPECTIVE_REVIEW:'Open · paid invoice, review for recovery',
      NEEDS_REVIEW:'Open · needs review', REVIEW_REQUIRED:'Open · review required'};
    function amountRow(label, value, cls) { return add(el('div', null, 'outcome-row' + (cls ? ' ' + cls : '')), el('dt', label), el('dd', value)); }
    // The headline: the bill outcome once a credit is applied, otherwise the credit's current stage, and the
    // separate price exception. Every amount and stage is the server's finance projection; nothing is computed here.
    function serverStages(data) { return list((data.finance || {}).stages).filter(row => row && typeof row === 'object'); }
    function outcome(data, months) {
      const ledger = data.ledger || {}, claim = data.claim || {}, price = data.price_finding || {};
      const fbill = (data.finance || {}).bill || {}, lbill = ledger.bill || {};
      const currency = ledger.currency || 'USD', destination = ledger.destination;
      const node = el('section', null, 'outcome'); node.id = 'finance-outcome'; node.setAttribute('aria-label', 'Outcome');
      const credit = el('article', null, 'outcome-card outcome-credit');
      if (fbill.id && fbill.application_ref) {
        const billMonth = monthOnly(lbill.month) || monthOnly(lbill.service_start);
        add(credit, el('h2', (billMonth ? billMonth + ' invoice ' : 'Invoice ') + fbill.id), add(el('dl', null, 'outcome-rows'),
          amountRow('Invoice', money(fbill.original, currency)), amountRow('Credit applied', money(fbill.applied, currency), 'outcome-applied'),
          amountRow('Remaining balance', money(fbill.outstanding, currency), 'outcome-total')),
          note('Credit recorded in ' + text(destination) + ' and applied to this invoice.'));
      } else {
        const rows = serverStages(data), estimate = rows.find(r => r.stage === 'estimated');
        const reached = rows.filter(r => r.stage !== 'estimated' && r.status === 'recorded').pop();
        const claimMonth = claim.month ? monthOnly(claim.month) : null;
        const shown = reached || estimate;
        add(credit, el('h2', (claimMonth ? claimMonth + ' service credit' : 'Service credit')),
          el('div', shown ? money(shown.amount, currency) : money(null), 'outcome-value'),
          note(reached ? 'Current stage: ' + reached.label + '. Not yet applied to an invoice.'
            : estimate && estimate.amount != null ? 'Estimated from the governing agreement. Not yet claimed.'
            : 'No amount is determined yet.'));
      }
      node.append(credit);
      if (price.invoice_id || price.amount != null || price.state) {
        const priceMonth = monthOnly(price.month) || monthFor(price.invoice_id, months);
        node.append(add(el('article', null, 'outcome-card outcome-exception'), el('h2', (priceMonth ? priceMonth + ' price exception' : 'Price exception')),
          el('div', money(price.amount, price.currency || currency), 'outcome-value'),
          add(el('p', null, 'help'), el('span', (PRICE_STATUS[price.state] || state(price.state)) + (price.invoice_id ? ' · invoice ' : '')),
            price.invoice_id ? el('span', price.invoice_id, 'nowrap') : null),
          note('Separate from the service credit and not included in it.')));
      }
      return node;
    }
    function monthFor(invoiceId, months) {
      const match = list(months).find(m => m && m.invoice && m.invoice.id === invoiceId);
      return match ? monthOnly(match.month) : null;
    }
    // One credit at each stage of its life, exactly as the server's finance projection lists it. The amounts are
    // the same credit, never added together.
    const STAGE_STATE = {recorded:'Recorded', 'not yet':'Not yet', 'not determined':'Not determined'};
    function lifecycle(data) {
      const currency = (data.ledger || {}).currency || 'USD', rows = serverStages(data);
      const node = el('section', null, 'lifecycle'); node.setAttribute('aria-label', 'Credit lifecycle');
      node.append(add(el('div', null, 'lifecycle-head'), el('h2', 'Credit lifecycle'), note('One credit, shown at each stage. The amounts are not added together.')));
      if (!rows.length) return add(node, note('The server reported no credit stages for this case.'));
      const items = el('ol', null, 'lifecycle-steps');
      let current = null;
      rows.forEach(row => {
        const done = row.status === 'recorded';
        const item = add(el('li', null, 'lifecycle-step ' + (done ? 'done' : 'pending')), el('span', text(row.label), 'step-label'),
          el('strong', row.amount == null ? 'Not determined' : money(row.amount, currency), 'step-amount'),
          el('span', STAGE_STATE[row.status] || state(row.status), 'step-state'));
        if (done) current = item;
        items.append(item);
      });
      if (current) current.setAttribute('aria-current', 'step');
      return add(node, items);
    }
    function guidePanel(token) {
      const node = panel('Ask about this case', 'guide');
      node.append(note('Answers come only from this case’s records and name the record behind each statement. The guide can’t take actions.'));
      const form = el('form', null, 'guide-form'), label = el('label', 'Question'), input = el('input');
      input.type = 'text'; input.maxLength = 1000; input.autocomplete = 'off'; input.placeholder = 'For example: why is March undetermined?';
      label.append(input);
      const submit = el('button', 'Ask'); submit.type = 'submit';
      const output = el('div', null, 'guide-answer'); output.setAttribute('role', 'status'); output.setAttribute('aria-live', 'polite');
      let asking = false;
      function show(result) {
        const parts = [];
        list(result.sentences).forEach(sentence => {
          const row = add(el(result.abstained ? 'p' : 'li'), el('span', fingerprints(instants(sentence.text))));
          list(sentence.citations).forEach(id => {
            const cite = list(result.citations).find(c => c.id === id);
            if (cite) row.append(add(el('span', null, 'guide-citation'), cite.section ? jumpButton('Source: ' + text(cite.label), cite.section) : el('span', 'Source: ' + text(cite.label)), cite.ref ? el('code', cite.ref) : null));
          });
          parts.push(row);
        });
        const answer = add(el(result.abstained ? 'div' : 'ol', null, result.abstained ? 'guide-abstain' : 'guide-sentences'), ...parts);
        const related = list(result.citations).filter(c => !list(result.sentences).some(s => list(s.citations).includes(c.id)));
        output.replaceChildren(answer, ...(related.length ? [add(el('div', null, 'guide-related'), note('Related records'),
          ...related.map(c => add(el('span', null, 'guide-citation'), jumpButton('Show ' + text(c.label), c.section))))] : []),
          ...(result.scope_note ? [note(result.scope_note)] : []), note('As of ' + when(result.as_of) + '. Read only; nothing was changed.'));
      }
      async function ask(question) {
        if (asking || token !== epoch) return;
        if (!question) { output.replaceChildren(note('Enter a question about this case.')); return; }
        asking = true; submit.disabled = true; suggestions.forEach(b => { b.disabled = true; }); output.replaceChildren(note('Reading this case’s records…'));
        try {
          const result = await api('/api/workspace/guide', {question});
          if (token !== epoch) return;
          show(result || {});
        } catch (error) {
          if (token !== epoch) return;
          if (error.status === 401 && typeof onUnauthorized === 'function') { epoch++; onUnauthorized(); return; }
          output.replaceChildren(note('The guide could not answer just now. Nothing was changed. Try again.'));
        } finally { asking = false; submit.disabled = false; suggestions.forEach(b => { b.disabled = false; }); }
      }
      form.addEventListener('submit', event => { event.preventDefault(); return ask(String(input.value || '').trim()); });
      // One-click questions for common reviews; each is asked through the same read-only route as a typed question.
      const suggestions = SUGGESTED_QUESTIONS.map(question => {
        const b = el('button', question, 'quiet suggestion'); b.type = 'button';
        b.addEventListener('click', () => { if (asking || token !== epoch) return; input.value = question; return ask(question); });
        return b;
      });
      const tries = add(el('div', null, 'guide-suggestions'), el('span', 'Try:', 'help'), ...suggestions);
      tries.setAttribute('role', 'group'); tries.setAttribute('aria-label', 'Suggested questions');
      add(form, label, submit);
      // Suggestions sit above the question so Tab from the question still reaches Ask, then the answer's sources.
      return add(node, tries, form, output);
    }
    const OUTCOME_TONE = {ELIGIBLE:'ok', INSUFFICIENT_EVIDENCE:'warn', UNKNOWN:'warn'};
    // A table that reads as stacked rows on a narrow screen. Each cell carries its column name for that layout, and
    // explicit roles keep the table's meaning for assistive technology when the layout changes.
    function sheet(titles, numeric = []) {
      const table = el('table', null, 'stack'), head = el('thead'), headRow = el('tr'), body = el('tbody');
      table.setAttribute('role', 'table'); head.setAttribute('role', 'rowgroup'); headRow.setAttribute('role', 'row'); body.setAttribute('role', 'rowgroup');
      titles.forEach((title, index) => { const th = el('th', title, numeric.includes(index) ? 'num' : null); th.scope = 'col'; th.setAttribute('role', 'columnheader'); headRow.append(th); });
      add(table, add(head, headRow), body);
      const row = (...cells) => {
        const tr = el('tr'); tr.setAttribute('role', 'row');
        cells.forEach((cell, index) => { cell.setAttribute('role', 'cell'); if (index) cell.setAttribute('data-label', titles[index]); tr.append(cell); });
        body.append(tr);
      };
      return {table, row};
    }
    function renderData(root,data,token) {
      // A decision pressed on this page leaves the projection it was pressed on; its new steps are shown one at a time.
      const replay = pendingReplay; pendingReplay = null; lastData = data;
      const plan = replay && replayOn() && data.automation && data.automation.enabled !== false
        && newSteps(replay.prior, data).some(step => !(step.authority && step.authority.kind === 'PERSON')) ? newSteps(replay.prior, data) : null;
      const vendor = typeof data.vendor === 'object' ? data.vendor.name : data.vendor;
      const months = list(data.months);
      // The vendor's initials beside its name: decoration, hidden from assistive technology.
      const tile=el('span',String(vendor || '').split(/\s+/).filter(Boolean).slice(0,2).map(part=>part[0].toUpperCase()).join(''),'page-tile brand-'+String(vendor || '').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,''));tile.setAttribute('aria-hidden','true');
      const header=add(el('div',null,'page-head'),tile,add(el('div'),el('p','Contract review & recovery','eyebrow'),el('h1',vendor || 'Contract review')),
        data.as_of ? el('p','As of '+when(data.as_of),'as-of') : null);
      const ledger=data.ledger || {}, currency=ledger.currency || 'USD';
      const finance = data.finance && typeof data.finance === 'object' ? data.finance : null;
      const claim=data.claim || {}, connection=data.connection || {};
      const claimMonth = claim.month ? monthOnly(claim.month) : null;
      const recovery=panel(claimMonth ? claimMonth + ' recovery' : 'Claim recovery','recovery');
      const agreement=data.contract || {}, reviewer=data.reviewer || {};
      const contract=fold('Governing agreement','agreement');
      add(contract,fields([['Agreement',agreement.title],['Document reference',agreement.ref],['Version',shortRef(agreement.version)]]));
      list(agreement.documents).forEach(document=>contract.append(add(el('article',null,'workflow-document'),el('h3',document.title),
        note(document.effective_at ? 'Effective ' + day(document.effective_at) : 'Effective date not provided'),
        inspector('Document details', fields([['Reference',document.ref],['Version',document.version],['Effective date',document.effective_at]]), note(document.description)))));
      if (agreement.summary) contract.append(inspector('Agreement text', el('p', agreement.summary, 'help prose')));
      let attention = null, ramp = null, drawAttention = () => {};
      if (finance) {
        // While a decision's steps are being shown, the list is the one the page held before it; it updates when they have all appeared.
        const attentionFor = source => { const items = el('ol', null, 'attention-list');
        list(source && source.attention).forEach(item => {
          const row = add(el('li', null, 'attention-item'), el('span', OWNERS[item.owner] || 'Next step', 'attention-owner' + (OWNERS[item.owner] ? ' owner-' + item.owner : '')),
            el('h3', item.title), note(instants(item.detail)));
          if (item.section) row.append(jumpButton('Show details', item.section));
          items.append(row);
        });
        return items; };
        const items = attentionFor(plan && replay.prior && replay.prior.finance ? replay.prior.finance : finance);
        // The heading keeps its exact name; the number of items sits beside it.
        const attentionHeading = el('h2', 'Needs attention'); attentionHeading.tabIndex = -1;
        const tally = items.children.length ? el('span', String(items.children.length), 'count') : null;
        if (tally) tally.setAttribute('aria-label', items.children.length + (items.children.length === 1 ? ' item' : ' items'));
        attention = add(el('section', null, 'panel'), add(el('div', null, 'panel-head'), attentionHeading, tally));
        attention.id = SECTION_IDS.attention;
        const attentionBody = el('div', null, 'attention-body');
        attention.append(attentionBody);
        drawAttention = () => { const now = attentionFor(finance); attentionBody.replaceChildren(now.children.length ? now : note('Nothing in this case needs action now.'));
          if (tally) { tally.textContent = String(now.children.length); tally.setAttribute('aria-label', now.children.length + (now.children.length === 1 ? ' item' : ' items')); } };
        attentionBody.append(items.children.length ? items : note('Nothing in this case needs action now.'));
        const rampInfo = finance.ramp || {};
        ramp = panel('Ramp record', 'ramp');
        const linked = rampInfo.linked_record && typeof rampInfo.linked_record === 'object' ? rampInfo.linked_record : null;
        add(ramp, fields([['Connection destination', rampInfo.destination], ['Ramp bill', linked ? linked.id : 'Not linked']]),
          note(linked ? 'Open the linked bill in Ramp to continue its native workflow.' : rampInfo.note));
        const records = el('a', 'Open Ramp records', 'case-link ramp-glyph'); records.href = '#records'; ramp.append(records);
      }
      // The claim's own stage is shown as the server reports it, beside the credit's latest recorded lifecycle stage.
      const recoveryFacts = view => {
        const reachedStage = serverStages(view).filter(row => row.status === 'recorded').pop(), shownClaim = view.claim || {};
        return fields([['Claim stage',state(shownClaim.state)],['Credit stage',reachedStage ? reachedStage.label : null],['Destination',ledger.destination],['Claim reference',claim.id]].filter(([, value]) => value != null));
      };
      const factsBox = el('div', null, 'recovery-facts');
      // Who the reviewer is and of what kind, in view on this card: the name as the server sends it and its authority
      // kind in the same words the records below use. A plain field; left out when the server names no reviewer.
      if (reviewer.name != null && reviewer.name !== '') {
        const who = fields([['Reviewer', reviewer.name + (reviewer.authority_kind ? ' · ' + state(reviewer.authority_kind) : '')]]);
        who.className += ' recovery-reviewer'; recovery.append(who);
      }
      factsBox.append(recoveryFacts(plan ? stagedView(replay.prior, data, plan) : data));
      add(recovery,factsBox,
        claim.summary == null || claim.summary === '' ? null : note(claim.summary));
      const status=el('p',null,'help');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
      const controls=el('div',null,'actions');
      // After a reload the read session remains but the signing key does not; actions are shown disabled with one way back.
      const signedIn = canAct() !== false;
      list(data.next_actions).forEach(action=>{
        if (!action.id) return;
        const button=el('button',action.label || state(action.id));button.type='button';button.disabled=busy || uncertain || action.enabled === false || !signedIn;
        // A repeated key event (a held Enter or Space) never activates a decision; only a fresh key press or click does.
        button.addEventListener('keydown', event => { if (event && event.repeat && (event.key === 'Enter' || event.key === ' ')) event.preventDefault(); });
        button.addEventListener('click', async()=>{
          if (busy || uncertain || token !== epoch || action.enabled === false || canAct() === false) return;
          const prior=lastData;busy=true;Array.from(controls.children).forEach(c=>{c.disabled=true;});status.textContent='Recording action…';
          try {
            await api('/api/workspace/workflow/actions/'+encodeURIComponent(action.id),{});
            if (token !== epoch) return;
            focusNextStep=true;recordedLabel=action.label || state(action.id);pendingReplay={prior};try{await render(root);}finally{focusNextStep=false;recordedLabel=null;}await onRefresh();
          } catch(error) {
            if(token !== epoch) return;
            if(error.status === 401 && typeof onUnauthorized === 'function') {
              epoch++;onUnauthorized();return;
            }
            uncertain=true;status.textContent='Refresh to check the recorded outcome before continuing.';
          } finally {busy=false;}
        });controls.append(button);
      });
      const offered = controls.children.length > 0;
      if(!offered) controls.append(note('No actions available in the current state.'));
      else if (!signedIn) {
        const again = el('button', 'Sign in again to take actions', 'quiet'); again.type = 'button';
        again.addEventListener('click', () => { if (typeof onUnauthorized === 'function') { epoch++; onUnauthorized(); } });
        controls.append(again);
        status.textContent = 'Reading only: reloading the page cleared the signing key. Sign in again to take actions.';
      }
      // The next decision follows the heading directly: no link sits between them, so one Tab from the heading reaches it.
      const routine = data.automation && data.automation.enabled !== false ? automationSummary(data.automation) : null;
      // Paused with nothing offered here means a reviewer is needed elsewhere (for example on the case); that state is marked.
      const stopped = !offered && data.automation && data.automation.enabled !== false && data.automation.state === 'PAUSED';
      const routineLine = routine ? el('span', routine) : null;
      const decision = add(el('div', null, 'decision' + (offered ? '' : stopped ? ' idle stopped' : ' idle')), routineLine ? add(el('p', null, 'help automation-line'), routineLine) : null, controls);
      // The steps a decision added, shown one at a time under the decision bar, and the switch that turns this off.
      const feed = el('div', null, 'overview-steps');
      const showSteps = data.automation && data.automation.enabled !== false ? (() => {
        const box = el('input'); box.type = 'checkbox'; box.checked = replayOn();
        box.addEventListener('change', () => { writeSetting(REPLAY_KEY, box.checked ? 'on' : 'off'); if (!box.checked && stopReplay) stopReplay(); });
        return add(el('label', null, 'replay-toggle overview-replay-toggle'), box, el('span', 'Show the steps one at a time after each decision'));
      })() : null;
      const caseLink = typeof claim.id === 'string' && claim.id ? el('a', 'Open this claim’s case and correspondence', 'case-link') : null;
      if (caseLink) caseLink.href = '#cases/' + encodeURIComponent(claim.id);
      const stepsLink = routine ? el('a', 'See every step in Activity', 'case-link') : null;
      if (stepsLink) stepsLink.href = '#activity';
      add(recovery,decision,status,feed,showSteps,caseLink || stepsLink ? add(el('p', null, 'help recovery-links'), caseLink, stepsLink) : null,
        inspector('Connection details', fields([['Connection destination',connection.destination],['Connection status',state(connection.status)],['Receipt status',state(connection.receipt_status)]])));
      const monthly=panel('Service credit evaluations','months'), evaluations=sheet(['Service month','Decision','Service credit','Basis'],[2]);
      months.forEach(month=>{
        // An ineligible month owes no credit. That is a determined outcome, so it is not shown as an unknown amount,
        // and no zero is printed that the server did not send.
        const credit = month.amount == null && month.outcome === 'INELIGIBLE' ? 'No credit' : money(month.amount,month.currency || currency);
        evaluations.row(el('td',monthLabel(month.month)),
          add(el('td',null,'tag'),el('span',state(month.outcome),'pill'+(OUTCOME_TONE[month.outcome] ? ' '+OUTCOME_TONE[month.outcome] : ''))),
          el('td',credit,'num'),monthEvidence(month));
      });
      add(monthly,add(el('div',null,'table-scroll'),evaluations.table));
      const price=data.price_finding || {}, priceMonth = monthFor(price.invoice_id, months);
      const pricing=panel(priceMonth ? priceMonth + ' price review' : 'Price review','price');
      add(pricing,fields([['Finding','Price cap review'],['Status',PRICE_STATUS[price.state] || state(price.state)],['Invoice',price.invoice_id]].filter(([,value]) => value != null)));
      if (list(price.lines).length) {
        const lines = sheet(['Invoice line','Governing version','Billed','Contract amount','Difference'],[2,3,4]);
        list(price.lines).forEach(line => lines.row(el('td', line.line_id), el('td', line.version),
          el('td', money(line.billed, price.currency || currency), 'num'), el('td', money(line.expected, price.currency || currency), 'num'),
          add(el('td', null, 'num'), el('span', money(line.delta, price.currency || currency)), line.direction ? el('span', state(line.direction), 'pill' + (line.direction === 'OVERCHARGE' ? ' warn' : '')) : null)));
        pricing.append(add(el('div', null, 'table-scroll'), lines.table));
        if (finance) pricing.append(note('An open price finding. It is not a credit and is not included in the credit stages.'));
      }
      add(pricing,inspector('Evaluator trace', note(reason(price.reason))),clauseList(price.citations));
      const bill=ledger.bill || {}, billing=panel('Bill reconciliation','bill');
      add(billing,fields([['Destination',ledger.destination],['Bill reference',bill.id],
        ['Service period',bill.service_start ? period(bill.service_start, bill.service_end) : null],
        ['Original bill',money(bill.original_amount,currency)],['Applied credit',ledger.record_ids?.application ? money(ledger.applied,currency) : 'None applied'],
        ['Outstanding balance',money(bill.outstanding_amount,currency)]].filter(([,value]) => value != null)));
      // References the server has recorded so far; absent ones are omitted rather than shown empty.
      const references = [['Invoice issued',bill.issued_at],['Service starts',bill.service_start],['Service ends',bill.service_end],
        ['Receipt reference',claim.receipt_id],['Award reference',ledger.record_ids?.award],['Credit reference',ledger.record_ids?.credit],['Application reference',ledger.record_ids?.application]].filter(([,value]) => value != null && value !== '');
      if (references.length) billing.append(inspector('References', fields(references)));
      const detail=fold('Agreement & review record');
      add(detail,fields([['Agreement',agreement.title],['Version',agreement.version],['Document reference',agreement.ref],['Reviewer',reviewer.name],['Principal',reviewer.principal],['Role',reviewer.role],['Authority kind',state(reviewer.authority_kind)]]),citations(agreement.citations));
      const onboarding=data.onboarding || {}, expansion=fold(onboarding.vendor ? onboarding.vendor+' coverage in this workspace' : 'Vendor coverage','coverage');
      const coverageReviewer=onboarding.reviewer || {};
      add(expansion,fields([['State in this workspace',state(onboarding.state)],['Adapter version',shortRef(onboarding.version)],
        ['Reviewer',coverageReviewer.name ? coverageReviewer.name + (coverageReviewer.authority_kind ? ' · ' + state(coverageReviewer.authority_kind) : '') : null]].filter(([,value]) => value != null)));
      const coverage=coverageHistory(onboarding), actors=[...new Set(list(onboarding.history).map(event=>event.actor).filter(Boolean))];
      if (!coverage.children.length) expansion.append(note('Coverage history not provided.'));
      else if (finance) expansion.append(add(el('details',null,'workflow-evidence inspector'),el('summary','History in this workspace ('+coverage.children.length+' entries)'),actors.length===1 ? note('Every entry is recorded by '+actors[0]+'.') : null,coverage));
      else expansion.append(coverage);
      const vendorLink=el('a','Inspect vendor contracts','case-link');vendorLink.href='#vendors';expansion.append(add(el('p', null, 'help'), vendorLink));
      const guide=finance ? guidePanel(token) : null;
      // One reading order at every width: the recovery card, what needs attention beside it, then the Ramp record and the guide.
      const columns = add(el('div', null, 'overview-columns' + (attention ? '' : ' single')), recovery, attention, ramp, guide);
      const evidence = add(el('div', null, 'section-head'), el('h2', 'Evidence'));
      const records = add(el('div', null, 'fold-group'), contract, data.onboarding ? expansion : null, detail);
      const activityLink = add(el('p', null, 'help foot-link'), (() => { const a = el('a', 'See the full activity history', 'case-link'); a.href = '#activity'; return a; })());
      // The outcome and the credit lifecycle: while a decision's steps are being shown they hold each stage until its step appears.
      const figures = el('div', null, 'overview-figures');
      const drawFigures = view => { figures.replaceChildren(outcome(view, months), lifecycle(view)); factsBox.replaceChildren(recoveryFacts(view)); if (view === data) drawAttention(); };
      figures.replaceChildren(...(plan ? [outcome(stagedView(replay.prior, data, plan), months), lifecycle(stagedView(replay.prior, data, plan))] : [outcome(data, months), lifecycle(data)]));
      let afterReplay = null;
      root.replaceChildren(header,figures,columns,evidence,monthly,add(el('div',null,'section-grid'),pricing,billing),records,activityLink);
      if (focusNextStep) {
        focusNextStep=false;
        const next=Array.from(controls.children).find(c=>c.tagName==='BUTTON' && !c.disabled);
        // While the steps are shown the next decision waits out of view; it is named once they have all appeared.
        if (recordedLabel) status.textContent='Recorded: '+recordedLabel+'.'+(next && !plan ? ' Next: '+next.textContent+'.' : '');
        if (plan && recordedLabel) { const said = status.textContent; afterReplay = () => { status.textContent = said + (next ? ' Next: '+next.textContent+'.' : ''); }; }
        recordedLabel=null;
        const target=recovery.children[0];
        if (target && typeof target.focus==='function') target.focus();
      }
      if (plan) playOverview({plan, prior: replay.prior, data, token, feed, controls, routineLine, routine, drawFigures, done: () => afterReplay && afterReplay()});
    }
    // The Overview's replay: display only. The decision has returned and every step below is already recorded; each is
    // shown after a short line naming it, and the figures above move to the value that step recorded. No request is made.
    const LEAD_MS = 500, STEP_MS = 900;
    function stepRow(step) {
      const tag = actorTag(step);
      return add(el('li', null, 'overview-step' + (step.authority && step.authority.kind === 'PERSON' ? ' by-reviewer' : '') + (still() ? '' : ' replay-reveal')),
        add(el('div', null, 'step-head'), el('strong', text(step.label || state(step.operation))), tag ? el('span', tag.label, 'pill ' + tag.cls) : null),
        note(authorityText(step.authority)));
    }
    function playOverview({plan, prior, data, token, feed, controls, routineLine, routine, drawFigures, done}) {
      const decision = plan[0] && plan[0].authority && plan[0].authority.kind === 'PERSON' ? plan[0] : null;
      const key = decision ? String(decision.intent_id || decision.seq || '') : '';
      if (key) writeSetting(REPLAY_SEEN_KEY, key);
      const list_ = el('ol', null, 'overview-step-list');
      const show = row => { list_.append(row); if (typeof row.scrollIntoView === 'function') row.scrollIntoView({block:'nearest', behavior: still() ? 'auto' : 'smooth'}); };
      feed.replaceChildren(el('p', 'Steps recorded after ' + (decision ? '“' + text(decision.label || state(decision.operation)) + '”' : 'this decision') + ', shown in order', 'overview-steps-head'), list_);
      controls.hidden = true;
      if (routineLine) routineLine.textContent = 'Showing the steps this decision recorded, one at a time.';
      let index = 0, stopped = false;
      const alive = () => !stopped && token === epoch;
      const finish = () => {
        stopped = true; if (stopReplay === stop) stopReplay = null;
        while (index < plan.length) list_.append(stepRow(plan[index++]));
        Array.from(list_.children).filter(row => String(row.className).includes('overview-lead')).forEach(row => { row.hidden = true; });
        drawFigures(data); controls.hidden = false; if (routineLine) routineLine.textContent = routine; done();
      };
      const stop = () => { if (!stopped && token === epoch) finish(); };
      stopReplay = stop;
      const next = () => {
        if (!alive()) return;
        if (index >= plan.length) { finish(); return; }
        const step = plan[index];
        if (step.authority && step.authority.kind === 'PERSON') { index++; show(stepRow(step)); drawFigures(stagedView(prior, data, plan.slice(index))); schedule(next, STEP_MS); return; }
        const lead = el('li', leadIn(step), 'overview-lead'); show(lead);
        schedule(() => {
          if (!alive()) return;
          lead.hidden = true; index++; show(stepRow(step));
          drawFigures(stagedView(prior, data, plan.slice(index)));
          schedule(next, STEP_MS);
        }, LEAD_MS);
      };
      next();
    }
    function coverageHistory(onboarding) {
      const coverage=el('ol',null,'activity'), actors=[...new Set(list(onboarding.history).map(event=>event.actor).filter(Boolean))];
      list(onboarding.history).forEach(event=>coverage.append(add(el('li'),el('time',when(event.at)),el('span',event.event),actors.length>1 && event.actor ? note('Recorded by '+event.actor) : null,event.ref ? el('code',event.ref) : null)));
      return coverage;
    }
    // Activity: what happened, in order, from the same projection. Absent data renders as absent.
    // Automation state is the server's persisted record. Step times are on the case's own timeline (the clock that
    // "As of" shows); the server's recording time stays in each step's details. No durations are derived from either.
    const AUTOMATION_STATE = {RUNNING:'Running', PAUSED:'Paused', COMPLETE:'Complete'};
    const PAUSE_REASON = {APPROVAL_REQUIRED:'Waiting for a reviewer to approve', FINANCIAL_APPROVAL_REQUIRED:'Waiting for a reviewer to approve a ledger change',
      JUDGMENT_REQUIRED:'Waiting for a reviewer’s judgment', UNEXPECTED_GROUND:'Stopped for a reviewer: the vendor gave a ground the system does not recognize',
      CONTRADICTORY_EVIDENCE:'Stopped for a reviewer: the evidence conflicts', MISSING_AUTHORITY:'Stopped: no current approval covers the next step',
      UNCERTAIN_DELIVERY:'Stopped: an interrupted action must be resumed by a reviewer', WAITING:'Waiting for the next event',
      ROUTINE_READY:'Routine steps are ready to continue'};
    const STEP_CLASS = {INTAKE:'Intake', COMPUTATION:'Computation', DELIVERY:'Delivery', JUDGMENT:'Judgment', APPROVAL:'Approval', FINANCIAL_MUTATION:'Ledger change'};
    const STEP_STATE = {COMPLETED:'Completed', PAUSED:'Paused', UNCERTAIN:'Outcome uncertain', FAILED:'Failed'};
    function pauseText(automation) {
      const pause = automation && automation.pause;
      if (!pause || typeof pause !== 'object') return null;
      return PAUSE_REASON[pause.reason] || state(pause.reason);
    }
    function authorityText(authority) {
      const a = authority && typeof authority === 'object' ? authority : {};
      if (a.kind === 'PERSON') return 'Decided by ' + text(a.actor || 'a signed-in reviewer');
      if (a.kind === 'APPROVED_OPERATION') return 'Run automatically under the approval recorded by ' + text(a.actor || 'a reviewer') + (a.approved_at ? ', ' + when(a.approved_at) : '');
      if (a.kind === 'EVENT_INTAKE') return 'Received automatically: event ' + text(a.event_id) + (a.source_subject ? ' from ' + a.source_subject : '');
      return a.kind ? state(a.kind) : 'Authority not reported';
    }
    function automationSummary(automation) {
      if (!automation || typeof automation !== 'object') return null;
      if (automation.enabled === false) return 'Each step runs when a reviewer presses it in this workspace.';
      const counts = automation.counts || {}, pause = pauseText(automation);
      const head = (AUTOMATION_STATE[automation.state] || state(automation.state)) + (pause && automation.state !== 'COMPLETE' ? ' · ' + pause : '');
      const reason = (automation.pause || {}).reason, detail = (automation.pause || {}).detail;
      const explained = typeof detail === 'string' && detail && !['APPROVAL_REQUIRED', 'FINANCIAL_APPROVAL_REQUIRED', 'ROUTINE_READY', 'WAITING'].includes(reason) && automation.state !== 'COMPLETE';
      const plural = (n, word) => n + ' ' + word + (n === 1 ? '' : 's');
      // The server counts decisions made by a signed-in reviewer account; the account itself is named on each step.
      const tally = [counts.person_decisions ? plural(counts.person_decisions, 'reviewer decision') : null,
        counts.automatic_steps ? plural(counts.automatic_steps, 'automatic step') : null].filter(Boolean);
      return 'Routine steps: ' + head + '.' + (explained ? ' ' + detail.trim().replace(/([^.])$/, '$1.') : '') + (tally.length ? ' ' + tally.join(' and ') + ' recorded.' : '');
    }
    // What authorised a step, as one short tag beside the server's own sentence. A decision is attributed to the
    // reviewer account the server names, never to "a person": the account may be a scripted one.
    const AUTOMATION_TONE = {COMPLETE:'ok', PAUSED:'warn', RUNNING:'accent'};
    function automationPanel(automation, nextActions) {
      const heading = el('h2', 'Steps in order'), head = add(el('div', null, 'panel-head'), heading), node = add(el('section', null, 'panel'), head);
      if (!automation || typeof automation !== 'object') return add(node, note('This workspace does not report automation runs.'));
      if (automation.enabled !== false && automation.state) head.append(el('span', AUTOMATION_STATE[automation.state] || state(automation.state), 'pill' + (AUTOMATION_TONE[automation.state] ? ' ' + AUTOMATION_TONE[automation.state] : '')));
      const counts = automation.counts && typeof automation.counts === 'object' ? automation.counts : {};
      const steps = recordedOrder(automation.steps);
      // Who did what, at a glance: a legend counted from the recorded steps, in the same tags the steps carry.
      if (steps.length) {
        const legend = stepLegend(steps, counts);
        const figure = (cls, label, value) => add(el('div'), add(el('dt'), el('span', label, 'pill ' + cls)), el('dd', String(value)));
        node.append(add(el('dl', null, 'tally step-legend'), figure('accent tag-reviewer', 'Reviewer decisions', legend.reviewer),
          figure('tag-agent', 'Uptime agent', legend.approved), figure('tag-received', 'Received from the vendor and other sources', legend.received),
          legend.other ? add(el('div'), el('dt', 'Other steps, or not completed'), el('dd', String(legend.other))) : null));
        node.append(note('The Uptime agent runs a step only under an approval a reviewer already recorded. Its steps and the received events are the automatic steps the server counts.'));
        const counted = (n, word) => n == null ? null : n + ' ' + word + (n === 1 ? '' : 's');
        if (!legend.agrees) node.append(note('The server’s own counts differ from the steps listed: ' + [counted(legend.server.person_decisions, 'reviewer decision'),
          counted(legend.server.automatic_steps, 'automatic step')].filter(Boolean).join(' and ') + '.'));
      }
      node.append(note(automationSummary(automation)));
      const offered = list(nextActions).filter(action => action && action.label).map(action => action.label);
      if (automation.enabled !== false && offered.length && automation.state !== 'COMPLETE') node.append(note('Next: ' + offered.join(', ') + '.'));
      if (!steps.length) return add(node, note('No step has been recorded yet.'));
      node.append(note('Times are on this case’s timeline, the same clock as “As of”. Each step’s details hold the time the server recorded it.'));
      const items = el('ol', null, 'automation-steps'), rows = [];
      steps.forEach(step => {
        const timing = step.timing && typeof step.timing === 'object' ? step.timing : {};
        const authority = step.authority && typeof step.authority === 'object' ? step.authority : {};
        const actor = actorTag(step), tag = actor ? [actor.label, actor.cls] : null;
        const lines = [];
        if (timing.filing_cutoff) lines.push('Filing cutoff ' + when(timing.filing_cutoff));
        if (timing.not_before) lines.push('Not sent before ' + when(timing.not_before) + ', the end of the response cooldown');
        const item = add(el('li', null, 'automation-step' + (authority.kind === 'PERSON' ? ' by-reviewer' : '') + (step.state && step.state !== 'COMPLETED' ? ' attention' : '')),
          el('time', when(step.at)),
          add(el('div', null, 'step-head'), el('strong', text(step.label || state(step.operation))), tag ? el('span', tag[0], 'pill' + (tag[1] ? ' ' + tag[1] : '')) : null),
          el('span', [STEP_CLASS[step['class']] || state(step['class']), STEP_STATE[step.state] || state(step.state)].join(' · '), 'step-state'),
          note(authorityText(step.authority)), ...lines.map(line => el('p', line, 'help step-note')), step.detail ? el('p', text(step.detail), 'help step-note') : null,
          inspector('Step details', fields([['Recorded by the server', step.recorded_at ? when(step.recorded_at) : null], ['Intent', step.intent_id],
            ['Approval digest', step.authority && step.authority.approval_digest], ['Event', step.authority && step.authority.event_id]].filter(([, value]) => value != null))));
        items.append(item); rows.push(item);
      });
      return add(node, replayControls(steps, rows, automation.enabled !== false), items);
    }
    // Replay: display only. The steps have already run and been recorded when this page shows them; the replay reveals
    // them one at a time, in recorded order, so each can be read. It sends no request, changes no record and waits on
    // nothing but its own display timer. Off unless turned on with the visible control below.
    function replayControls(steps, rows, automatic) {
      const token = epoch, group = replayGroup(steps);
      const latest = group ? String(group.decision.intent_id || group.decision.seq || '') : '';
      const toggle = el('input'); toggle.type = 'checkbox'; toggle.checked = replayOn();
      const again = el('button', 'Replay', 'quiet'); again.type = 'button';
      const skip = el('button', 'Show every step now', 'quiet link-button'); skip.type = 'button'; skip.hidden = true;
      const line = el('p', null, 'help replay-line'); line.setAttribute('role', 'status'); line.setAttribute('aria-live', 'polite'); line.hidden = true;
      let running = false, run = 0;
      const say = message => { line.textContent = message || ''; line.hidden = !message; };
      function finish(message) { running = false; run++; rows.forEach(row => { row.hidden = false; }); skip.hidden = true; say(message); }
      function play(from, message) {
        if (token !== epoch) return;
        const mine = ++run; running = true; skip.hidden = false; say(message);
        rows.forEach((row, index) => { row.hidden = index >= from; });
        let next = from;
        const tick = () => {
          if (!running || mine !== run || token !== epoch) return;
          const row = rows[next++];
          if (row) { row.hidden = false; if (!still()) row.className += ' replay-reveal'; }
          if (next >= rows.length) { finish('Replay finished. These steps were recorded before the replay began; nothing ran during it.'); return; }
          schedule(tick, REPLAY_PACE_MS);
        };
        tick();
      }
      toggle.addEventListener('change', () => {
        if (token !== epoch) return;
        writeSetting(REPLAY_KEY, toggle.checked ? 'on' : 'off');
        // Turning it on marks the decision already shown; the steps of the next decision are the ones replayed.
        if (toggle.checked) { if (latest) writeSetting(REPLAY_SEEN_KEY, latest); say('On. After the next reviewer decision, its steps are shown here one at a time.'); }
        else finish('');
      });
      again.addEventListener('click', () => play(0, 'Replay: every step below has already run and been recorded. Shown one at a time so each can be read.'));
      skip.addEventListener('click', () => { if (token === epoch) finish(''); });
      const control = add(el('label', null, 'replay-toggle'), toggle, el('span', 'Show new steps one at a time'));
      const box = add(el('div', null, 'replay-controls'), control, again, skip, line);
      // A decision this page has not yet replayed is shown one step at a time, starting with the decision itself.
      if (automatic && toggle.checked && group && latest && readSetting(REPLAY_SEEN_KEY) !== latest) {
        writeSetting(REPLAY_SEEN_KEY, latest);
        play(group.before.length, 'Replay: these steps ran when the reviewer decision “' + text(group.decision.label || state(group.decision.operation)) + '” was recorded. Shown one at a time so each can be read.');
      }
      return box;
    }
    function renderActivity(root, data) {
      const vendor = typeof data.vendor === 'object' ? data.vendor.name : data.vendor;
      const tile = el('span', null, 'page-tile tile-activity'); tile.setAttribute('aria-hidden', 'true');
      const header = add(el('div', null, 'page-head'), tile, add(el('div'), el('p', vendor ? vendor + ' · contract review & recovery' : 'Contract review & recovery', 'eyebrow'), el('h1', 'Activity')),
        data.as_of ? el('p', 'As of ' + when(data.as_of), 'as-of') : null);
      const history = panel('Workflow history'), timeline = el('ol', null, 'activity');
      list(data.audit).forEach(event => timeline.append(add(el('li'), el('time', when(event.at)), el('span', event.event), event.ref ? el('code', shortRef(event.ref)) : null)));
      history.append(timeline.children.length ? timeline : note('No workflow actions recorded.'));
      const onboarding = data.onboarding || {};
      const entries = coverageHistory(onboarding);
      const coverage = fold((onboarding.vendor ? onboarding.vendor + ' coverage history in this workspace' : 'Vendor coverage history') + (entries.children.length ? ' (' + entries.children.length + ' entries)' : ''));
      coverage.append(entries.children.length ? entries : note('Coverage history not provided.'));
      const jobs = panel('Model jobs');
      const casesLink = el('a', 'Cases', 'case-link'); casesLink.href = '#cases';
      const agreementsLink = el('a', 'Agreements', 'case-link'); agreementsLink.href = '#agreements';
      add(jobs, note('Each model job is shown with what it read: a vendor reply on its case, a contract on its agreement. A model proposes; a reviewer decides.'),
        add(el('p', null, 'help recovery-links'), casesLink, agreementsLink));
      root.replaceChildren(header, automationPanel(data.automation, data.next_actions), history, jobs, coverage);
    }
    async function render(root, supplied) {
      const token=++epoch;
      try {
        const data=supplied || (await api('/api/workspace/workflow')).workflow;
        if(token !== epoch) return;
        uncertain=false;busy=false;renderData(root,data,token);
      } catch(error) { if(token !== epoch) return;throw error; }
    }
    async function activity(root, supplied) {
      const token=++epoch;
      const data=supplied || (await api('/api/workspace/workflow')).workflow;
      if (token !== epoch) return;
      renderActivity(root, data);
    }
    return {render,activity,unmount:()=>{epoch++;}};
  }
  const exports={create,money,when,day,rates,monthLabel,recordedOrder,replayGroup,stepLegend,actorTag,leadIn,newSteps,stagedView};
  if(typeof module !== 'undefined' && module.exports) module.exports=exports;
  global.UptimeWorkspace=exports;
})(typeof window === 'undefined' ? globalThis : window);
