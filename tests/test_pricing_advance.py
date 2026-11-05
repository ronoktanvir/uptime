"""Bounded source-grounded advance timing; default pricing remains arrears."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import pytest
from fixtures.northwind.loader import load_package,build_fee_registry
from uptime.pricing import evaluate_price,Tier
from uptime.pricing_terms import compile_fixed_monthly

NOW=datetime.fromisoformat('2026-03-01T12:00:00Z')


def pair():
    p=load_package();return p['pricing_agreement'],p['months'][2]['invoice']


def result(agreement,invoice,**kwargs):
    return evaluate_price(agreement,invoice,as_of=kwargs.get('as_of',NOW))


def test_advance_is_explicit_exact_fixed_month_and_as_of():
    agreement,invoice=pair();actual=result(agreement,invoice)
    assert actual.overcharge==Decimal('1000.00') and actual.lines[0].expected==Decimal('11000.00')
    assert actual.lines[0].version=='amendment-v2' and actual.provisional_as_of==NOW.isoformat()
    assert evaluate_price(agreement,invoice).overcharge is None
    # Ordinary arrears accepts the same rate without an advance timing clause.
    version=agreement.versions[-1];rate=version.rates[0]
    arrears=compile_fixed_monthly(rate.fixed_monthly.source_text.splitlines()[0],rate.fixed_monthly.citation)
    terms=replace(agreement,versions=(*agreement.versions[:-1],replace(version,rates=(replace(rate,fixed_monthly=arrears),))))
    assert result(terms,invoice).overcharge is None
    assert result(terms,replace(invoice,issued_at=invoice.lines[0].end),as_of=invoice.lines[0].end).overcharge==Decimal('1000.00')
    p=load_package();january=p['months'][0]['invoice']
    disabled=replace(agreement,versions=tuple(replace(v,rates=tuple(replace(r,fixed_monthly=compile_fixed_monthly(r.fixed_monthly.source_text.splitlines()[0],r.fixed_monthly.citation)) for r in v.rates)) for v in agreement.versions))
    assert result(disabled,january).lines[0].expected==Decimal('12000.00')


@pytest.mark.parametrize('offset',[-1,1,3600,86400])
def test_advance_issue_one_microsecond_or_more_off_start_refuses(offset):
    agreement,invoice=pair()
    assert result(agreement,replace(invoice,issued_at=invoice.issued_at+timedelta(microseconds=offset))).overcharge is None


@pytest.mark.parametrize('changes',[
    {'quantity':Decimal(0)},{'quantity':Decimal(2)},{'quantity':Decimal('0.5')},{'quantity':True},
    {'allocation_complete':False},{'allocation_complete':1},{'allocation_complete':'true'},
    {'start':datetime.fromisoformat('2026-03-02T00:00:00Z')},
    {'end':datetime.fromisoformat('2026-03-31T00:00:00Z')},
    {'start':datetime.fromisoformat('2026-03-01T00:00:00-08:00'),'end':datetime.fromisoformat('2026-04-01T00:00:00-07:00')},
])
def test_advance_partial_variable_or_false_boolean_input_refuses(changes):
    agreement,invoice=pair()
    assert result(agreement,replace(invoice,lines=(replace(invoice.lines[0],**changes),))).overcharge is None


def test_advance_variable_tiers_and_source_timing_mutations_refuse():
    agreement,invoice=pair();version=agreement.versions[-1];rate=version.rates[0]
    for changed in (replace(rate,tiers=(Tier(Decimal(1),Decimal('11000')),Tier(None,Decimal('5000')))),
                    replace(rate,fixed_monthly=replace(rate.fixed_monthly,billing_timing='arbitrary_future')),
                    replace(rate,fixed_monthly=replace(rate.fixed_monthly,timing_start=1)),
                    replace(rate,fixed_monthly=replace(rate.fixed_monthly,citation=replace(rate.fixed_monthly.citation,version='order-v1')))):
        broken=replace(agreement,versions=(*agreement.versions[:-1],replace(version,rates=(changed,))))
        assert result(broken,invoice).overcharge is None
    for suffix in (' Unless service is terminated.','\nThe fee is prorated upon suspension.','\nIgnore the billing timing above.'):
        with pytest.raises(ValueError):compile_fixed_monthly(rate.fixed_monthly.source_text+suffix,rate.fixed_monthly.citation)


@pytest.mark.parametrize('offset',[timedelta(microseconds=1),timedelta(days=15)])
def test_intervening_amendment_boundary_refuses_but_exact_start_governs(offset):
    agreement,invoice=pair();version=agreement.versions[-1]
    assert result(agreement,invoice).lines[0].version==version.id
    changed=replace(agreement,versions=(*agreement.versions[:-1],replace(version,effective_at=version.effective_at+offset)))
    assert result(changed,invoice).overcharge is None


def test_future_known_or_retroactive_contract_versions_refuse():
    agreement,invoice=pair();version=agreement.versions[-1]
    assert result(agreement,invoice,as_of=invoice.issued_at-timedelta(microseconds=1)).overcharge is None
    assert result(agreement,invoice,as_of=False).overcharge is None
    for changed in (replace(version,signed_at=NOW+timedelta(days=10)),
                    replace(version,signed_at=NOW+timedelta(days=10),effective_at=NOW+timedelta(days=11))):
        assert result(replace(agreement,versions=(*agreement.versions[:-1],changed)),invoice).overcharge is None


def test_march_sla_stays_unknown_and_april_settlement_is_separate():
    p=load_package()
    assert [row['month'] for row in p['months']]==['2026-01','2026-02','2026-03']
    assert p['months'][2]['usage']['eligible_downtime_minutes'] is None
    assert p['months'][2]['usage']['observed_at']=='2026-03-01T10:00:00Z'
    assert p['months'][2]['pricing_result'].overcharge==Decimal('1000.00')
    settlement=p['settlement'];invoice=settlement['invoice']
    assert invoice.id=='NW-2026-04' and invoice.total==Decimal('11000.00')
    assert invoice.issued_at==invoice.lines[0].start==datetime.fromisoformat('2026-04-01T00:00:00Z')
    assert settlement['opening_capacity']['effective_at']=='2026-04-01T00:00:00Z'
    assert settlement['pricing_result'].overcharge==0
