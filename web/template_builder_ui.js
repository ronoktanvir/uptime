/* Template builder (docs/demo/TEMPLATE-BUILDER.md, including "Version 2"): a section on the Agreements page for a
 * contract type Uptime has not read before (a shipped sample or a pasted contract), and the page #template-build/<id>
 * that draws one run from the server's `build` object alone.
 * Every figure on these pages comes from a `build` or `reading` object the server sent; the only thing computed here
 * is the elapsed time of a step that is still working, from its own `started_at`. Amounts are never computed here.
 * Only Claude and Jev are models. Uptime's interpreter, checks and guards are code and are named as such.
 */
(function (global) {
  'use strict';
  const list = value => Array.isArray(value) ? value : [];
  const object = value => value && typeof value === 'object' && !Array.isArray(value) ? value : null;
  const given = value => typeof value === 'string' ? value !== '' : typeof value === 'number' && Number.isFinite(value);
  const ACTORS = {JEV:'Jev', CLAUDE:'Claude', UPTIME:'Uptime · fixed rules', REVIEWER:'Reviewer'};
  const CHECK_BY = {UPTIME:'Uptime’s code', JEV:'Jev'};
  const BUILD_STATES = {QUEUED:'Starting', CLASSIFYING:'Jev is deciding the contract type', READING:'Claude readers are reading the contract',
    BUILDING:'Claude is writing the template', CHECKING:'Uptime is checking the template', READY_FOR_REVIEW:'Ready for a reviewer',
    APPROVED:'Approved', FAILED:'Failed', MATCHED:'Read by an approved template', NEEDS_REVIEWER:'Waiting for a reviewer’s decision'};
  const BUILD_TONES = {READY_FOR_REVIEW:'warn', APPROVED:'ok', FAILED:'bad', MATCHED:'ok', NEEDS_REVIEWER:'warn'};
  const TERMINAL = ['READY_FOR_REVIEW', 'APPROVED', 'FAILED', 'MATCHED', 'NEEDS_REVIEWER'];
  const POLL_MS = 700;
  // The three readers differ in their instructions (Version 2); the role is the server's `detail.role`.
  const ROLES = {clause_by_clause:'Reads clause by clause', numbers_first:'Lists every number first', sceptic:'Looks for a conflicting second statement'};
  // The checks in the interface page's order; a check the page does not know is drawn after these.
  const CHECK_ORDER = ['quotes', 'value_in_sentence', 'agreement', 'reproduce', 'second_document', 'jev'];
  // The run's stages, in order; the server always sends these seven step ids.
  const STAGES = [['Decide the contract type', ['classify']], ['Read the contract three different ways', ['reader-1', 'reader-2', 'reader-3']],
    ['Write the template', ['build']], ['Check the template', ['checks']], ['Approve this version', ['review']]];
  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const MONTH_NAMES = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  const INSTANT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/;
  function instant(value) {
    if (typeof value !== 'string' || !INSTANT.test(value)) return given(value) ? String(value) : null;
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}, ${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')} UTC`;
  }
  // "2026-10" as "October 2026"; anything else is shown as sent.
  function monthLabel(value) {
    const m = /^(\d{4})-(\d{2})$/.exec(String(value ?? ''));
    return m && Number(m[2]) >= 1 && Number(m[2]) <= 12 ? MONTH_NAMES[Number(m[2]) - 1] + ' ' + m[1] : given(value) ? String(value) : null;
  }
  // A decimal string probability ("0.975") as a percentage ("97.5%"), shifted as text so nothing is rounded.
  function percent(value) {
    const m = /^(\d+)(?:\.(\d*))?$/.exec(String(value ?? ''));
    if (!m) return null;
    const fraction = (m[2] || '').padEnd(2, '0');
    const whole = (m[1] + fraction.slice(0, 2)).replace(/^0+(?=\d)/, '');
    const rest = fraction.slice(2).replace(/0+$/, '');
    return whole + (rest ? '.' + rest : '') + '%';
  }
  const thousands = n => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  // A decimal money string as sent ("2000.00") with digit grouping; the digits themselves are never changed.
  function money(amount, currency) {
    const m = /^(-?)(\d+)(\.\d+)?$/.exec(String(amount ?? ''));
    if (!m) return null;
    const figure = m[1] + thousands(m[2]) + (m[3] || '');
    return currency === 'USD' ? (m[1] ? '-$' + figure.slice(1) : '$' + figure) : figure + (given(currency) ? ' ' + currency : '');
  }
  // A term's value with its unit, from the term's own type or field name; the value text is shown as sent.
  function withUnit(term, value) {
    if (value === null || value === undefined || value === '') return null;
    const t = object(term) || {}, field = String(t.field || ''), type = String(t.type || '');
    if (type === 'percent' || field.endsWith('_percent')) return value + '%';
    if (type === 'days' || field.endsWith('_days')) return value + (String(value) === '1' ? ' day' : ' days');
    if (type === 'hours' || field.endsWith('_hours')) return value + (String(value) === '1' ? ' hour' : ' hours');
    return String(value);
  }
  // `read_by` worded for a person: "template:<id>" is the approved template run by fixed rules.
  function readByWords(value) {
    if (typeof value !== 'string' || !value) return null;
    if (value.startsWith('template:')) return 'Fixed rules · template ' + value.slice(9);
    if (value === 'TEMPLATE') return 'Fixed rules';
    return value;
  }
  const actorName = actor => ACTORS[actor] || (given(actor) ? String(actor) : 'Not named');
  // A step's state in words. A working step counts up from its own started_at.
  function stepState(step, nowMs) {
    const s = object(step) || {};
    switch (s.state) {
      case 'RUNNING': {
        const started = Date.parse(s.started_at);
        const seconds = Number.isNaN(started) ? null : Math.max(0, (nowMs - started) / 1000);
        return {word:'Working', tone:'accent', elapsed:seconds === null ? null : seconds.toFixed(1) + ' s', running:true};
      }
      case 'DONE': return {word:given(s.seconds) ? 'Done in ' + s.seconds + ' s' : 'Done', tone:'ok'};
      case 'FAILED': return {word:'Failed', tone:'bad'};
      case 'SKIPPED': return {word:'Not started', tone:''};
      case 'PENDING': return {word:'Waiting', tone:''};
      default: return {word:given(s.state) ? String(s.state).toLowerCase() : 'Waiting', tone:''};
    }
  }
  const jevCheck = build => list(object(build)?.checks).find(c => object(c) && (c.id === 'jev' || c.by === 'JEV')) || null;
  // Jev's figures are shown only when Jev really answered.
  const jevRan = build => { const c = jevCheck(build); return !(c && c.ran === false); };
  // The blocking checks that failed; approval is refused while any is listed. A check that did not run is not a failure.
  const blockingFailures = build => list(object(build)?.checks).filter(c => object(c) && c.blocking === true && c.ok === false && c.ran !== false);
  // The checks in the interface page's order.
  function orderedChecks(checks) {
    const rank = c => { const i = CHECK_ORDER.indexOf(c.id); return i < 0 ? CHECK_ORDER.length : i; };
    return list(checks).filter(object).map((c, i) => [c, i]).sort((a, b) => rank(a[0]) - rank(b[0]) || a[1] - b[1]).map(([c]) => c);
  }
  // The terms the reviewer must acknowledge before approving (Jev did not support them, or did not answer).
  const needsAcknowledgement = build => list(object(build)?.terms).filter(t => object(t) && t.needs_acknowledgement === true);
  // Why the readers started, or did not, in one line for the Jev step.
  function routeLine(build) {
    const b = object(build) || {};
    const steps = list(b.steps).filter(object);
    const classify = steps.find(s => s.id === 'classify') || {};
    const readers = steps.filter(s => /^reader-/.test(String(s.id)));
    const started = readers.some(s => s.state && s.state !== 'PENDING' && s.state !== 'SKIPPED');
    const detail = object(classify.detail) || {};
    if (b.state === 'MATCHED') {
      const m = object(b.matched_template) || {};
      return 'Matched approved template ' + (given(m.id) ? m.id : 'on file') + (percent(m.probability) ? ' (' + percent(m.probability) + ')' : '') + ', so no reader started.';
    }
    if (b.state === 'NEEDS_REVIEWER') return null;
    if (!started) return null;
    if (classify.state === 'FAILED') {
      const decision = object(detail.reviewer_decision) || object(detail.decision);
      const by = decision && given(decision.by) ? decision.by : given(detail.decided_by) ? detail.decided_by : null;
      return 'Jev could not be reached; the readers started on a reviewer’s decision' + (by ? ' (' + by + ')' : '') + '.';
    }
    if (classify.state !== 'DONE') return null;
    if (detail.asked === false) return 'No approved template is on file, so Jev was not asked and the readers started.';
    if (detail.choice === 'unrecognised' || !given(detail.choice)) return 'No approved template matched, so the readers started.';
    return 'Jev’s closest template, ' + detail.choice + (percent(detail.probability) ? ' at ' + percent(detail.probability) : '') + ', was not a confident match, so the readers started.';
  }
  const safePath = value => typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') ? value : null;
  function latestBuild(builds, sampleId) {
    return list(builds).filter(b => object(b) && b.sample_id === sampleId)
      .sort((a, b) => String(b.started_at || '').localeCompare(String(a.started_at || '')))[0] || null;
  }
  function readingLine(reading) {
    const r = object(reading) || {}, t = object(r.template) || {};
    const jevType = object(r.jev_template);
    const parts = [r.read_by === 'TEMPLATE' && r.model_calls === 0 && jevType ? 'Values by fixed rules · Jev checked the document type'
      : r.read_by === 'TEMPLATE' ? 'Read by fixed rules' : 'Read by ' + (given(r.read_by) ? String(r.read_by).toLowerCase() : 'an unnamed reader')];
    if (given(t.id)) parts.push('template ' + t.id);
    if (Number.isInteger(r.model_calls) && !jevType) parts.push(r.model_calls + (r.model_calls === 1 ? ' model call' : ' model calls'));
    if (given(r.milliseconds)) parts.push(r.milliseconds + ' ms');
    return parts.join(' · ');
  }

  function create(options = {}) {
    const doc = options.document || global.document;
    const api = options.api;
    const onNavigate = typeof options.onNavigate === 'function' ? options.onNavigate : () => {};
    // An expired session found by a timer or a click goes to the existing sign-in; nothing else is thrown from there.
    const unauthorized = error => { if (error && error.status === 401) { unmount(); if (typeof options.onUnauthorized === 'function') options.onUnauthorized(); return true; } return false; };
    const now = typeof options.now === 'function' ? options.now : () => Date.now();
    const later = options.setTimeout || ((fn, ms) => setTimeout(fn, ms));
    const cancel = options.clearTimeout || (id => clearTimeout(id));
    const every = options.setInterval || ((fn, ms) => setInterval(fn, ms));
    const stopEvery = options.clearInterval || (id => clearInterval(id));
    let mount = 0, pollTimer = null, ticker = null;

    function el(tag, className, text) {
      const node = doc.createElement(tag);
      if (className) node.className = className;
      if (text != null) node.textContent = String(text);
      return node;
    }
    function add(parent, ...children) { children.flat().filter(Boolean).forEach(child => parent.append(child)); return parent; }
    function button(label, handler, className) {
      const node = el('button', className || '', label); node.type = 'button';
      node.addEventListener('click', handler); return node;
    }
    const pill = (text, tone) => el('span', 'pill' + (tone ? ' ' + tone : ''), text);
    const errorSentence = (error, fallback) => error && error.message ? error.message : fallback;
    function input(className, kind) { const node = el(kind === 'textarea' ? 'textarea' : 'input', className); if (kind !== 'textarea') node.type = kind || 'text'; node.value = ''; return node; }
    function field(label, control, extra) { return add(el('label', 'tb-field'), el('span', 'tb-field-label', label), control, extra); }
    function checkbox(label, checked, onChange, className) {
      const box = el('input', ''); box.type = 'checkbox'; box.checked = !!checked;
      box.addEventListener('change', () => onChange(!!box.checked));
      return {box, node:add(el('label', 'tb-check-box' + (className ? ' ' + className : '')), box, el('span', '', label))};
    }
    function unmount() {
      mount++;
      if (pollTimer !== null) { cancel(pollTimer); pollTimer = null; }
      if (ticker !== null) { stopEvery(ticker); ticker = null; }
    }

    // ---- Agreements page: "A contract type Uptime has not read before" ----
    async function section(root) {
      const token = ++mount;
      let data;
      try { data = await api('/api/template-builds'); }
      catch (error) { if (error && error.status === 401) throw error; return null; }
      if (token !== mount || !object(data)) return null;
      const node = add(el('section', 'panel tb-section'),
        add(el('div', 'tb-section-head'), el('p', 'eyebrow', 'New contract type'), el('h2', '', 'A contract type Uptime has not read before'),
          el('p', 'help', 'Jev checks whether an approved template already reads the contract. If none does, three Claude readers read it in different ways and Claude writes a template; Uptime’s code checks it and a reviewer approves it before it reads anything.')));
      const enabled = data.enabled === true;
      if (!enabled) node.append(el('p', 'tb-reason', given(data.reason) ? data.reason : 'Template building is off on this server.'));
      const cards = el('div', 'tb-samples');
      list(data.samples).filter(object).forEach(sample => {
        const docu = object(sample.document) || {};
        const card = add(el('article', 'tb-sample'), el('p', 'eyebrow', given(sample.vendor) ? sample.vendor : 'Vendor not named'),
          el('h3', '', given(sample.title) ? sample.title : given(docu.title) ? docu.title : sample.id));
        const facts = el('p', 'help tb-sample-facts');
        if (Number.isInteger(docu.chars)) facts.append(el('span', '', thousands(docu.chars) + ' characters'));
        const href = safePath(docu.text_url);
        if (href) { const link = el('a', 'tb-text-link', 'Read the contract text'); link.href = href; link.target = '_blank'; link.rel = 'noopener'; facts.append(link); }
        card.append(facts);
        const template = list(data.templates).find(t => object(t) && t.sample_id === sample.id && t.state === 'APPROVED');
        if (template) card.append(el('p', 'tb-sample-template', 'Template ' + template.id + ' approved' + (given(template.approved_by) ? ' by ' + template.approved_by : '')));
        if (enabled) {
          const existing = latestBuild(data.builds, sample.id);
          const actions = el('div', 'actions');
          if (existing && given(existing.id)) {
            actions.append(button('Open the run', () => onNavigate('template-build/' + encodeURIComponent(existing.id)), 'tb-primary'),
              pill(BUILD_STATES[existing.state] || String(existing.state || ''), BUILD_TONES[existing.state] || 'accent'));
          } else {
            const said = el('p', 'help tb-said'); said.setAttribute('role', 'status');
            const start = button('Build a reader with Claude agents', async () => {
              start.disabled = true; said.textContent = '';
              try {
                const answer = await api('/api/template-builds', {sample_id:sample.id});
                const build = object(answer) && object(answer.build);
                if (!build || !given(build.id)) throw new Error('The server did not return a run.');
                onNavigate('template-build/' + encodeURIComponent(build.id));
              } catch (error) {
                if (unauthorized(error)) return;
                said.textContent = errorSentence(error, 'The run could not be started.');
                start.disabled = false;
              }
            }, 'tb-primary');
            actions.append(start);
            card.append(actions, said);
            cards.append(card); return;
          }
          card.append(actions);
        }
        cards.append(card);
      });
      if (cards.children.length) node.append(cards);
      if (enabled) node.append(pasteCard(data));
      const body = typeof root.querySelector === 'function' ? root.querySelector('.v4-body') : null;
      if (body && typeof body.prepend === 'function') body.prepend(node); else root.append(node);
      return node;
    }

    // "Paste a contract": the pasted shape of POST /api/template-builds. Nothing is sent before consent is ticked.
    function pasteCard(data) {
      const title = input('tb-input'), vendor = input('tb-input'), text = input('tb-textarea', 'textarea');
      const secondTitle = input('tb-input'), secondText = input('tb-textarea tb-textarea-small', 'textarea');
      text.rows = 10; secondText.rows = 6;
      title.placeholder = 'For example: Platform Availability Addendum'; vendor.placeholder = 'The vendor’s name';
      text.placeholder = 'Paste the full contract text here.'; secondText.placeholder = 'Paste a second contract of the same form.';
      const count = el('span', 'help tb-char-count', '');
      const consent = checkbox('I agree that this text will be sent to Claude and to Jev: Claude agents read it and write a template, and Jev decides its contract type and checks each term. It is stored only in this workspace.', false, () => update(), 'tb-consent');
      const said = el('p', 'help tb-said'); said.setAttribute('role', 'status');
      let busy = false;
      const start = button('Build a reader from this contract', async () => {
        if (start.disabled || busy) return;
        busy = true; update(); said.textContent = '';
        const second = String(secondText.value || '');
        const body = {contract:{title:String(title.value || '').trim(), vendor:String(vendor.value || '').trim(), text:String(text.value || '')},
          second_contract:second.trim() ? {title:String(secondTitle.value || '').trim(), text:second} : null, consent:true};
        try {
          const answer = await api('/api/template-builds', body);
          const build = object(answer) && object(answer.build);
          if (!build || !given(build.id)) throw new Error('The server did not return a run.');
          onNavigate('template-build/' + encodeURIComponent(build.id));
        } catch (error) {
          if (unauthorized(error)) return;
          said.textContent = errorSentence(error, 'The run could not be started.');
        }
        busy = false; update();
      }, 'tb-primary');
      const waiting = el('span', 'help tb-paste-wait', '');
      function update() {
        const hasText = String(text.value || '').trim() !== '';
        start.disabled = busy || !hasText || !consent.box.checked;
        count.textContent = hasText ? thousands(String(text.value).length) + ' characters' : '';
        waiting.textContent = busy ? '' : !hasText ? 'Paste the contract text to start.' : !consent.box.checked ? 'Tick the box above to send the text.' : '';
      }
      [title, vendor, text, secondTitle, secondText].forEach(control => control.addEventListener('input', update));
      const second = add(el('details', 'tb-second'), el('summary', '', 'Add a second contract of the same form (optional)'),
        el('p', 'help', 'With a second contract, three fresh Claude readers read it and the template must return what they agree on. Without one, the template is not checked on a second contract.'),
        field('Title of the second contract', secondTitle), field('Second contract text', secondText));
      const pasted = list(data.builds).filter(b => object(b) && given(b.id) && (object(b.source)?.kind === 'pasted' || (b.sample_id === null && object(b.source))))
        .sort((a, b) => String(b.started_at || '').localeCompare(String(a.started_at || ''))).slice(0, 3);
      const earlier = pasted.length ? add(el('div', 'tb-pasted'), el('p', 'tb-detail-label', 'Contracts pasted earlier'),
        pasted.map(b => add(el('div', 'tb-pasted-row'), el('span', 'tb-pasted-title', given(object(b.source)?.title) ? b.source.title : b.id),
          pill(BUILD_STATES[b.state] || String(b.state || ''), BUILD_TONES[b.state] || 'accent'),
          button('Open the run', () => onNavigate('template-build/' + encodeURIComponent(b.id)), 'link-button')))) : null;
      update();
      return add(el('article', 'tb-paste'),
        add(el('div', 'tb-paste-head'), el('p', 'eyebrow', 'Your own contract'), el('h3', '', 'Paste a contract'),
          el('p', 'help', 'A contract of a type Uptime has not read. Jev decides first whether an approved template already reads it.')),
        add(el('div', 'tb-paste-names'), field('Title', title), field('Vendor', vendor)),
        field('Contract text', text, count), second, consent.node,
        add(el('div', 'actions'), start, waiting), said, earlier);
    }

    // ---- #template-build/<id> ----
    async function run(root, id) {
      unmount();
      const token = mount;
      const view = {root, id, sample:null, build:null, drawn:null, open:new Set(), acks:new Set(), autoOpened:false, readings:new Map(),
        said:'', busy:false, clocks:[], draft:{title:'', vendor:'', text:'', consent:false}};
      root.replaceChildren(el('p', 'empty', 'Loading the run…'));
      try {
        const data = await api('/api/template-builds');
        if (token !== mount) return;
        view.samples = list(object(data)?.samples);
      } catch (error) { if (error && error.status === 401) throw error; view.samples = []; }
      const path = '/api/template-builds/' + encodeURIComponent(id);
      ticker = every(() => tick(view), 250);
      async function poll() {
        pollTimer = null;
        if (token !== mount) return;
        let build;
        try {
          const answer = await api(path);
          build = object(answer) && object(answer.build);
          if (!build) throw new Error('The server did not return this run.');
        } catch (error) {
          if (token !== mount) return;
          if (error && error.status === 401) { if (!view.build) { unmount(); throw error; } unauthorized(error); return; }
          if (!view.build) { root.replaceChildren(failurePanel(errorSentence(error, 'This run could not be read.'))); unmount(); return; }
          pollTimer = later(() => poll().catch(() => {}), POLL_MS * 3);
          return;
        }
        if (token !== mount) return;
        draw(view, build);
        follow(build);
      }
      function follow(build) {
        if (!TERMINAL.includes(build.state)) {
          if (pollTimer === null) pollTimer = later(() => poll().catch(() => {}), POLL_MS);
          if (ticker === null) ticker = every(() => tick(view), 250);
        } else if (ticker !== null) { tick(view); stopEvery(ticker); ticker = null; }
      }
      // After "Build without Jev" the run moves again, so polling resumes from the answer.
      view.follow = build => { if (token === mount) follow(build); };
      await poll();
      return view;
    }
    function failurePanel(sentence) {
      return add(el('section', 'panel error'), el('h2', '', 'This run could not be shown'), el('p', '', sentence),
        button('Back to Agreements', () => onNavigate('agreements'), 'quiet'));
    }
    function tick(view) { const t = now(); view.clocks.forEach(c => { const s = Math.max(0, (t - c.started) / 1000); c.node.textContent = s.toFixed(1) + ' s'; }); }

    function draw(view, build, force) {
      const json = JSON.stringify(build);
      if (!force && json === view.drawn) return;
      view.drawn = json; view.build = build; view.clocks = [];
      view.sample = view.samples.find(s => object(s) && s.id === build.sample_id) || null;
      // A term the reviewer must acknowledge opens once, so its sentence and tick box are in view.
      const needs = needsAcknowledgement(build);
      if (!view.autoOpened && needs.length) { needs.forEach(t => view.open.add(t.field)); view.autoOpened = true; }
      const sample = view.sample || {};
      const source = object(build.source) || {};
      const tone = BUILD_TONES[build.state] || 'accent';
      const back = el('a', 'tb-back', 'Agreements'); back.href = '#agreements';
      back.addEventListener('click', event => { if (event && typeof event.preventDefault === 'function') event.preventDefault(); onNavigate('agreements'); });
      const tile = el('span', 'page-tile tile-agreements'); tile.setAttribute('aria-hidden', 'true');
      const stateNode = pill(BUILD_STATES[build.state] || String(build.state || 'Unknown state'), tone + (TERMINAL.includes(build.state) ? '' : ' tb-live'));
      stateNode.setAttribute('role', 'status');
      const vendor = given(source.vendor) ? source.vendor : given(sample.vendor) ? sample.vendor : 'Vendor not named';
      const title = given(source.title) ? source.title : given(sample.title) ? sample.title : given(build.sample_id) ? build.sample_id : 'Template build';
      const orchestration = build.state === 'MATCHED' ? 'Jev recognised an approved template, so no Claude agent ran: the template read this contract under Uptime’s guards.'
        : build.state === 'NEEDS_REVIEWER' ? 'Jev could not be reached, so nothing has started. A reviewer decides whether to build without Jev.'
        : (object((list(build.steps).find(s => s && s.id === 'classify') || {}).detail)?.asked === false
            ? 'No approved template is on file, so Jev had nothing to match. Uptime started '
            : 'Jev found no approved template that matches, so Uptime started ')
          + 'three Claude readers on this contract, ' + (object(build.second)?.provided ? 'three more on the second contract, ' : '')
          + 'and one Claude template builder.';
      const facts = [source.kind === 'pasted' ? 'Pasted contract' : source.kind === 'sample' ? 'Shipped sample' : null,
        Number.isInteger(source.chars) ? thousands(source.chars) + ' characters' : null,
        object(build.second) ? (build.second.provided ? 'Second contract: ' + (given(build.second.title) ? build.second.title : 'untitled') : 'No second contract given') : null].filter(Boolean);
      const head = add(el('div', 'page-head tb-head'), tile,
        add(el('div', ''), back, el('p', 'eyebrow', vendor), el('h1', '', title),
          el('p', 'tb-orchestration' + (build.state === 'MATCHED' ? ' tb-orchestration-matched' : ''), orchestration),
          facts.length ? el('p', 'help tb-source', facts.join(' · ')) : null),
        add(el('div', 'tb-head-state'), stateNode, given(build.started_at) ? el('p', 'as-of', 'Started ' + instant(build.started_at)) : null,
          el('p', 'page-ref', build.id)));
      const parts = [head];
      if (build.state === 'FAILED') {
        parts.push(add(el('section', 'panel error tb-stopped'), el('h2', '', 'The run stopped'),
          el('p', '', object(build.error) && given(build.error.sentence) ? build.error.sentence : 'The server did not say why.'),
          button('Back to Agreements', () => onNavigate('agreements'), 'quiet')));
      }
      if (build.state === 'NEEDS_REVIEWER') parts.push(needsReviewerPanel(view, build));
      if (build.state === 'MATCHED') {
        parts.push(matchedPanel(view, build));
        parts.push(flow(view, build));
      } else {
        parts.push(flow(view, build));
        if (list(build.terms).length) parts.push(termsPanel(view, build));
        if (list(build.checks).length) parts.push(checksPanel(view, build));
        if (object(build.template)) parts.push(approvalPanel(view, build));
        if (build.state === 'APPROVED' || object(build.template)?.state === 'APPROVED') parts.push(nextPanel(view, build));
      }
      view.root.replaceChildren(add(el('div', 'tb-page'), parts));
      tick(view);
    }

    function needsReviewerPanel(view, build) {
      const classify = list(build.steps).find(s => object(s) && s.id === 'classify') || {};
      const said = el('p', 'tb-said'); said.setAttribute('role', 'status');
      const go = button('Build without Jev', async () => {
        if (view.busy) return;
        view.busy = true; go.disabled = true; said.textContent = '';
        try {
          const answer = await api('/api/template-builds/' + encodeURIComponent(build.id) + '/continue', {});
          const next = object(answer) && object(answer.build);
          if (!next) throw new Error('The server did not return the run.');
          view.busy = false; draw(view, next, true);
          if (typeof view.follow === 'function') view.follow(next);
        } catch (error) {
          view.busy = false;
          if (unauthorized(error)) return;
          said.textContent = errorSentence(error, 'The run could not be continued.'); go.disabled = false;
        }
      }, 'tb-primary');
      return add(el('section', 'panel tb-needs'), add(el('div', 'panel-head'), el('h2', '', 'Jev could not be reached')),
        given(classify.summary) ? el('p', 'tb-needs-sentence', classify.summary) : null,
        el('p', 'help', 'Nothing has started. Jev decides whether an approved template already reads this contract. Without Jev, three Claude readers read it and Claude writes a new template, as for a contract type Uptime has not read.'),
        add(el('div', 'actions'), go), el('p', 'help tb-needs-record', 'Your choice is recorded on the run as a reviewer’s decision.'), said);
    }

    function matchedPanel(view, build) {
      const m = object(build.matched_template) || {};
      const readings = list(build.readings).filter(object);
      const node = add(el('section', 'panel tb-matched'),
        add(el('div', 'panel-head'), el('h2', '', 'Read by an approved template'), percent(m.probability) ? pill('Jev · ' + percent(m.probability), 'ok') : null),
        add(el('dl', 'northwind-fields tb-template-facts'),
          add(el('div', 'northwind-field'), el('dt', '', 'Template'), el('dd', '', given(m.id) ? m.id : 'Not sent')),
          add(el('div', 'northwind-field'), el('dt', '', 'SHA-256'), add(el('dd'), el('code', '', given(m.sha256) ? String(m.sha256).slice(0, 12) : 'Not sent'))),
          add(el('div', 'northwind-field'), el('dt', '', 'Jev’s decision'), el('dd', '', percent(m.probability) ? 'This template, ' + percent(m.probability) : 'This template'))),
        el('p', 'tb-no-agents', 'No Claude agent ran. Uptime’s fixed interpreter read the contract with this template’s rules.'));
      if (readings.length) readings.forEach(r => node.append(readingView(r)));
      else if (list(build.checks).length) node.append(guardList(build.checks, null));
      else node.append(el('p', 'help', 'The reading has not been recorded yet.'));
      return node;
    }

    function stepCard(view, step, build) {
      const s = object(step) || {};
      const notAsked = s.id === 'classify' && s.state === 'DONE' && object(s.detail)?.asked === false;
      // Jev was not asked (no approved template on file): no timing or figure is shown for it.
      const st = notAsked ? {word:'Not asked', tone:''} : stepState(s, now());
      const card = el('article', 'tb-step tb-' + String(s.state || 'PENDING').toLowerCase() + ' tb-actor-' + String(s.actor || '').toLowerCase());
      const detail = object(s.detail) || {};
      const meta = add(el('div', 'tb-step-meta'), el('span', 'tb-actor', actorName(s.actor)), given(s.model) ? el('code', 'tb-model', s.model) : null);
      const state = add(el('div', 'tb-step-state'), pill(st.word, st.tone));
      if (st.running) {
        const clock = el('span', 'tb-clock', st.elapsed || '');
        const started = Date.parse(s.started_at);
        if (!Number.isNaN(started)) view.clocks.push({node:clock, started});
        state.append(clock);
      }
      // "Not started: <reason>" reads once: the pill already says "Not started".
      const summary = given(s.summary) ? (s.state === 'SKIPPED' ? String(s.summary).replace(/^Not started:\s*/, '') : s.summary) : null;
      const role = ROLES[detail.role] || null;
      const route = s.id === 'classify' ? routeLine(build) : null;
      add(card, meta, add(el('div', 'tb-step-title'), el('h3', '', given(s.label) ? s.label : s.id), state),
        role ? el('p', 'tb-role tb-role-' + detail.role, role) : null,
        summary ? el('p', 'tb-summary', summary.charAt(0).toUpperCase() + summary.slice(1)) : null,
        route ? el('p', 'tb-route', route) : null,
        st.running ? el('div', 'tb-working') : null);
      card.setAttribute('aria-busy', st.running ? 'true' : 'false');
      return card;
    }
    function flow(view, build) {
      const steps = new Map(list(build.steps).filter(object).map(s => [s.id, s]));
      const node = add(el('section', 'panel tb-flow'), add(el('div', 'panel-head'), el('h2', '', 'The run')));
      const stages = el('ol', 'tb-stages');
      STAGES.forEach(([label, ids], i) => {
        const items = ids.map(id => steps.get(id)).filter(Boolean);
        if (!items.length) return;
        const states = items.map(s => s.state);
        const stageTone = states.includes('FAILED') ? 'failed' : states.includes('RUNNING') ? 'running'
          : states.every(s => s === 'SKIPPED') ? 'skipped' : states.every(s => s === 'DONE' || s === 'SKIPPED') ? 'done' : 'pending';
        const row = add(el('li', 'tb-stage tb-stage-' + stageTone), add(el('div', 'tb-stage-mark'), el('span', 'tb-stage-number', String(i + 1))),
          add(el('div', 'tb-stage-body'), el('p', 'tb-stage-label', label + (items.length > 1 ? ' · ' + items.length + ' at once' : '')),
            add(el('div', 'tb-stage-cards' + (items.length > 1 ? ' tb-parallel' : '')), items.map(s => stepCard(view, s, build)))));
        stages.append(row);
      });
      node.append(stages);
      return node;
    }

    function termsPanel(view, build) {
      const terms = list(build.terms).filter(object);
      const showJev = jevRan(build);
      // Jev has been asked once its check is on the build; a term without an answer then says so and shows no number.
      const jevAsked = !!jevCheck(build);
      const approved = build.state === 'APPROVED' || object(build.template)?.state === 'APPROVED';
      const review = terms.filter(t => t.status === 'REVIEW').length;
      const needs = terms.filter(t => t.needs_acknowledgement === true);
      const left = needs.filter(t => !view.acks.has(t.field)).length;
      const showSecond = terms.some(t => t.second_readers !== undefined);
      const showInSentence = terms.some(t => typeof t.value_in_sentence === 'boolean');
      const headPill = needs.length && !approved ? (left ? pill(left + (left === 1 ? ' term needs' : ' terms need') + ' your acknowledgement', 'warn') : pill('All ' + needs.length + ' acknowledged', 'ok'))
        : review ? pill(review + (review === 1 ? ' term' : ' terms') + ' for the reviewer', 'warn') : null;
      const node = add(el('section', 'panel tb-terms'), add(el('div', 'panel-head'), el('h2', '', 'The terms'), el('span', 'count', String(terms.length)), headPill));
      const table = el('table', 'tb-table'), body = el('tbody');
      const titles = ['Term', 'Value', 'Readers agree'].concat(showSecond ? ['Second contract'] : []).concat(showInSentence ? ['In its sentence'] : [])
        .concat(showJev ? ['Jev: supported by its sentence'] : []).concat(['Status', '']);
      add(table, add(el('thead'), add(el('tr'), titles.map(t => { const th = el('th', '', t); th.scope = 'col'; return th; }))), body);
      terms.forEach(term => {
        const open = view.open.has(term.field);
        const needsAck = term.needs_acknowledgement === true;
        const acked = view.acks.has(term.field);
        const row = el('tr', 'tb-term' + (term.status === 'REVIEW' || (needsAck && !acked) ? ' tb-term-review' : '') + (needsAck && acked ? ' tb-term-acked' : '') + (open ? ' tb-open' : ''));
        const agreement = object(term.agreement);
        const jev = object(term.jev);
        const second = object(term.second_readers);
        const shownValue = v => v !== null && v !== undefined && v === term.value && given(term.display) ? term.display : withUnit(term, v);
        const toggle = button(open ? 'Hide sentence' : 'Show sentence', () => { if (view.open.has(term.field)) view.open.delete(term.field); else view.open.add(term.field); draw(view, view.build, true); }, 'link-button');
        toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        const secondCell = !showSecond ? null : add(el('td', 'tb-second-cell'), second && Number.isInteger(second.agree) && Number.isInteger(second.of)
          ? add(el('span', term.second_document_ok === false ? 'tb-mismatch' : ''), el('span', 'tb-agree', second.agree + ' of ' + second.of), el('span', 'tb-second-value', ' · ' + (shownValue(second.value) || 'not found')))
          : el('span', 'help', 'Not given'));
        const status = needsAck && !approved ? (acked ? pill('Acknowledged', 'ok') : pill('To acknowledge', 'warn'))
          : needsAck ? pill('Acknowledged', 'ok') : term.status === 'PASS' ? pill('Passed', 'ok') : term.status === 'REVIEW' ? pill('For the reviewer', 'warn') : pill('Checking', '');
        add(row, add(el('td', 'tb-term-label'), el('strong', '', given(term.label) ? term.label : term.field)),
          el('td', 'tb-value', given(term.display) ? term.display : 'Not found'),
          el('td', 'tb-agree', agreement && Number.isInteger(agreement.agree) && Number.isInteger(agreement.of) ? agreement.agree + ' of ' + agreement.of : 'Not yet'),
          secondCell,
          showInSentence ? add(el('td', 'tb-in-sentence'), term.value_in_sentence === true ? pill('Yes', 'ok') : term.value_in_sentence === false ? pill('No', 'bad') : el('span', 'help', 'Not yet')) : null,
          showJev ? add(el('td', 'tb-jev'), jev ? add(el('span', ''), pill((jev.yes ? 'Yes' : 'No') + (percent(jev.probability) ? ' · ' + percent(jev.probability) : ''), !jev.yes ? 'bad' : term.status === 'REVIEW' || needsAck ? 'warn' : 'ok'))
            : el('span', 'help', jevAsked ? 'No answer' : 'Not yet')) : null,
          add(el('td', 'tb-status'), status),
          add(el('td', 'tb-toggle'), toggle));
        body.append(row);
        if (open) {
          const span = titles.length;
          const cell = el('td', 'tb-term-detail'); cell.colSpan = span;
          const rule = object(term.rule);
          const secondLine = second ? 'Three fresh readers: ' + (shownValue(second.value) || 'not found') + (Number.isInteger(second.agree) && Number.isInteger(second.of) ? ' (' + second.agree + ' of ' + second.of + ')' : '')
              + ' · the template returns ' + (term.second_document_value === null || term.second_document_value === undefined ? 'nothing' : shownValue(term.second_document_value))
              + (term.second_document_ok === true ? ' · the same' : term.second_document_ok === false ? ' · different' : '')
            : term.second_readers === null ? 'No second contract was given' : null;
          add(cell, el('p', 'tb-detail-label', 'The sentence in the contract'), given(term.quote) ? el('blockquote', '', term.quote) : el('p', 'help', 'No sentence was recorded for this term.'),
            add(el('dl', 'record tb-detail'),
              typeof term.value_in_sentence === 'boolean' ? [el('dt', '', 'Value in its sentence'), el('dd', term.value_in_sentence ? '' : 'tb-rule-error', term.value_in_sentence ? 'Yes: the value is written in this sentence' : 'No: the value is not written in this sentence')] : null,
              rule && given(rule.pattern) ? [el('dt', '', 'Extraction rule'), add(el('dd'), el('code', 'tb-pattern', rule.pattern))] : null,
              rule && object(rule.map) ? [el('dt', '', 'Phrase to option'), el('dd', '', Object.entries(rule.map).map(([k, v]) => '“' + k + '” → ' + v).join(' · '))] : null,
              given(term.rule_value) || term.rule_value === null ? [el('dt', '', 'The rule returns'), el('dd', '', term.rule_value === null ? 'Not found' : term.rule_value)] : null,
              given(term.rule_quote) && term.rule_quote !== term.quote ? [el('dt', '', 'The rule matched'), el('dd', 'tb-quote-text', term.rule_quote)] : null,
              given(term.rule_error) ? [el('dt', '', 'Rule error'), el('dd', 'tb-rule-error', term.rule_error)] : null,
              list(term.readers).length ? [el('dt', '', 'Each reader'), el('dd', '', list(term.readers).filter(object).map(r => 'Reader ' + r.reader + ': ' + (r.value === null || r.value === undefined ? 'Not found' : r.value) + (r.quote_found === false ? ' (quote not in the contract)' : '')).join(' · '))] : null,
              secondLine ? [el('dt', '', 'Second contract'), el('dd', term.second_document_ok === false ? 'tb-rule-error' : '', secondLine)]
                : term.second_document_value !== undefined && term.second_readers === undefined ? [el('dt', '', 'Second contract'), el('dd', '', (term.second_document_value === null ? 'Not found' : term.second_document_value) + (term.second_document_ok === true ? ' · as authored' : term.second_document_ok === false ? ' · does not match the authored value' : ''))] : null,
              given(term.conflict) ? [el('dt', '', 'Reader 3 found a conflict'), el('dd', 'tb-quote-text tb-conflict', term.conflict)] : null,
              Number.isInteger(term.rule_places) && term.rule_places > 1 ? [el('dt', '', 'Places the rule matched'), el('dd', '', term.rule_places + ', all with the same value')] : null,
              showJev && jev && given(jev.model) ? [el('dt', '', 'Jev model'), el('dd', '', jev.model)] : null));
          if (needsAck && !approved) {
            const why = !jev ? 'Jev did not answer for this term.' : !jev.yes ? 'Jev says this sentence does not support the value' + (percent(jev.probability) ? ' (' + percent(jev.probability) + ' yes)' : '') + '.'
              : 'Jev’s answer is under its threshold' + (percent(jev.probability) ? ' (' + percent(jev.probability) + ')' : '') + '.';
            const tickBox = checkbox('I have read this sentence and the value is right', acked, on => { if (on) view.acks.add(term.field); else view.acks.delete(term.field); draw(view, view.build, true); }, 'tb-ack');
            tickBox.box.setAttribute('data-field', term.field);
            cell.append(add(el('div', 'tb-ack-box' + (acked ? ' tb-ack-done' : '')), el('p', 'tb-ack-why', why), tickBox.node));
          }
          body.append(add(el('tr', 'tb-detail-row' + (needsAck && !acked && !approved ? ' tb-detail-ack' : '')), cell));
        }
      });
      node.append(add(el('div', 'table-scroll'), table));
      if (!showJev) node.append(el('p', 'help tb-jev-missing', 'Jev could not be reached, so no term has a Jev decision.'));
      return node;
    }

    function checksPanel(view, build) {
      const node = add(el('section', 'panel tb-checks'), add(el('div', 'panel-head'), el('h2', '', 'The checks')));
      const rows = el('ul', 'tb-check-list');
      const second = object(build.second) && given(build.second.title) ? {title:build.second.title} : object(view.sample)?.second_document;
      orderedChecks(build.checks).forEach(check => {
        const isSecond = check.id === 'second_document';
        const named = isSecond ? (object(check.document) || object(second)) : null;
        const isJev = check.id === 'jev' || check.by === 'JEV';
        const notRun = check.ran === false;
        // An advisory check that did not pass marks terms for the reviewer; only a blocking failure reads as a failure.
        const advisory = !check.ok && check.blocking !== true;
        const row = el('li', 'tb-check tb-check-' + String(check.id || 'other').replace(/[^a-z0-9_-]/gi, '') + ' ' + (notRun ? 'tb-check-off' : check.ok ? 'tb-check-ok' : advisory ? 'tb-check-advisory' : 'tb-check-bad'));
        const figures = notRun ? (isJev ? 'Jev could not be reached' : '') : Number.isInteger(check.passed) && Number.isInteger(check.total) ? check.passed + ' of ' + check.total : '';
        const extra = !notRun && isJev && percent(check.lowest) && percent(check.threshold) ? 'lowest ' + percent(check.lowest) + ', threshold ' + percent(check.threshold) : null;
        const how = isJev ? 'a term it does not support needs your acknowledgement' : check.blocking ? 'blocks approval if it fails' : notRun ? 'does not block approval' : 'advisory';
        add(row, add(el('div', 'tb-check-text'), el('strong', '', given(check.label) ? check.label : check.id),
          isSecond && notRun ? el('p', 'tb-check-doc tb-not-checked', 'No second contract was given, so the template was not checked on a second contract.')
            : named && given(named.title) ? el('p', 'tb-check-doc', 'Second contract: ' + named.title) : null,
          isSecond && !notRun ? el('p', 'tb-check-doc', given(check.basis) ? check.basis : 'No answer key: three fresh Claude readers read the second contract, and the template must return what they agreed on.') : null,
          isSecond && !notRun && list(check.readers).filter(object).length ? add(el('p', 'help tb-second-readers'), list(check.readers).filter(object).map(r => el('span', 'tb-second-reader' + (r.ok === false ? ' tb-mismatch' : ''), 'Reader ' + r.reader + (ROLES[r.role] ? ' · ' + ROLES[r.role].toLowerCase() : '') + (given(r.model) ? ' · ' + r.model : '') + (given(r.seconds) ? ' · ' + r.seconds + ' s' : '') + (r.ok === false ? ' · ' + (given(r.summary) ? r.summary : 'failed') : '')))) : null,
          el('p', 'help', [CHECK_BY[check.by] || actorName(check.by), how].join(' · '))),
          add(el('div', 'tb-check-figures'), el('span', 'tb-check-count', figures), extra ? el('span', 'help', extra) : null),
          notRun ? pill(isJev ? 'Not run' : 'Not checked', '') : check.ok ? pill('Pass', 'ok') : advisory ? pill('For the reviewer', 'warn') : pill('Fail', 'bad'));
        rows.append(row);
      });
      node.append(rows);
      return node;
    }

    function approvalPanel(view, build) {
      const t = build.template;
      const approved = t.state === 'APPROVED' || build.state === 'APPROVED';
      const node = add(el('section', 'panel tb-approval' + (approved ? ' tb-approved' : '')), add(el('div', 'panel-head'), el('h2', '', 'Reviewer approval')));
      add(node, add(el('dl', 'northwind-fields tb-template-facts'),
        add(el('div', 'northwind-field'), el('dt', '', 'Template'), el('dd', '', t.id)),
        add(el('div', 'northwind-field'), el('dt', '', 'SHA-256'), add(el('dd'), el('code', '', given(t.sha256) ? String(t.sha256).slice(0, 12) : 'Not sent'))),
        add(el('div', 'northwind-field'), el('dt', '', 'Rules'), el('dd', '', Number.isInteger(t.rules) ? String(t.rules) : 'Not sent'))));
      const secondCheck = list(build.checks).find(c => object(c) && c.id === 'second_document');
      const notChecked = secondCheck && secondCheck.ran === false ? el('p', 'tb-not-checked-note', 'This template was not checked on a second contract.') : null;
      if (approved) {
        const review = object(list(build.steps).find(s => object(s) && s.id === 'review')?.detail) || {};
        const ackedFields = list(review.acknowledged).filter(given);
        const labels = ackedFields.map(f => { const term = list(build.terms).find(x => object(x) && x.field === f); return term && given(term.label) ? term.label : f; });
        node.append(el('p', 'tb-approved-line', 'Approved by ' + (given(t.approved_by) ? t.approved_by : 'a reviewer not named by the server') + (given(t.approved_at) ? ' · ' + instant(t.approved_at) : '') + '. Only this exact version is active.'));
        if (labels.length) node.append(el('p', 'help tb-acked-line', 'The reviewer acknowledged ' + labels.join(', ') + '.'));
        if (notChecked) node.append(notChecked);
        return node;
      }
      const failed = blockingFailures(build);
      let reason = null;
      if (failed.length) reason = 'Approval is not possible: ' + failed.map(c => c.label || c.id).join('; ') + ' failed.';
      else if (build.state !== 'READY_FOR_REVIEW') reason = 'Approval opens when the checks have finished.';
      const needs = needsAcknowledgement(build);
      const missing = needs.filter(x => !view.acks.has(x.field));
      const said = el('p', 'tb-said'); said.setAttribute('role', 'status'); said.textContent = view.said;
      const approve = button('Approve this template', async () => {
        if (view.busy || approve.disabled) return;
        view.busy = true; approve.disabled = true; view.said = ''; said.textContent = '';
        try {
          const acknowledged = needs.filter(x => view.acks.has(x.field)).map(x => x.field);
          const answer = await api('/api/template-builds/' + encodeURIComponent(build.id) + '/approve', {template_sha256:t.sha256, acknowledged});
          const next = object(answer) && object(answer.build);
          if (!next) throw new Error('The server did not return the approved run.');
          view.busy = false; draw(view, next, true);
        } catch (error) {
          view.busy = false;
          if (unauthorized(error)) return;
          view.said = errorSentence(error, 'Approval was refused.');
          said.textContent = view.said; approve.disabled = false;
        }
      });
      approve.disabled = !!reason || missing.length > 0;
      const marked = list(build.terms).filter(x => object(x) && x.status === 'REVIEW');
      const ackNote = !reason && needs.length ? el('p', missing.length ? 'tb-review-note' : 'tb-ack-all',
        missing.length ? missing.length + ' of ' + needs.length + (needs.length === 1 ? ' term' : ' terms') + ' still to acknowledge: ' + missing.map(x => x.label || x.field).join(', ') + '. Jev did not support ' + (missing.length === 1 ? 'it' : 'them') + '; read each sentence above and tick its box.'
          : 'Every term Jev did not support is acknowledged: ' + needs.map(x => x.label || x.field).join(', ') + '.') : null;
      const markedNote = !reason && !needs.length && marked.length ? el('p', 'tb-review-note', 'Jev marked ' + marked.map(x => x.label || x.field).join(', ') + ' for you to read before approving. Jev’s check is advisory: open the term above, compare the value with its sentence, then approve.') : null;
      const count = !reason && missing.length ? el('span', 'tb-ack-count', missing.length + ' still to acknowledge') : null;
      add(node, el('p', 'help', 'Approving makes this exact version (by its SHA-256) the reader for this contract type. Nothing is active before that.'),
        ackNote, markedNote, notChecked, add(el('div', 'actions'), approve, count), reason ? el('p', 'tb-blocked', reason) : null, said);
      return node;
    }

    function nextPanel(view, build) {
      const docs = list(object(view.sample)?.next_documents).filter(object);
      const served = list(build.readings).filter(object);
      const readingFor = docId => view.readings.get(docId) || served.find(r => object(r.document)?.id === docId) || null;
      const node = add(el('section', 'panel tb-next'), add(el('div', 'panel-head'), el('h2', '', 'The next contract of this type')),
        el('p', 'help', 'Read by the approved template alone: Uptime’s fixed interpreter runs its rules with no Claude call, and every read is guarded. A refused read feeds nothing downstream.'));
      if (!docs.length) node.append(el('p', 'help', 'No further contract of this type is on file. Paste one below.'));
      docs.forEach(d => {
        const reading = readingFor(d.id);
        const top = add(el('div', 'tb-next-head'),
          add(el('div', ''), el('p', 'eyebrow', given(d.vendor) ? d.vendor : ''), el('h3', '', given(d.title) ? d.title : d.id),
            Number.isInteger(d.chars) ? el('p', 'help', thousands(d.chars) + ' characters') : null));
        const box = add(el('div', 'tb-next-doc'), top);
        if (!reading) {
          const said = el('p', 'tb-said'); said.setAttribute('role', 'status');
          const go = button('Read the next contract with the template', async () => {
            go.disabled = true; said.textContent = '';
            try {
              const answer = await api('/api/template-builds/' + encodeURIComponent(build.id) + '/read', {document_id:d.id});
              const r = object(answer) && object(answer.reading);
              if (!r) throw new Error('The server did not return a reading.');
              view.readings.set(d.id, r); draw(view, view.build, true);
            } catch (error) {
              if (unauthorized(error)) return;
              said.textContent = errorSentence(error, 'The contract could not be read.'); go.disabled = false;
            }
          });
          top.append(go); box.append(said);
        } else box.append(readingView(reading));
        node.append(box);
      });
      // Readings of pasted contracts: those not of a listed next document, from the server and from this page.
      const listed = new Set(docs.map(d => d.id));
      const pastedReadings = [];
      served.concat([...view.readings.values()]).forEach(r => {
        const key = given(r.id) ? r.id : JSON.stringify(r);
        if (listed.has(object(r.document)?.id) || pastedReadings.some(p => p.key === key)) return;
        pastedReadings.push({key, r});
      });
      pastedReadings.forEach(({r}) => {
        const d = object(r.document) || {};
        node.append(add(el('div', 'tb-next-doc'), add(el('div', 'tb-next-head'), add(el('div', ''), el('p', 'eyebrow', given(d.vendor) ? d.vendor : 'Pasted contract'),
          el('h3', '', given(d.title) ? d.title : given(d.id) ? d.id : 'Pasted contract'))), readingView(r)));
      });
      node.append(pasteNext(view, build));
      return node;
    }
    // A next contract pasted after approval, read by the template under the same guards.
    function pasteNext(view, build) {
      const draft = view.draft;
      const title = input('tb-input'), vendor = input('tb-input'), text = input('tb-textarea', 'textarea');
      title.value = draft.title; vendor.value = draft.vendor; text.value = draft.text; text.rows = 7;
      text.placeholder = 'Paste the next contract of this type.';
      const said = el('p', 'tb-said'); said.setAttribute('role', 'status');
      const consent = checkbox('I agree that this text will be sent to Jev, which checks that it follows this template. The values are read by fixed rules.', draft.consent, on => { draft.consent = on; update(); }, 'tb-consent');
      const go = button('Read this contract with the template', async () => {
        if (go.disabled) return;
        go.disabled = true; said.textContent = '';
        try {
          const answer = await api('/api/template-builds/' + encodeURIComponent(build.id) + '/read',
            {contract:{title:draft.title.trim(), vendor:draft.vendor.trim(), text:draft.text}, consent:true});
          const r = object(answer) && object(answer.reading);
          if (!r) throw new Error('The server did not return a reading.');
          view.readings.set(given(r.id) ? r.id : 'pasted-' + view.readings.size, r);
          view.draft = {title:'', vendor:'', text:'', consent:false};
          draw(view, view.build, true);
        } catch (error) {
          if (unauthorized(error)) return;
          said.textContent = errorSentence(error, 'The contract could not be read.'); update();
        }
      }, 'tb-primary');
      function update() {
        draft.title = String(title.value || ''); draft.vendor = String(vendor.value || ''); draft.text = String(text.value || '');
        go.disabled = draft.text.trim() === '' || !consent.box.checked;
      }
      [title, vendor, text].forEach(control => control.addEventListener('input', update));
      update();
      return add(el('details', 'tb-next-paste'), el('summary', '', 'Paste the next contract to read'),
        add(el('div', 'tb-paste-names'), field('Title', title), field('Vendor', vendor)), field('Contract text', text), consent.node,
        add(el('div', 'actions'), go), said);
    }

    // The guards a read ran (Version 2), each in words; Jev's document-type guard shows its probability.
    function guardList(guards, reading) {
      const jevType = object(reading?.jev_template);
      const items = list(guards).filter(object);
      if (!items.length) return null;
      return add(el('ul', 'tb-guards'), items.map(g => {
        const isJev = g.id === 'template_match';
        const advisory = g.advisory === true || g.blocking === false;
        const detail = isJev && percent(g.detail) ? 'Jev · ' + percent(g.detail) + (jevType && given(jevType.model) ? ' · ' + jevType.model : '')
          : given(g.detail) ? String(g.detail) : null;
        const tone = g.ok === true ? 'ok' : advisory ? 'warn' : 'bad';
        return add(el('li', 'tb-guard tb-guard-' + tone), pill(g.ok === true ? 'Pass' : advisory ? 'Advisory' : 'Fail', tone),
          add(el('span', 'tb-guard-text'), el('span', 'tb-guard-label', given(g.label) ? g.label : g.id), detail ? el('span', 'help tb-guard-detail', detail) : null));
      }));
    }

    function readingView(reading) {
      const refused = reading.status === 'REFUSED';
      const accepted = reading.status === 'ACCEPTED';
      const node = el('div', 'tb-reading' + (refused ? ' tb-reading-refused' : accepted ? ' tb-reading-accepted' : ''));
      const failed = list(reading.guards).filter(g => object(g) && g.ok === false && g.advisory !== true);
      add(node, add(el('div', 'tb-reading-head'),
          refused ? pill('Refused', 'bad') : accepted ? pill('Accepted', 'ok') : null,
          add(el('p', 'tb-reading-line'), el('span', 'tb-rules-mark', readingLine(reading)))),
        Number.isInteger(reading.found) && Number.isInteger(reading.total) ? el('p', 'help', reading.found + ' of ' + reading.total + ' terms found' + (given(reading.read_at) ? ' · ' + instant(reading.read_at) : '')) : null,
        refused ? add(el('div', 'tb-refused'), el('p', 'tb-refused-line', 'This reading was refused, so nothing from it is used: no agreement, no credit.'),
          list(reading.reasons).filter(given).length ? add(el('ul', 'tb-refused-reasons'), list(reading.reasons).filter(given).map(r => el('li', '', r)))
            : failed.length ? add(el('ul', 'tb-refused-reasons'), failed.map(g => el('li', '', (given(g.label) ? g.label : g.id) + (given(g.detail) ? ': ' + g.detail : '')))) : null) : null,
        list(reading.guards).length ? add(el('div', 'tb-guards-box'), el('p', 'tb-detail-label', 'Guards on this read'), guardList(reading.guards, reading)) : null);
      const terms = list(reading.terms).filter(object);
      if (terms.length) {
        const table = el('table', 'tb-table'), body = el('tbody');
        add(table, add(el('thead'), add(el('tr'), ['Term', refused ? 'Found (not accepted)' : 'Value', 'The sentence the rule matched'].map(t => { const th = el('th', '', t); th.scope = 'col'; return th; }))), body);
        terms.forEach(term => {
          const found = term.value !== null && term.value !== undefined;
          body.append(add(el('tr', found ? '' : 'tb-not-found'), add(el('td', 'tb-term-label'), el('strong', '', given(term.label) ? term.label : term.field)),
            add(el('td', refused ? 'tb-value tb-value-refused' : 'tb-value'), found ? el('span', '', given(term.display) ? term.display : term.value) : pill('Not found', 'warn')),
            add(el('td', 'tb-quote'), found && given(term.quote) ? el('span', 'tb-quote-text', term.quote) : el('span', 'help', 'No sentence matched. Nothing is guessed.'),
            given(term.error) ? el('p', 'tb-term-error', term.error) : null)));
        });
        node.append(add(el('div', 'table-scroll' + (refused ? ' tb-not-accepted' : '')), refused ? el('p', 'tb-not-accepted-label', 'What the rules found · not accepted') : null, table));
      }
      if (!refused && object(reading.agreement)) node.append(agreementCard(reading.agreement));
      else if (!refused && given(reading.agreement_note)) node.append(el('p', 'help tb-agreement-note', reading.agreement_note));
      return node;
    }

    // The money link: the agreement the server made from an accepted read, and the engine's estimate. Shown as sent.
    function agreementCard(a) {
      const credit = object(a.credit);
      const currency = credit && given(credit.currency) ? credit.currency : given(a.currency) ? a.currency : null;
      const portfolio = el('a', 'tb-portfolio-link', 'Open the portfolio'); portfolio.href = '#overview';
      portfolio.addEventListener('click', event => { if (event && typeof event.preventDefault === 'function') event.preventDefault(); onNavigate('overview'); });
      const fieldsList = [['Service month', monthLabel(a.month)], ['Availability', given(a.availability_percent) ? a.availability_percent + '%' : null],
        ['Credit percent', given(a.credit_percent) ? a.credit_percent + '%' : null], ['Monthly fee', given(a.monthly_fee) ? money(a.monthly_fee, currency) || a.monthly_fee : null]];
      const amount = credit && given(credit.amount) ? money(credit.amount, credit.currency) || credit.amount : null;
      const stage = credit && credit.stage === 'ESTIMATED' ? 'Estimated · not claimed' : credit && given(credit.stage) ? String(credit.stage).toLowerCase() : null;
      return add(el('section', 'tb-money' + (amount ? '' : ' tb-money-none')),
        add(el('div', 'tb-money-head'), add(el('div', ''), el('p', 'eyebrow', 'Agreement from this reading'), el('h3', '', given(a.agreement_id) ? a.agreement_id : 'Agreement not named')),
          pill(a.state === 'SHADOW' ? 'In shadow' : given(a.state) ? String(a.state).toLowerCase() : 'State not sent', a.state === 'SHADOW' ? 'accent' : '')),
        readByWords(a.read_by) ? el('p', 'help tb-money-readby', 'Contract read by ' + readByWords(a.read_by).replace(/^Fixed rules/, 'fixed rules')) : null,
        add(el('div', 'tb-money-body'),
          add(el('div', 'tb-money-figure'), el('p', 'tb-detail-label', amount ? 'Estimated credit' : 'Credit'),
            amount ? el('p', 'tb-money-amount', amount) : el('p', 'tb-money-missing', given(a.evaluation) ? a.evaluation : 'No amount'),
            amount && stage ? el('p', 'help', stage) : null),
          add(el('dl', 'northwind-fields tb-money-fields'), fieldsList.map(([k, v]) => add(el('div', 'northwind-field'), el('dt', '', k), el('dd', '', v || 'Not known'))))),
        list(a.inputs).filter(object).length ? add(el('dl', 'record tb-money-inputs'), list(a.inputs).filter(object).flatMap(i => [el('dt', '', given(i.label) ? i.label : ''), el('dd', '', given(i.value) ? i.value : 'Not known')])) : null,
        amount && given(a.evaluation) ? el('p', 'tb-evaluation', a.evaluation) : null,
        add(el('p', 'tb-money-foot'), el('span', 'help', 'Computed by Uptime’s credit engine, not by a model. Nothing is posted, claimed or applied.'), portfolio));
    }

    return Object.freeze({section, run, unmount});
  }

  const api = Object.freeze({create, percent, money, monthLabel, withUnit, readByWords, stepState, actorName, jevRan, blockingFailures, orderedChecks,
    needsAcknowledgement, routeLine, readingLine, latestBuild, TERMINAL, POLL_MS, ROLES, CHECK_ORDER});
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (global) global.UptimeTemplateBuilder = api;
})(typeof window !== 'undefined' ? window : globalThis);
