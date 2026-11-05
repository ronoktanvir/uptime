"""Post-observation gold predicates. No fixture reading or app mutations here."""
from calendar import monthrange
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from fractions import Fraction
import re


def normalized(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def metrics(row):
    """Project actual response fields or the evaluator's exact arithmetic trace."""
    result = {k: row[k] for k in ("downtime_microseconds", "total_microseconds", "affected_fee_cents",
              "rate_units", "service_estimate", "remaining_estimate", "prior_issued_cents",
              "claim_cutoff", "filing_status") if k in row}
    for text in row.get("trace", []):
        measured = re.fullmatch(r"([0-9]+)/([0-9]+) UTC microseconds of qualifying downtime after overlap union and exclusion subtraction\.", text)
        if measured:
            result.update(downtime_microseconds=int(measured[1]), total_microseconds=int(measured[2]))
        fee = re.fullmatch(r"([0-9]+) eligible service cents, rate ([0-9]+)/1000000%, modeled USD [0-9.]+\.", text)
        if fee:
            result.update(affected_fee_cents=int(fee[1]), rate_units=int(fee[2]))
    return result


NUMERIC_FIELDS = {"confirmed_covered_seconds", "excluded_seconds", "unresolved_claimed_seconds", "eligible_base",
                  "credit_percent", "unrounded_credit", "supported_credit", "remaining_credit",
                  "previously_granted_credit", "increment_over_initial_supported_estimate", "period_seconds",
                  "availability_percent_exact_fraction", "availability_percent_decimal_display"}


def metric_value(name, observed):
    data = observed.get("metrics", {})
    if name == "confirmed_covered_seconds":
        return Decimal(data["downtime_microseconds"]) / 1_000_000 if "downtime_microseconds" in data else None
    if name == "period_seconds":
        return Decimal(data["total_microseconds"]) / 1_000_000 if "total_microseconds" in data else None
    if name == "eligible_base":
        return Decimal(data["affected_fee_cents"]) / 100 if "affected_fee_cents" in data else None
    if name == "credit_percent":
        return Decimal(data["rate_units"]) / 1_000_000 if "rate_units" in data else None
    if name == "previously_granted_credit":
        return Decimal(data["prior_issued_cents"]) / 100 if "prior_issued_cents" in data else None
    if name in {"availability_percent_exact_fraction", "availability_percent_decimal_display"}:
        if not {"total_microseconds", "downtime_microseconds"} <= data.keys():
            return None
        return Fraction(100 * (data["total_microseconds"]-data["downtime_microseconds"]), data["total_microseconds"])
    if name == "unrounded_credit":
        if not {"affected_fee_cents", "rate_units"} <= data.keys():
            return None
        return Decimal(data["affected_fee_cents"]) * data["rate_units"] / 10_000_000_000
    aliases = {"supported_credit": "service_estimate", "remaining_credit": "remaining_estimate",
               "excluded_seconds": "excluded_seconds", "unresolved_claimed_seconds": "unresolved_claimed_seconds",
               "increment_over_initial_supported_estimate": "increment_over_initial_supported_estimate"}
    key = aliases.get(name)
    return Decimal(data[key]) if key and data.get(key) is not None else None


def numeric_check(name, expected, observed):
    actual = metric_value(name, observed)
    if not observed.get("observation", {}).get("available"):
        return "UNAVAILABLE"
    if expected is None or actual is None:
        return "PASS" if expected is actual else "UNKNOWN_MISMATCH"
    if name == "availability_percent_exact_fraction":
        try:
            wanted = Fraction(expected)
        except (ValueError, TypeError, ZeroDivisionError):
            return "EXPECTATION_ENCODING_UNSUPPORTED"
    elif name == "availability_percent_decimal_display":
        with localcontext() as ctx:
            ctx.prec = max(60, len(expected) + 10)
            actual = Decimal(actual.numerator) / actual.denominator
            wanted = Decimal(expected)
            actual = actual.quantize(Decimal(1).scaleb(wanted.as_tuple().exponent))
    else:
        wanted = Decimal(expected)
    return "PASS" if actual == wanted else "WRONG_MEASUREMENT" if "seconds" in name or "availability" in name else "WRONG_MONEY"


def decision_check(value, observed):
    words = normalized(value)
    target = observed.get("observation", {})
    if words.startswith("refuse account") or words.startswith("refuse resource"):
        return "scope", "PASS" if observed.get("scope_refused") is True else "WRONG_SCOPE"
    if not target.get("available"):
        return "decision", "UNAVAILABLE"
    stage, outcome = target.get("stage"), target.get("outcome")
    if words.startswith("accept denial"):
        passed = stage == "DENIAL_ACCEPTED" and outcome == "INELIGIBLE"
    elif words.startswith("draft evidence request"):
        passed = stage in {"NEEDS_EVIDENCE", "RESPONSE_DRAFTED"}
    elif (words.startswith("draft") or words.startswith("timely")) and "claim" in words:
        passed = outcome == "ELIGIBLE" and stage in {"DRAFTED", "EVALUATED", "RESPONSE_DRAFTED"}
    elif words.startswith("draft correct channel filing"):
        passed = outcome == "INSUFFICIENT_EVIDENCE" and "filing_material" in observed.get("missing_categories", [])
    elif words.startswith("request"):
        passed = outcome == "INSUFFICIENT_EVIDENCE" and bool(observed.get("missing_categories"))
    elif any(term in words for term in ("late", "wrong channel", "deadline", "expired")):
        passed = outcome == "INELIGIBLE" and (target.get("filing_status") in {"OUTSIDE_WINDOW", "LATE_SUPPLEMENT"}
                  or stage in {"EXPIRED", "DENIAL_ACCEPTED"})
    elif any(term in words for term in ("no credit", "no breach", "threshold", "ineligible")):
        passed = outcome == "INELIGIBLE"
    else:
        return "decision", "SEMANTIC_PREDICATE_REVIEW_REQUIRED"
    return "decision", "PASS" if passed else "WRONG_DECISION"


def term_value(path, manifest):
    name = path[0]
    aliases = {"amount_rounding": "rounding", "availability_comparison": "boundary", "filing_channel": "submission_channel"}
    if name == "availability_comparison" and {"exact_elapsed", "availability_ratio"} <= set(manifest.get("interval_measurement", [])):
        return "exact_unrounded"
    if name in aliases:
        return manifest.get(aliases[name])
    if name == "effective_date":
        return manifest.get("effective", [None])[0]
    if name == "covered_endpoint":
        return manifest.get("scope", {}).get("product")
    if name == "strict_tiers_descending_credit":
        tier = sorted(manifest["tiers"], key=lambda r: -r["credit_units"])[int(path[1])]
        return Decimal(tier[{"availability_below": "below_units", "credit_percent": "credit_units"}[path[2]]]) / 1_000_000
    if name in {"period_start", "period_end_exclusive", "period_seconds", "filing_deadline_inclusive"}:
        month = manifest.get("_measurement_month")
        if not month:
            return None
        first = datetime.fromisoformat(month + "-01").replace(tzinfo=UTC)
        end = first + timedelta(days=monthrange(first.year, first.month)[1])
        if name == "period_seconds":
            return int((end-first).total_seconds())
        if name == "period_start":
            return first
        if name == "period_end_exclusive":
            return end
        rule = manifest["filing"]
        if rule["kind"] != "calendar_days" or rule["endpoint"] != "inclusive":
            return None
        day = end + timedelta(days=rule["count"]-1)
        return datetime.fromisoformat(day.date().isoformat()+"T"+rule["utc_time"]+"+00:00")
    current = manifest
    for key in path:
        current = current[int(key)] if isinstance(current, list) else current[key]
    return current


def term_equal(path, expected, actual):
    if isinstance(actual, datetime):
        return actual == datetime.fromisoformat(expected)
    if isinstance(actual, (Decimal, int)):
        return Decimal(expected) == actual
    if path[0] == "covered_endpoint":
        return normalized(expected) in normalized(actual).split(" queue endpoint")[0] or normalized(expected) == normalized(actual)
    aliases = {"strict below": "strict below", "strict below without rounding availability": "strict below",
               "nearest cent half up": "nearest cent half up", "nearest cent half up once": "nearest cent half up",
               "future invoice credit only": "future noncash credit",
               "future invoice credit": "future noncash credit"}
    return aliases.get(normalized(expected), normalized(expected)) == aliases.get(normalized(actual), normalized(actual))
