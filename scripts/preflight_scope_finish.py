"""NO-MODEL claim schema and governing-family preflight for claim-scope/1 (pure and write-free).

``check_schema_and_family(claim_payload, manifest, overlay)`` answers one question for one claim
request body: would ordinary claim intake accept it under the current ``Claim`` schema AND the
server's ``claim_scope`` family table, if the supplied adapter (manifest + overlay, exactly as the
server stores them) were the tenant's only installed, non-revoked adapter? Pass ``manifest=None,
overlay=None`` when no adapter is installed (built-in profile or nothing).

Nothing outside the process is touched: no model, CLI, network, application server, file, or
evaluation database. Nothing is written, so this check can't consume a first attempt. The real
``uptime.claim_scope.resolve`` runs against a private in-memory SQLite connection that holds at
most one adapter row. That way the identity predicate, built-in profile, ambiguity rule and family
table are the server's own code, not a reimplementation.

Nothing is filled, slugged, defaulted, coerced or normalized. The record copies the caller's
input. If the schema adds or drops an obligation field, that is reported, not trusted. The current
family behavior is evaluated as implemented. An explicit whole-month basis needs its exact source
text as the optional source_text keyword; neither text nor effective dates are inferred.

Outcomes. The first failing stage is reported:
  setup     SETUP_INPUT_INVALID, SETUP_ENVIRONMENT_UNAVAILABLE
  schema    SCHEMA_INVALID
  adapter   ADAPTER_UNREADABLE           (route would fail with a server error, not a scope refusal)
  route     SCOPE_UNRESOLVABLE           reason NO_GOVERNING_TERMS | UNSUPPORTED_FAMILY | AMBIGUOUS_FAMILY
            FAMILY_SCOPE_MISSING         required family fields absent (not_applicable also listed)
            FAMILY_SCOPE_NOT_APPLICABLE  only fields the family says must be omitted
            SCHEMA_AND_FAMILY_ADMISSIBLE
  preflight PREFLIGHT_DISAGREEMENT       this module and the real code disagree; never guessed

ADMISSIBLE does not mean ready. These things are not checked here and are listed in
``not_checked``: install state, whether the manifest is the server's actual artifact, claim id use,
D03 identity policy, fee authority and evidence.
"""
from __future__ import annotations

import copy
import json
import sqlite3

from pydantic import ValidationError

from uptime import claim_scope
from uptime.correspondence_types import OPTIONAL_SCOPE, Claim

SCHEMA = 'preflight-scope-finish/1'
ADMISSIBLE = 'SCHEMA_AND_FAMILY_ADMISSIBLE'
# Private in-memory install. It has only the tables and columns that claim_scope._installed queries.
TENANT, ADAPTER_ROW, ADAPTER_VERSION = 'preflight-tenant', 'preflight-adapter', 'preflight-version'
# Assumed state of the single adapter row. Every record reports this. Checking the real state is a setup-stage job.
ASSUMED_STATE = 'ACTIVE'
# (claim field, terms side, terms key): the exact equalities the route's install query requires.
IDENTITY = (('vendor', 'manifest', 'vendor'), ('account', 'overlay', 'account'),
            ('contract', 'overlay', 'agreement'), ('service', 'overlay', 'product'))
NOT_CHECKED = ('adapter_install_state', 'manifest_is_server_installed_artifact', 'route_parity_on_real_database',
               'claim_id_unused', 'd03_identity_policy', 'fee_authority', 'evidence')
_ADAPTER_FAILURES = (AttributeError, KeyError, TypeError, ValueError)


def check_schema_and_family(claim_payload, manifest, overlay, *, source_text=None):
    """Classify one claim request body against the real schema and family table (see module doc)."""
    record = _record(claim_payload, manifest is not None or overlay is not None)
    problem, artifact = _adapter_artifact(manifest, overlay, source_text)
    if problem:
        return _finish(record, 'setup', 'SETUP_INPUT_INVALID', problem)
    try:
        claim = Claim.model_validate(copy.deepcopy(claim_payload))
    except ValidationError as error:
        record['schema_errors'] = _schema_errors(error)
        return _finish(record, 'schema', 'SCHEMA_INVALID')
    scope, source_scope = claim.scope, claim_payload['scope']
    record['schema_changed_values'] = sorted(
        [name for name, value in source_scope.items() if getattr(scope, name) != value]
        + (['claim_id'] if claim.claim_id != claim_payload['claim_id'] else []))
    present = {name for name in claim_scope.OBLIGATION_FIELDS if getattr(scope, name) is not None}
    if present != set(record['stated_obligation_fields']):
        return _finish(record, 'preflight', 'PREFLIGHT_DISAGREEMENT', 'SCHEMA_ADDED_OR_DROPPED_OBLIGATION_FIELD')
    if artifact is not None:
        record['adapter_identity'] = _identity(source_scope, scope, manifest, overlay)
    try:
        route = _route(scope, artifact)
    except sqlite3.Error as error:
        return _finish(record, 'setup', 'SETUP_ENVIRONMENT_UNAVAILABLE', f'{type(error).__name__}: {error}')
    if route.get('selection_refusal') is not None:
        record['route_message'] = str(route['selection_refusal'])
        return _finish(record, 'adapter', 'ADAPTER_SCOPE_PREREQUISITE_REFUSED', 'INVALID_EFFECTIVE_PERIOD')
    builtin = claim_scope.builtin_twilio(scope)
    record.update(adapter_matched=route['matched'], builtin_profile_applies=builtin)
    if route['adapter_failure'] is not None:
        failure = route['adapter_failure']
        record['route_message'] = f'{type(failure).__name__}: {failure}'
        return _finish(record, 'adapter', 'ADAPTER_UNREADABLE', type(failure).__name__)
    if route['refusal'] is not None:
        record['route_message'] = str(route['refusal'])
        if route['adapter_refusal'] is not None:
            reason = ('GOVERNING_SOURCE_BASIS_REFUSED' if manifest and manifest.get('evidence_basis') else 'UNSUPPORTED_FAMILY')
        elif route['matched'] and builtin:
            reason = 'AMBIGUOUS_FAMILY'
        elif not route['matched'] and not builtin:
            reason = 'NO_GOVERNING_TERMS'
        else:
            return _finish(record, 'preflight', 'PREFLIGHT_DISAGREEMENT', 'UNATTRIBUTED_ROUTE_REFUSAL')
        return _finish(record, 'route', 'SCOPE_UNRESOLVABLE', reason)
    if route['adapter_refusal'] is not None:
        return _finish(record, 'preflight', 'PREFLIGHT_DISAGREEMENT', 'ROUTE_RESOLVED_UNSUPPORTED_ADAPTER')
    variant = route['variant']
    missing, extra = sorted(variant.required - present), sorted(present - variant.required)
    record.update(family=variant.family, variant=type(variant).__name__, variant_builtin=variant.builtin,
                  required=sorted(variant.required), missing=missing, not_applicable=extra)
    try:
        variant.check(scope)  # The real admission check decides. The lists above only explain its result.
    except claim_scope.InvalidClaimScope as error:
        record['route_message'] = str(error)
        if missing:
            return _finish(record, 'route', 'FAMILY_SCOPE_MISSING')
        if extra:
            return _finish(record, 'route', 'FAMILY_SCOPE_NOT_APPLICABLE')
        return _finish(record, 'preflight', 'PREFLIGHT_DISAGREEMENT', 'UNATTRIBUTED_FAMILY_REFUSAL')
    if missing or extra:
        return _finish(record, 'preflight', 'PREFLIGHT_DISAGREEMENT', 'ROUTE_ADMITTED_FAMILY_MISMATCH')
    return _finish(record, 'route', ADMISSIBLE)


def _record(claim_payload, adapter_supplied):
    scope = claim_payload.get('scope') if isinstance(claim_payload, dict) else None
    scope = scope if isinstance(scope, dict) else {}
    return dict(
        schema=SCHEMA, claim_scope_version=claim_scope.VERSION, stage=None, outcome=None, reason=None,
        source=copy.deepcopy(claim_payload),
        stated_obligation_fields=sorted(n for n in claim_scope.OBLIGATION_FIELDS if scope.get(n) is not None),
        explicit_null_fields=sorted(n for n in OPTIONAL_SCOPE if n in scope and scope[n] is None),
        schema_errors=[], schema_changed_values=[],
        adapter_supplied=adapter_supplied, assumed_adapter_state=ASSUMED_STATE if adapter_supplied else None,
        adapter_identity=None, adapter_matched=None, builtin_profile_applies=None,
        family=None, variant=None, variant_builtin=None, required=None, missing=[], not_applicable=[],
        route_message=None, not_checked=list(NOT_CHECKED))


def _finish(record, stage, outcome, reason=None):
    record.update(stage=stage, outcome=outcome, reason=reason)
    return record


def _adapter_artifact(manifest, overlay, source_text=None):
    """(problem, stored JSON) for the single adapter. Returns (None, None) when no adapter is supplied."""
    if manifest is None and overlay is None:
        return ('SOURCE_WITHOUT_ADAPTER', None) if source_text is not None else (None, None)
    if manifest is None or overlay is None:
        return 'MANIFEST_AND_OVERLAY_MUST_BE_SUPPLIED_TOGETHER', None
    if not isinstance(manifest, dict) or not isinstance(overlay, dict):
        return 'MANIFEST_AND_OVERLAY_MUST_BE_OBJECTS', None
    if source_text is not None and not isinstance(source_text, str):
        return 'SOURCE_TEXT_MUST_BE_A_STRING', None
    if manifest.get('evidence_basis') is not None and source_text is None:
        return 'OPT_IN_SOURCE_TEXT_REQUIRED', None
    artifact = {'manifest': manifest, 'overlay': overlay}
    if source_text is not None:
        artifact['source_text'] = source_text
    try:
        return None, json.dumps(artifact, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        return 'ADAPTER_NOT_JSON', None


def _schema_errors(error):
    found = []
    for item in error.errors():
        loc = list(item['loc'])
        field = loc[1] if len(loc) > 1 and loc[0] == 'scope' else (loc[0] if loc else None)
        found.append(dict(loc=loc, field=field, type=item['type']))
    return sorted(found, key=lambda item: (json.dumps(item['loc']), item['type']))


def _identity(source_scope, scope, manifest, overlay):
    """Field-by-field view of the route's exact identity equality, with both sides as supplied."""
    terms, view = {'manifest': manifest, 'overlay': overlay}, {}
    for field, side, key in IDENTITY:
        stated = key in terms[side]
        view[field] = dict(claim=copy.deepcopy(source_scope[field]), terms_path=f'{side}.{key}', terms_present=stated,
                           terms=copy.deepcopy(terms[side][key]) if stated else None,
                           equal=stated and terms[side][key] == getattr(scope, field))
    return view


def _install(db, artifact):
    db.execute('CREATE TABLE v4_vendor_event (tenant TEXT, vendor TEXT, revision INTEGER, payload TEXT)')
    db.execute('CREATE TABLE v4_vendor_artifact (tenant TEXT, vendor TEXT, version TEXT, payload TEXT)')
    db.execute('INSERT INTO v4_vendor_event VALUES (?, ?, 1, ?)',
               (TENANT, ADAPTER_ROW, json.dumps({'state': ASSUMED_STATE, 'version': ADAPTER_VERSION})))
    db.execute('INSERT INTO v4_vendor_artifact VALUES (?, ?, ?, ?)', (TENANT, ADAPTER_ROW, ADAPTER_VERSION, artifact))


def _route(scope, artifact):
    """Run the real claim_scope selection and resolution. The in-memory connection is never shared or persisted."""
    db = sqlite3.connect(':memory:')
    try:
        if artifact is not None:
            _install(db, artifact)
        try:
            matched = claim_scope._installed(db, TENANT, scope)
        except claim_scope.InvalidClaimScope as error:
            return dict(selection_refusal=error)
        result = dict(matched=bool(matched), adapter_refusal=None, adapter_failure=None, variant=None, refusal=None)
        for stored in matched:  # The route reads only adapters whose identity equals the claim's identity.
            try:
                claim_scope.variant_for(stored['manifest'], stored['overlay'], source_text=stored.get('source_text', ''))
            except claim_scope.InvalidClaimScope as error:
                result['adapter_refusal'] = error
            except _ADAPTER_FAILURES as error:
                result['adapter_failure'] = error
                return result
        try:
            result['variant'] = claim_scope.resolve(db, TENANT, scope)
        except claim_scope.InvalidClaimScope as error:
            result['refusal'] = error
        return result
    finally:
        db.close()
