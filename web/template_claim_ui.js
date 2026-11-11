// Demo line (November 10, 2026): the case page of a claim for a contract an approved template read.
// The page is the recovery page itself (UptimeWorkspace.create) over this case's own routes, with one more card that
// says how the contract was read. Every figure, stage, step and decision is the server's; nothing is computed here.
(function (global) {
  const text = value => value == null ? '' : String(value);
  const given = value => typeof value === 'string' && value !== '';
  const short = value => given(value) && value.length > 16 ? value.slice(0, 12) + '…' : text(value);
  const percent = value => { const n = Number(value); return Number.isFinite(n) ? (Math.round(n * 1000) / 10) + '%' : text(value); };

  // "How this contract was read": fixed rules from an approved template that Claude agents built. Code is never
  // called an agent: the template's rules read the contract, Claude agents wrote the rules, a reviewer approved them.
  function readingLines(reading) {
    const r = reading && typeof reading === 'object' ? reading : {};
    const lines = [];
    lines.push('Values read by fixed rules: approved template ' + text(r.template_id || 'not named') + (given(r.template_sha256) ? ' (SHA-256 ' + short(r.template_sha256) + ')' : '')
      + (r.model_calls === 0 ? '. No model read or computed a value.' : '.'));
    // Jev is a model: what it was asked about this document is said separately, from the reading's own record.
    const jev = r.jev_template && typeof r.jev_template === 'object' ? r.jev_template : null;
    if (jev && jev.asked && given(jev.probability)) lines.push('Jev confirmed the document follows the template at ' + percent(jev.probability)
      + (given(jev.model) ? ' (' + jev.model + ')' : '') + '. No Claude call took part in the read.');
    else if (jev && jev.asked === false) lines.push('Jev was not asked whether the document follows the template. No Claude call took part in the read.');
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

  // The template builder's agreement card follows the case once a claim exists: one credit, shown at the case's
  // latest recorded stage and amount; with no case (or the case not yet opened) the card is left exactly as drawn.
  function cardFollows(summary) {
    const s = summary && typeof summary === 'object' ? summary : null;
    if (!s || s.claim_state === 'NOT_OPENED' || !given(s.label) || !given(s.amount)) return null;
    return {label: 'Credit', amount: s.amount, currency: s.currency || 'USD', stage: 'Claim stage: ' + s.label,
      foot: 'Computed by Uptime’s credit engine, not by a model. Its claim is at stage “' + s.label + '” in its case.'};
  }
  function money(value, currency) {
    const n = Number(value);
    if (!Number.isFinite(n)) return text(value);
    return (currency === 'USD' ? '$' : currency + ' ') + n.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  }
  async function followCard({api, caseId, figureLabel, amountNode, stageNode, footNote}) {
    let answer;
    try { answer = await api('/api/template-claims'); } catch (_) { return null; }  // unreadable: the card stays as drawn
    const summary = (answer && Array.isArray(answer.claims) ? answer.claims : []).find(c => c && c.case_id === caseId);
    const shown = cardFollows(summary);
    if (!shown) return null;
    figureLabel.textContent = shown.label; amountNode.textContent = money(shown.amount, shown.currency);
    stageNode.textContent = shown.stage; footNote.textContent = shown.foot;
    return shown;
  }

  // Cases and Activity list the template claim cases beside the workspace's own, each labelled with its vendor.
  async function listed(api) {
    try { const answer = await api('/api/template-claims'); return (answer && Array.isArray(answer.claims) ? answer.claims : []).filter(c => c && c.claim_state && c.claim_state !== 'NOT_OPENED'); }
    catch (_) { return []; }
  }
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const monthName = m => given(m) && /^\d{4}-\d{2}$/.test(m) ? MONTHS[Number(m.slice(5)) - 1] + ' ' + m.slice(0, 4) : text(m);

  function casesSection(claims, doc) {
    if (!claims.length) return null;
    const el = (tag, value, cls) => { const n = doc.createElement(tag); if (value != null) n.textContent = text(value); if (cls) n.className = cls; return n; };
    const node = el('section', null, 'panel template-claim-cases');
    node.append(el('h2', 'Claims for contracts read by an approved template'));
    const rows = el('ol', null, 'attention-list');
    claims.forEach(c => {
      const link = el('a', 'Open the case', 'case-link'); link.href = c.href;
      const item = el('li', null, 'attention-item');
      item.append(el('span', text(c.vendor), 'attention-owner'), el('h3', text(c.vendor) + ' · ' + monthName(c.month) + ' service credit · ' + text(c.claim_id)),
        el('p', 'Claim stage ' + text(c.claim_state).replaceAll('_', ' ').toLowerCase() + ' · credit ' + text(c.label) + ' · ' + money(c.amount, c.currency || 'USD'), 'help'), link);
      rows.append(item);
    });
    node.append(rows);
    return node;
  }

  function create({api, document: doc = global.document, onUnauthorized, canAct = () => true, workspace = global.UptimeWorkspace}) {
    let page = null;
    const pageFor = caseId => {
      const base = '/api/template-claims/' + encodeURIComponent(caseId);
      return workspace.create({api, document: doc, onUnauthorized, canAct, viewPath: base, actionPath: base + '/actions/',
        guide: false, caseLinks: false, decorate: data => readingCard(data, doc)});
    };
    async function render(root, caseId) {
      page = pageFor(caseId);
      await page.render(root);
    }
    async function cases(root) {
      const section = casesSection(await listed(api), doc);
      if (section) root.append(section);
    }
    async function activity(root) {
      for (const c of await listed(api)) {
        const answer = await api('/api/template-claims/' + encodeURIComponent(c.case_id));
        if (answer && answer.workflow) root.append(pageFor(c.case_id).activitySection(answer.workflow, text(c.vendor) + ' · ' + monthName(c.month) + ' claim'));
      }
    }
    return {render, cases, activity, unmount: () => { if (page) page.unmount(); page = null; }};
  }

  const exports = {create, readingCard, readingLines, termsLine, cardFollows, followCard, casesSection};
  if (typeof module !== 'undefined' && module.exports) module.exports = exports;
  global.UptimeTemplateClaim = exports;
})(typeof window === 'undefined' ? globalThis : window);
