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
    let epoch = 0, busy = false, uncertain = false;
    const el = (tag, value, cls) => { const n = doc.createElement(tag); if (value != null) n.textContent = text(value); if (cls) n.className = cls; return n; };
    const add = (n, ...children) => { children.filter(Boolean).forEach(c => n.append(c)); return n; };
    const note = value => el('p',value,'help');
    const panel = title => add(el('section',null,'panel'),el('h2',title));
    const field = (label,value) => add(el('div',null,'northwind-field'),el('dt',label),el('dd',value));
    const fields = pairs => add(el('dl',null,'northwind-fields'),...pairs.map(([k,v])=>field(k,v)));
    function citations(items) {
      const refs = el('ul',null,'northwind-citations');
      list(items).forEach(c => refs.append(add(el('li'), el('span',typeof c === 'string' ? c : c.label || c.title || c.ref), typeof c === 'object' && c.ref ? el('code', c.ref) : null)));
      return refs.children.length ? refs : note('Source references not provided.');
    }
    function monthEvidence(month) {
      const cell=el('td');add(cell,note(reason(month.reason)),citations(month.citations));
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
    function renderData(root,data,token) {
      const vendor = typeof data.vendor === 'object' ? data.vendor.name : data.vendor;
      const header=add(el('div',null,'page-head'),add(el('div'),el('h1',vendor || 'Contract operations'),note('Contract review & recovery')),note(data.as_of ? 'Updated '+data.as_of : ''));
      const ledger=data.ledger || {}, currency=ledger.currency || 'USD';
      const metrics=el('section',null,'metrics');metrics.setAttribute('aria-label','Financial stages');
      for (const [key,title] of [['claimed','Claimed'],['awarded','Awarded'],['posted','Posted to '+text(ledger.destination)],['applied','Applied to bill']]) metrics.append(add(el('article',null,'metric'),el('h2',title),el('div',money(ledger[key],currency),'metric-value')));
      const recovery=panel('January recovery'), claim=data.claim || {}, connection=data.connection || {};
      const agreement=data.contract || {}, reviewer=data.reviewer || {};
      const contract=panel('Governing agreement');
      add(contract,note(agreement.summary),fields([['Agreement',agreement.title],['Version',agreement.version],['Document reference',agreement.ref]]));
      list(agreement.documents).forEach(document=>contract.append(add(el('article',null,'workflow-document'),el('h3',document.title),fields([['Reference',document.ref],['Version',document.version],['Effective date',document.effective_at]]),note(document.description))));
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
            await render(root);await onRefresh();
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
      const monthly=panel('Service credit evaluations'), table=el('table'), body=el('tbody');
      add(table,add(el('thead'),add(el('tr'),...['Service month','Decision','Service credit','Evidence'].map(t=>{const th=el('th',t);th.scope='col';return th;}))),body);
      list(data.months).forEach(month=>body.append(add(el('tr'),el('td',month.month),el('td',state(month.outcome)),el('td',money(month.amount,month.currency || currency)),monthEvidence(month))));
      add(monthly,add(el('div',null,'table-scroll'),table));
      const price=data.price_finding || {}, pricing=panel('March price review');
      add(pricing,fields([['Finding','Price cap review'],['Exposure',money(price.amount,price.currency || currency)],['Status',state(price.state)]]),note(reason(price.reason)),citations(price.citations));
      const bill=ledger.bill || {}, billing=panel('Bill reconciliation');
      add(billing,fields([['Destination',ledger.destination],['Bill reference',bill.id],['Invoice issued',bill.issued_at],['Service starts',bill.service_start],['Service ends',bill.service_end],['Original bill',money(bill.original_amount,currency)],['Outstanding balance',money(bill.outstanding_amount,currency)],['Receipt reference',claim.receipt_id],['Award reference',ledger.record_ids?.award],['Credit reference',ledger.record_ids?.credit],['Application reference',ledger.record_ids?.application]]));
      const detail=add(el('details',null,'panel ramp-details'),el('summary','Agreement & review record'));
      add(detail,fields([['Agreement',agreement.title],['Version',agreement.version],['Document reference',agreement.ref],['Reviewer',reviewer.name],['Principal',reviewer.principal],['Role',reviewer.role],['Authority kind',state(reviewer.authority_kind)]]),citations(agreement.citations));
      const onboarding=data.onboarding || {}, expansion=panel(onboarding.vendor ? onboarding.vendor+' contract coverage' : 'Vendor coverage');
      add(expansion,fields([['Current state',state(onboarding.state)],['Adapter version',onboarding.version]]));
      const coverage=el('ol',null,'activity');
      list(onboarding.history).forEach(event=>coverage.append(add(el('li'),el('time',event.at),el('span',event.event),event.ref ? el('code',event.ref) : null)));
      expansion.append(coverage.children.length ? coverage : note('Coverage history not provided.'));
      const vendorLink=el('a','Inspect vendor contracts','case-link');vendorLink.href='#vendors';expansion.append(vendorLink);
      const history=panel('Workflow history'), timeline=el('ol',null,'activity');
      list(data.audit).forEach(event=>timeline.append(add(el('li'),el('time',event.at),el('span',event.event),event.ref ? el('code',event.ref) : null)));
      history.append(timeline.children.length ? timeline : note('No workflow actions recorded.'));
      root.replaceChildren(header,metrics,contract,recovery,monthly,add(el('div',null,'section-grid'),pricing,billing),...(data.onboarding ? [expansion] : []),detail,history);
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
