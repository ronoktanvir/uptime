"""Source-grounded extensions for resource-month terms. This module never executes proposals."""
import re


PROMPT = """
Additional supported resource-month operators. Attach each operator to the immutable block stating it;
a block may have several keys. Do not label these material terms nonmaterial or unsupported when they fit:
interval_measurement: list containing "union_overlaps" for counting concurrent/duplicate intervals once,
"exact_elapsed" for actual elapsed or fractional time, "clip_to_month" for counting just time within the service month.
Repeat relevant items across blocks. For an explicit availability formula using qualifying elapsed downtime and
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
    'union_overlaps': r'overlap|concurrent|intersect|union|once|without double|not double',
    'exact_elapsed': r'fraction|elapsed|sub.?minute|sub.?second|actual duration|without rounding|not round',
    'clip_to_month': r'within|inside|clip|portion|boundary|boundaries',
    'availability_ratio': r'percent|100|ratio|divid|subtract|minus',
}


def _cites(patterns, text):
    return all(re.search(pattern, text, re.I) for pattern in patterns)


def apply_operator(manifest, key, value, quote):
    """Only compile operators whose controlling predicates are evidenced by this source block."""
    if key == 'interval_measurement':
        if not isinstance(value, list) or not value or any(
                not isinstance(item, str) or item not in _MEASURES or not re.search(_MEASURES[item], quote, re.I)
                for item in value):
            raise ValueError('Uncited interval measurement proposition.')
        if 'availability_ratio' in value and not _cites([r'availab|uptime', r'month', r'downtime|unavaila|outage'], quote):
            raise ValueError('Availability ratio requires scoped downtime and monthly measurement.')
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
