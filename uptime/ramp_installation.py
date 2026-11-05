"""Prove the sandbox installation identity without retaining the business profile or tokens."""
from urllib.parse import urlencode
from datetime import UTC, datetime
from hashlib import sha256
import json
import re
from .ramp import RampError, Token, SCOPE, uuid_text

DISCOVERY_SCOPES = frozenset({
    "business:read", "bills:read", "vendors:read", "transactions:read", "purchase_orders:read",
    "approvals:read", "unified_requests:read", "custom_forms:read", "spend_programs:read",
    "spend_requests:read", "custom_records:read", "bills:write", "transactions:write",
    "spend_requests:write", "blank_canvas:write", "custom_records:write",
})


def installation_token(provider, scope):
    if scope not in DISCOVERY_SCOPES:
        raise RampError("Unrecognized installation scope")
    data = provider._http("POST", "token", {"Authorization": "Basic " + provider._basic,
                          "Content-Type": "application/x-www-form-urlencoded"},
                          urlencode({"grant_type": "client_credentials", "scope": scope}))
    if not isinstance(data, dict) or not isinstance(data.get("scope", ""), str):
        raise RampError("Malformed OAuth response")
    bearer = data.get("access_token")
    grants = frozenset(data.get("scope", "").split())
    if (not isinstance(bearer, str) or not bearer or "\n" in bearer or "\r" in bearer
            or str(data.get("token_type", "")).lower() != "bearer" or any(not SCOPE.fullmatch(s) for s in grants)):
        raise RampError("Malformed OAuth response")
    return Token(bearer, grants, frozenset({scope}), "scope" in data)


def current_business(provider):
    token = installation_token(provider, "business:read")
    if not token.exact:
        raise RampError("Installation requires a verified business:read grant")
    # No business names, addresses, tax records or contact fields are retained.
    response = provider._http("GET", "business", {"Authorization": "Bearer " + token.value})
    return uuid_text(response.get("id"))


def browser_bill_id(url):
    """Only the exact native bill route observed through the supported Ramp UI."""
    match = re.fullmatch(r'https://demo[.]ramp[.]com/bill-pay/bills/list/([0-9a-f-]{36})', url) if isinstance(url, str) else None
    if match is None:
        raise RampError('Exact observed sandbox bill URL required')
    return uuid_text(match[1])


def verify_browser_bill(provider, url):
    """Read-only one-object association. A caller-supplied URL is not browser attestation."""
    from .ramp_records import sanitize_bill
    ident = browser_bill_id(url)  # Reject destination confusion before any network operation.
    business = current_business(provider)
    token = provider.token({'bills:read'})
    if not token.exact:
        raise RampError('Exact bills:read grant required')
    record = provider.request(token, 'GET', 'bills/'+ident)
    if not isinstance(record, dict) or record.get('id') != ident:
        raise RampError('Browser bill does not match the API response')
    projection = sanitize_bill(record)
    digest = sha256(json.dumps(projection, sort_keys=True, separators=(',',':'), allow_nan=False).encode()).hexdigest()
    return {'schema':'uptime-ramp-browser-association/1', 'status':'ONE_BILL_READ_VERIFIED',
            'observed_at':datetime.now(UTC).isoformat(), 'origin':'https://demo-api.ramp.com',
            'business_id':business, 'bill_id':ident, 'browser_url':url,
            'browser_url_source':'OPERATOR_SUPPLIED_OBSERVED_URL', 'bill_record_sha256':digest,
            'client_id_sha256':getattr(provider,'client_fingerprint',None),
            'verified_read_scopes':['business:read','bills:read'],
            'write_attempted':False, 'inventory_comparison':False,
            'note':'Local observation receipt; no provider signature, write authority or recovered money.'}
