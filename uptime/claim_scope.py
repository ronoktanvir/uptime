"""Claim scope requirements from the governing family — team decision D04, option C (2026-11-09).

The server, never the client, resolves the governing obligation family from trusted
terms: the built-in Twilio API SLA profile, or the installed adapter whose manifest
vendor and overlay account, agreement and product equal the claim scope exactly. A
versioned table (``claim-scope/1``) then states which of component, incident and region
the obligation needs. Needed fields must be present. Every other obligation field
must be absent, so no placeholder value can be invented to satisfy a schema. Invoice
is an optional evidence reference and never an intake key. An unknown or ambiguous
family is refused. Refusals raise :class:`InvalidClaimScope`, which is distinct
from INSUFFICIENT_EVIDENCE.

"Monthly keeps incident" (Ronok, 2026-11-09): the monthly-availability evidence join
reconciles signed monthly coverage to exactly one incident, so monthly families
require an incident until a separate whole-month evidence decision is made. The built-in
Twilio profile also needs the affected component: its dispute flow cures a vendor's
component request only with a component record matching the claim scope.

Stored claims are grandfathered: they are read and evaluated with their stored scope.
This module only decides admissibility of new intake; it grants no entitlement.
"""
from dataclasses import dataclass
import json
import re

VERSION = "claim-scope/1"
OBLIGATION_FIELDS = ("component", "incident", "region")
TWILIO_FAMILY = "twilio-api-sla/2026-04-09"
MONTHLY_FAMILY = "monthly-availability/1"
RESOURCE_FAMILY = "resource-month/1"
# Filing-field vocabulary that makes a resource filing reference the claim's incident,
# region or resource (mirrors uptime.correspondence_resource.filing_refs).
INCIDENT_WORDS = frozenset({"incident", "outage", "ticket"})
REGION_WORDS = frozenset({"region", "location"})
RESOURCE_WORDS = frozenset({"resource", "station", "component", "endpoint", "instance", "cluster", "zone"})


class InvalidClaimScope(ValueError):
    """The claim scope does not fit its governing family. Never reported as missing evidence."""


@dataclass(frozen=True)
class ScopeVariant:
    family: str
    required: frozenset
    builtin: bool = False

    def check(self, scope):
        present = {name for name in OBLIGATION_FIELDS if getattr(scope, name) is not None}
        missing, extra = sorted(self.required - present), sorted(present - self.required)
        if missing or extra:
            reasons = ([f"requires {', '.join(missing)}"] if missing else []) + (
                [f"{', '.join(extra)} not applicable and must be omitted"] if extra else [])
            raise InvalidClaimScope(f"Invalid claim scope for {type(self).__name__} ({self.family}): {'; '.join(reasons)}.")
        return self


class IncidentScope(ScopeVariant):
    """A monthly obligation whose evidence is reconciled to exactly one incident."""


class ResourcePeriodScope(ScopeVariant):
    """A resource-specific monthly obligation: the resource and its region are needed."""


class ServiceMonthScope(ScopeVariant):
    """A whole-service monthly obligation measured by an aggregate monitor."""


def builtin_twilio(scope):
    """Identity of the built-in Twilio API SLA profile (same predicate as correspondence_rules)."""
    return scope.vendor.casefold() == "twilio" and scope.service == "Twilio Messaging API"


def _filing_words(manifest, overlay):
    words = set()
    labels = manifest.get("label_bindings", {}).get("request_fields", {})
    for target in manifest.get("request_fields", []):
        phrase = labels.get(target, {}).get("phrase", target)
        words.update(re.findall(r"[a-z0-9]+", str(phrase).casefold()))
    return words, RESOURCE_WORDS | set(str(overlay.get("resource_label", "")).casefold().split())


def variant_for(manifest, overlay):
    """The versioned requirement table for one governing adapter."""
    family = manifest.get("family")
    if family == MONTHLY_FAMILY:
        return IncidentScope(MONTHLY_FAMILY, frozenset({"incident"}))
    if family != RESOURCE_FAMILY:
        raise InvalidClaimScope("The governing terms belong to an unsupported family; no claim scope is defined.")
    words, resource_words = _filing_words(manifest, overlay)
    needed = {name for name, vocabulary in (("incident", INCIDENT_WORDS), ("region", REGION_WORDS),
                                             ("component", resource_words)) if words & vocabulary}
    if manifest.get("aggregate_monitor"):
        return ServiceMonthScope(RESOURCE_FAMILY + "/service-month", frozenset(needed))
    return ResourcePeriodScope(RESOURCE_FAMILY, frozenset({"component", "region"} | needed))


def _installed(db, tenant, scope):
    """Manifests and overlays installed for this exact identity, whether shadow or active."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='v4_vendor_event'").fetchone():
        return []
    rows = db.execute("""SELECT a.payload FROM v4_vendor_event e
        JOIN v4_vendor_artifact a ON a.tenant=e.tenant AND a.vendor=e.vendor
          AND a.version IN (json_extract(e.payload, '$.version'), json_extract(e.payload, '$.active_version'))
        WHERE e.tenant=? AND e.revision=(SELECT max(v.revision) FROM v4_vendor_event v
          WHERE v.tenant=e.tenant AND v.vendor=e.vendor)
          AND json_extract(e.payload, '$.state') NOT IN ('REVOKED', 'QUARANTINED')
          AND json_extract(a.payload, '$.manifest.vendor')=?
          AND json_extract(a.payload, '$.overlay.account')=?
          AND json_extract(a.payload, '$.overlay.agreement')=?
          AND json_extract(a.payload, '$.overlay.product')=?""",
                      (tenant, scope.vendor, scope.account, scope.contract, scope.service)).fetchall()
    return [json.loads(row[0]) for row in rows]


def resolve(db, tenant, scope):
    """Return the scope variant the trusted terms require, or refuse an unknown or ambiguous family."""
    variants = set()
    if builtin_twilio(scope):
        variants.add(IncidentScope(TWILIO_FAMILY, frozenset({"incident", "component"}), builtin=True))
    for artifact in _installed(db, tenant, scope):
        variants.add(variant_for(artifact["manifest"], artifact["overlay"]))
    if not variants:
        raise InvalidClaimScope("No governing terms establish this claim's scope family; an unknown family is refused.")
    if len(variants) > 1:
        raise InvalidClaimScope("More than one governing family matches this claim scope; an ambiguous family is refused.")
    return next(iter(variants))


def admit(db, tenant, scope):
    """Resolve and check a new intake scope. Stored claims are never re-checked by this rule."""
    return resolve(db, tenant, scope).check(scope)
