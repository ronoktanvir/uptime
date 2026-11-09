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
  const shortRef = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value) ? value.slice(0, 10) + '…' : text(value);
  const isZero = value => /^-?0*(\.0*)?$/.test(String(value));
  function create({api, document:doc = global.document, onRefresh = () => {}, onUnauthorized, canAct = () => true}) {
    // After a recorded action the page re-renders and focus moves to the recovery heading, never to the next
    // decision: a held or repeated Enter must not approve the next step. The status names what was recorded and what
    // comes next, one Tab away.
    let epoch = 0, busy = false, uncertain = false, focusNextStep = false, recordedLabel = null;
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
    // Move to a section without changing the route hash, which the shell uses for navigation.
    function jump(sectionId) {
      const target = typeof doc.getElementById === 'function' ? doc.getElementById(sectionId) : null;
      if (!target) return;
      if (typeof target.scrollIntoView === 'function') target.scrollIntoView({block:'start'});
      const heading = target.querySelector ? target.querySelector('h2') : null;
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
      const cell = el('td'), lines = list(month.calculation);
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
        if(list(month.trace).length) detail.append(add(el('ol',null,'trace'),...month.trace.map(line=>el('li',reason(line)))));
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
          amountRow('Invoice', money(fbill.original, currency)), amountRow('Credit applied', money(fbill.applied, currency)),
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
          note((PRICE_STATUS[price.state] || state(price.state)) + (price.invoice_id ? ' · invoice ' + price.invoice_id : '')),
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
      node.append(el('h2', 'Credit lifecycle'), note('One credit, shown at each stage. The amounts are not added together.'));
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
          const row = add(el(result.abstained ? 'p' : 'li'), el('span', sentence.text));
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
    function renderData(root,data,token) {
      const vendor = typeof data.vendor === 'object' ? data.vendor.name : data.vendor;
      const months = list(data.months);
      const header=add(el('div',null,'page-head'),add(el('div'),el('h1',vendor || 'Contract review'),note('Contract review & recovery')),note(data.as_of ? 'As of '+when(data.as_of) : ''));
      const ledger=data.ledger || {}, currency=ledger.currency || 'USD';
      const finance = data.finance && typeof data.finance === 'object' ? data.finance : null;
      const claim=data.claim || {}, connection=data.connection || {};
      const claimMonth = claim.month ? monthOnly(claim.month) : null;
      const recovery=panel(claimMonth ? claimMonth + ' recovery' : 'Claim recovery','recovery');
      const agreement=data.contract || {}, reviewer=data.reviewer || {};
      const contract=panel('Governing agreement','agreement');
      add(contract,fields([['Agreement',agreement.title],['Document reference',agreement.ref],['Version',shortRef(agreement.version)]]));
      list(agreement.documents).forEach(document=>contract.append(add(el('article',null,'workflow-document'),el('h3',document.title),
        note(document.effective_at ? 'Effective ' + day(document.effective_at) : 'Effective date not provided'),
        inspector('Document details', fields([['Reference',document.ref],['Version',document.version],['Effective date',document.effective_at]]), note(document.description)))));
      if (agreement.summary) contract.append(inspector('Agreement text', note(agreement.summary)));
      let attention = null, ramp = null;
      if (finance) {
        attention = panel('Needs attention', 'attention');
        const items = el('ol', null, 'attention-list');
        list(finance.attention).forEach(item => {
          const row = add(el('li', null, 'attention-item'), el('span', OWNERS[item.owner] || 'Next step', 'attention-owner'),
            el('h3', item.title), note(item.detail));
          if (item.section) row.append(jumpButton('Show details', item.section));
          items.append(row);
        });
        attention.append(items.children.length ? items : note('Nothing in this case needs action now.'));
        const rampInfo = finance.ramp || {};
        ramp = panel('Ramp record', 'ramp');
        const linked = rampInfo.linked_record && typeof rampInfo.linked_record === 'object' ? rampInfo.linked_record : null;
        add(ramp, fields([['Connection destination', rampInfo.destination], ['Ramp bill', linked ? linked.id : 'Not linked']]),
          note(linked ? 'Open the linked bill in Ramp to continue its native workflow.' : rampInfo.note));
        const records = el('a', 'Open Ramp records', 'case-link'); records.href = '#records'; ramp.append(records);
      }
      add(recovery,fields([['Current stage',state(claim.state)],['Destination',ledger.destination],['Claim reference',claim.id]]),note(claim.summary));
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
          busy=true;Array.from(controls.children).forEach(c=>{c.disabled=true;});status.textContent='Recording action…';
          try {
            await api('/api/workspace/workflow/actions/'+encodeURIComponent(action.id),{});
            if (token !== epoch) return;
            focusNextStep=true;recordedLabel=action.label || state(action.id);try{await render(root);}finally{focusNextStep=false;recordedLabel=null;}await onRefresh();
          } catch(error) {
            if(token !== epoch) return;
            if(error.status === 401 && typeof onUnauthorized === 'function') {
              epoch++;onUnauthorized();return;
            }
            uncertain=true;status.textContent='Refresh to check the recorded outcome before continuing.';
          } finally {busy=false;}
        });controls.append(button);
      });
      if(!controls.children.length) controls.append(note('No actions available in the current state.'));
      else if (!signedIn) {
        const again = el('button', 'Sign in again to take actions', 'quiet'); again.type = 'button';
        again.addEventListener('click', () => { if (typeof onUnauthorized === 'function') { epoch++; onUnauthorized(); } });
        controls.append(again);
        status.textContent = 'Reading only: reloading the page cleared the signing key. Sign in again to take actions.';
      }
      add(recovery,controls,status,inspector('Connection details', fields([['Connection destination',connection.destination],['Connection status',state(connection.status)],['Receipt status',state(connection.receipt_status)]])));
      const monthly=panel('Service credit evaluations','months'), table=el('table'), body=el('tbody');
      add(table,add(el('thead'),add(el('tr'),...['Service month','Decision','Service credit','Basis'].map(t=>{const th=el('th',t);th.scope='col';return th;}))),body);
      months.forEach(month=>body.append(add(el('tr'),el('td',monthLabel(month.month)),el('td',state(month.outcome)),el('td',money(month.amount,month.currency || currency)),monthEvidence(month))));
      add(monthly,add(el('div',null,'table-scroll'),table));
      const price=data.price_finding || {}, priceMonth = monthFor(price.invoice_id, months);
      const pricing=panel(priceMonth ? priceMonth + ' price review' : 'Price review','price');
      add(pricing,fields([['Finding','Price cap review'],['Status',PRICE_STATUS[price.state] || state(price.state)],['Invoice',price.invoice_id]].filter(([,value]) => value != null)));
      if (list(price.lines).length) {
        const lineTable = el('table'), lineBody = el('tbody');
        add(lineTable, add(el('thead'), add(el('tr'), ...['Invoice line','Governing version','Billed','Contract amount','Difference'].map(t => { const th = el('th', t); th.scope = 'col'; return th; }))), lineBody);
        list(price.lines).forEach(line => lineBody.append(add(el('tr'), el('td', line.line_id), el('td', line.version),
          el('td', money(line.billed, price.currency || currency)), el('td', money(line.expected, price.currency || currency)),
          el('td', money(line.delta, price.currency || currency) + (line.direction ? ' · ' + state(line.direction) : '')))));
        pricing.append(add(el('div', null, 'table-scroll'), lineTable));
        if (finance) pricing.append(note('An open price finding. It is not a credit and is not included in the credit stages.'));
      }
      add(pricing,inspector('Evaluator trace', note(reason(price.reason))),clauseList(price.citations));
      const bill=ledger.bill || {}, billing=panel('Bill reconciliation','bill');
      add(billing,fields([['Destination',ledger.destination],['Bill reference',bill.id],
        ['Service period',bill.service_start ? day(bill.service_start) + ' – ' + day(bill.service_end) : null],
        ['Original bill',money(bill.original_amount,currency)],['Applied credit',ledger.record_ids?.application ? money(ledger.applied,currency) : 'None applied'],
        ['Outstanding balance',money(bill.outstanding_amount,currency)]].filter(([,value]) => value != null)),
        inspector('References', fields([['Invoice issued',bill.issued_at],['Service starts',bill.service_start],['Service ends',bill.service_end],
          ['Receipt reference',claim.receipt_id],['Award reference',ledger.record_ids?.award],['Credit reference',ledger.record_ids?.credit],['Application reference',ledger.record_ids?.application]])));
      const detail=add(el('details',null,'panel ramp-details'),el('summary','Agreement & review record'));
      add(detail,fields([['Agreement',agreement.title],['Version',agreement.version],['Document reference',agreement.ref],['Reviewer',reviewer.name],['Principal',reviewer.principal],['Role',reviewer.role],['Authority kind',state(reviewer.authority_kind)]]),citations(agreement.citations));
      const onboarding=data.onboarding || {}, expansion=panel(onboarding.vendor ? onboarding.vendor+' coverage in this workspace' : 'Vendor coverage','coverage');
      const coverageReviewer=onboarding.reviewer || {};
      add(expansion,fields([['State in this workspace',state(onboarding.state)],['Adapter version',shortRef(onboarding.version)],
        ['Reviewer',coverageReviewer.name ? coverageReviewer.name + (coverageReviewer.authority_kind ? ' · ' + state(coverageReviewer.authority_kind) : '') : null]].filter(([,value]) => value != null)));
      const coverage=coverageHistory(onboarding), actors=[...new Set(list(onboarding.history).map(event=>event.actor).filter(Boolean))];
      if (!coverage.children.length) expansion.append(note('Coverage history not provided.'));
      else if (finance) expansion.append(add(el('details',null,'workflow-evidence'),el('summary','History in this workspace ('+coverage.children.length+' entries)'),actors.length===1 ? note('Every entry is recorded by '+actors[0]+'.') : null,coverage));
      else expansion.append(coverage);
      const vendorLink=el('a','Inspect vendor contracts','case-link');vendorLink.href='#vendors';expansion.append(vendorLink);
      const guide=finance ? guidePanel(token) : null;
      const activityLink = add(el('p', null, 'help'), (() => { const a = el('a', 'See the full activity history', 'case-link'); a.href = '#activity'; return a; })());
      root.replaceChildren(header,outcome(data, months),lifecycle(data),recovery,...(attention ? [attention] : []),...(guide ? [guide] : []),...(ramp ? [ramp] : []),
        monthly,add(el('div',null,'section-grid'),pricing,billing),contract,...(data.onboarding ? [expansion] : []),detail,activityLink);
      if (focusNextStep) {
        focusNextStep=false;
        const next=Array.from(controls.children).find(c=>c.tagName==='BUTTON' && !c.disabled);
        if (recordedLabel) status.textContent='Recorded: '+recordedLabel+'.'+(next ? ' Next: '+next.textContent+'.' : '');
        recordedLabel=null;
        const target=recovery.children[0];
        if (target && typeof target.focus==='function') target.focus();
      }
    }
    function coverageHistory(onboarding) {
      const coverage=el('ol',null,'activity'), actors=[...new Set(list(onboarding.history).map(event=>event.actor).filter(Boolean))];
      list(onboarding.history).forEach(event=>coverage.append(add(el('li'),el('time',when(event.at)),el('span',event.event),actors.length>1 && event.actor ? note('Recorded by '+event.actor) : null,event.ref ? el('code',event.ref) : null)));
      return coverage;
    }
    // Activity: what happened, in order, from the same projection. Absent data renders as absent.
    function renderActivity(root, data) {
      const vendor = typeof data.vendor === 'object' ? data.vendor.name : data.vendor;
      const header = add(el('div', null, 'page-head'), add(el('div'), el('h1', 'Activity'), note(vendor ? vendor + ' · contract review & recovery' : 'Contract review & recovery')),
        note(data.as_of ? 'As of ' + when(data.as_of) : ''));
      const history = panel('Workflow history'), timeline = el('ol', null, 'activity');
      list(data.audit).forEach(event => timeline.append(add(el('li'), el('time', when(event.at)), el('span', event.event), event.ref ? el('code', shortRef(event.ref)) : null)));
      history.append(timeline.children.length ? timeline : note('No workflow actions recorded.'));
      const onboarding = data.onboarding || {};
      const coverage = panel(onboarding.vendor ? onboarding.vendor + ' coverage history in this workspace' : 'Vendor coverage history'), entries = coverageHistory(onboarding);
      coverage.append(entries.children.length ? entries : note('Coverage history not provided.'));
      const automation = panel('Automation and model jobs');
      automation.append(note('This workspace does not report automation runs or model jobs.'));
      root.replaceChildren(header, history, coverage, automation);
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
  const exports={create,money,when,day,rates,monthLabel};
  if(typeof module !== 'undefined' && module.exports) module.exports=exports;
  global.UptimeWorkspace=exports;
})(typeof window === 'undefined' ? globalThis : window);
