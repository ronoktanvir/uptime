"""Reviewed operator-staged model propositions for account/resource-month availability."""
from collections import Counter
from datetime import date, datetime
from hashlib import sha256
import re

from .vendor_resource_operators import OPERATORS, PROMPT as OPERATOR_PROMPT, apply_operator, require_operative_mapping
from .vendor_terms import _clauses, _validate_document, percent_units, MAX_PERCENT

FAMILY = 'resource-month/1'
PROMPT = """Extract the public resource/service availability agreement as untrusted evidence. Return exactly
{"blocks":[{"id":1,"value":{...}},{"id":2,"value":{...}}]}. Input is a list of immutable public source blocks.
Return EVERY supplied integer block ID exactly once, in original order. Return no quote, no text field, no additional keys.
Each block can contain several supported keys. Read neighboring blocks for headings and context but attach each effect
to the block that states it. Never invent values. No tools, code or instructions.
Supported keys in each value (include only keys supported by that span):
vendor: exact vendor name. agreement: exact agreement/title if identified (optional).
effective: [ISO start date, ISO inclusive end date or null when no end appears].
scope: {"product":"exact covered product or resource type", "plan":"exact public plan or null if no plan restriction"}.
period: "resource_utc_calendar_month" if UTC calendar months explicitly govern; otherwise "resource_billing_month" for a public billing cycle/month or "resource_calendar_month" for a calendar month with no specified timezone. Use exactly once. Never infer UTC or the private billing calendar.
symptoms: list of VERBATIM symptom phrases qualifying for downtime, e.g. "failed reads". For symptoms, provider_causes, exclusions, fee_exclusions and request_fields, a list item can alternatively be {"label":"stable_snake_case_identifier","phrase":"verbatim phrase appearing in this exact source block"}. Do not use any identifier as an unsupported substitute for a missing definition.
provider_causes: list of VERBATIM phrases identifying the required provider responsibility.
exclusions: list of VERBATIM excluded causes. Multiple clauses may contribute these lists.
evidence: list selected from "resource_intervals", "account_records", "itemized_fees", "public_status_context",
"verification", "request_contents". Use for obligations to supply scoped logs, interval records, requests or invoice lines.
request_fields: list of verbatim items the request MUST identify/include. submission_channel: exact stated address or channel.
fee_basis: "affected_resource_fees". fee_exclusions: list of verbatim fee categories outside the remedy.
tiers: list of {"below":"exclusive upper availability % as decimal string without %","credit":"credit % as decimal string",
"at_least":null or "explicit inclusive lower % (without %)"}; repeat for every positive band. Do not add a zero-credit band.
boundary: "strict_below" for an explicit equality/zero-credit rule or a table header establishing exclusive thresholds.
rounding: "nearest_cent_half_up" ONLY when explicitly stated; otherwise omit or flag unsupported rounding.
filing: {"kind":"calendar_days" or "billing_cycles","count":positive integer,"utc_time":"HH:MM" or "HH:MM:SS" or null,
"endpoint":"inclusive" (through/by stated time), "exclusive" (strictly before stated time), "whole_day" (all of Nth day),
"whole_cycle" (end of stated whole cycle), or "unclear" (boundary genuinely uncertain)}.
precedence: {"op":"this_sla_controls_conflicts_in_scope","phrase":"exact phrase including this document as subject and its controlling verb","scope":"exact limiting subject phrase"} ONLY if this document itself explicitly prevails in a conflict limited to its own subject matter. Private verification will be independently required. Outside rules incorporated by reference, new economic obligations or unresolved definitions must be unsupported.
account_conditions: list of {"op":"account_restriction" or "contract_noncompliance","effect":"causal_intervals" (loss resulting from that condition) or "filing_precondition" (the claim itself is disallowed),"phrase":"exact source phrase"}. These may summarize explicit account status, suspension or compliance conditions only. Never invent the local status or claim externally defined new economics.
cycle_calendar_month: true only for an explicit statement that billing cycles match UTC calendar months.
remedy: "future_noncash_credit" for a noncash future bill/service credit, contingent on verification as applicable.
nonmaterial: brief reason for a title, publisher, explanatory intro, table separator, or illustrative nonoperative text.
unsupported: brief reason for any unimplemented material condition, incorporated terms/cross-document dependencies,
unknown comparator, or non-supported economic basis. Include it even when other keys in the same span are supported.
Public text only. The customer overlay is supplied later. Retain source wording for identity, symptom and cause labels.
Do not use placeholder example strings. Do not use section/clause numbers as business thresholds.
""" + OPERATOR_PROMPT


def norm(value):
    return ' '.join(re.findall(r'[^\W_]+', value.casefold())) if isinstance(value, str) else ''


def grounded(value, quote):
    return isinstance(value, str) and 0 < len(value) <= 160 and bool(norm(value)) and norm(value) in norm(quote)


def source_date(value, quote):
    d = date.fromisoformat(value)
    choices = [value]
    for month in ('%B', '%b'):
        choices.extend((f'{d.strftime(month)} {d.day}, {d.year}', f'{d.day} {d.strftime(month)} {d.year}',
                        f'{d.strftime(month)} {d.day} {d.year}'))
    return any(norm(s) in norm(quote) for s in choices)


def count_grounded(number, kind, quote):
    words = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
             'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen',
             'nineteen', 'twenty', 'twenty-one', 'twenty-two', 'twenty-three', 'twenty-four', 'twenty-five',
             'twenty-six', 'twenty-seven', 'twenty-eight', 'twenty-nine', 'thirty', 'thirty-one']
    ordinal = {1:'first', 2:'second', 3:'third', 4:'fourth', 5:'fifth', 7:'seventh', 10:'tenth',
               12:'twelfth', 14:'fourteenth', 15:'fifteenth', 20:'twentieth', 30:'thirtieth'}
    candidates = [str(number)] + ([words[number]] if number < len(words) else []) + ([ordinal[number]] if number in ordinal else [])
    unit = {'calendar_days': r'calendar days?', 'billing_cycles': r'(?:monthly )?billing cycles?'}.get(kind)
    if unit is None:
        return False
    # A section number or UTC clock on the same line cannot establish the filing interval.
    number_phrase = r'(?:' + '|'.join(re.escape(w) for w in candidates) + r')(?:st|nd|rd|th)?'
    return bool(re.search(r'\b(?:' + number_phrase + r'(?:\s*\(' + number_phrase + r'\))?\s+' + unit
                          + r'|' + unit + r'\s+' + number_phrase + r')\b', quote, re.I))


def validate_filing(value, quote):
    if not isinstance(value, dict) or set(value) != {'kind', 'count', 'utc_time', 'endpoint'}:
        raise ValueError('Incomplete filing proposition.')
    kind, count, clock, endpoint = (value[k] for k in ('kind', 'count', 'utc_time', 'endpoint'))
    if type(count) is not int or not 1 <= count <= 365 or not isinstance(kind, str) or not count_grounded(count, kind, quote):
        raise ValueError('Unsupported filing interval.')
    if not re.search(r'claim|request|submit|fil(?:e|ing)|receiv|deadline|notice', quote, re.I):
        raise ValueError('Filing origin lacks a claim or request.')
    if not re.search(r'(?:after|following|from the end of|subsequent to)\b[^.;]{0,70}\b(?:month|billing period)|'
                     r'\b(?:month|billing period)[ -]end\b', quote, re.I):
        raise ValueError('Unsupported filing origin.')
    if kind == 'calendar_days':
        if not re.search(r'calendar day', quote, re.I) or endpoint not in {'inclusive','exclusive','whole_day','unclear'}:
            raise ValueError('Unsupported calendar-day filing policy.')
        if clock is not None:
            if (not isinstance(clock, str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?', clock)
                    or not re.search(r'(?<![\d:])' + re.escape(clock) + r'(?![\d:])', quote) or 'utc' not in quote.casefold() or endpoint not in {'inclusive','exclusive','unclear'}):
                raise ValueError('Filing cutoff must be a source-grounded UTC clock.')
            if endpoint != 'unclear':
                exclusive = bool(re.search(r'\b(?:strictly |earlier than |prior to |before )' + re.escape(clock), quote, re.I))
                inclusive = bool(re.search(r'\b(?:by|through|no later than|at or before|on or before)\s+' + re.escape(clock), quote, re.I))
                inclusive = inclusive or bool(re.search(r'\binclusive(?:ly)?\b|including (?:exactly )?(?:the |that )?(?:cutoff|instant|deadline)', quote, re.I))
                if inclusive:  # "on or before" contains a bare "before"
                    exclusive = False
                if (endpoint == 'inclusive' and not inclusive) or (endpoint == 'exclusive' and not exclusive):
                    raise ValueError('Filing endpoint does not match the source clock comparator.')
        elif re.search(r'\b\d{1,2}:\d{2}\b', quote) and endpoint == 'whole_day':
            raise ValueError('An explicit filing clock cannot be replaced by a whole-day cutoff.')
        elif endpoint not in {'whole_day', 'unclear'}:
            raise ValueError('Missing stated filing time.')
    elif kind == 'billing_cycles':
        if not re.search(r'billing cycles?', quote, re.I) or endpoint not in {'whole_cycle','unclear'} or clock is not None:
            raise ValueError('Unsupported billing-cycle filing policy.')
        if endpoint == 'whole_cycle' and not re.search(r'end|close|complete|whole|full|expiration', quote, re.I):
            raise ValueError('Ambiguous cycle endpoint requires review.')
    else:
        raise ValueError('Unsupported filing unit.')


_PERCENT_TOKEN = re.compile(r'(?<![\d.])(\d{1,3}(?:\.\d{1,6})?)\s*(?:%|percent\b)',re.I)


def _quoted_units(token):
    return 0 if re.fullmatch(r'0+(?:\.0+)?',token) else percent_units(token)


def _tier_columns(quote):
    cells=[c.strip().casefold() for c in quote.strip().strip('|').split('|')]
    if len(cells)<2:
        return None
    commitment=next((i for i,c in enumerate(cells) if re.search(r'availability|uptime',c)),None)
    credit=next((i for i,c in enumerate(cells) if re.search(r'credit',c)),None)
    if commitment is None or credit is None or commitment==credit:
        return None
    return commitment,credit,bool(re.search(r'below|less than|under|<',cells[commitment]))


def _source_pair(quote,upper,rate,columns):
    """The quoted rate and exclusive upper bound must refer to the same band."""
    if columns is not None and '|' in quote:
        cells=[c.strip().casefold() for c in quote.strip().strip('|').split('|')]
        threshold_col,credit_col,exclusive=columns
        if max(threshold_col,credit_col)>=len(cells):
            return False
        bound=cells[threshold_col]
        credits=[_quoted_units(m[1]) for m in _PERCENT_TOKEN.finditer(cells[credit_col])]
        if credits!=[rate]:
            return False
        if exclusive and [_quoted_units(m[1]) for m in _PERCENT_TOKEN.finditer(bound)]==[upper]:
            return True
        quote=bound+' yields a '+cells[credit_col]+' service credit'
    parts=re.split(r';|(?<=[.!?])\s+|\s+(?:and|while|whereas)\s+(?=(?:if |when |for |below |under |less than |monthly availability))',quote,flags=re.I)
    for part in parts:
        numbers=list(_PERCENT_TOKEN.finditer(part))
        bounds=[]
        credits=[]
        for i,token in enumerate(numbers):
            before=part[:token.start()].casefold()
            after=part[token.end():].casefold()
            units=_quoted_units(token[1])
            if re.search(r'(?:below|less than|under|lower than|<)\s*$',before) or re.match(r'\s*>\s*(?:monthly )?(?:uptime|availability)',after):
                bounds.append(units)
            elif re.search(r'(?:credit|rate)(?:\s+(?:is|of|equals|will be|shall be))?\s*[:=]?\s*$',before) or re.match(r'\s*(?:service )?credit',after):
                credits.append(units)
            elif i==len(numbers)-1 and re.search(r'credit|rate|earn|receive|yield|qualif|award|entitl|→',part,re.I):
                credits.append(units)
        if bounds==[upper] and credits==[rate]:
            return True
    return False


EVIDENCE_LANGUAGE = {
    'resource_intervals': r'interval|tim(?:e|ing)|timestamps?|logs?|duration|minutes?|seconds?|start.+end',
    'account_records': r'account|customer.{0,20}(?:records?|logs?|identif)',
    'itemized_fees': r'fees?|invoice|billing (?:lines?|statement)|charges?',
    'public_status_context': r'public|status page|status report',
    'verification': r'verif|confirm|validat|review|investigat|determin',
    'request_contents': r'claim|request|submit|submission|must (?:identify|include)|include|contain',
}


def validate_material_coverage(quote, values):
    """Refuse common controlling conditions even when a proposal assigns an unrelated effect."""
    if re.search(r'(?:filing|processing|application|administrative) (?:fee|charge)|'
                 r'\b(?:pay|prepay|remit)\b.{0,32}(?:fees?|charges?|deposit)|'
                 r'(?:\$|€|£)\s*\d', quote, re.I):
        raise ValueError('Unimplemented payment condition or monetary cap.')
    if not {'maintenance', 'supplement', 'account_conditions'} & values.keys() and re.search(r'\b(?:as long as|provided (?:that|however)|only if|contingent upon|conditional on|'
                 r'requires? (?:prior|written) (?:approval|consent)|forfeit(?:s|ed)?)\b', quote, re.I):
        raise ValueError('Unsupported conditional eligibility clause.')
    if re.search(r'(?:credits?|claims?|remedy)\b[^.;]{0,48}\b(?:expire[sd]?|expir(?:ation|y)|waiv(?:ed|er))', quote, re.I):
        raise ValueError('Unimplemented credit expiry or waiver.')
    if re.search(r'\b(?:round(?:ed|ing)?|half.cent)\b', quote, re.I) and not {'rounding','interval_measurement'} & values.keys():
        raise ValueError('Rounding instruction requires a typed calculation.')
    if re.search(r'\b(?:claims?|requests?|fil(?:e|ing))\b[^.;]{0,100}\b(?:calendar days?|billing cycles?)\b', quote, re.I) and 'filing' not in values:
        raise ValueError('Filing period lacks a source-bound deadline operator.')
    if _PERCENT_TOKEN.search(quote) and not {'tiers', 'boundary', 'interval_measurement'} & values.keys():
        raise ValueError('Percentage condition has no applicable threshold or tier.')
    evidence = values.get('evidence', [])
    if not isinstance(evidence, list) or any(not isinstance(kind, str) or kind not in EVIDENCE_LANGUAGE
            or not re.search(EVIDENCE_LANGUAGE[kind], quote, re.I) for kind in evidence):
        raise ValueError('Proposed evidence category has no supporting source wording.')


def compile_resource(document, clauses):
    _validate_document(document)
    spans = _clauses(document.text, [c['quote'] for c in clauses])
    manifest = {'family': FAMILY, 'document': {'name':document.name, 'uri':document.uri,
                'classification':document.classification, 'sha256':sha256(document.text.encode()).hexdigest()},
                'citations':[], 'tiers':[], 'interpretation':'model_proposition_human_review_required'}
    fields = {'vendor','agreement','effective','scope','period','symptoms','provider_causes','exclusions',
              'evidence','fee_basis','fee_exclusions','tiers','boundary','rounding','filing',
              'cycle_calendar_month','remedy','nonmaterial','unsupported','request_fields','submission_channel','precedence','account_conditions'} | OPERATORS
    lists = {'symptoms','provider_causes','exclusions','fee_exclusions','request_fields'}
    all_text = document.text.casefold()
    columns = None
    for index, (row, (start,end,quote)) in enumerate(zip(clauses,spans,strict=True),1):
        values = row['value']
        header=_tier_columns(quote)
        if header is not None:
            columns=header
        elif '|' not in quote:
            columns=None
        if row['field'] != 'resource_terms' or not isinstance(values,dict) or not values or set(values)-fields or 'unsupported' in values:
            raise ValueError(f'Unsupported material in resource clause {index}.')
        require_operative_mapping(quote, values)
        validate_material_coverage(quote, values)
        if re.search(r'\b(?:conflict|inconsisten\w*)\b',quote,re.I) and 'precedence' not in values:
            raise ValueError(f'Material conflict rule unresolved in clause {index}.')
        if re.search(r'(?:terminat|suspend|suspension|restrict|breach|non.complian|fail(?:ure)? to (?:comply|abide))',quote,re.I) and re.search(r'(?:account|agreement|terms|customer|access)',quote,re.I) and 'account_conditions' not in values:
            raise ValueError(f'Account/compliance condition requires a typed local evidence predicate at clause {index}.')
        if re.search(r'\b(?:other|additional) (?:terms|conditions|requirements).{0,50}(?:apply|govern)|'
                     r'\b(?:meaning|meanings|definitions?) (?:given|assigned|specified|set forth|provided) (?:in|by)|'
                     r'\b(?:capitalized|undefined) terms.{0,60}(?:meanings?|defined) .{0,50}agreement',quote,re.I):
            raise ValueError(f'External terms or definitions unresolved in clause {index}.')
        if re.search(r'incorporat(?:ed|es) by reference|subject to (?:section|clause|article|the .*?terms)|'
                     r'(?:as (?:defined|set forth|described)|governed) (?:in|by) (?:section|the .*?agreement|our .*?terms)',quote,re.I):
            raise ValueError(f'Unresolved governing reference in resource clause {index}.')
        if (re.search(r'\b(?:excluded|excludes?|excluding|unless|except(?:ions?)?)\b',quote,re.I)
                and not {'exclusions','fee_exclusions','account_conditions','maintenance'} & values.keys()):
            raise ValueError(f'Unmapped exclusion or condition in clause {index}.')
        if re.search(r'\b(?:capped at|up to|aggregate cap|total cap|at our discretion|sole discretion)\b',quote,re.I):
            raise ValueError(f'Unsupported discretionary amount or cap in clause {index}.')
        citation = {'id':index,'start':start,'end':end,'quote':quote,'field':'resource_terms','propositions':values,
                    'block_sha256':sha256(quote.encode()).hexdigest()}
        manifest['citations'].append(citation)
        lower = quote.casefold()
        for key,value in values.items():
            if key in OPERATORS:
                apply_operator(manifest, key, value, quote)
                continue
            if key == 'nonmaterial':
                ordinary_heading = bool(re.fullmatch(r'(?:section\s+)?[0-9]+(?:\.[0-9]+)*[.) :]+[a-z][a-z /-]{1,55}',lower.strip()))
                if len(values)==1 and re.search(r'[0-9]',lower) and not ordinary_heading:
                    raise ValueError('Numerical source condition lacks an operative mapping.')
                if (not isinstance(value,str) or not value.strip() or len(value)>300 or
                        len(values)==1 and re.search(r'[%≤≥]|\b(?:shall|must|unless|except|subject to|required|within|refund|exclusive|cap|eligible|only|not|provided that|excludes?)\b',lower)):
                    raise ValueError('Material source labeled nonoperative.')
                continue
            if key in lists:
                if not isinstance(value,list) or not value:
                    raise ValueError(f'Ungrounded {key} labels.')
                labels=manifest.setdefault(key,[])
                for item in value:
                    if isinstance(item,str) and grounded(item,quote):
                        label=item
                    elif (isinstance(item,dict) and set(item)=={'label','phrase'} and isinstance(item['label'],str)
                          and re.fullmatch(r'[a-z][a-z0-9_]{0,63}',item['label']) and isinstance(item['phrase'],str)
                          and 0<len(item['phrase'])<=256 and item['phrase'] in quote):
                        label=item['label']
                        bindings=manifest.setdefault('label_bindings',{}).setdefault(key,{})
                        old=bindings.get(label)
                        if old and old['phrase']!=item['phrase']:
                            raise ValueError('Conflicting definitions for the same stable source operator.')
                        bindings[label]={'phrase':item['phrase'],'block':index,'block_sha256':citation['block_sha256']}
                    else:
                        raise ValueError(f'Ungrounded {key} labels.')
                    if label not in labels:
                        labels.append(label)
                continue
            if key == 'precedence':
                if not isinstance(value,dict) or set(value)!={'op','phrase','scope'} or value['op']!='this_sla_controls_conflicts_in_scope':
                    raise ValueError('Unsupported precedence operator.')
                phrase,scope=value['phrase'],value['scope']
                if (not isinstance(phrase,str) or not isinstance(scope,str) or not scope.strip()
                        or phrase not in quote or scope not in quote
                        or not re.search(r'conflict|inconsisten',quote,re.I)
                        or not re.search(r'(?:this|these) (?:sla|service level agreement|schedule|agreement|terms)'
                                         r"(?:’s|'s| terms| provisions)?(?: will| shall| must)? (?:control|govern|prevail|takes? precedence)",phrase,re.I)
                        or not re.search(r'solely|only|limited to|with (?:respect|regard) to|subject matter|to the extent',quote,re.I)
                        or not re.search(r'uptime|availability|service level|service credit|subject matter|\bSLA\b',scope,re.I)
                        or re.search(r'(?:all|other) (?:commercial|contractual) (?:matters|terms)|unless|except',scope,re.I)):
                    raise ValueError('Source does not establish a limited controlling-document conflict rule.')
            if key == 'account_conditions':
                if not isinstance(value,list) or not value:
                    raise ValueError('Expected source-defined account condition list.')
                for condition in value:
                    if not isinstance(condition,dict) or set(condition)!={'op','effect','phrase'}:
                        raise ValueError('Invalid account condition proposition.')
                    op,effect,phrase=condition['op'],condition['effect'],condition['phrase']
                    language={'account_restriction':r'suspen|restrict|terminat|disabled|blocked|good standing',
                              'contract_noncompliance':r'breach|non.complian|compl(?:y|iance)|violat|abid'}
                    if (not isinstance(op,str) or op not in language or not isinstance(phrase,str) or not phrase or phrase not in quote
                            or not re.search(language[op],phrase,re.I)
                            or effect not in ('causal_intervals','filing_precondition')):
                        raise ValueError('Ungrounded account condition or effect.')
                    if effect=='causal_intervals' and not re.search(r'caus|result|attribut|due to|aris|stemming from',quote,re.I):
                        raise ValueError('Source does not establish an interval-specific causal exclusion.')
                    if effect=='filing_precondition' and (not re.search(r'claim|request|eligib|entitl',quote,re.I)
                            or re.search(r'downtime|unavailability|outage',phrase,re.I) and re.search(r'caus|result|due to',quote,re.I)):
                        raise ValueError('Cannot turn a causal exclusion into a global filing bar.')
                    previous=manifest.setdefault('account_conditions',[])
                    if any(c['op']==op and c!=condition for c in previous):
                        raise ValueError('Conflicting account condition predicates.')
                    if condition not in previous:
                        previous.append(condition)
                continue
            if key == 'evidence':
                if not value:
                    raise ValueError('Empty resource evidence condition.')
                manifest.setdefault(key,[]).extend(v for v in value if v not in manifest.get(key,[]))
                continue
            if key == 'tiers':
                if not isinstance(value,list) or not value:
                    raise ValueError('Missing tier values.')
                accounted = Counter()
                for tier in value:
                    if not isinstance(tier,dict) or set(tier)-{'below','credit','at_least'} or not {'below','credit'}<=set(tier):
                        raise ValueError('Malformed resource tier.')
                    if not all(isinstance(tier[k],str) for k in ('below','credit')):
                        raise ValueError('Expected decimal percent tokens.')
                    upper,rate = percent_units(tier['below']),percent_units(tier['credit'])
                    numbers=[_quoted_units(t[1]) for t in _PERCENT_TOKEN.finditer(lower)]
                    if upper not in numbers or rate not in numbers or not _source_pair(quote,upper,rate,columns):
                        raise ValueError('Credit tier values absent from cited source.')
                    floor = tier.get('at_least')
                    if floor is not None:
                        if not isinstance(floor,str):
                            raise ValueError('Invalid explicit band lower bound.')
                        floor = 0 if re.fullmatch(r'0(?:\.0+)?',floor) else percent_units(floor)
                        if floor not in numbers:
                            raise ValueError('Uncited tier lower bound.')
                    if re.search(r'(?:at most|no more than|less than or equal to|≤|<=)\s*'+re.escape(tier['below'])+r'\s*(?:%|percent)',lower):
                        raise ValueError('Inclusive upper tier is unsupported.')
                    accounted.update([upper, rate])
                    if floor is not None:
                        accounted.update([floor])
                    manifest['tiers'].append(dict(below_units=upper,credit_units=rate,citation=index,floor=floor))
                if accounted != Counter(_quoted_units(m[1]) for m in _PERCENT_TOKEN.finditer(quote)):
                    raise ValueError('Every percentage in a resource tier block must map to a threshold, floor or credit.')
                continue
            if key in manifest and manifest[key] != value:
                raise ValueError(f'Conflicting {key} propositions.')
            if key in {'vendor','agreement','submission_channel'} and not grounded(value,quote):
                raise ValueError(f'Ungrounded resource {key}.')
            if key == 'effective':
                if (not isinstance(value,list) or len(value)!=2 or not value[0]
                        or not all(isinstance(v,str) and source_date(v,quote) for v in value if v is not None)
                        or value[1] and value[1]<value[0]):
                    raise ValueError('Ungrounded source effective dates.')
            if key == 'scope':
                if (not isinstance(value,dict) or set(value)!={'product','plan'} or not grounded(value['product'],quote)
                        or value['plan'] is not None and not grounded(value['plan'],quote)):
                    raise ValueError('Ungrounded public product/plan scope.')
            if key == 'period' and (value not in {'resource_utc_calendar_month','resource_billing_month','resource_calendar_month'}
                    or 'month' not in lower and 'billing cycle' not in lower
                    or value=='resource_utc_calendar_month' and not any('utc' in sentence and 'month' in sentence
                        and not re.search(r'claims?|credit requests?|deadline|submission',sentence)
                        for sentence in re.split(r'[.;\n]',lower))):
                raise ValueError('Unsupported resource month denominator.')
            if key == 'boundary' and (value!='strict_below' or not re.search(r'below|lower than|less than|<|equal|threshold|at or above',lower)):
                raise ValueError('Uncited strict availability boundary.')
            if key == 'fee_basis' and (value != 'affected_resource_fees'
                    or not re.search(r'fees?|charges?|spend|billed|rental|subscription cost', lower)
                    or not re.search(r'\b(?:affected|impacted|unavailable|qualifying|same|corresponding)\b', lower)
                    or re.search(r'(?:all|aggregate|total) (?:account|tenant|customer|unaffected) (?:fees?|charges?|spend)', lower)):
                raise ValueError('Ungrounded affected-resource fee basis.')
            if key=='rounding' and (value!='nearest_cent_half_up' or 'cent' not in lower
                    or not re.search(r'half.{0,15}up|(?:ties|halves|half.a.cent).{0,35}(?:up|higher)',lower)):
                raise ValueError('Unconfirmed half-up cent rounding.')
            if key=='filing':
                validate_filing(value,quote)
            if key=='cycle_calendar_month' and (value is not True or not re.search(r'billing cycle',lower) or 'calendar month' not in lower):
                raise ValueError('Unsupported inferred billing calendar.')
            if key=='remedy' and (value!='future_noncash_credit' or 'credit' not in lower
                    or not re.search(r'\b(?:future|next|subsequent|following)\b',lower)
                    or not re.search(r'invoice|bill|service (?:fee|charge|credit)',lower)
                    or re.search(r'(?:option|elect|choose|exchange|redeem).{0,35}\bcash\b',lower)):
                raise ValueError('Unconfirmed future credit remedy.')
            manifest[key]=value
    required={'vendor','effective','scope','period','symptoms','provider_causes','fee_basis','filing','remedy','evidence'}
    if required-set(manifest) or not manifest['tiers']:
        raise ValueError('Incomplete resource-month source propositions: '+', '.join(sorted(required-set(manifest))))
    if not re.search(r'below|less than|lower than|<',all_text):
        raise ValueError('Exclusive availability comparison absent from the document.')
    if 'request_contents' in manifest['evidence'] and not manifest.get('request_fields'):
        raise ValueError('Explicit request contents must be mapped to locally verifiable filing proof.')
    if re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',document.text) and not manifest.get('submission_channel'):
        raise ValueError('Published filing contact requires source-bound channel interpretation.')
    manifest.setdefault('agreement',None)
    manifest.setdefault('exclusions',[])
    manifest.setdefault('fee_exclusions',[])
    if {norm(v) for v in manifest['provider_causes']} & {norm(v) for v in manifest['exclusions']}:
        raise ValueError('Conflicting included and excluded responsibility labels.')
    if manifest.get('maintenance') and any('maintenance' in norm(label) for label in manifest['exclusions']):
        raise ValueError('A conditional maintenance exclusion cannot also subtract maintenance unconditionally.')
    lower,previous=0,MAX_PERCENT+1
    manifest['tiers'].sort(key=lambda t:t['below_units'])
    for tier in manifest['tiers']:
        if tier['below_units']<=lower or tier['credit_units']>=previous or tier.pop('floor') not in {None,lower}:
            raise ValueError('Overlapping, missing or conflicting resource credit bands.')
        lower,previous=tier['below_units'],tier['credit_units']
        tier.update(product=manifest['scope']['product'],plan=manifest['scope']['plan'] or '*')
    return manifest


def public_blocks(text):
    """Stable, complete, ordered slices of original public source bytes (Unicode character offsets)."""
    blocks=[]
    for line in re.finditer(r'[^\r\n]+',text):
        left=line.start()
        end=line.end()
        while left<end:
            while left<end and text[left].isspace():
                left+=1
            if left==end:
                break
            limit=min(left+4096,end)
            if limit<end:
                split=text.rfind(' ',left,limit)
                if split>left:
                    limit=split
            right=limit
            while right>left and text[right-1].isspace():
                right-=1
            quote=text[left:right]
            blocks.append({'id':len(blocks)+1,'start':left,'end':right,'sha256':sha256(quote.encode()).hexdigest(),'text':quote})
            left=limit
    if not 1<=len(blocks)<=200:
        raise ValueError('Resource extraction supports 1–200 public source blocks.')
    return blocks


def project_blocks(text,response):
    """Model output cannot replace, reorder, duplicate or discard even one nonblank source block."""
    blocks=public_blocks(text)
    if not isinstance(response,dict) or set(response)!={'blocks'} or not isinstance(response['blocks'],list) or len(response['blocks'])!=len(blocks):
        raise ValueError('Model must return exactly one effect record per source block.')
    rows=[]
    for block,item in zip(blocks,response['blocks'],strict=True):
        if (not isinstance(item,dict) or set(item)!={'id','value'} or type(item['id']) is not int
                or item['id']!=block['id'] or not isinstance(item['value'],dict)):
            raise ValueError('Missing, altered, duplicate or reordered immutable source block ID.')
        rows.append({'quote':block['text'],'field':'resource_terms','value':item['value']})
    index=[{k:v for k,v in block.items() if k!='text'} for block in blocks]
    return rows,index
