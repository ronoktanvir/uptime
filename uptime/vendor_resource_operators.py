"""Source-grounded extensions for resource-month terms. This module never executes proposals."""
import re


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
"""

OPERATORS = {'maintenance', 'interval_measurement', 'fee_adjustment', 'supplement', 'prior_credit'}

_MEASURES = {
    'union_overlaps': (r'overlap|concurrent|intersect|union|simultaneous|double.count|(?:count|measure)[^.;]{0,30}once',
                       r'time|interval|minute|second|incident|outage|failure|duration|report'),
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
    if not _RATIO_LIKE.search(quote):
        return False
    for form in forms:
        match = re.search(r'(?<![\d.])' + form + end, expression)
        if match and not re.search(r'[+/*-]\s*$', expression[:match.start()]):
            units = {unit.rstrip('s') for unit in re.findall(_UNIT, match[0])}
            if len(units) == 1:
                return True
    return False


_MONTH_CLIP = re.compile(
    r'\b(?:clip|truncate|intersect|split)\w*\b.{0,55}\b(?:month.{0,12}boundar|service month|calendar month)|'
    r'\b(?:portion|part|intervals?)\b.{0,35}\b(?:within|inside|fall(?:s|ing)? in)\b.{0,22}\bmonth\b|'
    r'\bcount(?:s|ed)? only\b.{0,38}\b(?:during|within|inside)\b.{0,22}\bmonth\b', re.I)


def interval_options(quote):
    options = [name for name, patterns in _MEASURES.items() if _cites(patterns, quote)]
    if _MONTH_CLIP.search(quote):
        options.append('clip_to_month')
    if _availability_formula(quote):
        options.append('availability_ratio')
    return options


def apply_operator(manifest, key, value, quote):
    """Only compile operators whose controlling predicates are evidenced by this source block."""
    if key == 'interval_measurement':
        options = interval_options(quote)
        if not isinstance(value, list) or not value or any(not isinstance(item, str) or item not in options for item in value):
            raise ValueError('Uncited interval measurement proposition.')
        manifest[key] = sorted(set(manifest.get(key, [])) | set(value))
        return
    if key == 'maintenance':
        if not isinstance(value, dict) or set(value) not in ({'basis', 'notice'}, {'basis', 'notice', 'cause'}):
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
        notice = value['notice']
        if notice is not None:
            if (not isinstance(notice, dict) or set(notice) != {'count', 'unit'} or type(notice['count']) is not int
                    or not 1 <= notice['count'] <= 3660 or notice['unit'] not in ('minutes', 'hours', 'days')
                    or not re.search(r'\b' + str(notice['count']) + r'\s+' + notice['unit'][:-1] + r's?\b', quote, re.I)):
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
    if _RATIO_LIKE.search(quote):
        measurement = values.get('interval_measurement')
        if not isinstance(measurement, list) or 'availability_ratio' not in measurement or not _availability_formula(quote):
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
        if key not in values and all(re.search(pattern, quote, re.I) for pattern in patterns):
            raise ValueError('Unmapped controlling resource term: ' + key)
