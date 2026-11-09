"""D05 operator export for automatic family selection: one exact, permission-free export per supported family."""
import pytest

from test_public_proposal_export_79 import (DOCUMENT, SUBJECT, TARGET, TENANT, RefusingProvider, _tree, no_approval,  # noqa: F401
                                            private, providers, public_proposals)
from uptime.vendor_family_selection import FAMILIES


def test_auto_writes_one_exact_export_per_family_matching_single_profile_exports(private, providers):
    before = _tree(private.root)
    results = public_proposals.export_vendor_auto(DOCUMENT, private.config, private.exports / 'unseen.json',
                                                  tenant=TENANT, subject=SUBJECT, target=TARGET)
    assert [r['profile'] for r in results] == [profile for _, profile, _ in FAMILIES]
    for result in results:
        single = public_proposals.export_vendor(DOCUMENT, private.config, private.exports / ('single-' + result['profile'] + '.json'),
                                                tenant=TENANT, subject=SUBJECT, target=TARGET, profile=result['profile'])
        assert result['request_sha256'] == single['request_sha256']
        value, digest = public_proposals.read_export(result['output_path'])
        assert digest == result['request_sha256'] and value['request']['profile'] == result['profile']
    assert len({r['request_sha256'] for r in results}) == len(FAMILIES)
    assert {'exports/unseen.monthly-propositions.json', 'exports/unseen.resource-month.json'} <= _tree(private.root) - before
    assert not private.approvals.exists()


def test_auto_writes_nothing_when_any_family_path_already_exists(private, providers):
    (private.exports / 'taken.resource-month.json').write_text('{}')
    with pytest.raises(ValueError, match='must be new'):
        public_proposals.export_vendor_auto(DOCUMENT, private.config, private.exports / 'taken.json',
                                            tenant=TENANT, subject=SUBJECT, target=TARGET)
    assert not (private.exports / 'taken.monthly-propositions.json').exists()
    assert providers == []
    with pytest.raises(ValueError, match='.json'):
        public_proposals.export_vendor_auto(DOCUMENT, private.config, private.exports / 'unseen.txt',
                                            tenant=TENANT, subject=SUBJECT, target=TARGET)
