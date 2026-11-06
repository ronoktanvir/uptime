/* Local semantic review. Uses the existing signed client; contains no credentials or source authority. */
(function (global) {
  'use strict';
  const enc = new TextEncoder();
  function quoteSpan(text, quote) {
    const index = text.indexOf(quote);
    if (!quote || index < 0 || text.indexOf(quote, index + 1) >= 0) throw new Error('Each quotation must occur exactly once in the original reply.');
    return {start:enc.encode(text.slice(0,index)).length,end:enc.encode(text.slice(0,index+quote.length)).length,quote};
  }
  const JOB_TEXT={QUEUED:'Request queued. It runs only as the exact approved request; nothing is applied automatically.',
    RUNNING:'Request running. You can keep working; nothing is applied automatically.',
    SUCCEEDED:'Request completed. The proposal is listed below and still needs your review.',
    REFUSED:'Request refused or its result failed the source checks. No proposal was added. Refresh the original source before continuing.',
    CANCELLED:'Request cancelled before it ran. It is not sent again automatically.',
    UNCERTAIN:'Request outcome uncertain. A validated proposal may already appear below; check its request reference. This request is not sent again automatically.'};
  const STALE=/changed|stale|expired/i;
  async function mount(root, api, claim, options) {
    if (!/^inbox-[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$/.test(claim)) throw new Error('Choose a correspondence case.');
    const pollMs=Math.max(10,Number(options?.pollMs??1000)), maxPolls=Math.min(60,Math.max(1,Number(options?.maxPolls??60)));
    root.classList.add('interpretation-review');
    const base = '/api/correspondence/claims/' + encodeURIComponent(claim) + '/interpretation';
    const el = (tag,text,cls) => { const n=document.createElement(tag); if(text!==undefined)n.textContent=text; if(cls)n.className=cls; return n; };
    const status=el('p','',undefined); status.setAttribute('role','status');
    root.replaceChildren(el('h1','Review the vendor’s meaning'),status);
    const data=await api(base), context=data.context, original=context.text;
    root.append(el('p','First record your own reading. Any requested interpretation appears only after that reading is saved. Interpretation does not authorize a filing, financial entry, waiver or denial closure.','interpretation-note'));
    root.append(el('h2','Complete signed reply'),el('pre',data.visible_text));
    root.append(el('p',`Claim month: ${context.scope.month} · Filed amount: ${context.requested===null?'Not recorded; procedural review only':context.currency+' '+context.requested}`));
    root.append(el('p',`Case ${context.claim} · Vendor ${context.scope.vendor} · Service ${context.scope.service} · Region ${context.scope.region}`));
    const provenance=el('details'); provenance.append(el('summary','Original source and governing terms'),el('p',`Reply ${context.event_digest} · Text ${context.text_sha256} · Terms ${context.contract_version} · Document ${context.contract_source_sha256}`,'interpretation-meta')); root.append(provenance);
    // Exact original blocks (textContent only; never normalized or rendered as markup).
    const blocks=Array.isArray(data.source_blocks)?data.source_blocks:null, ranges=[];
    if(blocks){let cursor=0;const list=el('details',undefined,'interpretation-blocks');list.append(el('summary','Original reply by line'));
      blocks.forEach((b,i)=>{const size=enc.encode(b.text).length;ranges.push([cursor,cursor+size]);cursor+=size;list.append(el('p',`Line ${i+1} · ${b.id}`,'interpretation-meta'),el('pre',b.text));});
      provenance.after(list);}
    function where(span){const i=ranges.findIndex(([s,e])=>s<=span.start&&span.start<e);return i<0?`bytes ${span.start}–${span.end} of the reply`:`line ${i+1}, bytes ${span.start-ranges[i][0]}–${span.end-ranges[i][0]} of that line`;}
    let jobInfo=data.model_job||null, job=jobInfo?.job||null, polling=false;
    const permission=el('details',undefined,'interpretation-permission');
    function showPermission(){if(!jobInfo)return;permission.replaceChildren(el('summary','Interpretation request permission'),el('p',jobInfo.message||'Permission status unavailable.'),
      el('p',`Request reference ${jobInfo.request_sha256||'not available'} · Size ${jobInfo.request_bytes??'not available'} bytes · Profile ${jobInfo.profile||'not configured'}`,'interpretation-meta'),
      el('p',`Case ${jobInfo.target} · Source context ${jobInfo.context_digest} · Request type ${jobInfo.kind}`,'interpretation-meta'),
      el('p','An operator approves this exact request reference outside this page. This page cannot grant permission.'));
      if(jobInfo.approval_request){const exportView=el('details');exportView.append(el('summary','Complete request for operator approval'),el('pre',JSON.stringify(jobInfo.approval_request,null,2)));permission.append(exportView);}}
    if(jobInfo){showPermission();(blocks?provenance.nextSibling:provenance).after(permission);}
    const MAX_PROPOSITIONS=12;
    const form=el('div'), editorsBox=el('div',undefined,'interpretation-propositions'); form.append(el('h2','Your independent reading'),editorsBox); root.append(form);
    function field(parent,label,options,multiline=false) {
      const wrap=el('label',label), node=el(options?'select':multiline?'textarea':'input'); node.setAttribute('aria-label',label);
      if(options){node.append(new Option('Choose…','')); for(const [value,title] of options)node.append(new Option(title,value));}
      wrap.append(node);parent.append(wrap);return node;
    }
    const FAMILIES=[['availability','Availability met the agreement'],['time_bar','Original filing was late'],['artifact','A specific document is required'],['component','An affected component must be identified'],['maintenance','Maintenance excluded the incident'],['downtime','Vendor measured a shorter interruption'],['scope_error','Vendor identifies a different scoped record'],['filing_fields','Contractual filing items are required'],['award','Vendor reports a service credit'],['unsupported','Other or unresolved meaning']];
    const SLOT_LABELS=[['period','Exact month phrase, if stated'],['award','Exact awarded USD amount, if stated'],['remainder','Exact declined remainder, if stated'],['claimed','Exact restated claim amount, if stated'],['artifact_ref','Exact document reference, if stated'],['scope_ref','Exact incorrect identifier, if stated'],['downtime','Exact duration with unit, if stated']];
    // One separate editor per proposition. The first keeps the original labels; others are suffixed.
    const editors=[];
    function makeEditor(){
      const n=editors.length, suffix=n===0?'':` (proposition ${n+1})`, box=el('fieldset',undefined,'interpretation-proposition'), grid=el('div',undefined,'interpretation-grid');
      box.append(el('legend',`Your reading — proposition ${n+1}`));
      const e={box,imported:{source:null,conditions:null,slots:{}}};
      e.source=field(box,'Exact source passage for this proposition (copy from the reply)'+suffix,null,true);
      box.append(grid);
      e.family=field(grid,'Main assertion'+suffix,FAMILIES);
      e.polarity=field(grid,'Polarity'+suffix,[['positive','The vendor affirms this assertion'],['negative','The assertion is negated'],['uncertain','Uncertain']]);
      e.modality=field(grid,'Status of the assertion'+suffix,[['asserted','Current unconditional assertion'],['quoted','Quotation or another person’s position'],['conditional','Conditional'],['future','Future intent'],['offered','Offer'],['uncertain','Uncertain']]);
      e.referent=field(grid,'Which claim?'+suffix,[['current_claim','This exact claim'],['other_claim','A different claim'],['ambiguous','Ambiguous']]);
      e.artifact=field(grid,'Document type, if requested'+suffix,[['none','No document type'],['invoice_detail','Itemized billing record'],['resource_log','Incident or telemetry record'],['scope_mapping','Account or resource mapping']]);
      e.scopeField=field(grid,'Incorrect scoped identifier, if any'+suffix,[['none','No scoped identifier correction'],['account','Account'],['component','Component'],['invoice','Invoice']]);
      e.quotes={}; for(const [name,label] of SLOT_LABELS)e.quotes[name]=field(grid,label+suffix);
      e.condition=field(box,'Exact condition phrase, if any (copy from the reply)'+suffix,null,true);
      e.filing=field(box,'Contractual filing items, if requested (one exact name per line)'+suffix,null,true);
      editorsBox.append(box);editors.push(e);return e;
    }
    const add=el('button','Add another proposition'); add.type='button';
    form.append(add,el('p',`Up to ${MAX_PROPOSITIONS} separate propositions. Each exact source passage must occur once in the reply; leave it empty to use the complete reply. Together the passages must cover every non-courtesy part of the reply, exactly as before; uncovered text is rejected when saved. Only one bounded pair — a primary availability, late-filing or maintenance assertion plus a separate unconditional “no credit” statement — can reach the deterministic check; every other combination stays in human review.`,'interpretation-note'));
    if(context.filing_fields.length)form.append(el('p','Declared missing items: '+context.filing_fields.join('; ')));
    const residual=field(form,'Additional objection or unresolved meaning?', [['no','None after reviewing the complete reply'],['yes','Yes; keep this in human review']]);
    let blind=data.blind_entry, selected=null, preview=null, rows=[], loadedSegments=null, loadedResidual=null, generation=0;
    const reviewed=new Set();
    const copy=s=>({start:s.start,end:s.end,quote:s.quote});
    // An imported exact span is kept while its quote is unchanged, so duplicate text is never silently reselected.
    // An edited quote must occur exactly once in the reply.
    function exact(value,imported){return imported&&value===imported.quote?copy(imported):quoteSpan(original,value);}
    function proposition(e,i){
      if(!e.family.value||!e.polarity.value||!e.modality.value||!e.referent.value)throw new Error(i===0?'Complete the independent semantic judgments.':`Complete the semantic judgments for proposition ${i+1}.`);
      try{
        const source=e.source.value?exact(e.source.value,e.imported.source):quoteSpan(original,original);
        const imported=e.imported.conditions, text=e.condition.value;
        const conditions=imported&&text===imported.map(c=>c.quote).join('\n')?imported.map(copy):text.split('\n').filter(Boolean).map(q=>quoteSpan(original,q));
        const slots=Object.entries(e.quotes).filter(([,n])=>n.value).map(([name,n])=>({name,source:exact(n.value,e.imported.slots[name])}));
        return {family:e.family.value,source,polarity:e.polarity.value,modality:e.modality.value,referent:e.referent.value,conditions,slots,artifact_type:e.artifact.value&&e.artifact.value!=='none'?e.artifact.value:null,scope_field:e.scopeField.value&&e.scopeField.value!=='none'?e.scopeField.value:null,filing_fields:e.filing.value.split('\n').map(x=>x.trim()).filter(Boolean)};
      }catch(err){throw new Error(editors.length>1?`Proposition ${i+1}: ${err.message}`:err.message);}
    }
    function segmentsFor(){
      const role=residual.value==='yes'?'unsupported':'substantive';
      if(!loadedSegments)return [{source:quoteSpan(original,original),role}];
      if(residual.value===loadedResidual)return loadedSegments.map(s=>({source:copy(s.source),role:s.role}));
      return loadedSegments.map(s=>({source:copy(s.source),role:s.role==='courtesy'?'courtesy':role}));
    }
    function annotation(){
      if(!residual.value||!editors.length)throw new Error('Complete the independent semantic judgments.');
      return {propositions:editors.map(proposition),segments:segmentsFor()};
    }
    function fillOne(e,p){
      e.family.value=p.family;e.polarity.value=p.polarity;e.modality.value=p.modality;e.referent.value=p.referent;e.artifact.value=p.artifact_type||'none';e.scopeField.value=p.scope_field||'none';
      e.source.value=p.source.quote;e.condition.value=p.conditions.map(c=>c.quote).join('\n');e.filing.value=p.filing_fields.join('\n');
      e.imported={source:copy(p.source),conditions:p.conditions.map(copy),slots:{}};
      for(const n of Object.values(e.quotes))n.value='';
      for(const slot of p.slots)if(e.quotes[slot.name]){e.quotes[slot.name].value=slot.source.quote;e.imported.slots[slot.name]=copy(slot.source);}
    }
    function updateAdd(){add.disabled=editors.length>=MAX_PROPOSITIONS;}
    function load(value){
      editorsBox.replaceChildren();editors.length=0;
      for(const p of value.propositions.slice(0,MAX_PROPOSITIONS))fillOne(makeEditor(),p);
      loadedSegments=value.segments.map(s=>({source:copy(s.source),role:s.role}));
      loadedResidual=value.segments.some(s=>s.role==='unsupported')?'yes':'no';residual.value=loadedResidual;updateAdd();
    }
    // Any edit, addition or load clears earlier decisions, attestations and previews; nothing stale stays hidden.
    function invalidate(){preview=null;generation++;if(blind)showReview();}
    form.addEventListener('input',invalidate);form.addEventListener('change',invalidate);
    add.addEventListener('click',()=>{if(editors.length>=MAX_PROPOSITIONS)return;makeEditor();updateAdd();invalidate();status.textContent=`Added proposition ${editors.length}. Earlier decisions and previews were cleared.`;});
    const controls=el('div'), candidates=el('section'), decisions=el('section');root.append(controls,candidates,decisions);
    async function run(button,work){button.disabled=true;status.textContent='Checking the exact source and current state…';try{const note=await work();status.textContent=note||'Saved. No financial or external action was authorized.';}catch(e){status.textContent=e.message+(STALE.test(e.message)?' Refresh the page to review the current original source.':'');}finally{button.disabled=false;if(button===model)updateRequest();}}
    function button(label,handler){const b=el('button',label);b.type='button';b.addEventListener('click',()=>run(b,handler));return b;}
    const save=button('Save independent reading',async()=>{const interpretation=annotation();await api(base+'/blind-entry',{context_digest:context.digest,interpretation});blind=interpretation;
      if(jobInfo){const latest=await api(base);if(latest.context.digest!==context.digest)throw new Error('The original source changed. Refresh the page to review the current original source.');jobInfo=latest.model_job||jobInfo;job=jobInfo.job||job;showPermission();}
      showReview();save.hidden=true;showJob();if(job&&!job.terminal)poll();});controls.append(save);
    const model=button('Request interpretation',async()=>{
      if(jobInfo){job=await api(base+'/model-jobs',{context_digest:context.digest});showJob();poll();return 'Request recorded. Nothing is applied until you review it.';}
      await api(base+'/candidates/model',{context_digest:context.digest});const latest=await api(base);showCandidates(latest.candidates);});
    const requestNote=el('p','','interpretation-note'); requestNote.id='interpretation-request-reason'; model.setAttribute('aria-describedby',requestNote.id);
    const jobState=el('p',''); jobState.setAttribute('aria-live','polite');
    const refresh=el('button','Refresh request status'); refresh.type='button'; refresh.hidden=true;
    refresh.addEventListener('click',async()=>{if(!job||polling)return;refresh.disabled=true;try{job=await api(base+'/model-jobs/'+encodeURIComponent(job.id));showJob();if(job.state==='SUCCEEDED'||job.state==='UNCERTAIN')await loadCandidates();else if(!job.terminal)poll();}catch(e){jobState.textContent=e.message+' Refresh the original source before continuing.';}finally{refresh.disabled=false;}});
    controls.append(model,requestNote,jobState,refresh);model.hidden=true;
    if(jobInfo){controls.append(button('Refresh request permission',async()=>{
      const latest=await api(base);if(latest.context.digest!==context.digest)throw new Error('The original source changed. Refresh the page.');
      jobInfo=latest.model_job;job=jobInfo?.job||job;showPermission();showJob();
      return jobInfo?.message||'Permission status unavailable.';
    }));}
    function updateRequest(){
      if(!jobInfo){model.hidden=!blind||!data.model_enabled;requestNote.hidden=true;return;}
      model.hidden=!blind;model.disabled=!jobInfo.can_request||!!job;
      requestNote.textContent=job?'A request for this exact source already exists. It is never sent again automatically.':(jobInfo.message||'Permission status unavailable.');
    }
    function showJob(){refresh.hidden=!job;jobState.textContent=job?`Request ${job.id}: ${JOB_TEXT[job.state]||JOB_TEXT.UNCERTAIN}`:'';updateRequest();}
    const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
    async function loadCandidates(){
      const latest=await api(base);
      if(latest.context.digest!==context.digest){jobState.textContent='The original source changed. Refresh the page to review the current original source.';return;}
      if(latest.model_job){jobInfo=latest.model_job;showPermission();}
      showCandidates(latest.candidates);updateRequest();
    }
    async function poll(){
      if(polling||!job)return;polling=true;
      try{
        for(let i=0;i<maxPolls&&!job.terminal;i++){await sleep(pollMs);job=await api(base+'/model-jobs/'+encodeURIComponent(job.id));showJob();}
        if(job.state==='SUCCEEDED'||job.state==='UNCERTAIN')await loadCandidates();
        else if(!job.terminal)jobState.textContent+=' Still pending after the status check limit; use Refresh request status.';
      }catch(e){jobState.textContent=e.message+' Refresh the original source before continuing.';}
      finally{polling=false;}
    }
    function showCandidates(list){rows=list;candidates.replaceChildren(el('h2','Untrusted suggestions'));for(const candidate of list){const box=el('details');box.append(el('summary',candidate.origin==='model'?'Requested interpretation — requires your review':'Saved manual suggestion'));
      box.append(el('p',reviewed.has(candidate.id)?'State: reviewed by you; preview only':'State: proposed; not reviewed'));
      if(candidate.provenance?.request_sha256)box.append(el('p','Request reference '+candidate.provenance.request_sha256,'interpretation-meta'));
      const count=candidate.interpretation.propositions.length;
      if(count>1)box.append(el('p',`${count} separate propositions. Each needs its own decision; they are never combined or copied into your reading unless you load them.`));
      for(const [index,p] of candidate.interpretation.propositions.entries()){
        if(count>1)box.append(el('p',`Suggested proposition ${index+1} of ${count}`,'interpretation-meta'));
        box.append(el('p',`${p.family} · ${p.polarity} · ${p.modality} · ${p.referent}`),el('p','Source: '+where(p.source),'interpretation-meta'),el('blockquote',p.source.quote));for(const s of p.slots)box.append(el('p',`${s.name}: “${s.source.quote}” — ${where(s.source)}`));for(const c of p.conditions)box.append(el('p',`Condition: “${c.quote}” — ${where(c)}`));
        if(p.artifact_type)box.append(el('p','Document type: '+p.artifact_type));
        else if(p.family==='artifact')box.append(el('p','Document type not recorded. Reference-only matching can still be legitimate; check the original wording and choose a document type explicitly only if the source supports it.','interpretation-artifact-note'));
        if(p.scope_field)box.append(el('p','Incorrect scoped identifier: '+p.scope_field));
        if(p.filing_fields.length)box.append(el('p','Filing items: '+p.filing_fields.join('; ')));}
      for(const s of candidate.interpretation.segments){if(s.role==='unsupported')box.append(el('p','Unresolved content remains in review: '+where(s.source)));else if(s.role==='courtesy')box.append(el('p','Courtesy text: '+where(s.source)));}
      box.append(button('Compare this suggestion',async()=>{selected=candidate;showReview();}));
      // Explicit, reviewer-initiated copy into the editable draft. Nothing is accepted by loading.
      box.append(button('Load these propositions into your review draft',async()=>{selected=candidate;load(candidate.interpretation);invalidate();
        return `Loaded ${candidate.interpretation.propositions.length} proposition(s) into your review draft. Nothing is accepted; decide each proposition below.`;}));
      candidates.append(box);}}
    function describe(label,p){return el('p',p?`${label}: ${p.family} · ${p.polarity} · ${p.modality} · ${p.referent} · ${where(p.source)} · “${p.source.quote}”`:`${label}: none at this position`,'interpretation-alignment');}
    function showReview(){
      updateRequest();
      const mine=++generation;
      decisions.replaceChildren(el('h2','Reconcile and attest the meaning'),el('p','You may correct your reading above. Explain each changed proposition; any rejected proposition remains review-only. No automatic agreement is selected.'),
        el('p','Editing, adding or loading propositions clears these decisions, attestations and any earlier preview.','interpretation-note'));
      let draft=null, problem='';
      try{draft=annotation();}catch(e){problem=e.message;}
      const count=Math.max(blind.propositions.length,selected?selected.interpretation.propositions.length:0,editors.length), resolutions=[];
      for(let i=0;i<count;i++){const suffix=i===0?'':` (proposition ${i+1})`,box=el('fieldset');box.append(el('legend','Proposition '+(i+1)));
        box.append(describe('Your saved reading',blind.propositions[i]));
        if(selected)box.append(describe('Compared suggestion',selected.interpretation.propositions[i]));
        box.append(draft?describe('Review draft',draft.propositions[i]):el('p','Review draft: incomplete — '+problem,'interpretation-alignment'));
        if(draft&&i>=draft.propositions.length)box.append(el('p','This meaning is absent from your review draft; only “Reject; keep in human review” is accepted.'));
        const verdict=field(box,'Your decision'+suffix,[['accept','Accept unchanged meaning'],['correct','Correct the meaning with explanation'],['reject','Reject; keep in human review']]);const explanation=field(box,'Explanation of source meaning and any difference'+suffix);resolutions.push({i,verdict,explanation});decisions.append(box);}
      function check(label){const wrap=el('label',undefined,'interpretation-check'),input=el('input');input.type='checkbox';wrap.append(input,document.createTextNode(label));decisions.append(wrap);return input;}
      const full=check('I reviewed the complete original reply, including negation, conditions, attribution and claim identity.');
      const rest=check('I accounted for every additional objection or residual obligation; unresolved meaning remains review-only.');
      decisions.append(button('Save meaning review and inspect preview',async()=>{
        const body={context_digest:context.digest,interpretation:annotation(),candidate_id:selected?.id||null,resolutions:resolutions.map(r=>({proposition:r.i,verdict:r.verdict.value,explanation:r.explanation.value})),residuals_reviewed:rest.checked,complete_meaning_reviewed:full.checked};
        if(!full.checked||!rest.checked)throw new Error('Complete both source-review attestations.');
        const review=await api(base+'/reviews',body);const shown=await api(base+'/reviews/'+review.id+'/preview');
        if(mine!==generation)throw new Error('Your review draft changed while saving; decide each proposition again before inspecting a preview.');
        preview=shown;
        if(selected){reviewed.add(selected.id);showCandidates(rows);}
        const result=el('section');result.append(el('h2','Deterministic preview'),el('p',preview.disposition),el('p',preview.reported_award?'Interpreted reported award: USD '+preview.reported_award+'; no ledger entry.':'No awarded, posted or applied money changes.'));
        if('primary_proposition_index' in preview){
          const pi=preview.primary_proposition_index, reviewedProps=preview.reviewed_interpretation?.propositions||[];
          result.append(el('p',pi===null?'No proposition drives a deterministic disposition; the reply stays in human review.':`Primary proposition ${pi+1} (${reviewedProps[pi]?.family}) is the only input to the deterministic disposition.`));
          for(const r of preview.retained_propositions||[])result.append(el('p',`Retained proposition ${r.index+1}: ${r.family} · ${r.polarity} · ${r.modality} · ${r.referent} — informational only; no award, ledger or action effect.`));
        }
        if(preview.closure_suggested)result.append(el('p','The evidence supports a denial; closure remains a separate review decision.'));
        if(preview.prepare_allowed)result.append(button('Prepare evidence-backed response draft',async()=>{const changed=await api(base+'/prepare-response',{review_id:review.id,preview_digest:preview.digest});result.replaceChildren(el('h2','Draft prepared'),el('p',changed.stage+' · Existing exact approval and submission permissions still apply.'));}));
        else result.append(el('p','No response preparation is authorized by this preview.'));
        decisions.append(result);
      }));
    }
    updateRequest();showJob();
    if(blind){load(blind);save.hidden=true;showReview();showCandidates(data.candidates);if(job&&!job.terminal)poll();}
    else{makeEditor();updateAdd();}
  }
  global.UptimeInterpretation={mount,quoteSpan};
  const root=document.getElementById('interpretation-root');
  if(root){const claim=new URLSearchParams(location.search).get('claim')||'';root.replaceChildren(global.uptimeAuth.signInForm(()=>mount(root,global.uptimeAPI,claim).catch(e=>{root.textContent=e.message;})));}
})(window);
