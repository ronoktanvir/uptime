"""Grounded, read-only case guide for the configured finance workflow.

Answers are assembled from facts copied out of the current server projection.
Every sentence cites the fact it came from. Questions the case records cannot
answer, or that ask for a judgment, abstain. Requests to act are answered with
the current control's location; the guide itself never changes state.

No model is called. Model-composed wording is a separate change that depends on
the pending model-data (D10) and guide-scope (D12) decisions.
"""
import re

from .finance_view import SECTIONS, decimal, money, month_name, summarize

TOPICS = {
    'credit': r'credits?|sla|eligib\w*|calculat\w*|how much|percent|\d+\s?%|increments?|shortfall|uptime|availability|amounts?',
    'deadline': r'deadlines?|due|window|cut-?off|when|late|expir\w*|timely|in time|last day|time left|how long',
    'evidence': r'evidence|usage|missing|logs?|downtime|minutes|coverage|monitor\w*|proof|measur\w*|data|unknown|undetermined',
    'price': r'price|pricing|cap|capped|over-?charg\w*|overbill\w*|rates?|amendment|increase|fees?|billed|1,?000',
    'bill': r'bills?|invoices?|balance|outstanding|appl(?:y|ied|ication)|reconcil\w*|8,?600|11,?000|owe|owed|remaining|left to pay',
    'ramp': r'ramp|post(?:ed|ing)?|destination|ledger|recorded|payments?|paid|hold',
    'review': r'review\w*|approv\w*|calyx\s?quay|onboard\w*|adapter|roll(?:ed)?\s?back|activ\w*|revok\w*|ronok|dana',
    'agreement': r'agreements?|contracts?|clauses?|terms|governing|documents?|order form|signed',
    'next': r'next|to do|todo|attention|pending|blocked|waiting|what now|needs?|actions?',
    'status': r'status|stage|state|progress|happened|history',
    'award': r'award\w*|claimed',
}
MONTH_WORDS = {'01': r'january|jan', '02': r'february|feb', '03': r'march|mar', '04': r'april|apr',
               '05': r'may\s+\d{4}|in\s+may', '06': r'june|jun', '07': r'july|jul', '08': r'august|aug',
               '09': r'september|sept?', '10': r'october|oct', '11': r'november|nov', '12': r'december|dec'}
CLAUSE_TOPICS = {'credit': r'service credits?|credit|uptime target|percentage point',
                 'deadline': r'must be received|calendar days|deadline|within \d+',
                 'evidence': r'measured|measurement|evidence|monitor'}
ACTIONS = (r'approve|file|submit|send|post|apply|pay|activate|roll\s?back|revoke|delete|cancel|dispute|hold|stop|'
           r'create|mark|change|update|retry|run|execute|record|reject|accept|close|reopen')
ACTION_REQUEST = re.compile(rf'^\s*(?:please\s+)?(?:{ACTIONS})\b|\b(?:can|could|would|will)\s+you\s+(?:please\s+)?(?:{ACTIONS})\b|'
                            rf'\b(?:go ahead and|please)\s+(?:{ACTIONS})\b|\b(?:i want you to|you should)\s+(?:{ACTIONS})\b', re.I)
JUDGMENT = re.compile(r'\b(?:should (?:we|i)|ought|recommend\w*|advi[cs]e|advisable|legal(?:ly)?|lawyer|attorney|sue|'
                      r'lawsuit|liab\w*|negotiat\w*|predict\w*|forecast|likel(?:y|ihood)|probab\w*|chances?|odds|'
                      r'guarantee\w*|(?:will|would) (?:the )?vendor|worth\b|good idea|bad idea|wise|smart|best (?:option|course|move|way)|'
                      r'win|lose|risky|safe to|enforceable|in our favou?r|fair)\b', re.I)
KNOWN_NAMES = {'northwind', 'cloud', 'harborline', 'analytics', 'calyxquay', 'calyx', 'quay', 'ramp', 'local', 'ledger',
               'dana', 'reyes', 'ronok', 'tanvir', 'sla', 'usd', 'clause', 'order', 'form', 'amendment', 'uptime',
               'what', 'why', 'how', 'when', 'where', 'which', 'who', 'is', 'are', 'was', 'were', 'did', 'does', 'do',
               'can', 'could', 'should', 'will', 'would', 'please', 'tell', 'show', 'explain', 'the', 'i', 'a', 'an',
               'has', 'have', 'it', 'its', 'this', 'that', 'our', 'we', 'my', 'any', 'and', 'or', 'in', 'on', 'for'}
MONTH_NAMES = {'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october',
               'november', 'december', 'jan', 'feb', 'mar', 'apr'}
AUTHORITY = {'SCRIPTED_REVIEWER': 'a scripted reviewer', 'authenticated_reviewer': 'an authenticated reviewer account'}
ABSTAIN_SCOPE = "This case's records don't answer that."
SCOPE_NOTE = 'This answer covers only the cited records. Anything not cited is not established by this case.'
ABSTAIN_JUDGMENT = "That needs a reviewer's judgment. The guide reports what this case records and doesn't recommend decisions."
READ_ONLY = "The guide is read-only and can't take that action."
MAX_FACTS = 5
GENERIC = {'credit', 'status', 'agreement', 'next'}


def _fact(facts, fid, text, topics, section, *, months=(), ref=None, label=None, primary=None):
    facts.append(dict(id=fid, text=text, topics=set(topics), months=set(months), section=SECTIONS[section],
                      ref=ref if isinstance(ref, str) and ref else None, label=label or fid, primary=primary))


def _state(value):
    return str(value).replace('_', ' ').lower() if value else 'not recorded'


def _sentence(value):
    return str(value).rstrip(' .') + '.'


def facts(projection, summary=None):
    """Grounding facts; every value is copied from the projection."""
    summary = summary or summarize(projection)
    out = []
    contract = projection.get('contract') or {}
    claim = projection.get('claim') or {}
    ledger = projection.get('ledger') or {}
    price = projection.get('price_finding') or {}
    currency = ledger.get('currency') or 'USD'
    destination = ledger.get('destination') or 'the configured destination'
    if contract.get('title'):
        _fact(out, 'agreement', f'The governing service agreement is {contract["title"]} ({contract.get("ref")}).',
              {'agreement', 'credit'}, 'agreement', ref=contract.get('ref'), label='Governing agreement')
    for doc in contract.get('documents') or []:
        _fact(out, 'document.' + str(doc.get('version')),
              f'{doc.get("title")} (version {doc.get("version")}) is effective from {str(doc.get("effective_at"))[:10]}.',
              {'agreement', 'price'}, 'agreement', ref=doc.get('ref'), label=str(doc.get('title')))
    seen = set()
    for month in projection.get('months') or []:
        for cite in month.get('citations') or []:
            quote = cite.get('quote') if isinstance(cite, dict) else None
            if not quote or quote in seen:
                continue
            seen.add(quote)
            topics = {'agreement'} | {t for t, pattern in CLAUSE_TOPICS.items() if re.search(pattern, quote, re.I)}
            _fact(out, 'clause.' + str(len(seen)), f'{cite.get("label")}: “{quote}”', topics, 'months',
                  ref=cite.get('ref'), label=str(cite.get('label')))
    for month in projection.get('months') or []:
        key, name = str(month.get('month')), month_name(month.get('month'))
        outcome = month.get('outcome')
        lines = [str(x) for x in month.get('calculation') or []]
        if outcome == 'ELIGIBLE' and decimal(month.get('amount')) is not None:
            text = f'{name} is eligible for a {money(month["amount"], month.get("currency", currency))} service credit.'
        elif outcome == 'INELIGIBLE':
            text = f'{name} is not eligible for a service credit' + (f': {lines[0]}' if lines else '.')
        else:
            absent = [r.get('label') for r in month.get('evidence') or [] if isinstance(r, dict) and r.get('value') is None]
            text = (f'{name} is undetermined, not ineligible: ' + (', '.join(absent) or 'required evidence')
                    + ' not provided, so no credit amount is known.')
        undetermined = outcome not in ('ELIGIBLE', 'INELIGIBLE')
        _fact(out, f'month.{key}.outcome', _sentence(text), {'credit', 'status'} | ({'evidence'} if undetermined else set()),
              'months', months={key}, ref=(month.get('invoice') or {}).get('id'), label=f'{name} decision',
              primary='evidence' if undetermined else 'credit')
        if lines:
            _fact(out, f'month.{key}.calculation', f'{name} calculation: ' + ' '.join(lines), {'credit'}, 'months',
                  months={key}, label=f'{name} calculation')
        inputs = month.get('inputs') or {}
        if inputs:
            parts = ([f'governing fee {money(inputs["governing_fee"], inputs.get("currency") or currency)}']
                     if inputs.get('governing_fee') else [])
            parts += [f'{label} {inputs[k]}' for k, label in (('fee_version', 'fee reference'),
                      ('eligible_downtime_minutes', 'eligible downtime minutes'), ('completed_steps', 'completed increments'))
                      if inputs.get(k) is not None]
            parts += [f'credit rate {inputs["credit_percent"]}%'] if inputs.get('credit_percent') is not None else []
            if parts:
                _fact(out, f'month.{key}.inputs', f'{name} inputs: ' + '; '.join(parts) + '.', {'credit'}, 'months',
                      months={key}, label=f'{name} inputs')
        for row in month.get('evidence') or []:
            if isinstance(row, dict) and row.get('value') is not None:
                _fact(out, f'month.{key}.evidence.{len(out)}', _sentence(f'{name} {str(row.get("label")).lower()}: {row["value"]}'),
                      {'evidence'}, 'months', months={key}, ref=row.get('ref'), label=f'{name} {row.get("label")}')
    if claim.get('id'):
        cname = month_name(claim.get('month')) if claim.get('month') else 'The'
        _fact(out, 'claim.status', f'The {cname} claim {claim["id"]} is at stage {_state(claim.get("state"))}.',
              {'status', 'credit'}, 'recovery', months={str(claim.get('month'))}, ref=claim.get('id'), label='Claim status',
              primary='status')
        if claim.get('filing_cutoff'):
            filed = (f'It was filed with receipt {claim["receipt_id"]}.' if claim.get('receipt_id')
                     else 'It has not been filed.')
            _fact(out, 'claim.deadline', f'The {cname} claim must be received before {claim["filing_cutoff"]}. {filed}',
                  {'deadline', 'status'}, 'recovery', months={str(claim.get('month'))}, ref=claim.get('id'),
                  label='Filing deadline', primary='deadline')
    rows = summary['stages']
    stage_text = '; '.join(f'{r["label"].lower()} {money(r["amount"], currency) if r["amount"] else "not determined"}'
                           for r in rows)
    _fact(out, 'ledger.stages', f'The claim credit by stage: {stage_text}. These are stages of one credit, not amounts to add.',
          {'credit', 'status', 'ramp', 'bill', 'award'}, 'recovery', months={str(claim.get('month'))}, label='Financial stages',
          primary='award')
    bill = summary['bill']
    bill_period = (ledger.get('bill') or {}).get('service_start')
    if bill.get('id'):
        applied = (f'applied credit {money(bill["applied"], currency)}; ' if bill.get('applied') else 'no credit applied; ')
        _fact(out, 'bill', f'Invoice {bill["id"]}: original {money(bill.get("original"), currency)}; {applied}'
                           f'outstanding {money(bill.get("outstanding"), currency)}.',
              {'bill', 'credit'}, 'bill', months={str(bill_period)[:7]} if bill_period else set(), ref=bill['id'],
              label=f'Invoice {bill["id"]}', primary='bill')
    if price.get('invoice_id'):
        cur = price.get('currency', currency)
        lines = [l for l in price.get('lines') or [] if isinstance(l, dict)]
        detail = '; '.join(f'billed {money(l.get("billed"), cur)} against {money(l.get("expected"), cur)} under '
                           f'{l.get("version")}, a {money(l.get("delta"), cur)} {str(l.get("direction", "")).lower()}'
                           for l in lines)
        amount = (f'an open {money(price["amount"], cur)} price finding' if decimal(price.get('amount')) is not None
                  else 'a price review with no determined amount')
        _fact(out, 'price', f'Invoice {price["invoice_id"]} has {amount}' + (f' ({detail})' if detail else '')
              + '. It is separate from the service credit and is not an awarded credit.',
              {'price', 'bill'}, 'price', months={str(m.get('month')) for m in projection.get('months') or []
                                               if (m.get('invoice') or {}).get('id') == price['invoice_id']},
              ref=price['invoice_id'], label='Price finding', primary='price')
    ramp = summary['ramp']
    if ramp.get('linked_record'):
        _fact(out, 'ramp', f'The linked Ramp record is {ramp["linked_record"].get("id")}.', {'ramp'}, 'ramp',
              ref=ramp['linked_record'].get('id'), label='Ramp record')
    else:
        _fact(out, 'ramp', f'Credits in this workspace are recorded in {destination}. No Ramp bill is linked, and no Ramp '
                           'credit or Ramp bill application is recorded for this case.', {'ramp', 'bill'}, 'ramp',
              label='Destination', primary='ramp')
    coverage = projection.get('onboarding') or {}
    if coverage.get('vendor'):
        reviewer = coverage.get('reviewer') or {}
        actors = sorted({h.get('actor') for h in coverage.get('history') or [] if isinstance(h, dict) and h.get('actor')})
        kind = AUTHORITY.get(reviewer.get('authority_kind'), 'an unrecorded authority')
        # The exact version is the citation reference; identifiers are never shortened in answer text.
        _fact(out, 'coverage', f'{coverage["vendor"]} coverage in this workspace is {_state(coverage.get("state"))}'
              + f'; its reviewer is {reviewer.get("name") or "not recorded"}, recorded as {kind}.'
              + (f' Its history is recorded under {", ".join(actors)} only.' if actors else ''),
              {'review'}, 'coverage', ref=coverage.get('version'), label=f'{coverage["vendor"]} coverage', primary='review')
    for index, item in enumerate(summary['attention']):
        _fact(out, f'attention.{index}', f'{item["title"]}: {item["detail"]}', {'next'} | _attention_topics(item['kind']),
              next(k for k, v in SECTIONS.items() if v == item['section']), label=item['title'], primary='next')
    return out


def _attention_topics(kind):
    return {'RECONCILIATION_CONFLICT': {'bill', 'ramp'}, 'MISSING_AGREEMENT': {'agreement'},
            'CLAIM_DEADLINE': {'deadline'}, 'REVIEW_REQUIRED': {'review', 'price'},
            'MISSING_EVIDENCE': {'evidence'}, 'MISSING_USAGE': {'evidence'}, 'NEXT_STEP': {'status'}}.get(kind, set())


def _topics(text):
    return {topic for topic, pattern in TOPICS.items() if re.search(rf'(?<![A-Za-z0-9])(?:{pattern})(?![A-Za-z0-9])', text, re.I)}


def _months(text):
    """Calendar months named in the question, as two-digit strings; no year is assumed."""
    found = {m for m, words in MONTH_WORDS.items() if re.search(rf'\b(?:{words})\b', text, re.I)}
    return found | set(re.findall(r'\b\d{4}-(0[1-9]|1[0-2])\b', text))


def _unknown_names(question):
    """Capitalized names the case does not contain, ignoring the first word."""
    words = re.findall(r"[A-Za-z][A-Za-z'’]+", question)
    names = []
    for index, word in enumerate(words):
        base = re.sub(r"['’]s$", '', word)
        # A proper name: capitalized, not an acronym, not the first word and not a known case name.
        if (index and len(base) > 2 and base[:1].isupper() and not base.isupper()
                and base.lower() not in KNOWN_NAMES | MONTH_NAMES):
            names.append(base)
    return names


def _cite(fact):
    return dict(id=fact['id'], label=fact['label'], ref=fact['ref'], section=fact['section'])


def _response(question, projection, selected, *, abstained=False, reason=None, lead=None, related=()):
    sentences = ([dict(text=lead, citations=[])] if lead else []) + \
                [dict(text=f['text'], citations=[f['id']]) for f in selected]
    return dict(question=question, answer=' '.join(s['text'] for s in sentences), sentences=sentences,
                citations=[_cite(f) for f in list(selected) + list(related)], abstained=abstained, reason=reason,
                read_only=True, grounding='current case records', scope_note=None if abstained or not selected else SCOPE_NOTE,
                as_of=projection.get('as_of'),
                case=(projection.get('claim') or {}).get('id'), composer='deterministic', model=None,
                external_transmission=False)


def answer(question, projection):
    """Answer one question from the current projection. Pure; never writes."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError('Ask a question about this case.')
    summary = projection.get('finance') or summarize(projection)
    grounded = facts(projection, summary)
    text = question.strip()
    topics, months = _topics(text), _months(text)
    ranked = _rank(grounded, topics, months)
    if ACTION_REQUEST.search(text):
        steps = [f for f in grounded if f['id'].startswith('attention.') and 'Next step' in f['label']]
        lead = READ_ONLY + (' The current step is shown below; a signed-in reviewer runs it from the recovery panel.'
                            if steps else ' No step is available in this case right now.')
        return _response(text, projection, steps[:1], reason='read_only', lead=lead)
    if JUDGMENT.search(text):
        return _response(text, projection, [], abstained=True, reason='requires_judgment', lead=ABSTAIN_JUDGMENT,
                         related=ranked[:3])
    unknown = _unknown_names(text)
    if unknown:
        return _response(text, projection, [], abstained=True, reason='outside_case',
                         lead=f"{ABSTAIN_SCOPE} It doesn't include {', '.join(dict.fromkeys(unknown))}.")
    if not topics and not months:
        return _response(text, projection, [], abstained=True, reason='unsupported', lead=ABSTAIN_SCOPE)
    if not ranked:
        return _response(text, projection, [], abstained=True, reason='unsupported', lead=ABSTAIN_SCOPE)
    return _response(text, projection, ranked[:MAX_FACTS])


def _rank(grounded, topics, months):
    scored = []
    for order, fact in enumerate(grounded):
        overlap = fact['topics'] & topics
        month_match = bool(months) and any(str(m)[-2:] in months for m in fact['months'])
        if months and fact['months'] and not month_match:
            continue
        if not overlap and not (month_match and not topics):
            continue
        # Prefer specific case facts over clause quotations, then keep source order.
        specific = not fact['id'].startswith(('clause.', 'agreement', 'document.', 'attention.'))
        score = (sum(_weight(t) for t in fact['topics'] & topics) + (3 if month_match else 0) + (1 if specific else 0)
                 + (2 * _weight(fact['primary']) if fact['primary'] in topics else 0))
        scored.append((-score, order, fact))
    ranked = sorted(scored, key=lambda row: (row[0], row[1]))
    # Keep the answer focused: drop facts clearly weaker than the best match.
    best = -ranked[0][0] if ranked else 0
    return [fact for negative, _, fact in ranked if -negative >= best - 2]


def _weight(topic):
    """Specific subjects outrank broad words such as 'credit' or 'status'."""
    return 1 if topic in GENERIC else 2
