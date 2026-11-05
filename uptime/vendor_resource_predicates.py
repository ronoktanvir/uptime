"""Optional scoped operators for signed subscriptions, dual telemetry and portal correction clocks."""
import re


FIELDS = {'subscription', 'telemetry', 'fee_settlement', 'cure_clock', 'original_receipt', 'causal_report'}
PROMPT = """
For the following operators attach just the evidenced keys to each block. Multiple blocks may contribute
different keys to subscription, telemetry or fee_settlement. Exact account observations are private and absent here.
subscription: object with any of scope ("account_product_region" for separation per account and region), regions
(list of verbatim short region codes/names), excluded_types and excluded_products (verbatim lists),
version (exact version accepted by the signed subscription), signed_record (true), active_full_month (true).
Represent paid service product/plan using scope and the separate subscription object for applicability.
telemetry: object. join="intersect_customer_provider" requires BOTH customer and provider scoped records for the
same covered time. provider_status and customer_status are VERBATIM short positive status/description strings
(e.g. "all operations failed"), optionally supplemented by provider_nonqualifying/customer_nonqualifying lists
of literal statuses. custodian=true for a required signed scoped recording-system statement.
missing_unknown=true for missing records explicitly insufficient. These two independent records govern symptoms and
provider cause; positive status strings may also populate the legacy symptoms/provider_causes fields. Never invent them.
fee_settlement: list containing "paid_recurring_only", "subtract_fee_refunds" or "usd_only" where explicitly stated.
Use fee_adjustment for post-discount charges, and fee_basis for affected recurring fees.
causal_report: "scoped_sole_cause" for exclusions requiring an account-specific root-cause report and sole cause.
original_receipt: "portal_received_at" for mandatory portal timestamp, not sender/draft time. Use submission_channel
if a portal is the only filing channel. cite actual words for channel.
cure_clock: object {"count":number,"unit":"elapsed_days","trigger":["evidence_request","denial"] or source subset,
"endpoint":"inclusive" or "exclusive", "scope":"same_ticket","initial_fields":["verbatim required initial field",...]}.
Use for a correction deadline measured FROM independently delivered vendor evidence request or denial. A timely
initial receipt must be preserved; a late original cannot be cured. Do not emit supplement=same_filing_deadline
for this alternative. Capture quote-grounded identity fields and request_fields.
Unsupported economic terms remain unsupported. Do not mark a recognized condition nonmaterial.
"""


def folded(value):
    return ' '.join(value.casefold().split()) if isinstance(value, str) else ''


def grounded(value, text):
    phrase = folded(value)
    return bool(phrase and len(phrase) <= 180 and re.search(r'(?<!\w)' + re.escape(phrase) + r'(?!\w)', folded(text)))


def has(text, *patterns):
    return all(re.search(pattern, text, re.I) for pattern in patterns)


def _merge(manifest, key, values):
    target = manifest.setdefault(key, {})
    for name, value in values.items():
        if name in target and target[name] != value:
            raise ValueError('Conflicting scoped ' + key + ' ' + name)
        target[name] = value


def validate(manifest, key, value, quote):
    text = folded(quote)
    if key == 'subscription':
        rules = {'scope', 'regions', 'excluded_types', 'excluded_products', 'version', 'signed_record', 'active_full_month'}
        if not isinstance(value, dict) or not value or set(value) - rules:
            raise ValueError('Unsupported subscription parameters.')
        for name, item in value.items():
            if name in ('regions', 'excluded_types', 'excluded_products'):
                cue = {'regions': r'region', 'excluded_types': r'no remedy|exclud|not (?:cover|eligible)',
                       'excluded_products': r'no remedy|exclud|not (?:cover|eligible)'}[name]
                valid = isinstance(item, list) and bool(item) and all(grounded(x, text) for x in item) and has(text, cue)
            elif name == 'scope':
                valid = item == 'account_product_region' and has(text, 'account', 'region', 'each|separate|per')
            elif name == 'version':
                valid = grounded(item, text) and has(text, 'version|revision')
            elif name == 'signed_record':
                valid = item is True and has(text, 'sign', 'subscription|order|agreement')
            else:
                valid = item is True and has(text, 'active|in force|in effect', 'entire|throughout|whole|full', 'month')
            if not valid:
                raise ValueError('Ungrounded subscription ' + name)
        _merge(manifest, key, value)
    elif key == 'telemetry':
        rules = {'join', 'provider_status', 'customer_status', 'provider_nonqualifying', 'customer_nonqualifying',
                 'custodian', 'missing_unknown'}
        if not isinstance(value, dict) or not value or set(value) - rules:
            raise ValueError('Unsupported dual-telemetry parameters.')
        for name, item in value.items():
            if name == 'join':
                valid = (item == 'intersect_customer_provider' and has(text, 'provider|vendor', 'customer|client',
                         'both|simultaneous|intersect|concurrent|same.{0,38}(?:second|interval|instant)'))
            elif name.endswith('_status'):
                valid = grounded(item, text) and has(text, 'provider|vendor' if name.startswith('provider') else 'customer|client')
            elif name.endswith('_nonqualifying'):
                valid = isinstance(item, list) and bool(item) and all(grounded(x, text) for x in item) and has(text, 'not|ineligible|exclude')
            elif name == 'custodian':
                valid = item is True and has(text, 'custodian', 'sign', 'system|source')
            else:
                valid = item is True and has(text, 'missing|absent|incomplete', 'unknown|unestablished|insufficient|not')
            if not valid:
                raise ValueError('Ungrounded telemetry ' + name)
        _merge(manifest, key, value)
    elif key == 'fee_settlement':
        patterns = {'paid_recurring_only': ('paid', 'recurring|subscription|unpaid|void'),
                    'subtract_fee_refunds': ('refund', 'after|net|less|reduc|deduct|subtract'),
                    'usd_only': (r'\bUSD\b|US dollars?',)}
        if not isinstance(value, list) or not value or any(not isinstance(v, str) or v not in patterns or
                not has(text, *patterns[v]) for v in value):
            raise ValueError('Ungrounded paid-charge or fee-refund condition.')
        manifest[key] = sorted(set(manifest.get(key, [])) | set(value))
    elif key == 'causal_report':
        if value != 'scoped_sole_cause' or not has(text, 'sole|exclusive', 'root.cause|causal report', 'account|customer'):
            raise ValueError('Unrecognized causal exclusion attestation.')
        manifest[key] = value
    elif key == 'original_receipt':
        if value != 'portal_received_at' or not has(text, 'portal', 'receipt|receiv', 'time|clock|deadline|later than'):
            raise ValueError('Portal delivery authority is not established.')
        manifest[key] = value
    elif key == 'cure_clock':
        if not isinstance(value, dict) or set(value) != {'count', 'unit', 'trigger', 'endpoint', 'scope', 'initial_fields'}:
            raise ValueError('Incomplete supplemental deadline proposition.')
        from .vendor_resource_terms import count_grounded
        if (value['unit'] != 'elapsed_days' or type(value['count']) is not int or not 1 <= value['count'] <= 365
                or not count_grounded(value['count'], 'elapsed_days', text)
                or value['scope'] != 'same_ticket' or not has(text, 'same ticket|original ticket|same case',
                    'deliver|recei', 'correct|supplement|cure|outstanding|missing', 'claim|ticket|filing')
                or value['endpoint'] not in ('inclusive', 'exclusive')
                or not has(text, 'inclus|through|no later than' if value['endpoint'] == 'inclusive' else 'exclus|before')
                or not isinstance(value['trigger'], list) or not value['trigger']
                or len(value['trigger']) != len(set(value['trigger']))
                or not all(t in ('evidence_request','denial') and has(text, 'denial|denied' if t == 'denial'
                    else '(?:evidence|records|document) request|request.{0,45}(?:records|proof|evidence|documents)') for t in value['trigger'])
                or not isinstance(value['initial_fields'], list) or not value['initial_fields']
                or not all(grounded(x, text) for x in value['initial_fields'])):
            raise ValueError('Unsupported supplemental trigger, clock or mandatory original fields.')
        _merge(manifest, key, value)
