/* Local semantic review. Uses the existing signed client; contains no credentials or source authority. */
(function (global) {
  'use strict';
  const enc = new TextEncoder();
  function quoteSpan(text, quote) {
    const index = text.indexOf(quote);
    if (!quote || index < 0 || text.indexOf(quote, index + 1) >= 0) throw new Error('Each quotation must occur exactly once in the original reply.');
    return {start:enc.encode(text.slice(0,index)).length,end:enc.encode(text.slice(0,index+quote.length)).length,quote};
  }
  async function mount(root, api, claim) {
    if (!/^inbox-[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$/.test(claim)) throw new Error('Choose a correspondence case.');
    root.classList.add('interpretation-review');
    const base = '/api/correspondence/claims/' + encodeURIComponent(claim) + '/interpretation';
    const el = (tag,text,cls) => { const n=document.createElement(tag); if(text!==undefined)n.textContent=text; if(cls)n.className=cls; return n; };
    const status=el('p','',undefined); status.setAttribute('role','status');
    root.replaceChildren(el('h1','Review the vendor’s meaning'),status);
    const data=await api(base), context=data.context, original=context.text;
    root.append(el('p','First record your own reading. Any model suggestion appears only after that reading is saved. Interpretation does not authorize a filing, financial entry, waiver or denial closure.','interpretation-note'));
    root.append(el('h2','Complete signed reply'),el('pre',data.visible_text));
    root.append(el('p',`Claim month: ${context.scope.month} · Filed amount: ${context.requested===null?'Not recorded; procedural review only':context.currency+' '+context.requested}`));
    root.append(el('p',`Case ${context.claim} · Vendor ${context.scope.vendor} · Service ${context.scope.service} · Region ${context.scope.region}`));
    const provenance=el('details'); provenance.append(el('summary','Original source and governing terms'),el('p',`Reply ${context.event_digest} · Text ${context.text_sha256} · Terms ${context.contract_version} · Document ${context.contract_source_sha256}`,'interpretation-meta')); root.append(provenance);
    const form=el('div'), grid=el('div',undefined,'interpretation-grid'); form.append(el('h2','Your independent reading'),grid); root.append(form);
    function field(parent,label,options,multiline=false) {
      const wrap=el('label',label), node=el(options?'select':multiline?'textarea':'input'); node.setAttribute('aria-label',label);
      if(options){node.append(new Option('Choose…','')); for(const [value,title] of options)node.append(new Option(title,value));}
      wrap.append(node);parent.append(wrap);return node;
    }
    const family=field(grid,'Main assertion',[['availability','Availability met the agreement'],['time_bar','Original filing was late'],['artifact','A specific document is required'],['component','An affected component must be identified'],['maintenance','Maintenance excluded the incident'],['downtime','Vendor measured a shorter interruption'],['scope_error','Vendor identifies a different scoped record'],['filing_fields','Contractual filing items are required'],['award','Vendor reports a service credit'],['unsupported','Other or unresolved meaning']]);
    const polarity=field(grid,'Polarity',[['positive','The vendor affirms this assertion'],['negative','The assertion is negated'],['uncertain','Uncertain']]);
    const modality=field(grid,'Status of the assertion',[['asserted','Current unconditional assertion'],['quoted','Quotation or another person’s position'],['conditional','Conditional'],['future','Future intent'],['offered','Offer'],['uncertain','Uncertain']]);
    const referent=field(grid,'Which claim?', [['current_claim','This exact claim'],['other_claim','A different claim'],['ambiguous','Ambiguous']]);
    const artifact=field(grid,'Document type, if requested',[['none','No document type'],['invoice_detail','Itemized billing record'],['resource_log','Incident or telemetry record'],['scope_mapping','Account or resource mapping']]);
    const scopeField=field(grid,'Incorrect scoped identifier, if any',[['none','No scoped identifier correction'],['account','Account'],['component','Component'],['invoice','Invoice']]);
    const quotes={}; for(const [name,label] of [['period','Exact month phrase, if stated'],['award','Exact awarded USD amount, if stated'],['remainder','Exact declined remainder, if stated'],['claimed','Exact restated claim amount, if stated'],['artifact_ref','Exact document reference, if stated'],['scope_ref','Exact incorrect identifier, if stated'],['downtime','Exact duration with unit, if stated']])quotes[name]=field(grid,label);
    const condition=field(form,'Exact condition phrase, if any (copy from the reply)');
    const filing=field(form,'Contractual filing items, if requested (one exact name per line)',null,true);
    if(context.filing_fields.length)form.append(el('p','Declared missing items: '+context.filing_fields.join('; ')));
    const residual=field(form,'Additional objection or unresolved meaning?', [['no','None after reviewing the complete reply'],['yes','Yes; keep this in human review']]);
    let blind=data.blind_entry, selected=null, preview=null;
    function annotation(){
      if(!family.value||!polarity.value||!modality.value||!referent.value||!residual.value)throw new Error('Complete the independent semantic judgments.');
      const source=quoteSpan(original,original);
      return {propositions:[{family:residual.value==='yes'?'unsupported':family.value,source,polarity:polarity.value,modality:modality.value,referent:referent.value,conditions:condition.value?[quoteSpan(original,condition.value)]:[],slots:Object.entries(quotes).filter(([,n])=>n.value).map(([name,n])=>({name,source:quoteSpan(original,n.value)})),artifact_type:artifact.value&&artifact.value!=='none'?artifact.value:null,scope_field:scopeField.value&&scopeField.value!=='none'?scopeField.value:null,filing_fields:filing.value.split('\n').map(x=>x.trim()).filter(Boolean)}],segments:[{source,role:residual.value==='yes'?'unsupported':'substantive'}]};
    }
    function fill(value){const p=value.propositions[0];family.value=p.family;polarity.value=p.polarity;modality.value=p.modality;referent.value=p.referent;artifact.value=p.artifact_type||'none';scopeField.value=p.scope_field||'none';residual.value=value.segments.some(s=>s.role==='unsupported')?'yes':'no';condition.value=p.conditions.map(c=>c.quote).join('\n');filing.value=p.filing_fields.join('\n');for(const n of Object.values(quotes))n.value='';for(const slot of p.slots)if(quotes[slot.name])quotes[slot.name].value=slot.source.quote;}
    const controls=el('div'), candidates=el('section'), decisions=el('section');root.append(controls,candidates,decisions);
    async function run(button,work){button.disabled=true;status.textContent='Checking the exact source and current state…';try{await work();status.textContent='Saved. No financial or external action was authorized.';}catch(e){status.textContent=e.message;}finally{button.disabled=false;}}
    function button(label,handler){const b=el('button',label);b.type='button';b.addEventListener('click',()=>run(b,handler));return b;}
    const save=button('Save independent reading',async()=>{const interpretation=annotation();await api(base+'/blind-entry',{context_digest:context.digest,interpretation});blind=interpretation;showReview();save.hidden=true;});controls.append(save);
    const model=button('Request a public-only model suggestion',async()=>{await api(base+'/candidates/model',{context_digest:context.digest});const latest=await api(base);showCandidates(latest.candidates);});controls.append(model);model.hidden=true;
    function showCandidates(rows){candidates.replaceChildren(el('h2','Untrusted suggestions'));for(const candidate of rows){const box=el('details');box.append(el('summary',candidate.origin==='model'?'Model suggestion — requires your review':'Saved manual suggestion'));for(const p of candidate.interpretation.propositions){box.append(el('p',`${p.family} · ${p.polarity} · ${p.modality} · ${p.referent}`),el('blockquote',p.source.quote));for(const s of p.slots)box.append(el('p',s.name+': '+s.source.quote));for(const c of p.conditions)box.append(el('p','Condition: '+c.quote));}box.append(button('Compare this suggestion',async()=>{selected=candidate;showReview();}));candidates.append(box);}}
    function showReview(){
      model.hidden=!data.model_enabled;
      decisions.replaceChildren(el('h2','Reconcile and attest the meaning'),el('p','You may correct your reading above. Explain each changed proposition; any rejected proposition remains review-only. No automatic agreement is selected.'));
      const count=Math.max(blind.propositions.length,selected?selected.interpretation.propositions.length:0), resolutions=[];
      for(let i=0;i<count;i++){const box=el('fieldset');box.append(el('legend','Proposition '+(i+1)));const source=selected?.interpretation.propositions[i]?.source.quote||blind.propositions[i]?.source.quote;box.append(el('p',source||'Additional proposition'));const verdict=field(box,'Your decision',[['accept','Accept unchanged meaning'],['correct','Correct the meaning with explanation'],['reject','Reject; keep in human review']]);const explanation=field(box,'Explanation of source meaning and any difference');resolutions.push({i,verdict,explanation});decisions.append(box);}
      function check(label){const wrap=el('label',undefined,'interpretation-check'),input=el('input');input.type='checkbox';wrap.append(input,document.createTextNode(label));decisions.append(wrap);return input;}
      const full=check('I reviewed the complete original reply, including negation, conditions, attribution and claim identity.');
      const rest=check('I accounted for every additional objection or residual obligation; unresolved meaning remains review-only.');
      decisions.append(button('Save meaning review and inspect preview',async()=>{
        const body={context_digest:context.digest,interpretation:annotation(),candidate_id:selected?.id||null,resolutions:resolutions.map(r=>({proposition:r.i,verdict:r.verdict.value,explanation:r.explanation.value})),residuals_reviewed:rest.checked,complete_meaning_reviewed:full.checked};
        if(!full.checked||!rest.checked)throw new Error('Complete both source-review attestations.');
        const review=await api(base+'/reviews',body);preview=await api(base+'/reviews/'+review.id+'/preview');
        const result=el('section');result.append(el('h2','Deterministic preview'),el('p',preview.disposition),el('p',preview.reported_award?'Interpreted reported award: USD '+preview.reported_award+'; no ledger entry.':'No awarded, posted or applied money changes.'));
        if(preview.closure_suggested)result.append(el('p','The evidence supports a denial; closure remains a separate review decision.'));
        if(preview.prepare_allowed)result.append(button('Prepare evidence-backed response draft',async()=>{const changed=await api(base+'/prepare-response',{review_id:review.id,preview_digest:preview.digest});result.replaceChildren(el('h2','Draft prepared'),el('p',changed.stage+' · Existing exact approval and submission permissions still apply.'));}));
        else result.append(el('p','No response preparation is authorized by this preview.'));
        decisions.append(result);
      }));
    }
    if(blind){fill(blind);save.hidden=true;showReview();showCandidates(data.candidates);}
  }
  global.UptimeInterpretation={mount,quoteSpan};
  const root=document.getElementById('interpretation-root');
  if(root){const claim=new URLSearchParams(location.search).get('claim')||'';root.replaceChildren(global.uptimeAuth.signInForm(()=>mount(root,global.uptimeAPI,claim).catch(e=>{root.textContent=e.message;})));}
})(window);
