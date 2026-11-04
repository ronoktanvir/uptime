from decimal import Decimal
import json
from pathlib import Path
import pytest
from uptime.contracts import Citation, EvaluationResult, Money, Outcome, Source


def test_missing_fixture_has_no_estimated_award():
    f = json.loads(Path("fixtures/cp1.json").read_text())
    r = EvaluationResult(Outcome(f["status"]), (Citation("demo","1","fees","fixture:fees"),), ("No allocation",), tuple(f["missing"]))
    assert r.amount is None and Source(f["source"]) == Source.REPLAY


@pytest.mark.parametrize("invalid", [float(0.1), Decimal("NaN"), Decimal("Infinity")])
def test_financial_input_rejects_non_decimal_or_nonfinite(invalid):
    with pytest.raises(ValueError):
        Money(invalid)
