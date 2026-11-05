"""Source-grounded extensions for resource-month terms. This module never executes proposals."""
import re

from . import vendor_resource_predicates as scoped, vendor_service_month as service


PROMPT = """
Additional supported resource-month operators. Attach each operator to the immutable block stating it;
a block may have several keys. Do not label these material terms nonmaterial or unsupported when they fit:
interval_measurement: list containing "union_overlaps" for counting concurrent/duplicate intervals once,
"exact_elapsed" for actual elapsed or fractional time, "clip_to_month" for counting just time within the service month.
Each input block has interval_measurement_options. This list is a vocabulary restriction, not evidence.
If it is empty, NEVER output interval_measurement for that block. Even when an option is listed,
emit it only when THIS block directly establishes it. Scope, vendor and effective-date blocks typically have no
interval_measurement. Do not duplicate effects from adjacent blocks. For an explicit availability formula using qualifying elapsed downtime and
the entire resource month use "availability_ratio". A percentage conversion factor is not a payout tier.
maintenance: {"basis":"within_announced_window" or "caused_within_announced_window",
"notice":null or {"count":positive integer,"unit":"minutes","hours" or "days"}}. Use null for advance publication
without a stated minimum lead. For a cause requirement also include "cause": "short verbatim source phrase".
Use this conditional maintenance operator instead of listing scheduled maintenance as an unconditional exclusion.
fee_adjustment: "after_discounts" when the base is the actual affected resource's net fees after discounts.
supplement: "same_filing_deadline" for curing a missing required item before/by the original deadline, with no extension.
prior_credit: "subtract_issued_same_resource_month" when already granted or issued credits for the same resource and
month reduce its remaining payable credit. Do not apply this operator to unrelated/general credits.
Separate source-defined governance and financial conditions. For percentage tables, use the header's actual column
order and map each positive band, its exclusive upper bound, any explicit inclusive floor, and the rate.
The filing endpoint is inclusive for 'by' or an explicitly included cutoff. A printed UTC time must be preserved.
A clause requiring a timely initial filing AND allowing timely supplementation may contain filing, supplement,
evidence and request_fields together. Always mark genuinely unresolved other conditions unsupported.
Additional exact measurement operators: interval_measurement may contain "half_open" for including starts and excluding
ends, "no_minimum_duration", "fixed_denominator" when exclusions do not reduce total month duration, and
"unrounded_availability" when rounding before tier selection is forbidden.
measurement_symbols={"total":{"symbol":"exact single-letter name","phrase":"exact definition phrase"},
"down":{"symbol":"exact single-letter name","phrase":"exact definition phrase"}}. Keys may appear in separate blocks.
Use for total month duration and qualifying/unavailable duration. interval_measurement=["availability_ratio"] accepts
100 * (totalSymbol - downSymbol) / totalSymbol after both definitions are source-bound.
zero_band={"at_least":"decimal percentage string"} for an explicit zero credit at and above a threshold.
monthly_limit={"percent":"maximum credit percentage as decimal string","one_per_scope":true} may contain either or both
keys when explicitly stated. The percentage must match the maximum positive tier and a single remedy binds the existing
account/product/resource/month identity.
maintenance may additionally include customer_delivery=true if the notice must reach the customer in advance,
and scope=["product","region"] (or stated subset) when the notice must identify those fields. The private evidence then
requires actual delivery, recipient and exact notice scope, independently from the announcement timestamp.

""" + scoped.PROMPT + service.PROMPT

OPERATORS = {'maintenance', 'interval_measurement', 'fee_adjustment', 'supplement', 'prior_credit','measurement_symbols','zero_band','monthly_limit'} | scoped.FIELDS | service.FIELDS

_MEASURES = {
    'union_overlaps': (r'overlap|concurrent|intersect|union|simultaneous|double.count|(?:count|measure)[^.;]{0,30}once',
                       r'time|interval|minute|second|incident|outage|failure|duration|report'),
    'half_open': (r'include.{0,35}(?:start|begin)', r'exclude.{0,35}end'),
    'no_minimum_duration': (r'no minimum|without (?:a )?minimum', r'duration|incident|outage'),
    'fixed_denominator': (r'exclusion', r'(?:do|does) not reduce|unchanged|unaffected'),
    'unrounded_availability': (r'(?:do|must|shall) not round|unrounded|without rounding', r'availability|tier'),
    'exact_elapsed': (r'fraction|elapsed|sub.?minute|sub.?second|actual duration|without rounding|not round|partial minutes?|partial seconds?',
                      r'time|duration|minute|second|interval|outage'),

}


def _cites(patterns, text):
    return all(re.search(pattern, text, re.I) for pattern in patterns)


_UNIT = r'(?:seconds?|minutes?|hours?)'
_LOST = (r'(?:the )?(?:(?:total|actual|aggregate) )?(?:(?:covered|qualifying|eligible|unavailable|interrupted|lost) '
         r'(?:(?:outage|interruption|downtime) )?' + _UNIT + r'|(?:covered |qualifying |eligible )?'
         r'(?:downtime|interruption duration|outage duration)|(?:duration|elapsed time) of (?:the )?(?:covered|qualifying) interruptions?)')
_TOTAL = (r'(?:the )?(?:(?:all|total|number of) )?' + _UNIT
          + r' (?:in|during|of|for) (?:the |this |that |each )?(?:(?:utc|calendar|service|measurement|applicable|affected|billing) )*month')
_RATIO_LIKE = re.compile(r'\b(?:availability|uptime)\b[^.;\n]*(?:divided by|minus|[×÷*/−])[^.;\n]*'
                         r'\b(?:seconds?|minutes?|hours?|downtime|interruptions?)\b', re.I)


def _availability_formula(quote):
    # Recognize only algebra actually evaluated by the interpreter. Operand order matters.
    expression = re.sub(r'\s+', ' ', quote.casefold()).translate(str.maketrans({'×':'*','÷':'/','−':'-'}))
    for word, symbol in [('multiplied by','*'), ('times','*'), ('divided by','/'), ('minus','-'), ('one','1')]:
        expression = re.sub(r'\b' + word + r'\b', symbol, expression)
    end = r'(?!\s*(?:[+*/−-]|plus\b|less\b|squared\b))'
    forms = [r'100\s*\*\s*\(\s*1\s*-\s*' + _LOST + r'\s*/\s*' + _TOTAL + r'\s*\)',
             r'\(\s*1\s*-\s*' + _LOST + r'\s*/\s*' + _TOTAL + r'\s*\)\s*\*\s*100',
             r'100\s*\*\s*\(\s*' + _TOTAL + r'\s*-\s*' + _LOST + r'\s*\)\s*/\s*' + _TOTAL]
    fixed = re.search(r'100\s*\*\s*\(\s*([1-9][\d,]*)\s*-\s*unavailable minutes?\s*\)\s*/\s*([1-9][\d,]*)' + end, expression)
    if fixed and fixed[1].replace(',', '') == fixed[2].replace(',', '') and _RATIO_LIKE.search(quote):
        return 'fixed_minutes:' + fixed[1].replace(',', '')
    if not _RATIO_LIKE.search(quote):
        return False
    # Natural-language multiplication with no grouping has a second mathematical reading.
    # The registry requires disclosure, a distinguishing shadow case and authenticated interpretation.
    natural = bool(re.search(r'100\s+(?:times|multiplied by)\s+one\s+minus', quote, re.I))
    if natural:
        forms.append(r'100\s*\*\s*1\s*-\s*' + _LOST + r'\s*/\s*' + _TOTAL)
    for index, form in enumerate(forms):
        match = re.search(r'(?<![\d.])' + form + end, expression)
        if match and not re.search(r'[+/*-]\s*$', expression[:match.start()]):
            units = {unit.rstrip('s') for unit in re.findall(_UNIT, match[0])}
            if len(units) == 1:
                return 'review_grouping' if index == 3 else 'explicit_grouping'
    return False


def symbolic_formula(quote):
    expression = re.sub(r'\s+', ' ', quote).replace('×', '*')
    for phrase, op in [('multiplied by','*'),('times','*'),('divided by','/'),('minus','-')]:
        expression = re.sub(r'\b'+phrase+r'\b',op,expression,flags=re.I)
    match = re.search(r'100\s*\*\s*\(\s*([A-Za-z])\s*-\s*([A-Za-z])\s*\)\s*/\s*\1(?!\w|\s*[+*/-])',expression)
    return {'total':match[1], 'down':match[2]} if match and match[1]!=match[2] else None


_MONTH_CLIP = re.compile(
    r'\b(?:clip|truncate|intersect|split)\w*\b.{0,55}\b(?:month.{0,12}boundar|service month|calendar month)|'
    r'\b(?:portion|part|intervals?)\b.{0,35}\b(?:within|inside|fall(?:s|ing)? in)\b.{0,22}\bmonth\b|'
    r'\bcount(?:s|ed)? only\b.{0,38}\b(?:during|within|inside)\b.{0,22}\bmonth\b', re.I)


def interval_options(quote):
    options = [name for name, patterns in _MEASURES.items() if _cites(patterns, quote)]
    if _MONTH_CLIP.search(quote):
        options.append('clip_to_month')
    if _availability_formula(quote) or symbolic_formula(quote):
        options.append('availability_ratio')
    return options


def apply_operator(manifest, key, value, quote):
    """Only compile operators whose controlling predicates are evidenced by this source block."""
    if key == 'measurement_symbols':
        if not isinstance(value, dict) or not value or set(value)-{'total','down'}:
            raise ValueError('Unsupported symbolic duration definition.')
        for role, definition in value.items():
            if not isinstance(definition, dict) or set(definition)!={'symbol','phrase'}:
                raise ValueError('Incomplete symbolic duration definition.')
            symbol, phrase = definition['symbol'], definition['phrase']
            if (not isinstance(symbol, str) or not re.fullmatch('[A-Za-z]',symbol)
                    or not isinstance(phrase,str) or ' '.join(phrase.split()) not in ' '.join(quote.split())
                    or not re.search(r'\b' + re.escape(symbol) + r'\s+(?:(?:be|is|means|denotes|represents)\s+)?'
                                     + re.escape(' '.join(phrase.split())), ' '.join(quote.split()))
                       and not re.search(r'\b'+symbol+r'\b', phrase)
                    or not _cites([r'month',r'all|total|every',r'second|minute|duration|elapsed'] if role=='total'
                                  else [r'unavail|downtime|covered|qualifying',r'second|minute|duration|elapsed'],phrase)):
                raise ValueError('Symbol is not grounded in the proposed duration role.')
            old=manifest.setdefault('measurement_symbols',{}).get(role)
            if old and old!=symbol:
                raise ValueError('Conflicting symbolic duration definitions.')
            manifest['measurement_symbols'][role]=symbol
        return
    if key in ('zero_band', 'monthly_limit'):
        from .vendor_terms import percent_units
        if not isinstance(value,dict) or not value or set(value)-({'at_least'} if key=='zero_band' else {'percent','one_per_scope'}):
            raise ValueError('Unsupported zero band or monthly cap.')
        field='at_least' if key=='zero_band' else 'percent'
        if field in value:
            number=value[field]
            if not isinstance(number,str) or not re.search(re.escape(number)+r'\s*(?:%|percent)',quote,re.I):
                raise ValueError('Uncited credit boundary or cap percentage.')
            units=percent_units(number)
            if key=='zero_band' and not _cites([r'at least|≥|>=|at or above|equal.{0,15}above',r'0\s*(?:%|percent)|no credit|zero'],quote):
                raise ValueError('Source does not establish a zero rate above the boundary.')
            if key=='monthly_limit' and not re.search(r'maximum|cap|limit',quote,re.I):
                raise ValueError('Missing explicit monthly ceiling.')
            manifest['zero_at_or_above' if key=='zero_band' else 'monthly_maximum']=units
        if 'one_per_scope' in value:
            if value['one_per_scope'] is not True or not _cites([r'one|single',r'remedy|credit|entitlement',r'month'],quote):
                raise ValueError('Uncited single monthly remedy.')
            manifest['one_per_scope']=True
        return
    if key in service.FIELDS:
        service.validate(manifest, key, value, quote)
        return
    if key in scoped.FIELDS:
        scoped.validate(manifest, key, value, quote)
        return
    if key == 'interval_measurement':
        options = interval_options(quote)
        if not isinstance(value, list) or not value or any(not isinstance(item, str) or item not in options for item in value):
            raise ValueError('Uncited interval measurement proposition.')
        formula = _availability_formula(quote)
        symbols=symbolic_formula(quote)
        if 'availability_ratio' in value and symbols:
            manifest['formula_symbols']=symbols
        if 'availability_ratio' in value and formula and formula.startswith('fixed_minutes:'):
            manifest['fixed_formula_minutes'] = int(formula.split(':')[1])
        if 'availability_ratio' in value and formula == 'review_grouping':
            manifest['formula_grouping_review'] = {
                'source_block': manifest['citations'][-1]['id'],
                'selected': '100 * (1 - covered_duration / month_duration)',
                'alternative': '(100 * 1) - covered_duration / month_duration',
                'units': 'covered_duration and month_duration use the same unit',
                'endpoint_vectors': [{'covered_fraction': '0', 'selected_percent': '100', 'alternative_percent': '100'},
                                     {'covered_fraction': '1', 'selected_percent': '0', 'alternative_percent': '99'}],
                'decision': 'Approve the selected grouping only if the independent case and cited meaning support it.'}
        manifest[key] = sorted(set(manifest.get(key, [])) | set(value))
        return
    if key == 'maintenance':
        if (not isinstance(value, dict) or not {'basis','notice'}<=set(value)
                or set(value)-{'basis','notice','cause','customer_delivery','scope'}):
            raise ValueError('Invalid maintenance window proposition.')
        basis = value['basis']
        if (basis not in ('within_announced_window', 'caused_within_announced_window')
                or not _cites([r'maintenance', r'announc|notice|notif|publish|communicat|post(?:ed|ing)',
                                        r'window|period|interval|schedul'], quote)):
            raise ValueError('Maintenance requires a source-defined announced window.')
        if basis == 'caused_within_announced_window':
            if (not isinstance(value.get('cause'), str) or not value['cause'].strip() or value['cause'] not in quote
                    or not re.search(r'caus|due to|attribut|result|aris', quote, re.I)):
                raise ValueError('Maintenance causality requires an exact cited cause.')
        elif 'cause' in value:
            raise ValueError('Inconsistent maintenance cause.')
        if 'customer_delivery' in value and (value['customer_delivery'] is not True
                or not _cites([r'customer|client',r'deliver|receive|reach|sent to'],quote)):
            raise ValueError('Uncited customer delivery condition.')
        if 'scope' in value and (not isinstance(value['scope'],list) or not value['scope']
                or not all(k in ('product','region') and re.search(r'\b'+k+r'\b',quote,re.I) for k in value['scope'])):
            raise ValueError('Ungrounded maintenance notice scope.')
        notice = value['notice']
        if notice is not None:
            if (not isinstance(notice, dict) or set(notice) != {'count', 'unit'} or type(notice['count']) is not int
                    or not 1 <= notice['count'] <= 3660 or notice['unit'] not in ('minutes', 'hours', 'days')
                    or not re.search(r'\b' + str(notice['count']) + r'\s+(?:elapsed\s+)?' + notice['unit'][:-1] + r's?\b', quote, re.I)):
                raise ValueError('Unsupported maintenance advance-notice quantity.')
        elif re.search(r'\b(?:\d+|one|two|three|four|six|eight|twelve|twenty.four)\s*(?:hours?|minutes?|days?)\b', quote, re.I):
            raise ValueError('A stated maintenance-notice interval cannot be omitted.')
    elif key == 'fee_adjustment':
        if value != 'after_discounts' or not _cites([r'discount', r'net|after|less|deduct|subtract|reduc'], quote):
            raise ValueError('Unsupported discount or fee adjustment.')
    elif key == 'supplement':
        if value != 'same_filing_deadline' or not _cites([
                r'supplement|cure|missing|incomplete|additional (?:material|evidence|documentation)',
                r'(?:same|original|existing).{0,40}(?:deadline|cutoff|window|time|limit)|'
                r'(?:deadline|cutoff|window).{0,35}(?:same|appl|unchanged|extend)|without (?:an )?extension'], quote):
            raise ValueError('A supplement must preserve the contractual filing deadline.')
    elif key == 'prior_credit':
        if re.search(r'(?:all|across|any|unrelated) (?:resources|accounts|services)|account.wide', quote, re.I):
            raise ValueError('A wider credit ledger cannot be treated as a resource-specific deduction.')
        if value != 'subtract_issued_same_resource_month' or not _cites([
                r'credit', r'previous|prior|already|earlier', r'grant|award|issu|applie|posted|received',
                r'reduce|deduct|subtract|less|offset|net|remain', r'month|billing period',
                r'\bsame\b|\bthat\b|\bthis\b|\bcorresponding\b'], quote):
            raise ValueError('Unconfirmed scoped prior-credit deduction.')
    else:
        raise ValueError('Unknown resource operator.')
    if key in manifest and manifest[key] != value:
        raise ValueError('Conflicting resource operators for ' + key)
    manifest[key] = value


def require_operative_mapping(quote, values):
    if _RATIO_LIKE.search(quote) or symbolic_formula(quote):
        measurement = values.get('interval_measurement')
        if not isinstance(measurement, list) or 'availability_ratio' not in measurement or not (_availability_formula(quote) or symbolic_formula(quote)):
            raise ValueError('Explicit availability ratio is unsupported or unmapped.')
    cues = {
        'maintenance': (r'maintenance', r'notice|announc|notif|publish|post(?:ed|ing)'),
        'fee_adjustment': (r'discount', r'net|after|less|deduct|subtract|reduc'),
        'supplement': (r'supplement|incomplete (?:claim|request)|cure (?:a|the) missing', r'deadline|cutoff|window|original'),
        'prior_credit': (r'(?:previous|prior|already|earlier).{0,45}credit|credit.{0,45}(?:previous|prior|already|earlier)',
                         r'reduce|deduct|subtract|less|offset|net|remain'),
        'interval_measurement': (r'overlapping|fractional|concurrent', r'interval|time|duration|minute|second|outage|incident'),
    }
    for key, patterns in cues.items():
        if key == 'supplement' and 'cure_clock' in values:
            continue
        if key not in values and all(re.search(pattern, quote, re.I) for pattern in patterns):
            raise ValueError('Unmapped controlling resource term: ' + key)
