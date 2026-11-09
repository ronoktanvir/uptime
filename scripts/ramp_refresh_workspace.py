"""Install a bounded, read-only snapshot from the actual sandbox into its tenant-bound workbench."""
import argparse
import json
import os
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uptime.auth import bind_workspace
from uptime.installation_revocation import require_workspace_active
from uptime.ramp import RampError, RampHTTPError, RampNetworkError, SandboxRampProvider
from uptime.ramp_installation import current_business
from uptime.ramp_records import sync_records
from uptime.ramp_workspace import RampWorkspace
from uptime.workbench import Workbench


def refresh(path, tenant, *, page_size=20, max_pages=2, detail_limit=12,
            all_purchase_orders=False, provider=None):
    bind_workspace(path, "sandbox", False, tenant)
    # A revoked installation makes no provider request, not even a token exchange.
    require_workspace_active(path, tenant)
    provider = provider or SandboxRampProvider()
    business_id = current_business(provider)
    workspace = RampWorkspace(Workbench(path, "sandbox", tenant=tenant))
    observation = sync_records(provider, page_size=page_size, max_pages=max_pages, detail_limit=detail_limit,
                               include_unlinked_purchase_orders=all_purchase_orders)
    result = workspace.import_observation(observation, business_id)
    return observation, result


RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (5, 30)


def retryable(exc):
    """The refresh only reads. Authorization, scope, binding and revocation failures are never retried."""
    if isinstance(exc, RampHTTPError):
        return exc.status in RETRYABLE_STATUS
    return isinstance(exc, RampNetworkError)


def refresh_with_retries(path, tenant, *, attempts=1, sleep=time.sleep, run=None, **options):
    """Bounded reruns of the whole idempotent read; an interrupted import resumes on the next attempt.

    Each attempt exchanges a new client-credentials token, so attempts stay small.
    """
    if type(attempts) is not int or not 1 <= attempts <= MAX_ATTEMPTS:
        raise ValueError("Choose between one and three read attempts")
    run = run or refresh
    for attempt in range(1, attempts + 1):
        try:
            return (*run(path, tenant, **options), attempt)
        except Exception as exc:
            if attempt == attempts or not retryable(exc):
                raise
            sleep(BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--tenant", default="bears")
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--detail-limit", type=int, default=12)
    parser.add_argument("--all-purchase-orders", action="store_true")
    parser.add_argument("--attempts", type=int, default=1, choices=range(1, MAX_ATTEMPTS + 1), metavar="1..3",
                        help="Bounded reruns of the whole read after a raised network failure or HTTP 429/5xx, "
                             "mainly token and business reads; per-resource 429/5xx are recorded as PARTIAL or "
                             "UNAVAILABLE in the capture and are not retried. Never after a refusal.")
    parser.add_argument("--export", type=Path, help="Optional sanitized replay snapshot; contains sandbox UUIDs and amounts.")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        snapshot, result, attempts = refresh_with_retries(
            args.db, args.tenant, attempts=args.attempts, page_size=args.page_size, max_pages=args.max_pages,
            detail_limit=args.detail_limit, all_purchase_orders=args.all_purchase_orders)
        if args.export:
            args.export.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile("w", dir=args.export.parent, delete=False) as out:
                temp = Path(out.name)
                json.dump(snapshot, out, indent=2, allow_nan=False)
                out.write("\n")
                out.flush()
                os.fsync(out.fileno())
            try:
                temp.replace(args.export)
            finally:
                temp.unlink(missing_ok=True)
    except (RampError, ValueError, OSError, PermissionError) as exc:
        parser.exit(1, f"Ramp workspace refresh stopped ({type(exc).__name__}). Check sandbox grants and tenant binding.\n")
    print(json.dumps({"capture": result["digest"], "status": result["status"], "attempts": attempts,
                      "resources": {k: {"status": v["status"], "read_back": len(v["records"])}
                                    for k,v in snapshot["resources"].items()}}, indent=2))


if __name__ == "__main__":
    main()
