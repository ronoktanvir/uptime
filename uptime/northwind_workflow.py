"""Configured fictional workflow composition over the production services.

No financial calculation lives here. Local-ledger readback is a local
self-consistency check, never an external provider or human attestation.
"""
from copy import deepcopy
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from uuid import UUID, uuid5

from .contracts import Source, fingerprint
from .storage import database


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

    def __init__(self, financial_path, provider_path, instance):
        self.financial_path=Path(financial_path).resolve()
        self.path=Path(provider_path).resolve()
        self.instance=str(UUID(instance))
        require_fixture_workspace(self.financial_path)
        if self.path==self.financial_path:
            raise ValueError('Provider storage must be separate from the financial transaction.')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute('PRAGMA synchronous=FULL')
            db.execute('CREATE TABLE IF NOT EXISTS local_ledger_binding (id INTEGER PRIMARY KEY CHECK(id=1),instance TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO local_ledger_binding VALUES(1,?)',(self.instance,))
            if db.execute('SELECT instance FROM local_ledger_binding').fetchone()[0]!=self.instance:
                raise ValueError('Local ledger belongs to a different workspace instance.')
            db.execute('''CREATE TABLE IF NOT EXISTS local_ledger_record (
                tenant TEXT NOT NULL,id TEXT NOT NULL,kind TEXT NOT NULL,idempotency_key TEXT NOT NULL,
                payload TEXT NOT NULL,payload_sha256 TEXT NOT NULL,recorded_at TEXT NOT NULL,
                PRIMARY KEY(tenant,id),UNIQUE(tenant,idempotency_key))''')
            for operation in ('UPDATE','DELETE'):
                db.execute(f"CREATE TRIGGER IF NOT EXISTS local_ledger_no_{operation.lower()} BEFORE {operation} ON local_ledger_record BEGIN SELECT RAISE(ABORT,'Local provider records are immutable'); END")
        self.path.chmod(0o600)
        self.failure_point=None  # Test fault injector; never configured by requests.

    def _identity(self,tenant,kind,parents):
        if tenant!='bears':
            raise PermissionError('Local ledger tenant mismatch.')
        return 'local-ledger:'+str(uuid5(UUID(self.instance),encoded([tenant,kind,parents])))

    def credit(self,tenant,award):
        identity=self._identity(tenant,'credit',[award['id'],award['source_ref']])
        return dict(award,id=identity,source_ref=identity,award_id=award['id'],source=Source.REPLAY.value)

    def application(self,tenant,plan):
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

    def confirm(self,tenant,action,plan):
        """Called after SQL validation but before the financial transaction commits."""
        require_fixture_workspace(self.financial_path)
        if action=='record-credit':
            if len(plan.get('credits',[]))!=1:
                raise ValueError('One exact credit is required for provider posting.')
            row=deepcopy(plan['credits'][0]); kind='credit'
            expected=self.credit(tenant,plan['award'])
        elif action=='apply-balance':
            row=deepcopy(plan); kind='application'
            expected=self.application(tenant,plan)
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
