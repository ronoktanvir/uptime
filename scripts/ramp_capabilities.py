"""Report grants and bounded query coverage for the configured Ramp sandbox. Never sends a resource write."""
import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uptime.ramp import ORIGIN, RampError, RampHTTPError, SandboxRampProvider
from uptime.ramp_installation import DISCOVERY_SCOPES, current_business, installation_token

READ_QUERIES = {
    "agreements": ("vendors:read", "POST", "vendors/agreements", {"page_size": 5}),
    "transactions": ("transactions:read", "GET", "transactions?page_size=5", None),
    "purchase_orders": ("purchase_orders:read", "GET", "purchase-orders?page_size=5", None),
    "credits": ("vendors:read", "GET", "vendors/credits?page_size=5", None),
}


def inspect(provider):
    receipt = {"schema": "uptime-ramp-discovery/1", "origin": ORIGIN, "observed_at": datetime.now(UTC).isoformat(),
               "environment": "LIVE_RAMP_SANDBOX", "writes_attempted": False, "scope_grants": {}, "read_queries": {}}
    grants = {}
    for scope in sorted(DISCOVERY_SCOPES):
        try:
            token = installation_token(provider, scope)
            receipt["scope_grants"][scope] = {"granted": sorted(token.granted), "scope_field": token.scope_reported, "exact": token.exact}
            if token.exact and scope.endswith(":read"):
                grants[scope] = token
        except RampHTTPError as exc:
            receipt["scope_grants"][scope] = {"http": exc.status}
        except RampError:
            receipt["scope_grants"][scope] = {"status": "UNAVAILABLE"}
    for name, (scope, method, route, body) in READ_QUERIES.items():
        if scope not in grants:
            receipt["read_queries"][name] = {"status": "SCOPE_UNAVAILABLE"}
            continue
        headers = {"Authorization": "Bearer " + grants[scope].value}
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            response = provider._http(method, route, headers, json.dumps(body) if body is not None else None)
            rows = response["data"]
            if not isinstance(rows, list):
                raise RampError("Unexpected collection")
            receipt["read_queries"][name] = {"status": "READ_VERIFIED", "sample_count": len(rows),
                                             "has_next": bool((response.get("page") or {}).get("next"))}
        except RampHTTPError as exc:
            receipt["read_queries"][name] = {"status": "HTTP_REFUSAL", "http": exc.status}
        except (RampError, KeyError, ValueError):
            receipt["read_queries"][name] = {"status": "UNAVAILABLE"}
    if "business:read" in grants:
        try:
            current_business(provider)
            receipt["installation_identity"] = "CANONICAL_ID_VERIFIED"
        except RampError:
            receipt["installation_identity"] = "UNVERIFIED"
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(SandboxRampProvider())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v["status"] for k, v in result["read_queries"].items()}))
