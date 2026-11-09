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
require an incident unless the reviewed source opts in to whole-month evidence. The built-in
Twilio profile also needs the affected component: its dispute flow cures a vendor's
component request only with a component record matching the claim scope.

Strict whole-month evidence (parent relay "USER APPROVED strict monthly-evidence path now",
2026-11-09) is opt-in only. A monthly manifest carrying the exact, source-grounded marker
``evidence_basis == "complete_service_month/1"`` selects a whole-service scope with no incident,
component or region (uptime.correspondence_monthly joins its evidence). The marker is
absent everywhere else, so the legacy table entry is unchanged.

Stored claims are grandfathered: they are read and evaluated with their stored scope.
This module only decides admissibility of new intake; it grants no entitlement.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import re

from .vendor_monthly_basis import validate_monthly_evidence_basis

VERSION = "claim-scope/1"
OBLIGATION_FIELDS = ("component", "incident", "region")
TWILIO_FAMILY = "twilio-api-sla/2026-04-09"
MONTHLY_FAMILY = "monthly-availability/1"
RESOURCE_FAMILY = "resource-month/1"
# Opt-in whole-service month evidence basis, written by the reviewed terms compiler with one citation.
EVIDENCE_BASIS = "evidence_basis"
COMPLETE_SERVICE_MONTH = "complete_service_month/1"
MONTHLY_SERVICE_FAMILY = MONTHLY_FAMILY + "/" + COMPLETE_SERVICE_MONTH
CITATION_KEYS = frozenset({"id", "start", "end", "quote", "field"})
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
    """A resource-specific monthly obligation: the resource is needed; its region only for a regional subscription."""


class ServiceMonthScope(ScopeVariant):
    """A whole-service monthly obligation: an aggregate monitor, or opt-in complete-month evidence."""


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


def complete_service_month(manifest, source_text=None):
    """Whether reviewed terms opt in to strict whole-service month evidence.

    Returns False when the marker is absent (legacy). Returns True only for the exact marker on a
    monthly-availability manifest with exactly one well-formed ``evidence_basis`` citation; when the
    artifact's source text is supplied, the citation must also be its exact bytes. Anything else
    present is refused, never read as legacy, so a malformed opt-in cannot silently change scope.
    """
    def refuse(why):
        raise InvalidClaimScope("The governing terms' whole-month evidence basis is unsupported: " + why + ".")

    try:
        if not validate_monthly_evidence_basis(manifest):
            return False
    except ValueError as error:
        refuse(str(error))
    basis = manifest[EVIDENCE_BASIS]

    if manifest.get("family") != MONTHLY_FAMILY or basis != COMPLETE_SERVICE_MONTH:
        refuse("only " + COMPLETE_SERVICE_MONTH + " on " + MONTHLY_FAMILY + " is defined")
    citations = manifest.get("citations")
    if not isinstance(citations, list) or not all(isinstance(c, dict) for c in citations):
        refuse("citations are malformed")
    cited = [c for c in citations if c.get("field") == EVIDENCE_BASIS]
    if len(cited) != 1:
        refuse("exactly one source citation is required")
    citation = cited[0]
    start, end, quote, number = (citation.get(k) for k in ("start", "end", "quote", "id"))
    if (set(citation) != CITATION_KEYS or type(number) is not int or number < 1
            or type(start) is not int or type(end) is not int or not 0 <= start < end
            or not isinstance(quote, str) or not quote.strip()
            or sum(1 for c in citations if c.get("id") == number) != 1):
        refuse("the citation must be one exact source span")
    if source_text is not None:
        document = manifest.get("document")
        if (not isinstance(source_text, str) or not isinstance(document, dict)
                or sha256(source_text.encode()).hexdigest() != document.get("sha256")
                or end > len(source_text) or source_text[start:end] != quote):
            refuse("the citation is not grounded in the reviewed source text")
    return True


def variant_for(manifest, overlay, source_text=None):
    """The versioned requirement table for one governing adapter.

    ``source_text`` is the artifact's reviewed source; when given, an opt-in marker is also
    checked against its exact bytes.
    """
    family = manifest.get("family")
    if family not in (MONTHLY_FAMILY, RESOURCE_FAMILY):
        raise InvalidClaimScope("The governing terms belong to an unsupported family; no claim scope is defined.")
    if complete_service_month(manifest, source_text):
        return ServiceMonthScope(MONTHLY_SERVICE_FAMILY, frozenset())
    if family == MONTHLY_FAMILY:
        return IncidentScope(MONTHLY_FAMILY, frozenset({"incident"}))
    words, resource_words = _filing_words(manifest, overlay)
    needed = {name for name, vocabulary in (("incident", INCIDENT_WORDS), ("region", REGION_WORDS),
                                             ("component", resource_words)) if words & vocabulary}
    if manifest.get("aggregate_monitor"):
        return ServiceMonthScope(RESOURCE_FAMILY + "/service-month", frozenset(needed))
    # The region belongs to the obligation only when the terms bind a regional subscription
    # (the same condition claim_identity.resource_remedy uses) or a filing field cites it.
    regional = {"region"} if manifest.get("subscription") else set()
    return ResourcePeriodScope(RESOURCE_FAMILY, frozenset({"component"} | regional | needed))


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
        # An installed artifact without source text cannot ground an opt-in marker ("" never hashes to it).
        variants.add(variant_for(artifact["manifest"], artifact["overlay"], source_text=artifact.get("source_text", "")))
    if not variants:
        raise InvalidClaimScope("No governing terms establish this claim's scope family; an unknown family is refused.")
    if len(variants) > 1:
        raise InvalidClaimScope("More than one governing family matches this claim scope; an ambiguous family is refused.")
    return next(iter(variants))


def admit(db, tenant, scope):
    """Resolve and check a new intake scope. Stored claims are never re-checked by this rule."""
    return resolve(db, tenant, scope).check(scope)
