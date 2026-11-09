"""Temporal applicability of one signed evidence delivery to its granted service month.

A source grant names one exact claim scope, including its service month. A record whose
measured time lies entirely outside that month describes another period. The grant refuses
it before storage, so a mistaken delivery cannot occupy the claim's single record of that
kind and later make the correct record look contradictory.

Only measured service time is compared: outage, coverage, telemetry, resource, maintenance
and request intervals. Issue, announcement, filing, delivery and billing-cycle timestamps
legitimately fall outside the month and are not refused here. Partial overlap stays
admissible because boundary-spanning time is a contract rule for the evaluator.

A month can be measured in a named time zone. Short records (incidents, rows, requests) are
therefore compared with the UTC month widened by the largest civil offset on each side.
Period reports describe a measurement month. Every civil-zone version of a month overlaps
its UTC month for all but at most fourteen hours, while an adjacent month in any civil zone
overlaps it by at most fourteen hours (UTC-12 September ends 12:00 UTC on 1 October; UTC+14
November starts 10:00 UTC on 31 October). A period report that crosses the UTC month
boundary must therefore keep more than fourteen hours inside the unwidened UTC month. That
refuses an off-by-one-month report in any civil zone without refusing a zone-measured one.
A report wholly inside the UTC month is admitted however short it is; whether a partial
report can establish anything is the evaluator's decision.
Supported families measure calendar months; a contract measuring non-calendar periods would
need this rule revisited rather than bypassed.

This is an intake boundary, not an entitlement rule. Admission does not make a record
sufficient, and a source signature proves which enrolled key sent it, not that it is true.
"""
from datetime import UTC, datetime, timedelta
import re

from .correspondence_types import instant

# UTC-12:00 to UTC+14:00 are the extreme civil offsets.
MARGIN = timedelta(hours=14)
MONTH = re.compile(r"20[0-9]{2}-(0[1-9]|1[0-2])")

# Kinds whose own start/end is measured service time.
MEASURED = frozenset({"status", "coverage", "impact", "component", "notice", "resource_status",
                      "resource_attribution", "provider_telemetry", "customer_telemetry"})
# Nested rows that are measured service time, by record kind.
NESTED = {"resource_status": ("intervals",), "resource_attribution": ("causes", "exclusions"),
          "provider_telemetry": ("records",), "customer_telemetry": ("records", "exclusions"),
          "maintenance_evidence": ("records",)}
# Reports that state their own measured interval and may assert that it is complete.
INTERVAL_REPORTS = frozenset({"resource_status", "resource_attribution", "provider_telemetry", "customer_telemetry"})
# Whole-period reports: compared with the unwidened UTC month.
PERIOD_REPORTS = INTERVAL_REPORTS | {"coverage"}


def month_bounds(month: str) -> tuple[datetime, datetime]:
    """Exact UTC calendar bounds [first, following) of a granted YYYY-MM month."""
    if not isinstance(month, str) or not MONTH.fullmatch(month):
        raise ValueError("A granted YYYY-MM service month is required.")
    first = datetime.strptime(month, "%Y-%m").replace(tzinfo=UTC)
    following = (first + timedelta(days=32)).replace(day=1)
    return first, following


def _overlaps(start, end, low, high):
    return start < high and end > low


def _shared(start, end, low, high):
    return max(timedelta(0), min(end, high) - max(start, low))


def temporal_refusal(body, month: str) -> str | None:
    """Return why this record cannot describe the granted month, or None if it may."""
    data = body.model_dump(exclude_none=True) if hasattr(body, "model_dump") else dict(body)
    kind = data["kind"]
    first, following = month_bounds(month)
    low, high = first - MARGIN, following + MARGIN
    own = (instant(data["start"]), instant(data["end"])) if "start" in data and "end" in data else None
    if (kind in PERIOD_REPORTS and not first <= own[0] < own[1] <= following
            and _shared(*own, first, following) <= MARGIN):
        return f"The {kind} report period lies outside service month {month}."
    if kind in MEASURED and not _overlaps(*own, low, high):
        return f"The measured {kind} interval lies outside service month {month}."
    for collection in NESTED.get(kind, ()):
        for row in data.get(collection) or ():
            span = instant(row["start"]), instant(row["end"])
            if not _overlaps(*span, low, high) or (own is not None and not _overlaps(*span, *own)):
                return f"The {kind} row {row['ref']} lies outside service month {month} or its report interval."
    if kind == "request_evidence":
        for row in data["records"]:
            if not low <= instant(row["requested_at"]) < high:
                return f"The request_evidence row {row['ref']} lies outside service month {month}."
    if kind in INTERVAL_REPORTS and data.get("complete") and instant(data["observed_at"]) < own[1]:
        return f"A complete {kind} report cannot be observed before its measured interval ends."
    return None
