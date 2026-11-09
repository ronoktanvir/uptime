"""Tests for preflight_scope_finish.check_schema_and_family. No model, network, server, corpus or gold is used.

All claim, manifest and overlay data below was written for these tests. None of it is copied from or
derived from a vendor document, the frozen evaluation corpus, fixtures, gold or a historical claim.
Some fixed literals were not made up here:
- the built-in profile identity hard-coded in uptime.claim_scope.builtin_twilio
- the family names exported by uptime.claim_scope
Both are source code, not corpus data.
"""
import copy
import importlib.util
from pathlib import Path

import pytest

from uptime import claim_scope
from uptime.correspondence_types import Claim

from scripts import preflight_scope_finish as pf

check = pf.check_schema_and_family

MONTHLY, RESOURCE = claim_scope.MONTHLY_FAMILY, claim_scope.RESOURCE_FAMILY
VENDOR, ACCOUNT, CONTRACT, SERVICE = 'Lanternfish Relay', 'acct-4417', 'msa-lanternfish-9', 'Lanternfish Queue'
BUILTIN_VENDOR, BUILTIN_SERVICE = 'Twilio', 'Twilio Messaging API'  # literals of claim_scope.builtin_twilio
VALUES = dict(component='cmp-kiln-3', incident='inc-0001', region='region-north')


def payload(*, drop=(), vendor=VENDOR, service=SERVICE, **fields):
    scope = dict(account=ACCOUNT, vendor=vendor, contract=CONTRACT, service=service, currency='EUR', month='2031-02')
    scope.update(fields)
    for name in drop:
        del scope[name]
    return dict(claim_id='inbox-authored-0001', scope=scope)


def builtin_payload(**fields):
    return payload(vendor=BUILTIN_VENDOR, service=BUILTIN_SERVICE, **fields)


def manifest(family=MONTHLY, **fields):
    return {'family': family, 'vendor': VENDOR, 'effective': ['2031-01-01', '2031-12-31'], **fields}


def overlay(**fields):
    return {'account': ACCOUNT, 'agreement': CONTRACT, 'product': SERVICE,
            'effective_from': '2031-01-01', 'effective_until': '2031-12-31', **fields}


def outcome(result):
    return result['stage'], result['outcome'], result['reason']


# --- fixture sanity and the pending-policy guard -----------------------------------------------

def test_authored_baseline_is_valid_under_the_real_schema():
    # If this fails, the authored values break Claim/SourceIdentity. The preflight is not at fault.
    Claim.model_validate(payload(incident=VALUES['incident']))
    Claim.model_validate(builtin_payload(incident=VALUES['incident'], component=VALUES['component']))


def test_monthly_incident_requirement_is_kept_until_a_whole_month_policy_exists():
    # Fails on purpose if the requirement is dropped without a recorded whole-month decision.
    assert claim_scope.variant_for(manifest(), overlay()).required == frozenset({'incident'})


# --- family-specific scope ----------------------------------------------------------------------

def test_schema_valid_monthly_claim_without_incident_is_refused_by_the_family():
    body = payload()
    scope = Claim.model_validate(body).scope  # the old schema-only preflight stopped here and reported ready
    assert scope.incident is None and 'incident' not in scope.model_dump()
    result = check(body, manifest(), overlay())
    assert outcome(result) == ('route', 'FAMILY_SCOPE_MISSING', None)
    assert (result['family'], result['variant'], result['required']) == (MONTHLY, 'IncidentScope', ['incident'])
    assert (result['missing'], result['not_applicable']) == (['incident'], [])
    with pytest.raises(claim_scope.InvalidClaimScope):  # parity with the real admission check
        claim_scope.variant_for(manifest(), overlay()).check(scope)


def test_monthly_claim_with_incident_is_admissible_but_not_called_ready():
    result = check(payload(incident=VALUES['incident']), manifest(), overlay())
    assert outcome(result) == ('route', pf.ADMISSIBLE, None)
    assert result['adapter_matched'] is True and result['builtin_profile_applies'] is False
    assert result['assumed_adapter_state'] == 'ACTIVE' and 'READY' not in result['outcome']
    assert {'adapter_install_state', 'manifest_is_server_installed_artifact', 'fee_authority'} <= set(result['not_checked'])


def test_invoice_is_an_optional_reference_not_an_obligation_field():
    result = check(payload(incident=VALUES['incident'], invoice='inv-2031-02-a'), manifest(), overlay())
    assert result['outcome'] == pf.ADMISSIBLE and result['not_applicable'] == []


def test_field_the_family_does_not_use_is_not_applicable_rather_than_missing():
    result = check(payload(incident=VALUES['incident'], region=VALUES['region']), manifest(), overlay())
    assert outcome(result) == ('route', 'FAMILY_SCOPE_NOT_APPLICABLE', None)
    assert (result['missing'], result['not_applicable']) == ([], ['region'])


def test_missing_sets_the_outcome_and_not_applicable_is_still_listed():
    result = check(payload(component=VALUES['component']), manifest(), overlay())
    assert result['outcome'] == 'FAMILY_SCOPE_MISSING'
    assert (result['missing'], result['not_applicable']) == (['incident'], ['component'])


RESOURCE_CASES = [
    ('plain', {}, {}, ['component']),
    ('regional subscription', dict(subscription='authored-regional-plan'), {}, ['component', 'region']),
    ('incident filing field', dict(request_fields=['incident_ref']), {}, ['component', 'incident']),
    ('bound label phrase', dict(request_fields=['f1'], label_bindings={'request_fields': {'f1': {'phrase': 'Outage Location'}}}),
     {}, ['component', 'incident', 'region']),
    ('aggregate monitor', dict(aggregate_monitor=True), {}, []),
    ('aggregate monitor with overlay resource label', dict(aggregate_monitor=True, request_fields=['kiln']),
     dict(resource_label='Kiln'), ['component']),
]


@pytest.mark.parametrize('name, extra, overlay_extra, required', RESOURCE_CASES, ids=[case[0] for case in RESOURCE_CASES])
def test_resource_family_requirements_follow_the_real_table(name, extra, overlay_extra, required):
    terms, local = manifest(RESOURCE, **extra), overlay(**overlay_extra)
    assert sorted(claim_scope.variant_for(terms, local).required) == required  # authored expectation equals the real table
    exact = check(payload(**{field: VALUES[field] for field in required}), terms, local)
    assert (exact['outcome'], exact['required']) == (pf.ADMISSIBLE, required)
    bare = check(payload(), terms, local)
    assert bare['outcome'] == ('FAMILY_SCOPE_MISSING' if required else pf.ADMISSIBLE)
    assert bare['missing'] == required


def test_service_month_without_filing_fields_refuses_a_component():
    result = check(payload(component=VALUES['component']), manifest(RESOURCE, aggregate_monitor=True), overlay())
    assert (result['outcome'], result['variant'], result['not_applicable']) == (
        'FAMILY_SCOPE_NOT_APPLICABLE', 'ServiceMonthScope', ['component'])


# --- schema -------------------------------------------------------------------------------------

def test_explicit_null_is_a_schema_refusal_not_an_absent_field():
    result = check(payload(incident=None), manifest(), overlay())
    assert outcome(result) == ('schema', 'SCHEMA_INVALID', None)
    assert (result['explicit_null_fields'], result['stated_obligation_fields']) == (['incident'], [])
    assert result['family'] is None and result['missing'] == [] and result['adapter_matched'] is None
    assert 'incident' in result['source']['scope'] and result['source']['scope']['incident'] is None


@pytest.mark.parametrize('body, field, kind', [
    (payload(drop=('currency',), incident=VALUES['incident']), 'currency', 'missing'),
    (payload(incident=VALUES['incident'], tenant='tenant-a'), 'tenant', 'extra_forbidden'),
    (payload(incident=VALUES['incident'], month='2031-13'), 'month', None),
    (payload(incident=17), 'incident', None),  # strict: never coerced to '17'
    (payload(incident=''), 'incident', None),
], ids=['missing currency', 'unknown key', 'bad month', 'integer incident', 'empty incident'])
def test_schema_refusals_name_the_scope_field_and_keep_the_source(body, field, kind):
    result = check(body, manifest(), overlay())
    assert outcome(result) == ('schema', 'SCHEMA_INVALID', None)
    assert any(error['field'] == field and kind in (None, error['type']) for error in result['schema_errors'])
    assert result['source'] == body and result['required'] is None


def test_schema_refusal_comes_before_family_resolution():
    result = check(payload(month='2031-13'), manifest(), overlay())  # also lacks the monthly incident
    assert result['outcome'] == 'SCHEMA_INVALID' and result['required'] is None and result['missing'] == []


def test_non_object_payload_is_a_schema_refusal_and_is_preserved():
    body = ['not', 'a', 'claim']
    result = check(body, None, None)
    assert outcome(result) == ('schema', 'SCHEMA_INVALID', None)
    assert result['source'] == body and result['stated_obligation_fields'] == []


# --- unresolvable scope -------------------------------------------------------------------------

def test_no_adapter_and_no_builtin_profile_is_unresolvable():
    result = check(payload(incident=VALUES['incident']), None, None)
    assert outcome(result) == ('route', 'SCOPE_UNRESOLVABLE', 'NO_GOVERNING_TERMS')
    assert (result['adapter_supplied'], result['adapter_matched'], result['assumed_adapter_state']) == (False, False, None)
    assert result['family'] is None and result['route_message']


@pytest.mark.parametrize('terms, local, field, value', [
    (manifest(), overlay(account='acct-4418'), 'account', 'acct-4418'),
    (manifest(), overlay(agreement=CONTRACT + ' '), 'contract', CONTRACT + ' '),
    (manifest(), overlay(agreement=CONTRACT.upper()), 'contract', CONTRACT.upper()),
    (manifest(vendor=VENDOR + ' Ltd'), overlay(), 'vendor', VENDOR + ' Ltd'),
], ids=['other account', 'trailing space', 'case differs', 'other vendor'])
def test_identity_must_match_exactly_and_terms_are_reported_as_supplied(terms, local, field, value):
    result = check(payload(incident=VALUES['incident']), terms, local)
    assert outcome(result) == ('route', 'SCOPE_UNRESOLVABLE', 'NO_GOVERNING_TERMS')
    assert result['adapter_matched'] is False
    assert result['adapter_identity'][field]['terms'] == value
    assert [name for name, view in result['adapter_identity'].items() if not view['equal']] == [field]


def test_absent_identity_key_in_terms_is_reported_as_absent():
    local = overlay()
    del local['product']
    result = check(payload(incident=VALUES['incident']), manifest(), local)
    assert result['reason'] == 'NO_GOVERNING_TERMS'
    assert result['adapter_identity']['service'] == dict(
        claim=SERVICE, terms_path='overlay.product', terms_present=False, terms=None, equal=False)


@pytest.mark.parametrize('terms', [manifest('authored-unknown-family/9'), {'vendor': VENDOR, 'effective': ['2031-01-01', '2031-12-31']}], ids=['unknown', 'absent'])
def test_unsupported_or_absent_family_is_unresolvable(terms):
    result = check(payload(incident=VALUES['incident']), terms, overlay())
    assert outcome(result) == ('route', 'SCOPE_UNRESOLVABLE', 'UNSUPPORTED_FAMILY')
    assert result['adapter_matched'] is True and result['family'] is None


def test_adapter_for_another_identity_is_never_read():
    result = check(payload(incident=VALUES['incident']), manifest('authored-unknown-family/9'), overlay(account='acct-0002'))
    assert result['reason'] == 'NO_GOVERNING_TERMS'


def test_builtin_profile_needs_incident_and_component():
    result = check(builtin_payload(incident=VALUES['incident'], component=VALUES['component']), None, None)
    assert outcome(result) == ('route', pf.ADMISSIBLE, None)
    assert (result['family'], result['variant_builtin'], result['required']) == (
        claim_scope.TWILIO_FAMILY, True, ['component', 'incident'])
    missing = check(builtin_payload(incident=VALUES['incident']), None, None)
    assert (missing['outcome'], missing['missing']) == ('FAMILY_SCOPE_MISSING', ['component'])


@pytest.mark.parametrize('family, reason', [(MONTHLY, 'AMBIGUOUS_FAMILY'), ('authored-unknown-family/9', 'UNSUPPORTED_FAMILY')])
def test_builtin_profile_plus_a_matching_adapter_is_refused(family, reason):
    terms, local = manifest(family, vendor=BUILTIN_VENDOR), overlay(product=BUILTIN_SERVICE)
    result = check(builtin_payload(incident=VALUES['incident'], component=VALUES['component']), terms, local)
    assert outcome(result) == ('route', 'SCOPE_UNRESOLVABLE', reason)
    assert result['adapter_matched'] is True and result['builtin_profile_applies'] is True


# --- adapter, setup and preflight failures ------------------------------------------------------

def test_unreadable_adapter_is_an_adapter_failure_not_a_scope_refusal():
    terms = manifest(RESOURCE, request_fields=['f1'], label_bindings=None)
    result = check(payload(component=VALUES['component']), terms, overlay())
    assert outcome(result) == ('adapter', 'ADAPTER_UNREADABLE', 'AttributeError')
    assert result['adapter_matched'] is True and result['family'] is None


@pytest.mark.parametrize('terms, local, reason', [
    (manifest(), None, 'MANIFEST_AND_OVERLAY_MUST_BE_SUPPLIED_TOGETHER'),
    (None, overlay(), 'MANIFEST_AND_OVERLAY_MUST_BE_SUPPLIED_TOGETHER'),
    ([manifest()], overlay(), 'MANIFEST_AND_OVERLAY_MUST_BE_OBJECTS'),
    (manifest(note={'a', 'b'}), overlay(), 'ADAPTER_NOT_JSON'),
    (manifest(weight=float('nan')), overlay(), 'ADAPTER_NOT_JSON'),
], ids=['overlay absent', 'manifest absent', 'manifest list', 'set value', 'nan value'])
def test_bad_adapter_inputs_are_setup_failures_reported_before_schema(terms, local, reason):
    result = check(payload(incident=VALUES['incident']), terms, local)
    assert outcome(result) == ('setup', 'SETUP_INPUT_INVALID', reason)
    assert result['schema_errors'] == [] and result['family'] is None


def test_sqlite_without_json_support_is_an_environment_setup_failure(monkeypatch):
    def unavailable(*_args):
        raise pf.sqlite3.OperationalError('no such function: json_extract')
    monkeypatch.setattr(pf, '_route', unavailable)
    result = check(payload(incident=VALUES['incident']), manifest(), overlay())
    assert outcome(result)[:2] == ('setup', 'SETUP_ENVIRONMENT_UNAVAILABLE')


def test_disagreement_with_the_real_check_is_reported_not_resolved(monkeypatch):
    class Lenient(claim_scope.IncidentScope):
        def check(self, scope):
            return self
    monkeypatch.setattr(claim_scope, 'resolve', lambda *_args: Lenient(MONTHLY, frozenset({'incident'})))
    result = check(payload(), manifest(), overlay())
    assert outcome(result) == ('preflight', 'PREFLIGHT_DISAGREEMENT', 'ROUTE_ADMITTED_FAMILY_MISMATCH')


# --- exactness and purity -----------------------------------------------------------------------

def test_inputs_are_untouched_and_source_values_are_reported_exactly():
    body = payload(incident=VALUES['incident'], invoice='inv-2031-02-a')
    terms, local = manifest(notes={'nested': [1, 2.5, None]}), overlay(resource_label='Kiln')
    before = copy.deepcopy((body, terms, local))
    result = check(body, terms, local)
    assert (body, terms, local) == before
    assert result['source'] == body and result['source'] is not body
    assert set(result['source']['scope']) == set(body['scope'])  # no field added or dropped
    assert result['stated_obligation_fields'] == ['incident']
    assert result['schema_changed_values'] == [], 'the real schema altered a source value'
    result['source']['scope']['incident'] = 'changed-by-caller'
    assert body['scope']['incident'] == VALUES['incident']


def test_result_is_deterministic():
    body = payload(incident=VALUES['incident'])
    assert check(body, manifest(), overlay()) == check(body, manifest(), overlay())


@pytest.mark.parametrize('missing', ['source_period', 'overlay_start', 'overlay_end'])
def test_effective_dates_are_never_invented_to_make_preflight_admissible(missing):
    terms, local = manifest(), overlay()
    if missing == 'source_period': del terms['effective']
    elif missing == 'overlay_start': del local['effective_from']
    else: del local['effective_until']
    before = copy.deepcopy((terms, local))
    result = check(payload(incident=VALUES['incident']), terms, local)
    assert outcome(result) == ('adapter', 'ADAPTER_SCOPE_PREREQUISITE_REFUSED', 'INVALID_EFFECTIVE_PERIOD')
    assert (terms, local) == before and result['family'] is None


def test_out_of_period_governing_terms_cannot_make_a_past_claim_admissible():
    result = check(payload(incident=VALUES['incident']),
                   manifest(effective=['2032-01-01', '2032-12-31']),
                   overlay(effective_from='2032-01-01', effective_until='2032-12-31'))
    assert outcome(result) == ('route', 'SCOPE_UNRESOLVABLE', 'NO_GOVERNING_TERMS')


def test_explicit_monthly_basis_requires_original_source_bytes_in_preflight():
    from uptime.vendor_terms import Document, compile_terms
    source = f'''Vendor: {VENDOR}
Agreement: {CONTRACT}
Effective: 2031-01-01 through 2031-12-31
Availability is measured over each UTC calendar month.
For {SERVICE} on the Base plan, monthly availability below 99.9% earns a 10% service credit.
Claims must be received within 14 calendar days after month end.
Service credits apply to affected monthly fees on a future invoice.
Claims are based on a complete UTC calendar-month report for the entire service; incident identifiers are not required.'''
    terms = compile_terms(Document(name='Public preflight control', uri='urn:synthetic:preflight-source',
                                   classification='synthetic_public', text=source))
    local = overlay(plan='Base', fee_line_ref='authored-fee', currency='USD')
    missing = check(payload(currency='USD'), terms, local)
    assert outcome(missing) == ('setup', 'SETUP_INPUT_INVALID', 'OPT_IN_SOURCE_TEXT_REQUIRED')
    exact = check(payload(currency='USD'), terms, local, source_text=source)
    assert exact['outcome'] == pf.ADMISSIBLE and exact['variant'] == 'ServiceMonthScope'
    changed = check(payload(currency='USD'), terms, local, source_text=source + '\nDifferent source.')
    assert outcome(changed) == ('route', 'SCOPE_UNRESOLVABLE', 'GOVERNING_SOURCE_BASIS_REFUSED')
