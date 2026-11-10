/* How a contract was read: pure helpers for the Agreements page (demo line, November 10).
 * No network, no DOM. Everything here works only on what the server already sent: an agreement's source text and
 * its manifest citations, or a proposal job's clauses and the exact document that was submitted with it.
 * Loaded by v4_ui.js (require in Node, /static/contract_reading.js in the browser).
 */
(function (global) {
  'use strict';
  const MODEL_NAMES = {'claude-opus-5-5':'Claude Opus 5.5'};
  const list = value => Array.isArray(value) ? value : [];
  const words = value => String(value).replaceAll('_', ' ');
  const capital = text => text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
  // Attempt identifiers the workspace setup (setup_northwind.py --model-jobs) approves for each sample contract.
  // Each take is one live reading; a used take is never resent.
  const TAKES = ['retry-take1', 'retry-take2', 'retry-take3'];
  // The authored sample contracts of fixtures/submission_onboarding/, byte for byte (a test checks this).
  const SAMPLES = [
    {vendor_id:"corvid-ledger", fixture:"fixtures/submission_onboarding/corvid_ledger.json", document:{"name": "Corvid Ledger availability commitment (authored)", "uri": "urn:synthetic:submission:corvid-ledger-sla", "classification": "synthetic_public", "text": "The service provider under this agreement is Corvid Data Cooperative.\nThis contract is identified as CDC-SLA-07.\nThis service level agreement is valid from 2026-03-01 through 2027-02-28.\nAvailability is measured over each full calendar month in UTC.\nThe availability commitment covers the Corvid Ledger product on the Archive plan.\n| Monthly availability below | Service credit |\n| --- | --- |\n| 99.9% | 5% |\n| 99% | 20% |\nCredit requests must be received within 45 calendar days after the end of each calendar month.\nCredits are calculated as a percentage of the affected monthly fees and are applied to a future invoice."}},
    {vendor_id:"halden-relay", fixture:"fixtures/submission_onboarding/halden_relay.json", document:{"name": "Halden Relay Service Level Agreement (authored)", "uri": "urn:synthetic:submission:halden-relay-sla", "classification": "synthetic_public", "text": "Halden Relay Service Level Agreement\nHalden Systems provides Halden Relay on the Harbor plan.\nThis service level agreement is effective from 2026-01-01 through 2026-12-31.\nWe calculate availability for full calendar months using UTC.\n| Monthly availability below | Service credit |\n| --- | --- |\n| 99.95% | 10% |\n| 99.5% | 25% |\n| 98% | 50% |\nA claim must be submitted within 30 calendar days following month end.\nThe credit is calculated from the affected monthly service fees and credited to your next invoice."}},
    {vendor_id:"halden-relay-control", fixture:"fixtures/submission_onboarding/halden_relay_control.json", document:{"name": "Halden Relay control with conflicting and excluded terms (authored)", "uri": "urn:synthetic:submission:halden-relay-control", "classification": "synthetic_public", "text": "Halden Relay Service Level Agreement\nHalden Systems provides Halden Relay on the Harbor plan.\nThis service level agreement is effective from 2026-01-01 through 2026-12-31.\nWe calculate availability for full calendar months using UTC.\n| Monthly availability below | Service credit |\n| --- | --- |\n| 99.95% | 10% |\n| 99.5% | 25% |\n| 98% | 50% |\nA claim must be submitted within 30 calendar days following month end.\nClaims must be received within 10 calendar days after month end.\nDowntime caused by scheduled maintenance announced 72 hours in advance is excluded.\nThe credit is calculated from the affected monthly service fees and credited to your next invoice."}}
  ];

  // Who or what read an agreement, from its extraction record only. Nothing is guessed.
  function readingSummary(detail) {
    const d = detail && typeof detail === 'object' ? detail : {};
    const e = d.extraction && typeof d.extraction === 'object' ? d.extraction : {};
    const kind = e.method === 'tool_free_model_propositions' ? 'model' : e.method === 'deterministic_document_parser' ? 'rules' : null;
    const approver = typeof d.interpretation_reviewer === 'string' && d.interpretation_reviewer ? d.interpretation_reviewer
      : typeof d.reviewer === 'string' && d.reviewer ? d.reviewer : null;
    return {kind, model:kind === 'model' && typeof e.model === 'string' ? e.model : null,
      modelName:kind === 'model' ? MODEL_NAMES[e.model] || null : null,
      recordedAt:typeof e.at === 'string' && e.at ? e.at : null, session:typeof e.session === 'string' ? e.session : null,
      approver, approverKind:typeof d.reviewer_kind === 'string' ? d.reviewer_kind : null,
      interpretationAccepted:typeof d.interpretation_reviewer === 'string' && d.interpretation_reviewer !== ''};
  }

  // The label of one extracted term: the proposition names of a model citation, or the field name of a rules citation.
  function termLabel(field, propositions) {
    if (propositions && typeof propositions === 'object' && !Array.isArray(propositions)) {
      const keys = Object.keys(propositions);
      if (keys.length === 1 && keys[0] === 'nonmaterial') return 'Not a term: ' + String(propositions.nonmaterial);
      if (keys.length) return capital(keys.map(words).join(', '));
    }
    return typeof field === 'string' && field ? capital(words(field)) : 'Unlabelled';
  }

  // Terms of an installed agreement: one per manifest citation, with its recorded position and, where the server
  // sent one, its extracted value (the citation's propositions, or the manifest field the citation names).
  function termsFromRecord(detail) {
    const d = detail && typeof detail === 'object' ? detail : {};
    const manifest = d.manifest && typeof d.manifest === 'object' ? d.manifest : {};
    return list(manifest.citations).filter(c => c && typeof c === 'object' && typeof c.quote === 'string' && c.quote).map((c, i) => {
      const props = c.propositions && typeof c.propositions === 'object' ? c.propositions : null;
      const nonmaterial = !!props && Object.keys(props).length === 1 && 'nonmaterial' in props;
      let value = null;
      if (props && !nonmaterial) value = props;
      else if (!props && typeof c.field === 'string' && c.field !== 'heading' && manifest[c.field] !== undefined) value = manifest[c.field];
      return {id:c.id ?? i + 1, label:termLabel(c.field, props), quote:c.quote, value, nonmaterial,
        start:Number.isSafeInteger(c.start) ? c.start : null, end:Number.isSafeInteger(c.end) ? c.end : null};
    });
  }

  // Terms of a proposal job: its validated clauses, in the order the server returned them. No positions are sent.
  function termsFromProposal(job) {
    const p = job && typeof job === 'object' && job.proposal && typeof job.proposal === 'object' ? job.proposal : {};
    return list(p.clauses).filter(c => c && typeof c === 'object' && typeof c.quote === 'string' && c.quote).map((c, i) => ({
      id:i + 1, label:termLabel(c.field, null), quote:c.quote, value:c.value === undefined ? null : c.value,
      nonmaterial:c.value === null || c.value === undefined, start:null, end:null}));
  }

  // Ties each term to its sentence in the source text. A recorded position is used when the text there is exactly the
  // quote; otherwise the quote is searched for word for word (a repeated quote takes its next unused occurrence).
  function linkTerms(text, terms) {
    const source = typeof text === 'string' ? text : '';
    const used = new Map();
    return list(terms).map(term => {
      const quote = typeof term.quote === 'string' ? term.quote : '';
      if (quote && term.start !== null && term.end !== null && source.slice(term.start, term.end) === quote) {
        if (term.end > (used.get(quote) ?? 0)) used.set(quote, term.end);
        return {id:term.id, start:term.start, end:term.end, match:'recorded'};
      }
      const from = used.get(quote) ?? 0;
      let at = quote ? source.indexOf(quote, from) : -1;
      if (at < 0 && from > 0) at = source.indexOf(quote);
      if (at < 0) return {id:term.id, start:null, end:null, match:'missing'};
      used.set(quote, at + quote.length);
      return {id:term.id, start:at, end:at + quote.length, match:term.start !== null ? 'moved' : 'found'};
    });
  }

  // How many quotes appear word for word in the source; "all" only when every one does.
  function verbatim(links) {
    const rows = list(links);
    const found = rows.filter(l => l.match !== 'missing').length;
    const atRecorded = rows.filter(l => l.match === 'recorded').length;
    return {total:rows.length, found, atRecorded, all:rows.length > 0 && found === rows.length};
  }

  // The source text cut at every term boundary; each piece names the terms that cover it.
  function segments(text, links) {
    const source = typeof text === 'string' ? text : '';
    const spans = list(links).filter(l => l.start !== null && l.end !== null && l.end > l.start);
    const cuts = [...new Set([0, source.length, ...spans.flatMap(l => [l.start, l.end])])].filter(n => n >= 0 && n <= source.length).sort((a, b) => a - b);
    const out = [];
    for (let i = 0; i < cuts.length - 1; i++) {
      const a = cuts[i], b = cuts[i + 1];
      out.push({text:source.slice(a, b), start:a, ids:spans.filter(l => l.start <= a && l.end >= b).map(l => l.id)});
    }
    return out;
  }

  // Replay order: the terms whose sentences were found, in reading order (position in the source, then id).
  function replayOrder(links) {
    return list(links).filter(l => l.start !== null).slice()
      .sort((a, b) => a.start - b.start || a.end - b.end || String(a.id).localeCompare(String(b.id), undefined, {numeric:true}))
      .map(l => l.id);
  }

  // A proposal job's state in plain words: submitted, started, finished, or failed with its reason.
  const FAILURES = {provider_failed:'the model call failed', provider_identity_unverified:'the model that answered could not be verified',
    provider_timeout:'the model did not finish within the allowed time', provider_outcome_unknown:'the model outcome could not be confirmed',
    approval_unavailable_before_dispatch:'the operator approval was no longer available', restart_before_dispatch:'the server restarted before the call',
    restart_after_dispatch:'the server restarted during the call', disabled_before_dispatch:'model jobs were switched off before the call',
    dispatch_unavailable:'the job could not be dispatched'};
  function jobStateWords(job) {
    const j = job && typeof job === 'object' ? job : {};
    const reason = typeof j.reason === 'string' && j.reason ? j.reason : null;
    switch (j.status) {
      case 'QUEUED': return {word:'Submitted', tone:'accent', terminal:false};
      case 'RUNNING': return {word:'Started: Claude is reading the contract', tone:'accent', terminal:false};
      case 'SUCCEEDED': return {word:'Finished: every quote was checked against the source and the reading passed validation', tone:'ok', terminal:true};
      case 'REFUSED':
        if (reason === 'proposal_validation_failed') return {word:'Finished: validation refused this reading', tone:'bad', terminal:true};
        return {word:'Failed: ' + (FAILURES[reason] || (reason ? words(reason) : 'no reason returned')), tone:'bad', terminal:true};
      case 'CANCELLED': case 'UNCERTAIN':
        return {word:'Failed: ' + (FAILURES[reason] || (reason ? words(reason) : j.status.toLowerCase())), tone:'warn', terminal:true};
      default: return {word:'Unrecognised job state', tone:'warn', terminal:true};
    }
  }

  // What a selection answer means for one take of a live reading.
  function takeState(answer) {
    const a = answer && typeof answer === 'object' ? answer : {};
    const selected = a.selected && typeof a.selected === 'object' ? a.selected : null;
    if (a.outcome === 'NOT_SUBMITTED') return 'fresh';
    if (a.outcome === 'PENDING') return 'running';
    if (a.outcome === 'APPROVAL_REQUIRED') return 'not_approved';
    if (a.outcome === 'PROVIDER_UNCONFIGURED') return 'unconfigured';
    if (a.outcome === 'SELECTED' && selected && selected.method === 'deterministic_document_parser') return 'fixed_rules';
    return typeof a.outcome === 'string' ? 'used' : 'unknown';
  }

  const api = Object.freeze({MODEL_NAMES, TAKES, SAMPLES, readingSummary, termLabel, termsFromRecord, termsFromProposal,
    linkTerms, verbatim, segments, replayOrder, jobStateWords, takeState});
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (global) global.UptimeContractReading = api;
})(typeof window !== 'undefined' ? window : globalThis);
