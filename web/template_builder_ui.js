/* Template builder (docs/demo/TEMPLATE-BUILDER.md): a section on the Agreements page for a contract type Uptime has
 * not read before, and the page #template-build/<id> that draws one run from the server's `build` object alone.
 * Every figure on these pages comes from a `build` or `reading` object the server sent; the only thing computed here
 * is the elapsed time of a step that is still working, from its own `started_at`.
 * Only Claude and Jev are models. Uptime's interpreter and checks are code and are named as such.
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
    APPROVED:'Approved', FAILED:'Failed'};
  const BUILD_TONES = {READY_FOR_REVIEW:'warn', APPROVED:'ok', FAILED:'bad'};
  const TERMINAL = ['READY_FOR_REVIEW', 'APPROVED', 'FAILED'];
  const POLL_MS = 700;
  // The run's stages, in order; the server always sends these seven step ids.
  const STAGES = [['Decide the contract type', ['classify']], ['Read the contract in parallel', ['reader-1', 'reader-2', 'reader-3']],
    ['Write the template', ['build']], ['Check the template', ['checks']], ['Approve this version', ['review']]];
  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const INSTANT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/;
  function instant(value) {
    if (typeof value !== 'string' || !INSTANT.test(value)) return given(value) ? String(value) : null;
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}, ${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')} UTC`;
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
      case 'SKIPPED': return {word:'Skipped', tone:''};
      case 'PENDING': return {word:'Waiting', tone:''};
      default: return {word:given(s.state) ? String(s.state).toLowerCase() : 'Waiting', tone:''};
    }
  }
  const jevCheck = build => list(object(build)?.checks).find(c => object(c) && (c.id === 'jev' || c.by === 'JEV')) || null;
  // Jev's figures are shown only when Jev really answered.
  const jevRan = build => { const c = jevCheck(build); return !(c && c.ran === false); };
  // The blocking checks that failed; approval is refused while any is listed.
  const blockingFailures = build => list(object(build)?.checks).filter(c => object(c) && c.blocking === true && c.ok === false);
  const safePath = value => typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') ? value : null;
  function latestBuild(builds, sampleId) {
    return list(builds).filter(b => object(b) && b.sample_id === sampleId)
      .sort((a, b) => String(b.started_at || '').localeCompare(String(a.started_at || '')))[0] || null;
  }
  function readingLine(reading) {
    const r = object(reading) || {}, t = object(r.template) || {};
    const parts = [r.read_by === 'TEMPLATE' ? 'Read by fixed rules' : 'Read by ' + (given(r.read_by) ? String(r.read_by).toLowerCase() : 'an unnamed reader')];
    if (given(t.id)) parts.push('template ' + t.id);
    if (Number.isInteger(r.model_calls)) parts.push(r.model_calls + (r.model_calls === 1 ? ' model call' : ' model calls'));
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
          el('p', 'help', 'Jev checks whether a template on file matches. If none does, Claude agents read the contract and write a template; Uptime’s code checks it and a reviewer approves it before it reads anything.')));
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
                said.textContent = error && error.message ? error.message : 'The run could not be started.';
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
      const body = typeof root.querySelector === 'function' ? root.querySelector('.v4-body') : null;
      if (body && typeof body.prepend === 'function') body.prepend(node); else root.append(node);
      return node;
    }

    // ---- #template-build/<id> ----
    async function run(root, id) {
      unmount();
      const token = mount;
      const view = {root, id, sample:null, build:null, drawn:null, open:new Set(), readings:new Map(), said:'', busy:false, clocks:[]};
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
          if (!view.build) { root.replaceChildren(failurePanel(error && error.message ? error.message : 'This run could not be read.')); unmount(); return; }
          pollTimer = later(() => poll().catch(() => {}), POLL_MS * 3);
          return;
        }
        if (token !== mount) return;
        draw(view, build);
        if (!TERMINAL.includes(build.state)) pollTimer = later(() => poll().catch(() => {}), POLL_MS);
        else if (ticker !== null) { tick(view); stopEvery(ticker); ticker = null; }
      }
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
      const sample = view.sample || {};
      const tone = BUILD_TONES[build.state] || 'accent';
      const back = el('a', 'tb-back', 'Agreements'); back.href = '#agreements';
      back.addEventListener('click', event => { if (event && typeof event.preventDefault === 'function') event.preventDefault(); onNavigate('agreements'); });
      const tile = el('span', 'page-tile tile-agreements'); tile.setAttribute('aria-hidden', 'true');
      const stateNode = pill(BUILD_STATES[build.state] || String(build.state || 'Unknown state'), tone + (TERMINAL.includes(build.state) ? '' : ' tb-live'));
      stateNode.setAttribute('role', 'status');
      const head = add(el('div', 'page-head tb-head'), tile,
        add(el('div', ''), back, el('p', 'eyebrow', given(sample.vendor) ? sample.vendor : 'Vendor not named'),
          el('h1', '', given(sample.title) ? sample.title : given(build.sample_id) ? build.sample_id : 'Template build'),
          el('p', 'tb-orchestration', 'Uptime started one Jev decision, three Claude readers in parallel and one Claude template builder.')),
        add(el('div', 'tb-head-state'), stateNode, given(build.started_at) ? el('p', 'as-of', 'Started ' + instant(build.started_at)) : null,
          el('p', 'page-ref', build.id)));
      const parts = [head];
      if (build.state === 'FAILED') {
        parts.push(add(el('section', 'panel error tb-stopped'), el('h2', '', 'The run stopped'),
          el('p', '', object(build.error) && given(build.error.sentence) ? build.error.sentence : 'The server did not say why.'),
          button('Back to Agreements', () => onNavigate('agreements'), 'quiet')));
      }
      parts.push(flow(view, build));
      if (list(build.terms).length) parts.push(termsPanel(view, build));
      if (list(build.checks).length) parts.push(checksPanel(build));
      if (object(build.template)) parts.push(approvalPanel(view, build));
      if (build.state === 'APPROVED' || object(build.template)?.state === 'APPROVED') parts.push(nextPanel(view, build));
      view.root.replaceChildren(add(el('div', 'tb-page'), parts));
      tick(view);
    }

    function stepCard(view, step) {
      const s = object(step) || {};
      const st = stepState(s, now());
      const card = el('article', 'tb-step tb-' + String(s.state || 'PENDING').toLowerCase() + ' tb-actor-' + String(s.actor || '').toLowerCase());
      const meta = add(el('div', 'tb-step-meta'), el('span', 'tb-actor', actorName(s.actor)), given(s.model) ? el('code', 'tb-model', s.model) : null);
      const state = add(el('div', 'tb-step-state'), pill(st.word, st.tone));
      if (st.running) {
        const clock = el('span', 'tb-clock', st.elapsed || '');
        const started = Date.parse(s.started_at);
        if (!Number.isNaN(started)) view.clocks.push({node:clock, started});
        state.append(clock);
      }
      add(card, meta, add(el('div', 'tb-step-title'), el('h3', '', given(s.label) ? s.label : s.id), state), given(s.summary) ? el('p', 'tb-summary', s.summary) : null,
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
          : states.every(s => s === 'DONE' || s === 'SKIPPED') ? 'done' : 'pending';
        const row = add(el('li', 'tb-stage tb-stage-' + stageTone), add(el('div', 'tb-stage-mark'), el('span', 'tb-stage-number', String(i + 1))),
          add(el('div', 'tb-stage-body'), el('p', 'tb-stage-label', label + (items.length > 1 ? ' · ' + items.length + ' at once' : '')),
            add(el('div', 'tb-stage-cards' + (items.length > 1 ? ' tb-parallel' : '')), items.map(s => stepCard(view, s)))));
        stages.append(row);
      });
      node.append(stages);
      return node;
    }

    function termsPanel(view, build) {
      const terms = list(build.terms).filter(object);
      const showJev = jevRan(build);
      const review = terms.filter(t => t.status === 'REVIEW').length;
      const node = add(el('section', 'panel tb-terms'), add(el('div', 'panel-head'), el('h2', '', 'The terms'), el('span', 'count', String(terms.length)),
        review ? pill(review + (review === 1 ? ' term' : ' terms') + ' for the reviewer', 'warn') : null));
      const table = el('table', 'tb-table'), body = el('tbody');
      const titles = ['Term', 'Value', 'Readers agree'].concat(showJev ? ['Jev: supported by its sentence'] : []).concat(['Status', '']);
      add(table, add(el('thead'), add(el('tr'), titles.map(t => { const th = el('th', '', t); th.scope = 'col'; return th; }))), body);
      terms.forEach(term => {
        const open = view.open.has(term.field);
        const row = el('tr', 'tb-term' + (term.status === 'REVIEW' ? ' tb-term-review' : '') + (open ? ' tb-open' : ''));
        const agreement = object(term.agreement);
        const jev = object(term.jev);
        const toggle = button(open ? 'Hide sentence' : 'Show sentence', () => { if (view.open.has(term.field)) view.open.delete(term.field); else view.open.add(term.field); draw(view, view.build, true); }, 'link-button');
        toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        add(row, add(el('td', 'tb-term-label'), el('strong', '', given(term.label) ? term.label : term.field)),
          el('td', 'tb-value', given(term.display) ? term.display : 'Not found'),
          el('td', 'tb-agree', agreement && Number.isInteger(agreement.agree) && Number.isInteger(agreement.of) ? agreement.agree + ' of ' + agreement.of : 'Not yet'),
          showJev ? add(el('td', 'tb-jev'), jev ? add(el('span', ''), pill((jev.yes ? 'Yes' : 'No') + (percent(jev.probability) ? ' · ' + percent(jev.probability) : ''), jev.yes ? 'ok' : 'bad')) : el('span', 'help', 'Not yet')) : null,
          add(el('td', 'tb-status'), term.status === 'PASS' ? pill('Passed', 'ok') : term.status === 'REVIEW' ? pill('For the reviewer', 'warn') : pill('Checking', '')),
          add(el('td', 'tb-toggle'), toggle));
        body.append(row);
        if (open) {
          const span = titles.length;
          const cell = el('td', 'tb-term-detail'); cell.colSpan = span;
          const rule = object(term.rule);
          add(cell, el('p', 'tb-detail-label', 'The sentence in the contract'), given(term.quote) ? el('blockquote', '', term.quote) : el('p', 'help', 'No sentence was recorded for this term.'),
            add(el('dl', 'record tb-detail'),
              rule && given(rule.pattern) ? [el('dt', '', 'Extraction rule'), add(el('dd'), el('code', 'tb-pattern', rule.pattern))] : null,
              given(term.rule_value) || term.rule_value === null ? [el('dt', '', 'The rule returns'), el('dd', '', term.rule_value === null ? 'Not found' : term.rule_value)] : null,
              list(term.readers).length ? [el('dt', '', 'Each reader'), el('dd', '', list(term.readers).filter(object).map(r => 'Reader ' + r.reader + ': ' + (r.value === null || r.value === undefined ? 'Not found' : r.value) + (r.quote_found === false ? ' (quote not in the contract)' : '')).join(' · '))] : null,
              term.second_document_value !== undefined ? [el('dt', '', 'Second contract'), el('dd', '', (term.second_document_value === null ? 'Not found' : term.second_document_value) + (term.second_document_ok === true ? ' · as authored' : term.second_document_ok === false ? ' · does not match the authored value' : ''))] : null,
              showJev && jev && given(jev.model) ? [el('dt', '', 'Jev model'), el('dd', '', jev.model)] : null));
          body.append(add(el('tr', 'tb-detail-row'), cell));
        }
      });
      node.append(add(el('div', 'table-scroll'), table));
      if (!showJev) node.append(el('p', 'help tb-jev-missing', 'Jev could not be reached, so no term has a Jev decision.'));
      return node;
    }

    function checksPanel(build) {
      const node = add(el('section', 'panel tb-checks'), add(el('div', 'panel-head'), el('h2', '', 'The checks')));
      const rows = el('ul', 'tb-check-list');
      list(build.checks).filter(object).forEach(check => {
        const isJev = check.id === 'jev' || check.by === 'JEV';
        const notRun = isJev && check.ran === false;
        const row = el('li', 'tb-check ' + (notRun ? 'tb-check-off' : check.ok ? 'tb-check-ok' : 'tb-check-bad'));
        const figures = notRun ? 'Jev could not be reached' : Number.isInteger(check.passed) && Number.isInteger(check.total) ? check.passed + ' of ' + check.total : '';
        const extra = !notRun && isJev && percent(check.lowest) && percent(check.threshold) ? 'lowest ' + percent(check.lowest) + ', threshold ' + percent(check.threshold) : null;
        add(row, add(el('div', 'tb-check-text'), el('strong', '', given(check.label) ? check.label : check.id),
          el('p', 'help', [CHECK_BY[check.by] || actorName(check.by), check.blocking ? 'blocks approval if it fails' : 'advisory'].join(' · '))),
          add(el('div', 'tb-check-figures'), el('span', 'tb-check-count', figures), extra ? el('span', 'help', extra) : null),
          notRun ? pill('Not run', '') : check.ok ? pill('Pass', 'ok') : pill('Fail', 'bad'));
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
      if (approved) {
        node.append(el('p', 'tb-approved-line', 'Approved by ' + (given(t.approved_by) ? t.approved_by : 'a reviewer not named by the server') + (given(t.approved_at) ? ' · ' + instant(t.approved_at) : '') + '. Only this exact version is active.'));
        return node;
      }
      const failed = blockingFailures(build);
      let reason = null;
      if (failed.length) reason = 'Approval is not possible: ' + failed.map(c => c.label || c.id).join('; ') + (failed.length === 1 ? ' failed.' : ' failed.');
      else if (build.state !== 'READY_FOR_REVIEW') reason = 'Approval opens when the checks have finished.';
      const said = el('p', 'tb-said'); said.setAttribute('role', 'status'); said.textContent = view.said;
      const approve = button('Approve this template', async () => {
        if (view.busy) return;
        view.busy = true; approve.disabled = true; view.said = ''; said.textContent = '';
        try {
          const answer = await api('/api/template-builds/' + encodeURIComponent(build.id) + '/approve', {template_sha256:t.sha256});
          const next = object(answer) && object(answer.build);
          if (!next) throw new Error('The server did not return the approved run.');
          view.busy = false; draw(view, next, true);
        } catch (error) {
          view.busy = false;
          if (unauthorized(error)) return;
          view.said = error && error.message ? error.message : 'Approval was refused.';
          said.textContent = view.said; approve.disabled = false;
        }
      });
      approve.disabled = !!reason;
      add(node, el('p', 'help', 'Approving makes this exact version (by its SHA-256) the reader for this contract type. Nothing is active before that.'),
        add(el('div', 'actions'), approve), reason ? el('p', 'tb-blocked', reason) : null, said);
      return node;
    }

    function nextPanel(view, build) {
      const docs = list(object(view.sample)?.next_documents).filter(object);
      const node = add(el('section', 'panel tb-next'), add(el('div', 'panel-head'), el('h2', '', 'The next contract of this type')),
        el('p', 'help', 'Read by the approved template alone: Uptime’s fixed interpreter runs its rules, with no model call.'));
      if (!docs.length) node.append(el('p', 'help', 'No further contract of this type is on file.'));
      docs.forEach(d => {
        const reading = view.readings.get(d.id);
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
              said.textContent = error && error.message ? error.message : 'The contract could not be read.'; go.disabled = false;
            }
          });
          top.append(go); box.append(said);
        } else box.append(readingView(reading));
        node.append(box);
      });
      return node;
    }
    function readingView(reading) {
      const node = el('div', 'tb-reading');
      add(node, add(el('p', 'tb-reading-line'), el('span', 'tb-rules-mark', readingLine(reading))),
        Number.isInteger(reading.found) && Number.isInteger(reading.total) ? el('p', 'help', reading.found + ' of ' + reading.total + ' terms found' + (given(reading.read_at) ? ' · ' + instant(reading.read_at) : '')) : null);
      const table = el('table', 'tb-table'), body = el('tbody');
      add(table, add(el('thead'), add(el('tr'), ['Term', 'Value', 'The sentence the rule matched'].map(t => { const th = el('th', '', t); th.scope = 'col'; return th; }))), body);
      list(reading.terms).filter(object).forEach(term => {
        const found = term.value !== null && term.value !== undefined;
        body.append(add(el('tr', found ? '' : 'tb-not-found'), add(el('td', 'tb-term-label'), el('strong', '', given(term.label) ? term.label : term.field)),
          add(el('td', 'tb-value'), found ? el('span', '', given(term.display) ? term.display : term.value) : pill('Not found', 'warn')),
          add(el('td', 'tb-quote'), found && given(term.quote) ? el('span', 'tb-quote-text', term.quote) : el('span', 'help', 'No sentence matched. Nothing is guessed.'))));
      });
      node.append(add(el('div', 'table-scroll'), table));
      return node;
    }

    return Object.freeze({section, run, unmount});
  }

  const api = Object.freeze({create, percent, stepState, actorName, jevRan, blockingFailures, readingLine, latestBuild, TERMINAL, POLL_MS});
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (global) global.UptimeTemplateBuilder = api;
})(typeof window !== 'undefined' ? window : globalThis);
