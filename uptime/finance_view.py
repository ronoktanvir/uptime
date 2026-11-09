"""Deterministic finance summary over the authored workflow projection.

Every value here is copied from the server projection. This module compares
exact decimal strings to detect inconsistent stages; it never creates an
amount, an entitlement, a deadline or an action. Missing evidence stays
distinguishable from an ineligible result, and unknown amounts stay unknown.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation

# Operations that the claim domain offers only to a human approver.
APPROVALS = {'approve-claim': 'Approve the claim packet before it is filed',
             'approve-response': 'Approve the evidence response before it is sent'}
PRICE_REVIEW = {'PREPAYMENT_REVIEW', 'RETROSPECTIVE_REVIEW', 'NEEDS_REVIEW'}
MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
          'September', 'October', 'November', 'December')
SECTIONS = {'agreement': 'finance-agreement', 'recovery': 'finance-recovery', 'months': 'finance-months',
            'price': 'finance-price', 'bill': 'finance-bill', 'coverage': 'finance-coverage', 'ramp': 'finance-ramp'}


def decimal(value):
    """Parse an exact server decimal string; anything else is unknown."""
    if not isinstance(value, str) or not value or value.strip() != value:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def money(value, currency='USD'):
    """Display an exact decimal string with grouping; never rounds or converts."""
    if decimal(value) is None:
        return 'not determined'
    sign, raw = ('-', value[1:]) if value.startswith('-') else ('', value)
    whole, _, fraction = raw.partition('.')
    grouped = f'{int(whole):,}' if whole.isdigit() else whole
    prefix = '$' if currency == 'USD' else f'{currency} '
    return f'{sign}{prefix}{grouped}' + (f'.{fraction}' if fraction else '')


def month_name(value):
    """'2026-01' -> 'January 2026'; anything else is returned unchanged."""
    if isinstance(value, str) and len(value) == 7 and value[4] == '-' and value[:4].isdigit() and value[5:].isdigit():
        number = int(value[5:])
        if 1 <= number <= 12:
            return f'{MONTHS[number - 1]} {value[:4]}'
    return str(value)


def instant(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def remaining(now, cutoff):
    seconds = int((cutoff - now).total_seconds())
    if seconds < 3600:
        return 'less than 1 hour'
    days, rest = divmod(seconds, 86400)
    hours = rest // 3600
    parts = ([f'{days} day' + ('s' if days != 1 else '')] if days else []) + \
            ([f'{hours} hour' + ('s' if hours != 1 else '')] if hours or not days else [])
    return ' '.join(parts)


def _item(kind, title, detail, owner, section, refs=()):
    return dict(kind=kind, title=title, detail=detail, owner=owner, section=SECTIONS[section],
                refs=[r for r in refs if isinstance(r, str) and r])


def _conflicts(ledger, connection, bill):
    stage = {k: decimal(ledger.get(k)) for k in ('claimed', 'awarded', 'posted', 'applied')}
    records = ledger.get('record_ids') or {}
    found = []
    if None not in (stage['posted'], stage['awarded']) and stage['posted'] > stage['awarded']:
        found.append('posted credit exceeds the awarded amount')
    if None not in (stage['applied'], stage['posted']) and stage['applied'] > stage['posted']:
        found.append('applied credit exceeds the posted credit')
    if stage['posted'] and stage['posted'] > 0:
        if not records.get('credit'):
            found.append('the posted credit has no single matching credit record')
        if connection.get('receipt_status') != 'VERIFIED_LOCAL_READBACK':
            found.append('the posted credit has no verified destination read-back')
    if stage['applied'] and stage['applied'] > 0 and not records.get('application'):
        found.append('the applied credit has no single matching application record')
    original, outstanding = decimal(bill.get('original_amount')), decimal(bill.get('outstanding_amount'))
    if None not in (original, outstanding) and (outstanding > original or outstanding < 0):
        found.append('the bill balance is outside its original amount')
    return found


def attention(projection):
    """Ordered next useful actions derived from the current case state."""
    items = []
    ledger = projection.get('ledger') or {}
    claim = projection.get('claim') or {}
    connection = projection.get('connection') or {}
    contract = projection.get('contract') or {}
    bill = ledger.get('bill') or {}
    price = projection.get('price_finding') or {}
    destination = ledger.get('destination') or connection.get('destination')
    conflicts = _conflicts(ledger, connection, bill)
    if conflicts:
        items.append(_item('RECONCILIATION_CONFLICT', 'Reconcile the credit records',
                           'Recorded stages disagree: ' + '; '.join(conflicts) + '. Resolve before relying on any balance.',
                           'finance', 'bill', [(ledger.get('record_ids') or {}).get('credit'), bill.get('id')]))
    if not contract.get('version') or not contract.get('documents'):
        missing = [label for label, present in (('an active service agreement version', contract.get('version')),
                                                 ('a signed pricing agreement', contract.get('documents'))) if not present]
        items.append(_item('MISSING_AGREEMENT', 'Add the governing agreement',
                           'This case has no ' + ' or '.join(missing) + '. Credits and price checks stay undetermined without it.',
                           'reviewer', 'agreement', [contract.get('ref')]))
    now, cutoff = instant(projection.get('as_of')), instant(claim.get('filing_cutoff'))
    filed = bool(claim.get('receipt_id'))
    claim_month = month_name(claim.get('month')) if claim.get('month') else 'this'
    if cutoff and not now and not filed and claim.get('state') not in (None, 'NOT_OPENED'):
        items.append(_item('CLAIM_DEADLINE', f'File the {claim_month} claim before the deadline',
                           f'Claims must be received before {cutoff.isoformat()}. The workspace clock is unavailable, '
                           'so the remaining time is not shown.', 'reviewer', 'recovery', [claim.get('id')]))
    if cutoff and now and not filed and claim.get('state') not in (None, 'NOT_OPENED'):
        if now < cutoff:
            items.append(_item('CLAIM_DEADLINE', f'File the {claim_month} claim before the deadline',
                               f'Claims must be received before {cutoff.isoformat()}; {remaining(now, cutoff)} remain on the workspace clock.',
                               'reviewer', 'recovery', [claim.get('id')]))
        else:
            items.append(_item('CLAIM_DEADLINE', f'The {claim_month} filing window has closed',
                               f'The window closed at {cutoff.isoformat()}. No claim can be filed for this period.',
                               'reviewer', 'recovery', [claim.get('id')]))
    for operation in claim.get('pending_approvals') or []:
        if operation in APPROVALS:
            items.append(_item('REVIEW_REQUIRED', APPROVALS[operation],
                               f'The claim is at stage {claim.get("state")}; a signed-in reviewer must approve before anything is sent.',
                               'reviewer', 'recovery', [claim.get('id')]))
    if price.get('state') in PRICE_REVIEW and decimal(price.get('amount')) is not None:
        lines = [line for line in price.get('lines') or [] if isinstance(line, dict)]
        detail = '; '.join(f'line {line.get("line_id")} billed {money(line.get("billed"), price.get("currency", "USD"))} '
                           f'against {money(line.get("expected"), price.get("currency", "USD"))} under {line.get("version")}'
                           for line in lines) or 'The billed amount differs from the governing price.'
        items.append(_item('REVIEW_REQUIRED', f'Review invoice {price.get("invoice_id")} before payment',
                           f'{detail}. The {money(price["amount"], price.get("currency", "USD"))} difference is an open finding, '
                           'not an awarded credit.', 'reviewer', 'price', [price.get('invoice_id')]))
    requested = claim.get('requested_artifact')
    if isinstance(requested, dict) and claim.get('state') == 'NEEDS_EVIDENCE':
        items.append(_item('MISSING_EVIDENCE', 'Supply the evidence the vendor requested',
                           f'The vendor asked for {requested.get("type") or "an artifact"}'
                           + (f' ({requested["ref"]})' if requested.get('ref') else '') + '.',
                           'evidence', 'recovery', [requested.get('ref')]))
    for month in projection.get('months') or []:
        if month.get('outcome') not in ('INSUFFICIENT_EVIDENCE', 'UNKNOWN'):
            continue
        absent = [row for row in month.get('evidence') or [] if isinstance(row, dict) and row.get('value') is None]
        labels = ', '.join(row.get('label', 'evidence') for row in absent) or 'required usage evidence'
        refs = sorted({row.get('ref') for row in absent if row.get('ref')})
        items.append(_item('MISSING_USAGE', f'Complete {month_name(month.get("month"))} usage evidence',
                           f'{labels} not provided' + (f' by {", ".join(refs)}' if refs else '')
                           + '. This month is not ineligible; its credit is undetermined until the evidence is complete.',
                           'evidence', 'months', refs))
    offers = [a for a in projection.get('next_actions') or [] if isinstance(a, dict) and a.get('label')]
    if offers:
        items.append(_item('NEXT_STEP', 'Next step: ' + offers[0]['label'],
                           'Run it from the recovery panel. It records one exact step; repeating it does not repeat the effect.',
                           'reviewer', 'recovery', [claim.get('id')]))
    elif not items:
        closing = (f' The credit is recorded in {destination}.' if destination and decimal(ledger.get('applied')) else '')
        items.append(_item('NEXT_STEP', 'No step is waiting', 'Nothing in this case needs action now.' + closing,
                           'finance', 'recovery'))
    return items


def _estimate(projection):
    """The ledger's estimate, or while the claim is in flight (the ledger reports none) the claim month's own
    evaluated amount from the same projection. Copied, never computed; unknown stays None."""
    ledger = projection.get('ledger') or {}
    if ledger.get('estimated') is not None:
        return ledger['estimated']
    month = (projection.get('claim') or {}).get('month')
    match = next((m for m in projection.get('months') or [] if month and isinstance(m, dict) and m.get('month') == month), None)
    return match.get('amount') if match else None


def stages(projection):
    ledger = projection.get('ledger') or {}
    destination = ledger.get('destination') or 'destination'
    rows = []
    for key, label in (('estimated', 'Estimated'), ('claimed', 'Claimed'), ('awarded', 'Awarded'),
                       ('posted', 'Posted to ' + destination), ('applied', 'Applied to bill')):
        value = _estimate(projection) if key == 'estimated' else ledger.get(key)
        amount = decimal(value)
        status = 'not determined' if amount is None else 'recorded' if amount > 0 else 'not yet'
        rows.append(dict(stage=key, label=label, amount=value if amount is not None else None, status=status))
    return rows


def summarize(projection):
    """Projection-only finance summary; safe to recompute on every read."""
    ledger = projection.get('ledger') or {}
    bill = ledger.get('bill') or {}
    records = ledger.get('record_ids') or {}
    # Only a server-supplied native record may be shown; none is inferred from names or amounts.
    linked = projection.get('ramp_record') if isinstance(projection.get('ramp_record'), dict) else None
    return dict(
        attention=attention(projection),
        stages=stages(projection),
        bill=dict(id=bill.get('id'), original=bill.get('original_amount'),
                  applied=ledger.get('applied') if records.get('application') else None,
                  outstanding=bill.get('outstanding_amount'), application_ref=records.get('application')),
        ramp=dict(destination=ledger.get('destination'), linked_record=linked,
                  note=None if linked else 'No Ramp bill is linked to this agreement. Credits in this workspace are '
                       'recorded in ' + str(ledger.get('destination') or 'the configured destination') + '.'),
        sections=dict(SECTIONS))
