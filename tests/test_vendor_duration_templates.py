"""Duration absence is a bounded source assertion with whole-block refusal controls."""
import pytest

from test_vendor_resource import compiled, extend_source
from uptime.vendor_resource_operators import apply_operator, interval_options


@pytest.mark.parametrize("quote", [
    "There is no minimum invoice fee. Incident duration must exceed two minutes.",
    'The rejected example says "no minimum incident duration". That statement does not apply.',
    '"There is no minimum incident duration."',
    "There is no minimum duration exclusion.",
    "There is no minimum incident duration for scheduled maintenance.",
    "There is no minimum incident dura-\ntion.",
    "There is no minimum incident dura\u200btion.",
])
def test_only_exact_affirmative_duration_templates_are_operative(quote):
    assert "no_minimum_duration" not in interval_options(quote)
    with pytest.raises(ValueError):
        apply_operator({}, "interval_measurement", ["no_minimum_duration"], quote)
    with pytest.raises(ValueError):
        compiled(*extend_source([(quote, {"interval_measurement":["no_minimum_duration"]})]))


@pytest.mark.parametrize("extra", [
    "A minimum duration of 30 seconds applies.",
    "Only incidents lasting thirty seconds qualify.",
    "This rule applies only if the provider agrees.",
    'The example states "minimum outage duration is waived".',
    "Count at least 30 elapsed seconds before declaring an outage.",
])
@pytest.mark.parametrize("reverse", [False, True])
def test_unmapped_duration_conditions_refuse_the_entire_source_block(extra, reverse):
    pieces = ["There is no minimum incident duration.", extra]
    if reverse:
        pieces.reverse()
    effects = ["no_minimum_duration"]
    if "elapsed" in extra:
        effects.append("exact_elapsed")
    values = {"interval_measurement":effects}
    with pytest.raises(ValueError):
        compiled(*extend_source([(" ".join(pieces), values)]))


def test_source_bound_measurement_neighbours_preserve_the_exact_effect():
    quote = ("Clip each outage crossing a calendar month boundary to that month. "
             "There is no minimum outage duration. Exclusions do not reduce the denominator.")
    effects = ["clip_to_month", "no_minimum_duration", "fixed_denominator"]
    manifest = compiled(*extend_source([(quote, {"interval_measurement":effects})]))
    assert set(manifest["interval_measurement"]) == set(effects)
    assert manifest["citations"][-1]["quote"] == quote
