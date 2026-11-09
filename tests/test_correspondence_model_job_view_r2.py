"""Role 2: the dispute job view shows the shared service's public receipt block unchanged.

FakeJobs is the existing test double of the shared job service (tests/test_correspondence_model_jobs_75.py).
The receipt values below are authored; no provider is called.
"""
from test_correspondence import env, ID, REVIEWER  # noqa: F401 (fixture)
from test_correspondence_model_jobs_75 import setup, submit

RECEIPT = dict(model='claude-opus-5-5', session='session-r2', client_reported_cost_usd=0.044891,
               usage=dict(output_tokens=418), returncode=0, tool_events=0, tool_inventory=[], mcp_inventory=[],
               output_sha256='a' * 64, result_sha256='b' * 64,
               transport=dict(name='safe-public-claude', revision='r2', binary_sha256='c' * 64))


def test_dispute_job_view_passes_the_public_receipt_through_with_cost_and_empty_inventories(env):
    desk, jobs, fake, provider, context, _ = setup(env)
    job = submit(jobs, context)
    fake.run(job['id'])
    fake.jobs[job['id']]['provider'] = dict(RECEIPT)
    for shown in (jobs.view(REVIEWER, ID)['model_job']['job'], jobs.get(REVIEWER, ID, job['id'])):
        assert shown['provider'] == RECEIPT
        assert shown['provider']['client_reported_cost_usd'] == 0.044891
        assert shown['provider']['tool_inventory'] == [] and shown['provider']['mcp_inventory'] == []
        assert {'submitted_at', 'started_at', 'finished_at'} <= set(shown)


def test_a_failed_job_still_shows_its_receipt(env):
    desk, jobs, fake, provider, context, _ = setup(env)
    job = submit(jobs, context)
    provider.text = 'not json'
    assert fake.run(job['id'])['state'] == 'REFUSED'
    fake.jobs[job['id']]['provider'] = dict(RECEIPT, returncode=1)
    shown = jobs.get(REVIEWER, ID, job['id'])
    assert shown['state'] == 'REFUSED' and shown['result'] is None and shown['provider']['returncode'] == 1
