// Demo line (November 10, 2026): the case page of a claim for a contract an approved template read.
// The page is the recovery page itself (UptimeWorkspace.create) over this case's own routes, with one more card that
// says how the contract was read. Every figure, stage, step and decision is the server's; nothing is computed here.
(function (global) {
  const text = value => value == null ? '' : String(value);
  const given = value => typeof value === 'string' && value !== '';
  const short = value => given(value) && value.length > 16 ? value.slice(0, 12) + '…' : text(value);

  // "How this contract was read": fixed rules from an approved template that Claude agents built. Code is never
  // called an agent: the template's rules read the contract, Claude agents wrote the rules, a reviewer approved them.
  function readingLines(reading) {
    const r = reading && typeof reading === 'object' ? reading : {};
    const lines = [];
    lines.push('Read by fixed rules: approved template ' + text(r.template_id || 'not named') + (given(r.template_sha256) ? ' (SHA-256 ' + short(r.template_sha256) + ')' : '')
      + (r.model_calls === 0 ? ', with no model call.' : '.'));
    lines.push('Template built by ' + text(r.built_by || 'Claude agents') + (given(r.approved_by) ? ', approved by the reviewer account ' + r.approved_by : ', approval account not reported') + '.');
    if (given(r.reading_id)) lines.push('Reading ' + r.reading_id + (given(r.read_at) ? ' at ' + r.read_at : '') + '.');
    const terms = termsLine(r.values);
    if (terms) lines.push(terms);
    return lines;
  }

  // The read terms in words (version 3 shapes: a schedule of tiers, durations with the contract's own unit).
  const UNITS = {days: ['day', 'days'], business_days: ['business day', 'business days'], months: ['month', 'months'], hours: ['hour', 'hours']};
  const duration = d => d && typeof d === 'object' && given(d.value) && UNITS[d.unit] ? d.value + ' ' + UNITS[d.unit][d.value === '1' ? 0 : 1] : null;
  function termsLine(values) {
    const v = values && typeof values === 'object' ? values : null;
    if (!v) return null;
    const parts = [];
    if (given(v.availability_target_percent)) parts.push('commitment ' + v.availability_target_percent + '%');
    if (Array.isArray(v.credit_schedule)) v.credit_schedule.filter(t => t && typeof t === 'object').forEach(t =>
      parts.push('below ' + (t.below_percent === 'commitment' ? 'the commitment' : text(t.below_percent) + '%') + ': ' + text(t.credit_percent) + '% credit'));
    if (given(v.credit_cap_percent)) parts.push('cap ' + v.credit_cap_percent + '%');
    if (duration(v.claim_window)) parts.push('claim within ' + duration(v.claim_window));
    if (duration(v.maintenance_notice)) parts.push('maintenance notice ' + duration(v.maintenance_notice));
    return parts.length ? 'Terms read: ' + parts.join('; ') + '.' : null;
  }

  function readingCard(data, doc) {
    const reading = data && data.reading;
    if (!reading || typeof reading !== 'object') return null;
    const el = (tag, value, cls) => { const n = doc.createElement(tag); if (value != null) n.textContent = text(value); if (cls) n.className = cls; return n; };
    const node = el('section', null, 'panel template-claim-reading');
    node.setAttribute('aria-label', 'How this contract was read');
    const head = el('div', null, 'panel-head');
    head.append(el('h2', 'How this contract was read'), el('span', 'Fixed rules', 'pill tag-agent'));
    node.append(head);
    readingLines(reading).forEach(line => node.append(el('p', line, 'help')));
    if (data.reading_current === false) node.append(el('p', 'A newer reading of this contract exists. This claim stays bound to the reading above.', 'help'));
    const builder = el('a', 'Open the template build', 'case-link');
    builder.href = '#template-build/' + encodeURIComponent(text(reading.build_id));
    const back = el('p', null, 'help recovery-links'); back.append(builder); node.append(back);
    return node;
  }

  // One page per case: the recovery page's components over /api/template-claims/<document id>.
  function create({api, document: doc = global.document, onUnauthorized, canAct = () => true, workspace = global.UptimeWorkspace}) {
    let page = null;
    async function render(root, caseId) {
      const base = '/api/template-claims/' + encodeURIComponent(caseId);
      page = workspace.create({api, document: doc, onUnauthorized, canAct, viewPath: base, actionPath: base + '/actions/',
        guide: false, caseLinks: false, decorate: data => readingCard(data, doc)});
      await page.render(root);
    }
    return {render, unmount: () => { if (page) page.unmount(); page = null; }};
  }

  const exports = {create, readingCard, readingLines, termsLine};
  if (typeof module !== 'undefined' && module.exports) module.exports = exports;
  global.UptimeTemplateClaim = exports;
})(typeof window === 'undefined' ? globalThis : window);
