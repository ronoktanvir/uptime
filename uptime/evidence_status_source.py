"""Twilio's public status page as an enrolled evidence source (decision 91a, D07).

One verified public snapshot plus one operator-selected incident becomes one signed
`status` record for an exact enrolled grant. The record says only that the vendor
published a resolved incident naming the granted component during the stated interval.
It is not this customer's impact, affected fees or month coverage: those need separate
customer and billing sources, and a recent-incident feed never attests a complete month.

Every input is checked before signing: the official origin, snapshot freshness, the
granted vendor, incident and component, a published start and resolution, chronology,
and the decision-91 temporal rule. Missing published times are refused, never replaced
by creation or observation times. The untrusted public label never enters the record.
"""
from datetime import datetime, timedelta

from .correspondence_types import Delivery, Scope, instant
from .evidence import SOURCE_URI, Snapshot
from .evidence_applicability import temporal_refusal

# Matches the existing public-snapshot display freshness. A public incident record can be
# edited after collection, so a signer must deliver from a recent observation.
FRESHNESS = timedelta(hours=24)


class StatusSourceRefusal(ValueError):
    """The public observation cannot become this grant's status record."""


def status_delivery(snapshot: Snapshot, incident_id: str, scope: Scope, *, now: datetime,
                    max_age: timedelta = FRESHNESS) -> tuple[Delivery, dict]:
    """Return the exact signed-record body and its local provenance, or refuse."""
    if snapshot.source_uri != SOURCE_URI:
        raise StatusSourceRefusal("Only the official Twilio status feed is enrolled as this source.")
    if now.utcoffset() is None:
        raise StatusSourceRefusal("The delivery clock must be timezone-aware.")
    observed = instant(snapshot.observed_at)
    if observed > now:
        raise StatusSourceRefusal("The snapshot was collected after the delivery clock.")
    if now - observed > max_age:
        raise StatusSourceRefusal("The public snapshot is older than 24 hours; refresh it before delivery.")
    if scope.vendor.casefold() != "twilio":
        raise StatusSourceRefusal("This source publishes only Twilio status observations.")
    if scope.incident != incident_id:
        raise StatusSourceRefusal(f"The grant names incident {scope.incident}, not {incident_id}.")
    row = next((o for o in snapshot.observations if o.incident_id == incident_id), None)
    if row is None:
        raise StatusSourceRefusal(f"Incident {incident_id} is not in this snapshot.")
    if row.status != "resolved" or row.resolved_at is None:
        raise StatusSourceRefusal(f"Incident {incident_id} is not resolved; only completed intervals are delivered.")
    if row.started_at is None:
        raise StatusSourceRefusal(f"Incident {incident_id} has no published start; creation time is not substituted.")
    start, end = instant(row.started_at), instant(row.resolved_at)
    if end <= start:
        raise StatusSourceRefusal(f"Incident {incident_id} has a non-positive published interval.")
    if end > observed:
        raise StatusSourceRefusal(f"Incident {incident_id} resolves after the snapshot was observed.")
    if scope.component not in row.components:
        raise StatusSourceRefusal(f"Incident {incident_id} does not name the granted component {scope.component}.")
    event_id = f"twilio-status:{incident_id}:{row.content_hash[:16]}"
    delivery = Delivery(event_id=event_id, scope=scope,
                        body=dict(kind="status", start=start.isoformat(), end=end.isoformat()))
    if reason := temporal_refusal(delivery.body, scope.month):
        raise StatusSourceRefusal(reason)
    provenance = dict(source_uri=snapshot.source_uri, observed_at=snapshot.observed_at, raw_sha256=snapshot.raw_sha256,
                      incident_id=incident_id, content_hash=row.content_hash, published_status=row.status,
                      published_components=list(row.components), event_id=event_id, customer_impact="unverified",
                      month_coverage="not attested; a recent-incident feed is not complete month coverage",
                      standalone_entitlement=False)
    return delivery, provenance
