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
  function create({api, document:doc = global.document, onRefresh = () => {}, onUnauthorized}) {
    // After a recorded action the page re-renders; focus moves to the next offered step so keyboard use continues there.
    let epoch = 0, busy = false, uncertain = false, focusNextStep = false;
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
    function monthEvidence(month) {
      const cell=el('td');add(cell,note(reason(month.reason)),citations(month.citations));
      if(list(month.calculation).length) cell.append(add(el('ol',null,'trace'),...month.calculation.map(line=>el('li',line))));
      const inputs = month.inputs || {};
      if (Object.keys(inputs).length) {
        const rows = [['Governing fee', inputs.governing_fee == null ? null : money(inputs.governing_fee, inputs.currency || month.currency || 'USD')],
          ['Fee reference', inputs.fee_version], ['Eligible downtime (minutes)', inputs.eligible_downtime_minutes],
          ['Completed increments', inputs.completed_steps], ['Credit rate', inputs.credit_percent == null ? null : inputs.credit_percent + '%'],
          ['Claim deadline', inputs.claim_cutoff], ['Usage record', inputs.monitor_ref]].filter(([, value]) => value != null);
        if (rows.length) cell.append(add(el('details', null, 'workflow-evidence'), el('summary', 'Calculation inputs'), fields(rows)));
      }
      if (month.invoice || list(month.evidence).length || list(month.trace).length) {
        const detail=add(el('details',null,'workflow-evidence'),el('summary','Inspect invoice & usage'));
        const invoice=month.invoice || {};
        if (month.invoice) detail.append(fields([['Invoice',invoice.id],['Issued',invoice.issued_at],['Service starts',invoice.service_start],['Service ends',invoice.service_end]]));
        list(month.evidence).forEach(item=>detail.append(add(el('article',null,'workflow-document'),el('h3',item.label),note(item.value == null ? 'Not provided' : item.value),item.ref ? el('code',item.ref) : null)));
        if(list(month.trace).length) detail.append(add(el('ol',null,'trace'),...month.trace.map(line=>el('li',reason(line)))));
        cell.append(detail);
      }
      return cell;
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
          ...(result.scope_note ? [note(result.scope_note)] : []), note('As of ' + text(result.as_of) + '. Read only; nothing was changed.'));
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
      const header=add(el('div',null,'page-head'),add(el('div'),el('h1',vendor || 'Contract operations'),note('Contract review & recovery')),note(data.as_of ? 'Updated '+data.as_of : ''));
      const ledger=data.ledger || {}, currency=ledger.currency || 'USD';
      const metrics=el('section',null,'metrics');metrics.setAttribute('aria-label','Financial stages');
      for (const [key,title] of [['claimed','Claimed'],['awarded','Awarded'],['posted','Posted to '+text(ledger.destination)],['applied','Applied to bill']]) metrics.append(add(el('article',null,'metric'),el('h2',title),el('div',money(ledger[key],currency),'metric-value')));
      const finance = data.finance && typeof data.finance === 'object' ? data.finance : null;
      const stageNote = finance ? note('Stages of the same credit. Each amount shows how far that credit has progressed; the amounts are not added together.') : null;
      const recovery=panel('January recovery','recovery'), claim=data.claim || {}, connection=data.connection || {};
      const agreement=data.contract || {}, reviewer=data.reviewer || {};
      const contract=panel('Governing agreement','agreement');
      add(contract,note(agreement.summary),fields([['Agreement',agreement.title],['Version',agreement.version],['Document reference',agreement.ref]]));
      list(agreement.documents).forEach(document=>contract.append(add(el('article',null,'workflow-document'),el('h3',document.title),fields([['Reference',document.ref],['Version',document.version],['Effective date',document.effective_at]]),note(document.description))));
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
      add(recovery,fields([['Connection destination',connection.destination],['Connection status',state(connection.status)],['Receipt status',state(connection.receipt_status)]]));
      add(recovery,fields([['Current stage',state(claim.state)],['Claim reference',claim.id],['Destination',ledger.destination]]),note(claim.summary));
      const status=el('p',null,'help');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
      const controls=el('div',null,'actions');
      list(data.next_actions).forEach(action=>{
        if (!action.id) return;
        const button=el('button',action.label || state(action.id));button.type='button';button.disabled=busy || uncertain || action.enabled === false;
        button.addEventListener('click', async()=>{
          if (busy || uncertain || token !== epoch || action.enabled === false) return;
          busy=true;Array.from(controls.children).forEach(c=>{c.disabled=true;});status.textContent='Recording action…';
          try {
            await api('/api/workspace/workflow/actions/'+encodeURIComponent(action.id),{});
            if (token !== epoch) return;
            focusNextStep=true;try{await render(root);}finally{focusNextStep=false;}await onRefresh();
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
      add(recovery,controls,status);
      const monthly=panel('Service credit evaluations','months'), table=el('table'), body=el('tbody');
      add(table,add(el('thead'),add(el('tr'),...['Service month','Decision','Service credit','Evidence'].map(t=>{const th=el('th',t);th.scope='col';return th;}))),body);
      list(data.months).forEach(month=>body.append(add(el('tr'),el('td',month.month),el('td',state(month.outcome)),el('td',money(month.amount,month.currency || currency)),monthEvidence(month))));
      add(monthly,add(el('div',null,'table-scroll'),table));
      const price=data.price_finding || {}, pricing=panel('March price review','price');
      add(pricing,fields([['Finding','Price cap review'],['Exposure',money(price.amount,price.currency || currency)],['Status',state(price.state)]]));
      if (list(price.lines).length) {
        const lineTable = el('table'), lineBody = el('tbody');
        add(lineTable, add(el('thead'), add(el('tr'), ...['Invoice line','Governing version','Billed','Contract amount','Difference'].map(t => { const th = el('th', t); th.scope = 'col'; return th; }))), lineBody);
        list(price.lines).forEach(line => lineBody.append(add(el('tr'), el('td', line.line_id), el('td', line.version),
          el('td', money(line.billed, price.currency || currency)), el('td', money(line.expected, price.currency || currency)),
          el('td', money(line.delta, price.currency || currency) + (line.direction ? ' · ' + state(line.direction) : '')))));
        pricing.append(add(el('div', null, 'table-scroll'), lineTable));
        if (finance) pricing.append(note('An open price finding. It is not a credit and is not included in the credit stages.'));
      }
      add(pricing,note(reason(price.reason)),citations(price.citations));
      const bill=ledger.bill || {}, billing=panel('Bill reconciliation','bill');
      add(billing,fields([['Destination',ledger.destination],['Bill reference',bill.id],['Invoice issued',bill.issued_at],['Service starts',bill.service_start],['Service ends',bill.service_end],['Original bill',money(bill.original_amount,currency)],['Applied credit',ledger.record_ids?.application ? money(ledger.applied,currency) : 'None applied'],['Outstanding balance',money(bill.outstanding_amount,currency)],['Receipt reference',claim.receipt_id],['Award reference',ledger.record_ids?.award],['Credit reference',ledger.record_ids?.credit],['Application reference',ledger.record_ids?.application]]));
      const detail=add(el('details',null,'panel ramp-details'),el('summary','Agreement & review record'));
      add(detail,fields([['Agreement',agreement.title],['Version',agreement.version],['Document reference',agreement.ref],['Reviewer',reviewer.name],['Principal',reviewer.principal],['Role',reviewer.role],['Authority kind',state(reviewer.authority_kind)]]),citations(agreement.citations));
      const onboarding=data.onboarding || {}, expansion=panel(onboarding.vendor ? onboarding.vendor+' coverage in this workspace' : 'Vendor coverage','coverage');
      const coverageReviewer=onboarding.reviewer || {};
      add(expansion,fields([['State in this workspace',state(onboarding.state)],['Adapter version',onboarding.version],
        ['Reviewer',coverageReviewer.name ? coverageReviewer.name + (coverageReviewer.authority_kind ? ' · ' + state(coverageReviewer.authority_kind) : '') : null]].filter(([,value]) => value != null)));
      const coverage=el('ol',null,'activity'), actors=[...new Set(list(onboarding.history).map(event=>event.actor).filter(Boolean))];
      list(onboarding.history).forEach(event=>coverage.append(add(el('li'),el('time',event.at),el('span',event.event),actors.length>1 && event.actor ? note('Recorded by '+event.actor) : null,event.ref ? el('code',event.ref) : null)));
      if (!coverage.children.length) expansion.append(note('Coverage history not provided.'));
      else if (finance) expansion.append(add(el('details',null,'workflow-evidence'),el('summary','History in this workspace ('+coverage.children.length+' entries)'),actors.length===1 ? note('Every entry is recorded by '+actors[0]+'.') : null,coverage));
      else expansion.append(coverage);
      const vendorLink=el('a','Inspect vendor contracts','case-link');vendorLink.href='#vendors';expansion.append(vendorLink);
      const history=panel('Workflow history'), timeline=el('ol',null,'activity');
      const guide=finance ? guidePanel(token) : null;
      list(data.audit).forEach(event=>timeline.append(add(el('li'),el('time',event.at),el('span',event.event),event.ref ? el('code',event.ref) : null)));
      history.append(timeline.children.length ? timeline : note('No workflow actions recorded.'));
      root.replaceChildren(header,...(attention ? [attention] : []),metrics,...(stageNote ? [stageNote] : []),...(ramp ? [ramp] : []),contract,recovery,monthly,add(el('div',null,'section-grid'),pricing,billing),...(guide ? [guide] : []),...(data.onboarding ? [expansion] : []),detail,history);
      if (focusNextStep) {
        focusNextStep=false;
        const next=Array.from(controls.children).find(c=>c.tagName==='BUTTON' && !c.disabled), target=next || recovery.children[0];
        if (target && typeof target.focus==='function') target.focus();
      }
    }
    async function render(root, supplied) {
      const token=++epoch;
      try {
        const data=supplied || (await api('/api/workspace/workflow')).workflow;
        if(token !== epoch) return;
        uncertain=false;busy=false;renderData(root,data,token);
      } catch(error) { if(token !== epoch) return;throw error; }
    }
    return {render,unmount:()=>{epoch++;}};
  }
  const exports={create,money};
  if(typeof module !== 'undefined' && module.exports) module.exports=exports;
  global.UptimeWorkspace=exports;
})(typeof window === 'undefined' ? globalThis : window);
