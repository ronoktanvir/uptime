"""Role 1: model errors and timeouts are recoverable and never reported as source refusals; the job view carries
the timestamps and the bounded provider receipt the interface renders. Provider doubles only; no inference."""
import json

import pytest

from uptime.vendor_family_selection import MONTHLY, RESOURCE

from test_vendor_family_selection_89 import (PROSE, PROSE_AS_RESOURCE, PROSE_PROPOSAL, VENDOR, FamilyProvider, P, approve,
                                            auto, blocks_text, by_family, run, selecting)  # noqa: F401

RECEIPT = {'profile': {'name': 'safe-public-experimental-v2', 'revision': 2, 'binary_sha256': 'b' * 64},
           'before': {'secret-path': '/Users/someone/.claude'}, 'after': {}, 'persistence': {'project_entries_changed': []},
           'model': 'claude-opus-5-5', 'session': 'scripted-session-1', 'client_reported_cost_usd': 0.061,
           'usage': {'input_tokens': 1200, 'output_tokens': 300}, 'returncode': 0, 'tool_events': 0, 'tool_inventory': [],
           'mcp_inventory': [], 'output_sha256': 'c' * 64, 'result_sha256': 'd' * 64}


class FailingProvider(FamilyProvider):
    """Per-profile outcome: text, or an exception raised by the provider itself."""

    def __init__(self):
        super().__init__()
        self.errors, self.last_receipt = {}, None

    def __call__(self, request):
        profile = json.loads(request)['profile']
        self.calls.append(profile)
        self.last_receipt = dict(RECEIPT)
        if profile in self.errors:
            raise self.errors[profile]
        return {'model': 'claude-opus-5-5', 'session': 'scripted-session-1', 'text': self.outputs[profile]}


@pytest.fixture
def failing(selecting):
    db, manifest, _, service, jobs = selecting
    provider = FailingProvider()
    service.providers['vendor'] = provider
    return db, manifest, provider, service, jobs


def test_provider_failure_is_not_a_source_refusal_and_a_new_attempt_recovers(failing):
    _, _, provider, _, jobs = failing
    provider.outputs = {'monthly-propositions': json.dumps({'clauses': PROSE_PROPOSAL}),
                        'resource-month': blocks_text(PROSE, PROSE_AS_RESOURCE)}
    provider.errors = {'resource-month': ValueError('The public proposal provider failed; no retry was attempted.')}
    approve(failing, PROSE)
    view = run(failing, PROSE)
    resource = by_family(view)[RESOURCE]
    assert resource['job']['status'] == 'REFUSED' and resource['job']['reason'] == 'provider_failed'
    assert resource['state'] == 'INCONCLUSIVE' and resource['refusal'] is None
    assert view['outcome'] == 'INCOMPLETE' and view['selected'] is None
    assert 'new attempt identifier' in view['review_requirements'][0]
    assert sorted(provider.calls) == ['monthly-propositions', 'resource-month']
    # Recovery through the existing control: a new attempt identifier with its own approval. No automatic retry.
    provider.errors = {}
    approve(failing, PROSE, nonce='retry-1')
    recovered = run(failing, PROSE, 'retry-1')
    assert recovered['outcome'] == 'SELECTED' and recovered['selected']['family'] == MONTHLY
    assert sorted(provider.calls) == ['monthly-propositions', 'monthly-propositions', 'resource-month', 'resource-month']


def test_timeout_is_uncertain_and_recoverable(failing):
    _, _, provider, _, jobs = failing
    provider.outputs = {'monthly-propositions': json.dumps({'clauses': PROSE_PROPOSAL}),
                        'resource-month': blocks_text(PROSE, PROSE_AS_RESOURCE)}
    provider.errors = {'monthly-propositions': TimeoutError('provider exceeded its bounded time')}
    approve(failing, PROSE)
    view = run(failing, PROSE)
    monthly = by_family(view)[MONTHLY]
    assert (monthly['job']['status'], monthly['job']['reason']) == ('UNCERTAIN', 'provider_timeout')
    assert view['outcome'] == 'INCOMPLETE' and view['selected'] is None


def test_unverifiable_provider_identity_has_its_own_code(failing):
    _, _, provider, service, jobs = failing
    provider.outputs = {'monthly-propositions': json.dumps({'clauses': PROSE_PROPOSAL}),
                        'resource-month': blocks_text(PROSE, PROSE_AS_RESOURCE)}
    original = FailingProvider.__call__

    def wrong_model(self, request):
        result = original(self, request)
        return result | {'model': 'some-other-model'}
    provider.__class__ = type('WrongModel', (FailingProvider,), {'__call__': wrong_model})
    approve(failing, PROSE)
    view = run(failing, PROSE)
    for family in view['families']:
        assert (family['job']['status'], family['job']['reason']) == ('REFUSED', 'provider_identity_unverified')
        assert family['public_diagnostic'] is None
    assert view['outcome'] == 'INCOMPLETE'


def test_job_view_carries_kind_timestamps_and_only_the_public_receipt(failing):
    _, _, provider, _, jobs = failing
    provider.outputs = {'monthly-propositions': json.dumps({'clauses': PROSE_PROPOSAL}),
                        'resource-month': blocks_text(PROSE, PROSE_AS_RESOURCE)}
    approve(failing, PROSE)
    view = run(failing, PROSE)
    job = jobs.status(P, VENDOR, view['selected']['job_id'])
    assert job['kind'] == 'vendor' and job['status'] == 'SUCCEEDED'
    assert job['submitted_at'] <= job['started_at'] <= job['finished_at']
    assert job['provider'] == {'model': 'claude-opus-5-5', 'session': 'scripted-session-1', 'client_reported_cost_usd': 0.061,
                               'usage': {'input_tokens': 1200, 'output_tokens': 300}, 'returncode': 0, 'tool_events': 0,
                               'tool_inventory': [], 'mcp_inventory': [], 'output_sha256': 'c' * 64, 'result_sha256': 'd' * 64,
                               'transport': {'name': 'safe-public-experimental-v2', 'revision': 2, 'binary_sha256': 'b' * 64}}
    assert '/Users/' not in json.dumps(job) and 'persistence' not in json.dumps(job)
    assert job['proposal']['clauses'][0]['quote'] == PROSE_PROPOSAL[0]['quote']
