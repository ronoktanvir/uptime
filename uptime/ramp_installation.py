"""Prove the sandbox installation identity without retaining the business profile or tokens."""
from urllib.parse import urlencode
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
