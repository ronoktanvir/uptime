"""Demo line (November 10, 2026): the claim for a contract that an approved template read.

An ACCEPTED template read gives an agreement in SHADOW and an ESTIMATED credit (`uptime/template_agreements.py`).
This module carries that credit through the claim lifecycle the Northwind case already has, with the same machinery:
`northwind_workflow.WorkspaceWorkflow` (its exact intents, pins, signed source deliveries, local ledger provider and
invoice intake), the correspondence inbox and its claim state machine, the allocation ledger, and the workflow
coordinator for routine steps. Nothing here is a second state machine.

How one workspace carries a second case: each case lives in its own case workspace, a separate SQLite database under
`<workspace>/template-claims/<document id>/`, bound to the same scripted replay authority, tenant and signed source
registry as the main workspace. The workflow's per-workspace state (its event clock, intent table, step history,
inbox, ledger, settlement destination and governing-fee registry) is therefore the case's own, so the Northwind case
and this one never share a clock or a ledger. The case database is created by the reviewer's first decision.

The first decision ("Approve October claim") is pinned to what the case page showed: the reading (build, reading id,
template SHA-256, read values), the authored evidence files' SHA-256 and the estimated amount. Under it Uptime
installs the read terms in the case workspace's agreement catalog (the engine's own compiler; authored controls must
pass), opens the claim, receives the month's records through the signed sources, and checks that the claim the
engine assessed is the one shown (same agreement source, month and amount). Only then is the reviewer's approval of
the claim packet recorded. Every later decision is the existing workflow's own, unchanged.

The vendor is a simulated local counterparty; usage, invoices and replies are authored fixtures (see the README in
`fixtures/template_builder_demo/evidence/<document id>/`). Nothing goes to Ramp.
"""
from copy import deepcopy
from datetime import UTC, datetime
from functools import partial
from hashlib import sha256
import json
from pathlib import Path
import re
from threading import RLock

from . import template_agreements as money_link
from . import workflow_coordinator as coordinator
from .auth import SCRIPT
from .contracts import fingerprint
from .correspondence_types import Claim, Delivery, Scope, instant
from .northwind_workflow import LABELS, WorkspaceWorkflow, encoded
from .storage import database

OPEN = 'open-claim'
ROLES = ('billing', 'customer', 'status', 'vendor')
FILES = ('overlay.json', 'usage.json', 'invoice.json', 'estimate.json', 'lifecycle.json', 'correspondence.json',
         'next_invoice.json', 'agreement.json', 'order-monthly-rate.txt', 'service-log.txt')
MONTH_NAMES = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
               'November', 'December')
CONTRACTS = money_link.ROOT / 'fixtures' / 'template_builder_demo'


def month_name(month):
    return MONTH_NAMES[int(month[5:7]) - 1]


def _valid_id(value):
    return isinstance(value, str) and 0 < len(value) <= 64 and '/' not in value and not value.startswith('.') \
        and all(c.isalnum() or c in '-_' for c in value)


def documents():
    """Document ids that carry authored claim evidence (a lifecycle.json)."""
    return sorted(p.parent.name for p in money_link.EVIDENCE.glob('*/lifecycle.json') if _valid_id(p.parent.name))


def load_inputs(document_id):
    """The authored inputs of one document's claim, checked for internal consistency; None when none are on file."""
    if not _valid_id(document_id) or not (money_link.EVIDENCE / document_id / 'lifecycle.json').is_file():
        return None
    folder = money_link.EVIDENCE / document_id
    raw = {name: (folder / name).read_bytes() for name in FILES}
    read = lambda name: json.loads(raw[name])
    inputs = {name.split('.')[0].replace('-', '_'): (read(name) if name.endswith('.json') else raw[name].decode())
              for name in FILES}
    inputs['input_sha256'] = {name: sha256(raw[name]).hexdigest() for name in FILES}
    life, usage, invoice, overlay, nxt = inputs['lifecycle'], inputs['usage'], inputs['invoice'], inputs['overlay'], inputs['next_invoice']
    contract = (CONTRACTS / (document_id + '.txt')).read_text()
    supplement = life['supplement']
    citation = nxt['unchanged_sla']['citation']
    spans = life['usage']['eligible_intervals']
    minutes = sum((instant(s['end']) - instant(s['start'])).total_seconds() for s in spans) / 60
    line = life['invoice']['lines'][0]
    scope = life['claim_scope']
    if (sha256(inputs['service_log'].encode()).hexdigest() != supplement['artifact']['body_sha256']
            or supplement['artifact']['body_sha256'] != supplement['verification']['body_sha256']
            or contract[citation['start']:citation['end']] != citation['quote']
            or sha256(contract.encode()).hexdigest() != citation['source_sha256']
            or sha256(citation['quote'].encode()).hexdigest() != citation['quote_sha256']
            or minutes != usage['unavailable_minutes'] or life['usage']['eligible_downtime_minutes'] != usage['unavailable_minutes']
            or life['usage']['month'] != usage['month'] != scope['month']
            or life['invoice']['id'] != invoice['id'] or line['net'] != invoice['lines'][0]['amount']
            or line['id'] != overlay['fee_line_ref'] or len(life['invoice']['lines']) != 1
            or (scope['account'], scope['contract'], scope['service'], scope['invoice'], scope['vendor'])
            != (overlay['account'], overlay['agreement'], overlay['product'], invoice['id'], usage['vendor'])
            or nxt['scope']['invoice'] != nxt['invoice']['id']):
        raise ValueError('The authored claim inputs for ' + document_id + ' disagree with one another.')
    return inputs


def source_scopes():
    """(subject prefix, month, Scope) for every authored claim: the claim month and the next invoice's month.

    The setup script enrols one signed source per role for each, exactly as it does for Northwind's months."""
    rows = []
    for document_id in documents():
        inputs = load_inputs(document_id)
        for scope in (inputs['lifecycle']['claim_scope'], inputs['next_invoice']['scope']):
            rows.append((document_id + '-' + scope['month'], scope['month'], Scope(**scope)))
    return rows


def restated_document(manifest):
    """The engine's restated clause text, rebuilt from its own citations and checked against its SHA-256."""
    text = ''
    for citation in sorted(manifest['citations'], key=lambda c: c['start']):
        text += '\n' * (citation['start'] - len(text)) + citation['quote']
    text += '\n'
    if sha256(text.encode()).hexdigest() != manifest['document']['sha256']:
        raise ValueError('The restated terms could not be rebuilt exactly from the engine\'s citations.')
    return dict(name=manifest['document']['name'], uri=manifest['document']['uri'],
                classification=manifest['document']['classification'], text=text)


def reading_digest(entry):
    return fingerprint(dict(build_id=entry['build_id'], reading_id=entry['reading_id'], template=entry['template'],
                            vendor=entry['vendor'], document=entry['document'], values=entry['values']))


def build_package(entry, inputs):
    """The case's package in the shape `WorkspaceWorkflow` takes (as `fixtures/northwind/loader.py` builds Northwind's)."""
    from fixtures.northwind.loader import _agreement, _invoice, intake_scope
    overlay_doc = inputs['overlay']
    manifest, overlay = money_link.overlay_from_values(entry['values'], vendor=entry['vendor'], document=dict(
        overlay_doc, name='Template reading %s of %s' % (entry['reading_id'], entry['document']['id']),
        uri='urn:uptime:template-reading:%s:%s' % (entry['build_id'], entry['reading_id'])))
    life, nxt = inputs['lifecycle'], inputs['next_invoice']
    if intake_scope(manifest, overlay_doc, life['claim_scope']) != life['claim_scope'] or intake_scope(manifest, overlay_doc, nxt['scope']) != nxt['scope']:
        raise ValueError('The read terms belong to a claim family whose scope differs from the enrolled sources.')
    pricing = deepcopy(inputs['agreement'])
    for version in pricing['versions']:
        for rate in version['rates']:
            rate['fixed_monthly'].update(source_text=inputs['order_monthly_rate'],
                                         source_sha256=inputs['input_sha256']['order-monthly-rate.txt'])
    supplement = deepcopy(life['supplement'])
    supplement['artifact'].pop('content_file')
    supplement['artifact']['content'] = inputs['service_log']
    unchanged = dict(nxt['unchanged_sla'], sla_source_sha256=manifest['document']['sha256'])
    settlement = dict(nxt, invoice_input=nxt['invoice'], invoice=_invoice(nxt['invoice']), unchanged_sla=unchanged)
    month = life['claim_scope']['month']
    return dict(tenant='bears', document=restated_document(manifest), overlay=overlay_doc, manifest=manifest, bound_overlay=overlay,
                pricing_agreement=_agreement(pricing), pricing_agreement_input=pricing,
                months=[dict(month=month, invoice=_invoice(life['invoice']), invoice_input=life['invoice'], usage=life['usage'],
                             scope=life['claim_scope'], citations=[])],
                settlement=settlement, citations=[unchanged['citation']], supplements=[supplement],
                correspondence=inputs['correspondence'],
                input_sha256=dict(inputs['input_sha256'], **{'settlement_invoice.json': inputs['input_sha256']['next_invoice.json'],
                                                              'reading': reading_digest(entry)}))


def fee_registry(package):
    """The governing fee of the next invoice, from the authored order form (the existing fee resolver checks it)."""
    from .governing_fees import FeeEntry, FeeRegistry
    row, overlay = package['settlement'], package['bound_overlay']
    return FeeRegistry((FeeEntry(package['manifest']['agreement'] + '-fee-' + row['month'], package['tenant'], Scope(**row['scope']),
                                 overlay['plan'], overlay['fee_line_ref'], package['pricing_agreement'], row['invoice'],
                                 package['manifest']['document']['sha256'], fingerprint(package['manifest']), fingerprint(overlay)),))


VENDOR_ID_SHAPE = re.compile(r'[a-z0-9][a-z0-9-]{0,62}[a-z0-9]')


def catalog(document_id):
    """The document's authored catalog data (`catalog.json`): the installation id its case workspace uses and the
    engine controls written from its contract text. Data, not code: no vendor is named in this package.

    Kept outside `input_sha256`, so a case workspace opened before this file existed keeps its package digest."""
    data = json.loads((money_link.EVIDENCE / document_id / 'catalog.json').read_text())
    vendor_id, rows = data.get('vendor_id'), data.get('controls')
    if (data.get('schema') != 'authored-claim-catalog/1' or not isinstance(vendor_id, str) or not VENDOR_ID_SHAPE.fullmatch(vendor_id)
            or not isinstance(rows, list) or not 1 <= len(rows) <= 60 or not isinstance(data.get('control_base'), dict)
            or any(not isinstance(r, dict) or set(r) != {'name', 'facts', 'expected'} for r in rows)):
        raise ValueError('The authored catalog data for ' + document_id + ' is malformed.')
    return data


def controls(overlay, document_id):
    """Engine controls for installing the read terms: authored per document from its contract text, never from the
    read. A misread term fails a control and nothing is installed."""
    data = catalog(document_id)
    base = dict(data['control_base'], agreement=overlay['agreement'], account=overlay['account'], product=overlay['product'],
                plan=overlay['plan'], fee_line_ref=overlay['fee_line_ref'])
    return [dict(name='Source control: ' + row['name'], facts=dict(base, **row['facts']), expected=dict(row['expected']))
            for row in data['controls']]


def preflight(entry, inputs):
    """Before anything is created: the package builds and the read terms pass the authored controls in the engine."""
    from .vendor_eval import evaluate as engine
    package = build_package(entry, inputs)
    failed = []
    for control in controls(package['overlay'], entry['document']['id']):
        result = engine(package['manifest'], package['bound_overlay'], control['facts'], 'bears')
        if any(result.get(k) != v for k, v in control['expected'].items()):
            failed.append(control['name'])
    if failed:
        raise ValueError('The read terms failed authored controls, so nothing was installed: ' + '; '.join(failed))
    return package


class TemplateClaim(WorkspaceWorkflow):
    """The existing workflow over one case workspace; only its opening and its projection are its own."""

    def __init__(self, bench, auth, config, *, entry, inputs, main):
        self.entry, self.inputs, self.main = deepcopy(entry), inputs, main
        super().__init__(bench, auth, config)
        name = month_name(self.claim_month)
        self.labels = dict(LABELS, **{'approve-claim': 'Approve ' + name + ' claim', 'submit-claim': 'File ' + name + ' claim',
                                      OPEN: 'Approve ' + name + ' claim',
                                      'install-agreement': 'Install the read terms and open the claim',
                                      'receive-status': 'Receive the status record', 'receive-impact': 'Receive the customer impact record',
                                      'receive-coverage': 'Receive the month\'s coverage', 'receive-month-invoice': 'Receive the ' + name + ' invoice'})

    def _authorize(self, p, write=False):
        self.main._authorize(p, write)  # the main workspace's tenant, policy and scripted reviewer rules hold here too
        super()._authorize(p, write)

    def _offers(self, p, claim):
        if self.main.bench.setting(p)['mode'] == 'OBSERVE':
            return []
        return super()._offers(p, claim)

    def _record(self, operation, cls, authority, intent_id=None, detail=None):
        with database(self.bench.path) as db, db:
            db.execute('INSERT INTO workspace_workflow_step(operation,class,authority,state,at,recorded_at,intent_id,detail,timing) '
                       'VALUES(?,?,?,?,?,?,?,?,?)', (operation, cls, json.dumps(authority, sort_keys=True), 'COMPLETED',
                                                     self.now().isoformat(), datetime.now(UTC).isoformat(), intent_id, detail,
                                                     json.dumps(dict(clock='WORKSPACE', at=self.now().isoformat()))))

    def month_events(self):
        """The claim month's signed records, as the setup script builds Northwind's (status, impact, coverage, invoice)."""
        row = self.months[self.claim_month]; usage, invoice = row['usage'], row['invoice']
        scope = self.scopes[self.claim_month]; prefix = self.entry['document']['id'] + '-'
        span = usage['eligible_intervals'][0]; interval = {k: span[k] for k in ('start', 'end')}
        return [('receive-status', Delivery(event_id=usage['status_event_id'], scope=scope, body=dict(kind='status', **interval))),
                ('receive-impact', Delivery(event_id=prefix + 'impact-' + self.claim_month, scope=scope,
                                            body=dict(kind='impact', affected=span['affected'], exclusion=span['exclusion'], **interval))),
                ('receive-coverage', Delivery(event_id=usage['monitor_ref'], scope=scope, body=dict(
                    kind='coverage', start=usage['start'], end=usage['end'], complete=True, exclusions_removed=usage['exclusions_removed'],
                    incident_ids=[usage['incident_id']], total_eligible_minutes=usage['eligible_downtime_minutes']))),
                ('receive-month-invoice', Delivery(event_id=prefix + 'invoice-' + self.claim_month, scope=scope, body=dict(
                    kind='invoice', lines=[dict(id=line.id, kind='affected_api', amount=str(line.net)) for line in invoice.lines])))]

    def _install(self, p):
        from . import vendor_registry as registry
        from .vendor_registry import TestSubmission
        path = self.bench.path
        try:
            current = registry.get_vendor(path, p, self.installation)
        except KeyError:
            current = None
        if current and current.get('state') == 'ACTIVE':
            if current['manifest']['document']['sha256'] != self.package['manifest']['document']['sha256']:
                raise ValueError('A different agreement is already installed in this case workspace.')
            return current
        state = registry.install(path, p, self.installation, dict(document=self.package['document'], overlay=self.package['overlay']))
        if (state.get('manifest') or {}).get('document', {}).get('sha256') != self.package['manifest']['document']['sha256']:
            raise ValueError('The catalog compiled different terms from the restated reading: ' + str(state.get('reason') or ''))
        state = registry.submit_tests(path, p, self.installation, TestSubmission.model_validate(
            dict(revision=state['revision'], tests=controls(self.package['overlay'], self.entry['document']['id']))), governing_fees=())
        failed = [row.get('name') for row in state['checks'] if not row['passed']]
        if failed:
            raise ValueError('The read terms failed authored controls, so they were not installed: ' + '; '.join(map(str, failed)))
        for operation in ('approve', 'activate'):
            offer = next((a for a in state['actions'] if a['operation'] == operation), None)
            if offer is None:
                raise ValueError('The agreement catalog did not offer ' + operation + '.')
            state = registry.act(path, p, self.installation, offer['id'], governing_fees=self.governing_fees, trusted_now=self.now)
        return state

    async def open_and_approve(self, p, offer):
        """The first decision: install the read terms, open the claim, receive its month, check it, approve its packet."""
        self._authorize(p, True)
        with database(self.bench.path) as db, db:
            old = db.execute('SELECT status,expected,actor FROM workspace_workflow_intent WHERE id=?', (offer['id'],)).fetchone()
            if old and (old['actor'] != p.subject or json.loads(old['expected'])['pin'] != offer['pin']):
                raise PermissionError('This opening belongs to a different reviewer or a different reading.')
            if not old:
                if db.execute("SELECT 1 FROM workspace_workflow_intent WHERE status='EXECUTING'").fetchone():
                    raise ValueError('Resolve the existing interrupted action first.')
                db.execute('INSERT INTO workspace_workflow_intent VALUES(?,?,?,?,?,?,?,?)',
                           (offer['id'], OPEN, encoded(dict(pin=offer['pin'])), p.subject, 'EXECUTING', self.now().isoformat(), None, None))
            elif old['status'] == 'COMPLETED':
                return
        authority = dict(kind='APPROVED_OPERATION', actor=p.subject, approval_action=OPEN, approval_digest=fingerprint(offer['pin']),
                         approved_at=self.now().isoformat())
        if self._vendor(p, self.installation) is None or self._vendor(p, self.installation).get('state') != 'ACTIVE':
            state = self._install(p)
            self._record('install-agreement', 'INSTALLATION', authority, offer['id'],
                         'Agreement %s installed from template %s (version %s); controls passed.' % (
                             self.package['manifest']['agreement'], self.entry['template']['id'], state.get('active_version')))
        self.inbox.create(p, Claim(claim_id=self.claim_id, scope=self.scopes[self.claim_month]))
        for operation, event in self.month_events():
            source = {'status': 'status', 'impact': 'customer', 'coverage': 'status', 'invoice': 'billing'}[event.body.kind]
            receipt = await self.deliver(self.claim_id, event)
            if not receipt.get('refused'):
                claim = self._claim(p)
                if sum(1 for e in claim['evidence'] if e['detail'].split(' · ')[0] == event.event_id) and not any(
                        s['intent_id'] == offer['id'] and s['authority'].get('event_id') == event.event_id for s in coordinator.steps(self)):
                    self._record(operation, 'INTAKE', dict(kind='EVENT_INTAKE', event_id=event.event_id,
                                                           source_subject=self.senders[(self.claim_month, source)].subject), offer['id'])
        claim = self._claim(p)
        expected = offer['pin']
        if (claim is None or claim.get('outcome') != 'ELIGIBLE' or claim.get('amount') != expected['amount']
                or claim.get('contract_source_sha256') != self.package['manifest']['document']['sha256']):
            with database(self.bench.path) as db, db:
                db.execute("UPDATE workspace_workflow_intent SET status='COMPLETED',result_ref=?,error=? WHERE id=?",
                           (claim['state_sha256'] if claim else None, 'claim differs from the estimate shown', offer['id']))
            raise ValueError('The claim the engine assessed (%s %s) is not the estimate that was approved (%s); nothing was approved.'
                             % (claim and claim.get('outcome'), claim and claim.get('amount'), expected['amount']))
        with database(self.bench.path) as db, db:
            db.execute("UPDATE workspace_workflow_intent SET status='COMPLETED',result_ref=? WHERE id=?", (claim['state_sha256'], offer['id']))
        descriptor = self._descriptor(p, claim)
        if not descriptor or descriptor['operation'] != 'approve-claim':
            raise ValueError('The opened claim does not offer its approval.')
        await self._run(p, descriptor['id'], person=True)
        if self.automation:
            await coordinator.advance(self, p)

    async def _run(self, p, identity, *, person):
        with database(self.bench.path) as db:
            old = db.execute('SELECT operation,expected FROM workspace_workflow_intent WHERE id=?', (identity,)).fetchone()
        if old and old['operation'] == OPEN:
            # Resuming an interrupted opening repeats only what did not complete; every part is idempotent.
            return await self.open_and_approve(p, dict(id=identity, pin=json.loads(old['expected'])['pin']))
        return await super()._run(p, identity, person=person)

    def projection(self, p, base):
        """The existing workflow's claim, ledger and bill figures over this case, in the projection the case page reads."""
        self._authorize(p)
        claim = self._claim(p)
        try:
            balance = self.bench.allocations.bill_balance(p.tenant, self.bill_id)
        except KeyError:
            balance = None
        bill_view = dict(id=None, month=None, original_amount=None, outstanding_amount=None)
        if balance is not None:
            with database(self.bench.path) as db:
                receipt = db.execute('SELECT payload,digest FROM workspace_workflow_invoice WHERE id=?', (self.bill_id,)).fetchone()
            if not receipt or fingerprint(json.loads(receipt['payload'])) != receipt['digest']:
                raise ValueError('Eligible invoice has no intact source authority receipt.')
            proof = json.loads(receipt['payload'])
            bill_view = dict(id=self.bill_id, month=self.settlement['month'], original_amount=balance['total'],
                             outstanding_amount=balance['remaining_eligible'],
                             **{k: proof[k] for k in ('issued_at', 'service_start', 'service_end', 'known_at', 'source_sha256',
                                                      'governing_pricing_version', 'award_eligibility_version', 'sla_source_sha256', 'source_ref')})
        ledger = claim['ledger'] if claim else {}
        reconciliations = claim.get('reconciliations', []) if claim else []
        records = dict(award=None, credit=None, application=None)
        if len(reconciliations) == 1:
            rec = reconciliations[0]; records['award'] = rec['award_id']
            records['credit'] = rec['credit_ids'][0] if len(rec['credit_ids']) == 1 else None
            records['application'] = rec['application_ids'][0] if len(rec['application_ids']) == 1 else None
        posted = records['credit'] is not None
        if posted and not self.provider.verified_read(p.tenant, records['credit'], 'credit'):
            raise ValueError('A posted local credit has no matching provider readback.')
        vendor = self._vendor(p, self.installation)
        invoice = self.months[self.claim_month]['invoice']
        view = dict(base, workspace_instance=self.instance, as_of=self.now().isoformat(),
                    claim=dict(base['claim'], state=claim['stage'] if claim else 'NOT_OPENED', amount=claim['amount'] if claim else None,
                               outcome=claim['outcome'] if claim else None, filing_cutoff=claim.get('filing_cutoff') if claim else None,
                               pending_approvals=sorted(a['id'] for a in claim['actions'] if a['id'].startswith('approve-')) if claim else [],
                               requested_artifact=claim.get('requested_artifact') if claim else None,
                               receipt_id=claim['submissions'][-1]['id'] if claim and claim['submissions'] else None,
                               eligibility_version=claim['contract_version'] if claim else None,
                               sla_source_sha256=claim['contract_source_sha256'] if claim else None),
                    connection=dict(destination=self.provider.destination, status='CONNECTED',
                                    receipt_status='VERIFIED_LOCAL_READBACK' if posted else 'NOT_POSTED'),
                    ledger=dict(destination=self.provider.destination, estimated=claim['amount'] if claim else base['ledger']['estimated'],
                                claimed=ledger.get('claimed', '0.00'), awarded=ledger.get('awarded', '0.00'), posted=ledger.get('posted', '0.00'),
                                applied=ledger.get('applied', '0.00'), currency=invoice.currency, record_ids=records,
                                unapplied_credit=reconciliations[0]['unapplied_posted'] if len(reconciliations) == 1 else '0.00', bill=bill_view),
                    audit=[dict(at=r['at'], event=r['event'], ref=r.get('event_id', r.get('digest', ''))) for r in (claim or {}).get('timeline', [])],
                    next_actions=self._offers(p, claim), automation=coordinator.view(self, p, claim))
        view['contract'] = dict(base['contract'], version=vendor.get('active_version') if vendor else None)
        return view

    def view(self, p):
        # WorkspaceWorkflow.act returns this; the case page reads TemplateClaims.view, which calls projection().
        return {}


class TemplateClaims:
    """Every authored template claim in one served workspace, by document id."""

    def __init__(self, app, directory, senders):
        self.app, self.root, self.senders = app, Path(directory).resolve() / 'template-claims', dict(senders)
        self.lock, self.cases = RLock(), {}

    @property
    def service(self):
        return getattr(self.app.state, 'template_builds', None)

    @property
    def main(self):
        return self.app.state.workflow

    # ---- what can be claimed
    def _candidates(self):
        """document id -> (latest accepted reading, inputs, SHADOW agreement) for readings with an estimated credit."""
        service, found = self.service, {}
        if service is None or not hasattr(service, 'approved_readings'):
            return found
        for entry in service.approved_readings():
            document_id = (entry.get('document') or {}).get('id')
            if document_id not in documents():
                continue
            previous = found.get(document_id)
            if previous and str(previous[0].get('read_at')) > str(entry.get('read_at')):
                continue
            inputs = load_inputs(document_id)
            agreement = money_link.evaluate(entry, money_link.load_evidence(document_id))
            if agreement.get('credit') and agreement['credit'].get('stage') == 'ESTIMATED':
                found[document_id] = (entry, inputs, agreement)
        return found

    def _stored(self, document_id):
        path = self.root / document_id / 'case.json'
        return json.loads(path.read_text()) if path.is_file() else None

    def _case(self, document_id):
        """The opened case for a document, rebuilt from its stored reading after a restart; None before it opens."""
        with self.lock:
            if document_id in self.cases:
                return self.cases[document_id]
            stored = self._stored(document_id)
            if stored is None:
                return None
            self.cases[document_id] = self._construct(document_id, stored['entry'])
            return self.cases[document_id]

    def _construct(self, document_id, entry):
        from .auth import bind_workspace
        from .correspondence import CorrespondenceDesk
        from .v4_routes import resolve_active
        from .workbench import Workbench
        inputs = load_inputs(document_id)
        package = build_package(entry, inputs)
        fees = fee_registry(package)
        folder = self.root / document_id
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = folder / 'case.db'
        bind_workspace(path, 'replay', True, 'bears')
        bench = Workbench(path, 'replay')
        bench.inbox = CorrespondenceDesk(path, active_resolver=partial(resolve_active, path, governing_fees=fees))
        months = [inputs['lifecycle']['claim_scope']['month'], inputs['next_invoice']['scope']['month']]
        senders = {(month, role): self.senders[(month, role)] for month in months for role in ROLES
                   if self.senders.get((month, role)) is not None and self.senders[(month, role)].subject.startswith(document_id + '-')}
        if len(senders) != len(months) * len(ROLES):
            raise PermissionError('This workspace has no enrolled signed sources for this claim; create a new workspace.')
        month = months[0]
        vendor_id = catalog(document_id)['vendor_id']
        config = dict(package=package, installation=vendor_id, onboarding_installation=vendor_id + '-none',
                      claim_month=month, bill_month=month, claim_ids={month: 'inbox-' + document_id + '-' + month},
                      scopes={month: Scope(**package['months'][0]['scope'])}, senders=senders,
                      clock_start=inputs['lifecycle']['clock_start'], clock_steps={}, correspondence=deepcopy(inputs['correspondence']),
                      provider_path=folder / 'local-ledger.db', governing_fees=fees, routine_automation=self.main.automation)
        return TemplateClaim(bench, self.main.auth, config, entry=entry, inputs=inputs, main=self.main)

    # ---- the projection
    def _reading(self, entry):
        build = None
        try:
            build = self.service.get(entry['build_id']) if self.service is not None and hasattr(self.service, 'get') else None
        except (KeyError, ValueError):
            build = None
        template = dict((build or {}).get('template') or {}, **entry['template'])
        # What the reading's own record says took part: values by the template's rules (model_calls counts the calls
        # that produced values), and separately Jev's answer on whether the document follows the template, if asked.
        record = next((r for r in (build or {}).get('readings') or [] if r.get('id') == entry['reading_id']), {})
        guard = next((g for g in record.get('guards') or [] if g.get('id') == 'template_match'), None)
        jev = record.get('jev_template') if isinstance(record.get('jev_template'), dict) else None
        return dict(read_by='FIXED_RULES', template_id=template.get('id'), template_sha256=template.get('sha256'),
                    built_by='Claude agents: three readers and a template builder', approved_by=template.get('approved_by'),
                    approved_at=template.get('approved_at'), build_id=entry['build_id'], reading_id=entry['reading_id'],
                    read_at=entry.get('read_at'), document_id=entry['document'].get('id'), document_title=entry['document'].get('title'),
                    model_calls=record.get('model_calls'), values=dict(entry['values']),
                    jev_template=dict(asked=True, probability=jev.get('probability'), model=jev.get('model'),
                                      ok=guard.get('ok') if guard else None) if jev else dict(asked=False) if record else None)

    def _pin(self, entry, inputs, agreement):
        return dict(reading=reading_digest(entry), reading_id=entry['reading_id'], template_sha256=entry['template']['sha256'],
                    evidence=inputs['input_sha256'], month=agreement['month'], amount=agreement['credit']['amount'],
                    currency=agreement['credit']['currency'])

    def _offer(self, p, document_id, entry, inputs, agreement):
        main = self.main
        if (not main.auth.approvals_enabled or p.role != 'reviewer' or p.subject != SCRIPT
                or main.bench.setting(p)['mode'] == 'OBSERVE'):
            return None
        pin = self._pin(entry, inputs, agreement)
        return dict(id='action-' + fingerprint([main.instance, document_id, p.subject, OPEN, pin]), operation=OPEN,
                    label='Approve ' + month_name(agreement['month']) + ' claim', group='claim', pin=pin)

    def _base(self, p, document_id, entry, inputs, agreement):
        from .finance_view import summarize
        life, invoice = inputs['lifecycle'], inputs['invoice']
        reading = self._reading(entry)
        text = (CONTRACTS / (document_id + '.txt')).read_text()
        month = life['claim_scope']['month']
        claim_id = 'inbox-' + document_id + '-' + month
        return dict(case_id=document_id, kind='template_claim', reading=reading,
                    company={'name': entry['document'].get('customer')}, vendor=entry['vendor'], as_of=life['clock_start'],
                    contract=dict(title=entry['document'].get('title'), version=None, ref='urn:uptime:template-reading:%s:%s' % (entry['build_id'], entry['reading_id']),
                                  summary=text, documents=[dict(title=entry['document'].get('title'), ref='/fixtures/template_builder_demo/' + document_id + '.txt',
                                                                version='template ' + str(reading['template_id']), effective_at=inputs['overlay']['effective_from'] + 'T00:00:00Z',
                                                                description='Values read by fixed rules: approved template %s (SHA-256 %s), reading %s.'
                                                                            % (reading['template_id'], reading['template_sha256'], reading['reading_id']),
                                                                citations=[], source_sha256=sha256(text.encode()).hexdigest())]),
                    reviewer=dict(name='Dana Reyes', role='Contract reviewer', authority_kind='SCRIPTED_REVIEWER', principal=SCRIPT),
                    months=[dict(month=month, outcome='ELIGIBLE', amount=agreement['credit']['amount'], currency=agreement['credit']['currency'],
                                 reason=agreement['evaluation'], trace=[agreement['evaluation']], calculation=[agreement['evaluation']], inputs={},
                                 citations=[], invoice=dict(id=invoice['id'], issued_at=life['invoice']['issued_at'],
                                                            service_start=life['invoice']['lines'][0]['start'], service_end=life['invoice']['lines'][0]['end']),
                                 evidence=[dict(label='Unavailable minutes (authored, exclusion-adjusted)', ref=inputs['usage']['monitor_ref'],
                                                value=str(inputs['usage']['unavailable_minutes']))])],
                    price_finding=None, onboarding=None,
                    claim=dict(id=claim_id, month=month, state='NOT_OPENED', amount=None, currency=agreement['credit']['currency'],
                               filing_cutoff=None, pending_approvals=[], requested_artifact=None, receipt_id=None),
                    connection=dict(destination='Local ledger', status='CONNECTED', receipt_status='NOT_POSTED'),
                    ledger=dict(destination='Local ledger', estimated=agreement['credit']['amount'], claimed='0.00', awarded='0.00',
                                posted='0.00', applied='0.00', currency=agreement['credit']['currency'],
                                record_ids=dict(award=None, credit=None, application=None), unapplied_credit='0.00',
                                bill=dict(id=None, month=None, original_amount=None, outstanding_amount=None)),
                    audit=[], estimate=agreement), summarize

    def view(self, p, document_id):
        self.main._authorize(p)
        case = self._case(document_id)
        if case is not None:
            entry, inputs = case.entry, case.inputs
            agreement = money_link.evaluate(entry, money_link.load_evidence(document_id))
            base, summarize = self._base(p, document_id, entry, inputs, agreement)
            view = case.projection(p, base)
            view['reading_current'] = self._candidates().get(document_id, (entry,))[0]['reading_id'] == entry['reading_id']
        else:
            found = self._candidates().get(document_id)
            if found is None:
                raise KeyError(document_id)
            entry, inputs, agreement = found
            base, summarize = self._base(p, document_id, entry, inputs, agreement)
            offer = self._offer(p, document_id, entry, inputs, agreement)
            view = dict(base, next_actions=[{k: offer[k] for k in ('id', 'label', 'group')}] if offer else [],
                        automation=dict(enabled=self.main.automation, state='PAUSED',
                                        pause=dict(reason='APPROVAL_REQUIRED', detail='A reviewer approves the claim for the estimate shown.',
                                                   operation=OPEN, since=None),
                                        steps=[], counts=dict(person_decisions=0, automatic_steps=0)))
        view['finance'] = summarize(view)
        return view

    async def act(self, p, document_id, identity):
        self.main._authorize(p, True)
        with self.lock:
            case = self._case(document_id)
            if case is None:
                found = self._candidates().get(document_id)
                if found is None:
                    raise KeyError(document_id)
                entry, inputs, agreement = found
                offer = self._offer(p, document_id, entry, inputs, agreement)
                if offer is None or offer['id'] != identity:
                    raise ValueError('Stale or unavailable workflow action.')
                preflight(entry, inputs)
                case = self._construct(document_id, entry)
                stored = self.root / document_id / 'case.json'
                stored.write_text(json.dumps(dict(entry=entry, opened_by=p.subject, pin=offer['pin']), sort_keys=True, indent=1))
                stored.chmod(0o600)
                self.cases[document_id] = case
                await case.open_and_approve(p, offer)
            else:
                await case.act(p, identity)
        return self.view(p, document_id)

    # ---- the portfolio row
    def row(self, p, document_id):
        """The claim's real stage and who is next, for the portfolio row of this agreement; None if not claimable."""
        try:
            view = self.view(p, document_id)
        except (KeyError, ValueError, PermissionError):
            return None
        stages = [r for r in view['finance']['stages'] if r['status'] == 'recorded']
        reached = [r for r in stages if r['stage'] != 'estimated']
        stage = (reached or stages or [None])[-1]
        automation = view.get('automation') or {}
        reason = (automation.get('pause') or {}).get('reason')
        nxt = (None if automation.get('state') == 'COMPLETE' else 'Reviewer' if view.get('next_actions')
               else 'Uptime · automatic' if reason == 'ROUTINE_READY' else 'Vendor' if reason == 'WAITING' else 'Reviewer' if reason else None)
        # `steps` carries only what the portfolio's counters read (who authorised each step and whether it completed),
        # and `audit` the case's own history, each a read-only copy of this case's records.
        return dict(case_id=document_id, href='#template-claim/' + document_id, stage=stage['stage'] if stage else None,
                    label=('Estimated · not claimed' if stage and stage['stage'] == 'estimated' else stage['label'] if stage else None),
                    amount=stage['amount'] if stage else None, currency=view['ledger'].get('currency'), next=nxt,
                    claim_state=view['claim']['state'], claim_id=view['claim']['id'], month=view['claim']['month'],
                    vendor=view['vendor'], as_of=view['as_of'],
                    steps=[dict(seq=s.get('seq'), operation=s['operation'], label=s.get('label'), state=s['state'], at=s.get('at'),
                                authority=dict(kind=(s.get('authority') or {}).get('kind'))) for s in (view.get('automation') or {}).get('steps', [])],
                    audit=list(view.get('audit') or []))

    def listing(self, p):
        """Every claimable or opened template claim in this workspace, as portfolio, Cases and Activity read them."""
        self.main._authorize(p)
        rows = [self.row(p, document_id) for document_id in documents()]
        return [row for row in rows if row is not None]


def register_template_claims(app, auth):
    """Routes; answer 404 until `connect` is called for a served workspace."""
    from fastapi import Depends
    from .correspondence_types import Empty

    def claims():
        service = getattr(app.state, 'template_claims', None)
        if service is None:
            raise KeyError('template claims')
        return service

    @app.get('/api/template-claims')
    def listing(p=Depends(auth.actor)):
        service = getattr(app.state, 'template_claims', None)
        return {'claims': service.listing(p) if service is not None else []}

    @app.get('/api/template-claims/{document_id}')
    def view(document_id: str, p=Depends(auth.actor)):
        return {'workflow': claims().view(p, document_id)}

    @app.post('/api/template-claims/{document_id}/actions/{identity}')
    async def action(document_id: str, identity: str, body: Empty, p=Depends(auth.reviewer)):
        return {'workflow': await claims().act(p, document_id, identity)}


def claim_marker(entry, agreement):
    """`{"available": true, "case": <document id>}` when a claim can be opened for this reading, else None."""
    document_id = (entry.get('document') or {}).get('id')
    credit = (agreement or {}).get('credit') or {}
    if document_id in documents() and credit.get('stage') == 'ESTIMATED' and credit.get('amount') is not None:
        return {'available': True, 'case': document_id}
    return None


def connect(app, directory, senders):
    """Turn on template claims for a served workspace and give the portfolio rows their claim stage."""
    service = TemplateClaims(app, directory, senders)
    app.state.template_claims = service
    builds = getattr(app.state, 'template_builds', None)
    estimate = getattr(builds, 'on_reading', None)
    if estimate is not None:
        def on_reading(entry):
            # The money link's agreement, marked when a claim can be opened for it (the build page's link reads this).
            agreement = estimate(entry)
            marker = claim_marker(entry, agreement) if isinstance(agreement, dict) else None
            return dict(agreement, claim=marker) if marker else agreement
        builds.on_reading = on_reading
    workflow = getattr(app.state, 'workflow', None)
    lister = getattr(workflow, 'template_opportunities', None) if workflow is not None else None
    if lister is not None:
        def with_claims(p):
            rows = list(lister(p))
            for row in rows:
                document_id = (row.get('agreement') or {}).get('document_id')
                if document_id in documents():
                    claim = service.row(p, document_id)
                    if claim is not None:
                        row['claim'] = claim
            return rows
        workflow.template_opportunities = with_claims
    return service
