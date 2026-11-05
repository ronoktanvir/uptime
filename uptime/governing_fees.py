"""Server-only governing-fee resolution from immutable terms and signed evidence.

The caller must supply an already authenticated inbox record. This module checks
its exact scope/content against fixed server inputs; it is not a signature or
commercial-authority verifier. No browser endpoint accepts these objects.
"""
from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import datetime, UTC
from decimal import Decimal, localcontext
from hashlib import sha256
import json
from pathlib import Path
import re
from types import MappingProxyType
from weakref import WeakKeyDictionary

from .contracts import fingerprint
from .correspondence_types import Scope, Invoice as SignedInvoice, instant
from .pricing import Agreement, Invoice, evaluate_price, _validate_agreement

_ISSUED = WeakKeyDictionary()
_DIGEST = re.compile('[a-f0-9]{64}')


def _canonical(value):
    if isinstance(value,Decimal):return str(value)
    if isinstance(value,datetime):return value.isoformat()
    if is_dataclass(value):return {f.name:_canonical(getattr(value,f.name)) for f in fields(value)}
    if isinstance(value,(tuple,list)):return [_canonical(x) for x in value]
    if isinstance(value,dict):return {k:_canonical(v) for k,v in value.items()}
    if isinstance(value,Scope):return value.model_dump()
    return value


def dependency_digest():
    root=Path(__file__).parent
    return fingerprint({name:sha256((root/name).read_bytes()).hexdigest() for name in
                        ('pricing.py','pricing_terms.py','governing_fees.py','credit_steps.py','vendor_eval.py')})


@dataclass(frozen=True)
class FeeEntry:
    entry_id: str
    tenant: str
    scope: Scope
    plan: str
    fee_line_id: str
    agreement: Agreement
    invoice: Invoice
    sla_source_sha256: str
    manifest_sha256: str
    overlay_sha256: str


@dataclass(frozen=True)
class InvoiceSnapshot:
    tenant: str
    scope: Scope
    body_json: str
    evidence_digest: str
    subject: str
    source_key_id: str
    source_grant_id: str
    received_at: str


def authenticated_invoice_snapshot(tenant, scope, event):
    """Adapt an already authenticated stored billing event; never request JSON.

    Source authentication remains the inbox/adapter's responsibility. Requiring
    retained grant provenance prevents an ordinary fact map from accidentally
    taking this internal path. This function cannot establish external truth.
    """
    if (not isinstance(scope,Scope) or event.get('source')!='billing' or event.get('kind')!='invoice'
            or any(not isinstance(event.get(k),str) or not event[k] for k in
                   ('subject','source_key_id','source_grant_id','received_at','digest'))
            or not _DIGEST.fullmatch(event['digest'])):
        raise ValueError('Authenticated stored billing evidence with source grant provenance is required.')
    SignedInvoice.model_validate(event['body'])
    instant(event['received_at'])
    return InvoiceSnapshot(tenant,scope,json.dumps(event['body'],sort_keys=True,separators=(',',':')),
                           event['digest'],event['subject'],event['source_key_id'],event['source_grant_id'],event['received_at'])


@dataclass(frozen=True,eq=False,slots=True,weakref_slot=True)
class GoverningFeeContext:
    fee_minor: int
    currency: str
    minor_exponent: int
    tenant: str
    scope_json: str
    plan: str
    fee_line_id: str
    governing_pricing_version: str
    service_start: str
    service_end: str
    as_of: str
    provenance_class: str
    sla_source_sha256: str
    manifest_sha256: str
    overlay_sha256: str
    entry_digest: str
    signed_evidence_digest: str
    dependency_sha256: str
    digest: str


def _scope_key(tenant,scope):
    return fingerprint([tenant,scope.model_dump()])


class FeeRegistry:
    """Immutable startup configuration. close() revokes all issued contexts.

    Replacing a configured registry requires closing the old instance first.
    An already-running old process cannot be revoked merely by replacing a
    variable elsewhere; deployment must stop it. No public mutation API exists.
    """
    __slots__=('_entries','_digests','_dependency','_active')

    def __init__(self,entries):
        if type(entries) is not tuple or not entries:
            raise ValueError('An immutable nonempty tuple of registered pricing inputs is required.')
        indexed={};financial=set();ids=set()
        for entry in entries:
            if type(entry) is not FeeEntry or not isinstance(entry.scope,Scope):
                raise ValueError('Typed fixed server fee entries are required.')
            _validate_agreement(entry.agreement)
            scope=entry.scope
            if (not entry.tenant or not entry.entry_id or entry.entry_id in ids or scope.currency!='USD'
                    or entry.agreement.id!=scope.contract or entry.agreement.vendor!=scope.vendor
                    or entry.invoice.id!=scope.invoice or entry.invoice.vendor!=scope.vendor
                    or entry.invoice.customer!=entry.agreement.customer
                    or any(not _DIGEST.fullmatch(x) for x in (entry.sla_source_sha256,entry.manifest_sha256,entry.overlay_sha256))):
                raise ValueError('Fee entry identity, USD scope or source pins disagree.')
            identity=(entry.tenant,scope.account,scope.vendor,scope.contract,scope.service,entry.plan,scope.month,entry.fee_line_id)
            if identity in financial:
                raise ValueError('Duplicate or overlapping fixed monthly fee registrations are ambiguous.')
            key=_scope_key(entry.tenant,scope)
            if key in indexed:
                raise ValueError('Duplicate authenticated lookup scope is ambiguous regardless of plan or fee line.')
            financial.add(identity);ids.add(entry.entry_id)
            indexed[key]=entry
        self._entries=MappingProxyType(indexed)
        self._digests=MappingProxyType({key:fingerprint(_canonical(value)) for key,value in indexed.items()})
        self._dependency=dependency_digest();self._active=True

    def close(self):
        self._active=False

    def _resolve_values(self,snapshot,as_of):
        if not self._active or self._dependency!=dependency_digest():
            raise ValueError('Governing-fee registry is revoked or its pricing dependencies changed.')
        if type(snapshot) is not InvoiceSnapshot or not isinstance(snapshot.scope,Scope):
            raise ValueError('An authenticated invoice adapter snapshot is required.')
        if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
            raise ValueError('Trusted observation time is required.')
        clock_at=as_of.astimezone(UTC)
        as_of=instant(snapshot.received_at)
        entry=self._entries.get(_scope_key(snapshot.tenant,snapshot.scope))
        if entry is None or self._digests[_scope_key(snapshot.tenant,snapshot.scope)]!=fingerprint(_canonical(entry)):
            raise ValueError('Authenticated envelope has no exact current registered fee input.')
        if (not _DIGEST.fullmatch(snapshot.evidence_digest) or any(not isinstance(x,str) or not x for x in
                (snapshot.subject,snapshot.source_key_id,snapshot.source_grant_id))
                or as_of>clock_at or entry.invoice.issued_at>as_of
                or any(v.signed_at>as_of for v in entry.agreement.versions)):
            raise ValueError('Signed invoice or contractual input was not known at the observation time.')
        body=json.loads(snapshot.body_json);SignedInvoice.model_validate(body)
        scope=snapshot.scope.model_dump()
        registered={line.id:line for line in entry.invoice.lines}
        if len(registered)!=len(entry.invoice.lines) or len(body['lines'])!=len(registered):
            raise ValueError('Complete unique invoice lines must match registered inputs.')
        seen=set()
        for line in body['lines']:
            old=registered.get(line['id'])
            if old is None or line['id'] in seen or any(value is not None and value!=scope.get(key) for key,value in line.items() if key not in {'id','kind','amount'}):
                raise ValueError('Signed invoice line identity contradicts its authenticated envelope.')
            seen.add(line['id'])
            # Only a single covered subscription line is supported. Excluded or
            # split charges require a separately reviewed itemization adapter.
            if (line['id']!=entry.fee_line_id or line['kind']!='affected_api' or old.product!=scope['service']
                    or Decimal(line['amount'])!=old.net or old.tax!=Decimal(0)):
                raise ValueError('A single exact covered net invoice line with separate zero tax is required.')
        if len(registered)!=1:
            raise ValueError('Absent, split, duplicate or credit-memo fee invoices are unsupported.')
        line=next(iter(registered.values()))
        if (line.start is None or line.end is None or line.start.strftime('%Y-%m')!=scope['month']
                or line.quantity!=Decimal(1)):
            raise ValueError('The registered fee must cover the exact single-unit service month.')
        versions=[v for v in entry.agreement.versions if v.effective_at<=line.start]
        version=max(versions,key=lambda v:v.effective_at) if versions else None
        rates=[r for r in version.rates if r.product==scope['service']] if version else []
        if len(rates)!=1 or rates[0].fixed_monthly is None:
            raise ValueError('The governing contract must explicitly fix one monthly subscription unit.')
        result=evaluate_price(entry.agreement,entry.invoice,as_of=as_of)
        matches=[x for x in result.lines if x.line_id==entry.fee_line_id and x.product==scope['service']]
        if result.overcharge is None or len(matches)!=1 or matches[0].expected is None:
            raise ValueError('Complete governing fee pricing is unresolved.')
        with localcontext() as ctx:
            ctx.prec=60
            cents=matches[0].expected*100
            if cents<0 or cents!=cents.to_integral_value() or cents>10**15:
                raise ValueError('USD governing fee must have bounded exact cents.')
            values=dict(fee_minor=int(cents),currency='USD',minor_exponent=2,tenant=entry.tenant,
                scope_json=json.dumps(scope,sort_keys=True,separators=(',',':')),plan=entry.plan,fee_line_id=entry.fee_line_id,
                governing_pricing_version=matches[0].version,service_start=line.start.isoformat(),service_end=line.end.isoformat(),
                as_of=as_of.isoformat(),provenance_class='sandbox_provider' if entry.invoice.provider else 'local_synthetic',
                sla_source_sha256=entry.sla_source_sha256,manifest_sha256=entry.manifest_sha256,overlay_sha256=entry.overlay_sha256,
                entry_digest=self._digests[_scope_key(snapshot.tenant,snapshot.scope)],signed_evidence_digest=snapshot.evidence_digest,
                dependency_sha256=self._dependency)
        values['digest']=fingerprint(values)
        return values

    def contexts_from_inbox(self,path,tenant,*,as_of):
        """Resolve only tenant-scoped authenticated stored invoice envelopes.

        This read-only seam cannot register a fee or ingest request evidence.
        Ambiguous/missing/unpriced source groups simply produce no context.
        """
        from .storage import database
        contexts=[]
        with database(path) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='inbox_claim'").fetchone():
                return ()
            for row in db.execute('SELECT scope,state FROM inbox_claim WHERE tenant=?',(tenant,)):
                scope=Scope.model_validate_json(row['scope']);state=json.loads(row['state'])
                invoices=[e for e in state.get('evidence',[]) if e.get('kind')=='invoice']
                if len(invoices)!=1:
                    continue
                try:
                    snapshot=authenticated_invoice_snapshot(tenant,scope,invoices[0])
                    contexts.append(self.resolve(snapshot,as_of=as_of))
                except (ValueError,TypeError,KeyError):
                    continue
        return tuple(contexts)

    def resolve(self,snapshot,*,as_of):
        values=self._resolve_values(snapshot,as_of)
        context=GoverningFeeContext(**values)
        _ISSUED[context]=(self,snapshot,as_of)
        return context


def require_governing_fee(context,manifest,overlay,facts,tenant):
    if type(context) is not GoverningFeeContext or context not in _ISSUED:
        raise ValueError('A current server-issued governing-fee context is required.')
    registry,snapshot,as_of=_ISSUED[context]
    values=registry._resolve_values(snapshot,as_of)
    if asdict(context)!=values:
        raise ValueError('Governing fee context no longer matches its current registered inputs.')
    scope=json.loads(context.scope_json)
    if (context.tenant!=tenant or context.sla_source_sha256!=manifest['document']['sha256']
            or context.manifest_sha256!=fingerprint(manifest) or context.overlay_sha256!=fingerprint(overlay)
            or (scope['vendor'],scope['contract'],scope['account'],scope['service'],context.plan,context.fee_line_id,scope['month'])
            !=(manifest['vendor'],overlay['agreement'],overlay['account'],overlay['product'],overlay['plan'],overlay['fee_line_ref'],facts.get('month'))):
        raise ValueError('Governing fee context scope or source interpretation does not match this evaluation.')
    return context


class GoverningFeeRequired(ValueError):
    """Current pricing authority is absent; archived artifacts remain readable."""


def current_contexts(path,tenant,authority=(),trusted_now=None):
    """Explicit application-owned authority only; no path/global authority cache."""
    if type(authority) is FeeRegistry:
        clock=trusted_now or (lambda:datetime.now(UTC))
        return authority.contexts_from_inbox(path,tenant,as_of=clock())
    if type(authority) is not tuple:
        raise TypeError('Explicit FeeRegistry or tuple of current issued contexts is required.')
    return authority


def context_for_digest(path,tenant,digest,manifest,overlay,facts,authority=(),trusted_now=None):
    if not isinstance(digest,str) or not _DIGEST.fullmatch(digest):
        raise GoverningFeeRequired('Current governing-fee authority is required.')
    matches=[]
    for context in current_contexts(path,tenant,authority,trusted_now):
        if getattr(context,'digest',None)!=digest:
            continue
        try:matches.append(require_governing_fee(context,manifest,overlay,facts,tenant))
        except (ValueError,TypeError,KeyError):continue
    if len(matches)!=1:
        raise GoverningFeeRequired('Recorded governing-fee evidence is absent, ambiguous or no longer current.')
    return matches[0]
