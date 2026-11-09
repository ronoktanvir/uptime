"""Parent-authored admission controls for the separately reviewed complete-month path."""
import pytest
from uptime.evidence_applicability import temporal_refusal


@pytest.mark.parametrize("kind", ["monthly_coverage", "monthly_attribution"])
@pytest.mark.parametrize("start,end,observed", [
    ("2028-02-01T00:00:00Z", "2028-03-01T00:00:00Z", "2028-03-01T00:00:00Z"),
    ("2028-02-01T01:00:00+01:00", "2028-03-01T01:00:00+01:00", "2028-03-01T01:01:00+01:00"),
])
def test_exact_calendar_report_admitted(kind, start, end, observed):
    assert temporal_refusal(dict(kind=kind, start=start, end=end, observed_at=observed, complete=True), "2028-02") is None


@pytest.mark.parametrize("kind", ["monthly_coverage", "monthly_attribution"])
@pytest.mark.parametrize("start,end,observed", [
    ("2028-02-01T00:01:00Z", "2028-03-01T00:00:00Z", "2028-03-01T00:00:00Z"),
    ("2028-01-31T23:59:00Z", "2028-03-01T00:00:00Z", "2028-03-01T00:00:00Z"),
    ("2028-02-01T00:00:00Z", "2028-02-29T23:59:00Z", "2028-03-01T00:00:00Z"),
    ("2028-02-01T00:00:00Z", "2028-03-01T00:01:00Z", "2028-03-01T00:01:00Z"),
    ("2028-02-01T00:00:00Z", "2028-03-01T00:00:00Z", "2028-02-29T23:59:59Z"),
    ("2028-01-01T00:00:00Z", "2028-02-01T00:00:00Z", "2028-03-01T00:00:00Z"),
])
def test_partial_foreign_or_premature_report_refused(kind, start, end, observed):
    assert temporal_refusal(dict(kind=kind, start=start, end=end, observed_at=observed, complete=True), "2028-02") is not None


@pytest.mark.parametrize("kind", ["monthly_coverage", "monthly_attribution"])
def test_complete_false_does_not_admit_a_premature_month_report(kind):
    assert temporal_refusal(dict(kind=kind, start="2028-02-01T00:00:00Z", end="2028-03-01T00:00:00Z",
                                observed_at="2028-02-15T00:00:00Z", complete=False), "2028-02") is not None


def test_existing_offset_margin_is_unchanged():
    # Existing status scope is calendar/time-zone dependent; the new exact report rule is not global.
    assert temporal_refusal(dict(kind="status", start="2028-01-31T23:59:00Z", end="2028-02-01T00:01:00Z"), "2028-02") is None
