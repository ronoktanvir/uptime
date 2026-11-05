"""Configured fictional workflow composition over the production services.

No financial calculation lives here. Local-ledger readback is a local
self-consistency check, never an external provider or human attestation.
"""
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
from threading import RLock
from uuid import UUID, uuid4, uuid5

from .contracts import Source, fingerprint
from .storage import database,stored_cases
from .auth import SCRIPT
from .correspondence_types import instant
from .vendor_registry import get_vendor


def require_fixture_workspace(path):
    with database(path) as db:
        row=db.execute('SELECT mode,rehearsal,tenant FROM authority_workspace WHERE id=1').fetchone()
    if not row or tuple(row)!=('replay',1,'bears'):
        raise PermissionError('This connection requires a separately bound scripted replay workspace.')


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


class LocalLedgerProvider:
    """An operator-configured local destination with durable UUID readback."""
    destination='Local ledger'

    def __init__(self, financial_path, provider_path, instance, *, claim_id, bill_id, scope):
        self.financial_path=Path(financial_path).resolve()
        self.path=Path(provider_path).resolve()
        self.instance=str(UUID(instance))
        if (not isinstance(claim_id,str) or not claim_id.startswith('inbox-') or not bill_id
                or set(scope)!={'vendor_id','account_id','product_id','contract_id','currency'}
                or not all(isinstance(v,str) and v for v in scope.values()) or scope['currency']!='USD'):
            raise ValueError('Configure one exact claim, bill and complete financial scope.')
        self.claim_id,self.bill_id,self.scope=claim_id,bill_id,dict(scope)
        binding=encoded(dict(instance=self.instance,claim_id=claim_id,bill_id=bill_id,scope=scope))
        require_fixture_workspace(self.financial_path)
        if self.path==self.financial_path:
            raise ValueError('Provider storage must be separate from the financial transaction.')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute('PRAGMA synchronous=FULL')
            db.execute('CREATE TABLE IF NOT EXISTS local_ledger_binding (id INTEGER PRIMARY KEY CHECK(id=1),instance TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO local_ledger_binding VALUES(1,?)',(binding,))
            if db.execute('SELECT instance FROM local_ledger_binding').fetchone()[0]!=binding:
                raise ValueError('Local ledger belongs to a different workspace instance.')
            db.execute('''CREATE TABLE IF NOT EXISTS local_ledger_record (
                tenant TEXT NOT NULL,id TEXT NOT NULL,kind TEXT NOT NULL,idempotency_key TEXT NOT NULL,
                payload TEXT NOT NULL,payload_sha256 TEXT NOT NULL,recorded_at TEXT NOT NULL,
                PRIMARY KEY(tenant,id),UNIQUE(tenant,idempotency_key))''')
            for operation in ('UPDATE','DELETE'):
                db.execute(f"CREATE TRIGGER IF NOT EXISTS local_ledger_no_{operation.lower()} BEFORE {operation} ON local_ledger_record BEGIN SELECT RAISE(ABORT,'Local provider records are immutable'); END")
        self.path.chmod(0o600)
        self.failure_point=None  # Test fault injector; never configured by requests.

    def allows_case(self,case_id,scope):
        aliases=dict(vendor_id='vendor',account_id='account',product_id='service',contract_id='contract',currency='currency')
        return (case_id==self.claim_id and all(scope.get(k,scope.get(aliases[k]))==v for k,v in self.scope.items()))

    def _identity(self,tenant,kind,parents):
        if tenant!='bears':
            raise PermissionError('Local ledger tenant mismatch.')
        return 'local-ledger:'+str(uuid5(UUID(self.instance),encoded([tenant,kind,parents])))

    def credit(self,tenant,award,*,case_id):
        if not self.allows_case(case_id,award):
            raise PermissionError('Local ledger is not configured for this claim and financial scope.')
        identity=self._identity(tenant,'credit',[award['id'],award['source_ref']])
        return dict(award,id=identity,source_ref=identity,award_id=award['id'],source=Source.REPLAY.value)

    def application(self,tenant,plan,*,case_id):
        credit=self.read(tenant,plan['credit_id'])
        if (case_id!=self.claim_id or plan['bill_id']!=self.bill_id or not credit
                or not self.allows_case(case_id,credit['payload'])):
            raise PermissionError('Local ledger is not configured for this credit and eligible bill.')
        identity=self._identity(tenant,'application',[plan['credit_id'],plan['bill_id']])
        return dict(plan,id=identity,source_ref=identity)

    def _fail(self,point):
        if self.failure_point==point:
            raise RuntimeError('Injected local-provider crash: '+point)

    def read(self,tenant,identity):
        with sqlite3.connect(self.path) as db:
            db.row_factory=sqlite3.Row
            row=db.execute('SELECT * FROM local_ledger_record WHERE tenant=? AND id=?',(tenant,identity)).fetchone()
        if row is None:
            return None
        result=dict(row)
        result['payload']=json.loads(result['payload'])
        return result

    def confirm(self,tenant,action,plan,*,case_id):
        """Called after SQL validation but before the financial transaction commits."""
        require_fixture_workspace(self.financial_path)
        if action=='record-credit':
            if len(plan.get('credits',[]))!=1:
                raise ValueError('One exact credit is required for provider posting.')
            row=deepcopy(plan['credits'][0]); kind='credit'
            expected=self.credit(tenant,plan['award'],case_id=case_id)
        elif action=='apply-balance':
            row=deepcopy(plan); kind='application'
            expected=self.application(tenant,plan,case_id=case_id)
        else:
            raise ValueError('Unsupported local provider operation.')
        if row!=expected or row.get('source')!=Source.REPLAY.value:
            raise ValueError('Local provider identity or source differs from the financial plan.')
        content=encoded(row)
        payload_digest=fingerprint(row)
        identity=row['id']
        idem=fingerprint([self.instance,tenant,kind,identity])
        with sqlite3.connect(self.path,timeout=10) as db:
            db.execute('PRAGMA synchronous=FULL'); db.execute('BEGIN IMMEDIATE')
            previous=db.execute('SELECT kind,idempotency_key,payload,payload_sha256 FROM local_ledger_record WHERE tenant=? AND id=?',(tenant,identity)).fetchone()
            if previous:
                if tuple(previous)!=(kind,idem,content,payload_digest):
                    raise ValueError('Conflicting local provider idempotency replay.')
            else:
                db.execute('INSERT INTO local_ledger_record VALUES(?,?,?,?,?,?,?)',
                           (tenant,identity,kind,idem,content,payload_digest,datetime.now(UTC).isoformat()))
        self._fail('after-write')
        readback=self.read(tenant,identity)
        if (not readback or readback['id']!=identity or readback['tenant']!=tenant or readback['kind']!=kind
                or readback['idempotency_key']!=idem or readback['payload_sha256']!=payload_digest
                or encoded(readback['payload'])!=content or fingerprint(readback['payload'])!=payload_digest):
            raise ValueError('Local ledger readback does not match the exact intended record.')
        self._fail('after-readback')
        return identity


class WorkspaceWorkflow:
    """Projection and exact intents for one operator-configured authored package."""
    def __init__(self,bench,auth,config):
        require_fixture_workspace(bench.path)
        if not auth.rehearsal or auth.mode!='replay' or auth.tenant!='bears':
            raise PermissionError('A workflow cannot reinterpret this installation authority.')
        self.bench,self.auth,self.inbox=bench,auth,bench.inbox
        self.package=config['package']
        self.installation=config['installation']
        self.onboarding_installation=config['onboarding_installation']
        self.claim_month,self.bill_month=config['claim_month'],config['bill_month']
        self.claim_ids=dict(config['claim_ids']); self.scopes=dict(config['scopes'])
        self.senders=dict(config['senders']); self.clock_steps=dict(config['clock_steps'])
        self.correspondence=deepcopy(config['correspondence'])
        self.lock=RLock(); self.failure_point=None
        self.months={row['month']:row for row in self.package['months']}
        self.claim_id=self.claim_ids[self.claim_month]
        self.bill_id=self.months[self.bill_month]['invoice'].id
        overlay=self.package['overlay']
        scope=self.scopes[self.claim_month]
        if (scope.account!=overlay['account'] or scope.contract!=overlay['agreement']
                or scope.service!=overlay['product'] or scope.vendor!=self.package['manifest']['vendor']
                or set(self.scopes)!=set(self.months) or set(self.claim_ids)!=set(self.months)):
            raise ValueError('Workflow identities must match the complete verified package.')
        for month,subscription in self.scopes.items():
            if (subscription.month!=month or subscription.account!=scope.account or subscription.vendor!=scope.vendor
                    or subscription.contract!=scope.contract or subscription.service!=scope.service or subscription.currency!='USD'
                    or subscription.invoice!=self.months[month]['invoice'].id):
                raise ValueError('A configured monthly source scope differs from its package.')
        self.package_digest=fingerprint(dict(inputs=self.package['input_sha256'],installation=self.installation,
            onboarding_installation=self.onboarding_installation,claim_ids=self.claim_ids,claim_month=self.claim_month,
            bill_month=self.bill_month,scopes={k:v.model_dump() for k,v in self.scopes.items()},
            correspondence=self.correspondence,clock_start=config['clock_start'],clock_steps=self.clock_steps))
        with database(bench.path) as db,db:
            db.execute('''CREATE TABLE IF NOT EXISTS workspace_workflow (
                id INTEGER PRIMARY KEY CHECK(id=1),instance TEXT NOT NULL,package_digest TEXT NOT NULL,event_clock TEXT NOT NULL)''')
            db.execute('INSERT OR IGNORE INTO workspace_workflow VALUES(1,?,?,?)',
                       (str(uuid4()),self.package_digest,instant(config['clock_start']).isoformat()))
            row=db.execute('SELECT instance,package_digest FROM workspace_workflow WHERE id=1').fetchone()
            if row['package_digest']!=self.package_digest:
                raise ValueError('Workspace package changed; create a new isolated workspace.')
            self.instance=row['instance']
            db.execute('''CREATE TABLE IF NOT EXISTS workspace_workflow_intent (
                id TEXT PRIMARY KEY,operation TEXT NOT NULL,expected TEXT NOT NULL,actor TEXT NOT NULL,
                status TEXT NOT NULL,created_at TEXT NOT NULL,result_ref TEXT,error TEXT)''')
        self.inbox.clock=self.now
        ledger_scope=dict(vendor_id=scope.vendor,account_id=scope.account,product_id=scope.service,
                          contract_id=scope.contract,currency=scope.currency)
        self.provider=LocalLedgerProvider(bench.path,config['provider_path'],self.instance,
            claim_id=self.claim_id,bill_id=self.bill_id,scope=ledger_scope)
        self.bench.settlement_provider=self.provider

    def now(self):
        with database(self.bench.path) as db:
            return instant(db.execute('SELECT event_clock FROM workspace_workflow WHERE id=1').fetchone()[0])

    def _authorize(self,p,write=False):
        self.bench.require_tenant(p)
        if write:
            self.bench.check_write(p)
            if p.subject!=SCRIPT or p.role!='reviewer':
                raise PermissionError('This authored workflow requires its actual scripted reviewer identity.')
        require_fixture_workspace(self.bench.path)

    def _vendor(self,p,installation):
        try:return get_vendor(self.bench.path,p,installation)
        except KeyError:return None

    def _claim(self,p):
        try:case=self.bench.case(p,self.claim_id)
        except KeyError:return None
        if case.get('scope')!=self.scopes[self.claim_month].model_dump():
            raise PermissionError('Configured claim identity no longer matches the exact workflow scope.')
        return case

    @staticmethod
    def _citations(rows):
        return [dict(label=c.get('label') or c.get('section') or c.get('document') or 'Source document',
                     ref=c.get('uri') or c.get('ref') or c.get('source_sha256') or '') for c in rows]

    def _month_views(self,p):
        saved=stored_cases(self.bench.path,p.tenant)
        result=[]
        for month,row in self.months.items():
            matches=[c for c in saved if c.get('vendor_id')==self.installation
                     and c.get('account')==self.package['overlay']['account']
                     and c.get('agreement')==self.package['overlay']['agreement']
                     and any(isinstance(e.get('detail'),dict) and e['detail'].get('month')==month for e in c.get('evidence',[]))]
            current=matches[-1] if matches else None
            usage=row['usage']; known=instant(usage['observed_at'])<=self.now()
            invoice=row['invoice']; line=invoice.lines[0]
            result.append(dict(month=month,outcome=current['outcome'] if current and known else 'INSUFFICIENT_EVIDENCE',
                amount=current['amount'] if current and known else None,currency=invoice.currency,
                reason='; '.join(current.get('trace',[])) if current and known else 'A current source-bound evaluation is not yet available.',
                trace=current.get('trace',[]) if current and known else [],
                citations=self._citations(current.get('clauses',[]) if current else row.get('citations',[])),
                invoice=dict(id=invoice.id,issued_at=invoice.issued_at.isoformat(),service_start=line.start.isoformat(),service_end=line.end.isoformat()),
                evidence=[dict(label='Monthly coverage',ref=usage['monitor_ref'],value=usage['coverage_note'] if known else None),
                          dict(label='Eligible downtime minutes',ref=usage['monitor_ref'],value=str(usage['eligible_downtime_minutes']) if known and usage['eligible_downtime_minutes'] is not None else None)]))
        return result

    def view(self,p):
        self._authorize(p)
        claim=self._claim(p); contract=self._vendor(p,self.installation)
        onboarding=self._vendor(p,self.onboarding_installation)
        month=self.months[self.bill_month]; price=month['pricing_result']; invoice=month['invoice']
        invoice_known=invoice.issued_at<=self.now()
        price_amount=str(price.overcharge) if invoice_known and price.overcharge is not None else None
        try:balance=self.bench.allocations.bill_balance(p.tenant,self.bill_id)
        except KeyError:balance=None
        ledger=claim['ledger'] if claim else {}
        reconciliations=claim.get('reconciliations',[]) if claim else []
        records=dict(award=None,credit=None,application=None)
        if len(reconciliations)==1:
            rec=reconciliations[0];records['award']=rec['award_id']
            records['credit']=rec['credit_ids'][0] if len(rec['credit_ids'])==1 else None
            records['application']=rec['application_ids'][0] if len(rec['application_ids'])==1 else None
        posted=records['credit'] is not None
        reviewer=dict(name='Dana Reyes',role='Contract reviewer',authority_kind='SCRIPTED_REVIEWER',principal=SCRIPT)
        documents=[dict(title=v.citation.document,ref=v.citation.uri,version=v.id,effective_at=v.effective_at.isoformat(),
                        description=v.citation.section) for v in self.package['pricing_agreement'].versions if v.signed_at and v.signed_at<=self.now()]
        audit=[dict(at=r['at'],event=r['event'],ref=r.get('event_id',r.get('digest',''))) for r in (claim or {}).get('timeline',[])]
        projection=dict(company={'name':self.package['pricing_agreement'].customer},
            vendor=self.package['manifest']['vendor'],as_of=self.now().isoformat(),
            contract=dict(title=self.package['document']['name'],version=contract.get('active_version') if contract else None,
                          ref=self.package['document']['uri'],summary=self.package['document']['text'],documents=documents),
            reviewer=reviewer,months=self._month_views(p),
            price_finding=dict(id='pricing-'+fingerprint([invoice.id,self.package_digest]),
                state=price.stage if price_amount is not None else price.evaluation.outcome.value,
                amount=price_amount,currency=invoice.currency,reason='; '.join(price.evaluation.trace) if invoice_known else 'The invoice is not yet known.',
                citations=self._citations([dict(document=c.document,section=c.section,uri=c.uri) for c in price.evaluation.clauses])),
            claim=dict(id=self.claim_id,state=claim['stage'] if claim else 'NOT_OPENED',amount=claim['amount'] if claim else None,
                       currency=invoice.currency,receipt_id=claim['submissions'][-1]['id'] if claim and claim['submissions'] else None),
            connection=dict(destination=self.provider.destination,status='CONNECTED',receipt_status='VERIFIED_LOCAL_READBACK' if posted else 'NOT_POSTED'),
            ledger=dict(destination=self.provider.destination,estimated=claim['amount'] if claim else None,
                        claimed=ledger.get('claimed','0.00'),awarded=ledger.get('awarded','0.00'),posted=ledger.get('posted','0.00'),
                        applied=ledger.get('applied','0.00'),currency=invoice.currency,record_ids=records,
                        bill=dict(id=self.bill_id,original_amount=str(invoice.total) if invoice_known else None,
                                  outstanding_amount=balance['remaining_eligible'] if balance else None)),
            audit=audit,onboarding=dict(vendor='CalyxQuay',state=onboarding['state'] if onboarding else 'NOT_INSTALLED',
                version=onboarding.get('active_version') if onboarding else None,reviewer=reviewer,
                history=[dict(at=r['at'],event=r['kind'],ref=str(r['revision'])) for r in (onboarding or {}).get('audit',[])],actions=[]),
            next_actions=[])
        return {'workflow':projection}
