"""Authored source records remain separate from expected financial outcomes."""
from datetime import datetime
from hashlib import sha256
import json
import shutil

import pytest

from fixtures.northwind.loader import ROOT,load_package,verify_package


def test_authored_intervals_and_post_denial_log_are_independent_source_inputs():
    package=load_package()
    jan,feb,march=package['months']
    for row,minutes in ((jan,135),(feb,5)):
        spans=row['usage']['eligible_intervals']
        assert sum((datetime.fromisoformat(x['end'])-datetime.fromisoformat(x['start'])).total_seconds() for x in spans)==minutes*60
    assert march['usage']['eligible_intervals']==[] and march['usage']['eligible_downtime_minutes'] is None
    supplement=package['supplements'][0]
    assert supplement['verification']['linked_ref']==jan['usage']['status_event_id']
    assert datetime.fromisoformat(package['correspondence']['denial']['known_at'])<datetime.fromisoformat(supplement['artifact']['observed_at'])
    assert package['correspondence']['credit_decision']['credit_id']=='NW-CM-2026-01'
    assert 'USD 2400.00' in package['correspondence']['credit_decision']['text']


def test_source_loader_does_not_read_expectations(tmp_path):
    copied=tmp_path/'package';shutil.copytree(ROOT,copied)
    (copied/'expectations.json').unlink()
    assert load_package(copied)['months'][0]['governing_fee_cents']==1200000


def test_false_declared_measurement_refuses_even_with_updated_package_hash(tmp_path):
    copied=tmp_path/'package';shutil.copytree(ROOT,copied)
    usage=json.loads((copied/'usage.json').read_text());usage[0]['eligible_downtime_minutes']=136
    (copied/'usage.json').write_text(json.dumps(usage))
    index=json.loads((copied/'package.json').read_text());index['input_sha256']['usage.json']=sha256((copied/'usage.json').read_bytes()).hexdigest()
    (copied/'package.json').write_text(json.dumps(index))
    with pytest.raises(ValueError,match='disagrees with interval'):verify_package(copied)


def test_signature_specimen_is_integrity_only_and_source_tampering_refuses(tmp_path):
    package=load_package()
    assert all(row['kind']=='LOCAL_TEST_SIGNATURE' and row['certificate'] is None for row in package['signature_records'])
    copied=tmp_path/'package';shutil.copytree(ROOT,copied)
    (copied/'order-form.txt').write_text((copied/'order-form.txt').read_text().replace('12,000.00','13,000.00'))
    with pytest.raises(ValueError,match='input changed'):verify_package(copied)


def test_settlement_cites_unchanged_sla_and_authored_memo_has_one_identity():
    from fixtures.northwind.loader import build_fee_registry
    package=load_package();settlement=package['settlement'];unchanged=settlement['unchanged_sla']
    assert unchanged['sla_source_sha256']==package['manifest']['document']['sha256']
    assert unchanged['citation_id']=='amendment-2026-03.txt:4'
    assert unchanged['citation']['quote'].startswith('3. Unchanged terms.')
    assert 'completed-step SLA credits' in unchanged['citation']['quote']
    assert package['correspondence']['credit_decision']['event_id']==package['correspondence']['credit_decision']['credit_id']=='NW-CM-2026-01'
    assert package['correspondence']['credit_decision']['known_at']=='2026-03-02T13:00:00Z'
    assert len(build_fee_registry(package)._entries)==4
    assert [r['month'] for r in package['months']]==['2026-01','2026-02','2026-03']
    quotes=settlement['source_quotes']
    assert any('USD 11000.00' in q['quote'] for q in quotes['pricing'])
    assert any('invoiced exactly' in q['quote'] for q in quotes['pricing'])
    assert any('each completed 0.1' in q['quote'] for q in quotes['sla'])
    assert '5. Restated rate schedule.' in (ROOT/'amendment-2026-03.txt').read_text()
