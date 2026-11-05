"""Require every substantive clause to fit the factual explanation being proposed."""
import re
from dataclasses import dataclass
from decimal import Decimal


DENIAL = (
    r"(?:we (?:have )?(?:deny|denied|decline|declined|reject|rejected|refuse|refused) "
    r"(?:(?:your|this|the) )?(?:credit )?(?:claim|request)"
    r"|(?:(?:your|this|the) )?(?:claim|request) (?:is |was )?(?:denied|declined|rejected)"
    r"|denied|declined|rejected)"
)
DETERMINER = r"(?:(?:the|our|your|this|a|an) )?"
PERIOD = r"(?:(?:filing|submission|claim|30.day) )?(?:deadline|window|period)"
LATE = r"(?:too late|late|(?:after|outside|beyond) " + DETERMINER + PERIOD + r")"
REQUEST = (
    r"(?:(?:please )?(?:provide|send|supply|attach|furnish|share|forward|submit|identify|confirm|show|demonstrate|prove)"
    r"|(?:we|our desk) (?:need|require|lack|are missing|cannot verify|cannot complete review without|are awaiting)"
    r"|(?:we are )?(?:unable to verify|awaiting)) "
)
REFERENCE = r"(?=[a-z0-9._-]*[0-9_-])[a-z0-9][a-z0-9._-]{1,75}"
ARTIFACT = (
    DETERMINER + r"(?:(?:affected|missing|dated|itemized|supporting|service|station|component) )*"
    r"(?:logs?|log references|logbook|incident journal|telemetry extract|network trace|"
    r"invoice(?: detail| line| breakdown)?|charges|fees|statement|fee breakdown|charge breakdown|"
    r"account mapping|resource mapping|ownership record|account linkage|"
    r"component(?: id| identifier)?|endpoint(?: id| identifier)?|service (?:id|identifier)|affected api|"
    r"document|record|attachment|artifact)"
    r"(?: (?:reference |id |number )?" + REFERENCE + r")?"
    r"(?:, (?:document|record|attachment|artifact) " + REFERENCE + r")?"
    r"(?: and its supporting record)?"
)
PATTERNS = {
    "downtime": (
        r"(?:we (?:measured|logged|recorded|counted|observed)|our (?:monitors?|telemetry|records?|logs?|measurements?) "
        r"(?:measured|logged|recorded|counted|observed|show|shows)) "
        r"(?:(?:only|exactly|a total of) )?[0-9]{1,8}(?:\.[0-9]{1,6})? (?:hours?|minutes?|seconds?) "
        r"(?:of )?(?:(?:qualifying|countable|covered|service) )?(?:downtime|unavailability|outages?|interruptions?)"
        r"(?: (?:for|during|in) (?:the|this) (?:service )?month)?"
    ),
    "availability": (
        DETERMINER + r"(?:(?:scoped|measured|verified|contractual) )*"
        r"(?:availability|uptime|service availability|service levels?|service records?) "
        r"(?:meets?|met|satisfies|satisfied|exceeds?|exceeded|is at or above|was at or above|at or above|above) "
        + DETERMINER + r"(?:(?:applicable|contractual|published|contract|availability|service) )*"
        r"(?:commitment|threshold|target|guarantee|guaranteed level|minimum)"
    ),
    "time_bar": (
        r"(?:" + DETERMINER + PERIOD + r" (?:has |had |was )?(?:closed|elapsed|expired|passed)"
        r"|we (?:received|filed|submitted) " + DETERMINER + r"(?:claim|request|filing) " + LATE +
        r"|" + DETERMINER + r"(?:claim|request|filing|submission) (?:was )?"
        r"(?:received|filed|submitted|arrived|reached us) " + LATE +
        r"|" + DETERMINER + r"(?:claim|request|filing|submission) (?:is|was) (?:untimely|time.barred)"
        r"|" + LATE + r")"
    ),
    "maintenance": (
        r"(?:(?:this|the|your) (?:outage|incident|interruption)|this) "
        r"(?:was|is|coincided with|falls within|fell within|occurred during) "
        r"(?:(?:previously|scheduled|planned|announced|approved) )*(?:maintenance|planned work|scheduled work|planned downtime|scheduled downtime)"
        r"(?: announced in advance)?"
    ),
    "scope_error": (
        DETERMINER + r"(?:invoice|claim|account|resource|component) "
        r"(?:belongs? to|was filed for|was filed under|is registered to|is registered under|is associated with) "
        + DETERMINER + r"(?:account|resource|component|invoice)(?: id| identifier)? [a-z0-9][a-z0-9._-]{1,75}"
    ),
}


@dataclass(frozen=True)
class FactualInterpretation:
    reason: str
    artifact_type: str | None = None
    reference: str | None = None


def response_clauses(text):
    """Split punctuation boundaries, retaining decimal points inside tokens."""
    return [part.strip() for part in re.split(r"[!?;\n]+|\.(?=\s|$)", text) if part.strip()]


def _full(pattern, value):
    return re.fullmatch(pattern, value, re.I | re.ASCII)


def _courtesy(clause):
    return bool(_full(r"thank you(?: for your (?:time|patience|cooperation))?|thanks|(?:kind |best )?regards|sincerely", clause)
                or re.fullmatch(r"(?i:sent by) [A-Z][A-Za-z0-9'-]*(?: [A-Z][A-Za-z0-9'-]*){0,4}", clause))


_MONTHS = {name: i for i, name in enumerate(("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"), 1)}
_MONTH = r"(?:20[0-9]{2}-(?:0[1-9]|1[0-2])|(?:" + "|".join(_MONTHS) + r") 20[0-9]{2}|the service month)"
_PERCENT = r"[0-9]{1,3}(?:\.[0-9]{1,6})? ?(?:%|percent)"
_AVAIL_SUBJECT = DETERMINER + r"(?:(?:monthly|scoped|measured|verified|contractual) )*(?:availability|uptime|service availability|service levels?|service records?)"
_TARGET = DETERMINER + r"(?:(?:applicable|contractual|published|contract|monthly|service|availability) )*(?:" + _PERCENT + r" )?(?:(?:service|availability) )*(?:commitment|threshold|target|guarantee|guaranteed level|minimum)(?: (?:of|at) " + _PERCENT + r")?"
_MEETS = r"(?:meets?|met|satisfies|satisfied|exceeds?|exceeded|meeting|satisfying|exceeding|is at or above|was at or above|at or above|above)"
_AVAILABILITY = (
    _AVAIL_SUBJECT + r"(?: of (?P<measured>" + _PERCENT + r"))? (?P<relation>" + _MEETS + r") (?P<target>" + _TARGET + r")",
    _AVAIL_SUBJECT + r" (?:was|is) (?P<measured>" + _PERCENT + r"),? (?:which (?:was|is) )?(?P<relation>" + _MEETS + r") (?P<target>" + _TARGET + r")",
    r"(?P<target>" + _TARGET + r") (?:was|is|has been) met",
)


def _period(clause, scope_month):
    periods = []
    prefix = re.match(r"^(?:for|during|in) (" + _MONTH + r"),? ", clause, re.I | re.ASCII)
    if prefix:
        periods.append(prefix[1])
        clause = clause[prefix.end():]
    suffix = re.search(r" (?:for|during|in) (" + _MONTH + r")$", clause, re.I | re.ASCII)
    if suffix:
        periods.append(suffix[1])
        clause = clause[:suffix.start()]
    if len(periods) > 1:
        return None
    for period in periods:
        if not scope_month or not re.fullmatch(r"20[0-9]{2}-(?:0[1-9]|1[0-2])", scope_month):
            return None
        period = period.lower()
        if period == "the service month":
            continue
        if " " in period:
            month, year = period.split(" ")
            period = f"{year}-{_MONTHS[month]:02d}"
        if period != scope_month:
            return None
    return clause


def _availability(clause, scope_month):
    clause = _period(clause, scope_month)
    if clause is None:
        return False
    # These numbers describe only the incoming assertion. They never enter an
    # evaluation or ledger. Invalid percentage syntax/range is not a proposition.
    for match in re.finditer(r"([0-9]+(?:\.[0-9]+)?) ?(?:%|percent)", clause, re.I | re.ASCII):
        if not 0 <= Decimal(match[1]) <= 100:
            return False
    clause = re.sub(r"^our (?:records|measurements|status records) (?:show|showed) (?:that )?", "", clause, flags=re.I | re.ASCII)
    matches = [match for pattern in _AVAILABILITY[:2] if (match := _full(pattern, clause))]
    if re.search(r"\b(?:availability|uptime)\b", clause, re.I | re.ASCII):
        if match := _full(_AVAILABILITY[2], clause):
            matches.append(match)
    if len(matches) != 1:
        return False
    match = matches[0]
    limits = re.findall(_PERCENT, match["target"], re.I | re.ASCII)
    if len(limits) > 1:
        return False
    measured = match.groupdict().get("measured")
    if measured and limits:
        # This only rejects an internally contradictory statement; neither
        # number supplies contract terms, verified measurement or any money.
        value = Decimal(re.match(r"[0-9.]+", measured)[0])
        limit = Decimal(re.match(r"[0-9.]+", limits[0])[0])
        strict = match["relation"].lower() in {"above", "exceed", "exceeds", "exceeded", "exceeding"}
        if value < limit or strict and value == limit:
            return False
    return True


def _artifact_target(text):
    text = text.removesuffix(",")  # Closing punctuation on a named appositive.
    if not _full(ARTIFACT, text):
        return None
    patterns = {"resource_log":r"\b(?:logs?|logbook|incident journal|telemetry extract|network trace)\b",
                "invoice_detail":r"\b(?:itemi[sz]ed (?:invoice|charges|fees|statement)|invoice (?:detail|line|breakdown)|fee breakdown|charge breakdown)\b",
                "scope_mapping":r"\b(?:account mapping|resource mapping|ownership record|account linkage)\b"}
    kinds = [kind for kind, pattern in patterns.items() if re.search(pattern, text, re.I | re.ASCII)]
    refs = [m[1].rstrip(".") for m in re.finditer(r"\b(?:document|record|attachment|artifact|log|invoice)(?: (?:reference|id|number))? (" + REFERENCE + r")", text, re.I | re.ASCII)]
    if len(kinds) > 1 or len(set(refs)) > 1:
        return None
    kind, ref = kinds[0] if kinds else None, refs[0] if refs else None
    component = bool(re.search(r"\b(?:component|endpoint|service identifier|affected api|service id)\b", text, re.I | re.ASCII))
    if not kind and not ref and not component:
        return None
    return FactualInterpretation("component" if component and not kind and not ref else "artifact", kind, ref)


def _merge_artifacts(first, second):
    if first.reason != second.reason:
        return None
    if (first.artifact_type and second.artifact_type and first.artifact_type != second.artifact_type
            or first.reference and second.reference and first.reference != second.reference):
        return None
    return FactualInterpretation(first.reason, first.artifact_type or second.artifact_type, first.reference or second.reference)


def _unique_interpretation(candidates):
    return candidates[0] if len(candidates) == 1 else None


def interpret_factual(text, *, scope_month=None):
    """One finite grammar admits a complete, compatible factual response.

    Cross-family composition and ambiguous targets refuse. The only stateful
    reference is an immediately adjacent explicit missing-artifact target.
    """
    nodes = []
    seen = set()
    previous = None
    for raw in response_clauses(text):
        if _courtesy(raw):
            previous = None
            continue
        if raw.lower() in seen:
            return None
        seen.add(raw.lower())
        if _full(DENIAL, raw):
            nodes.append(("denial", None, False))
            previous = None
            continue
        clause = raw
        # The pronoun is bound syntactically, never inherited from another
        # sentence or across an appositive/intervening noun phrase.
        pronoun = re.fullmatch(r"we (?:have )?(?:denied|declined|rejected|refused) your (?:claim|request|filing) because it (?P<predicate>(?:was )?(?:received|filed|submitted|arrived) " + LATE + r")", clause, re.I | re.ASCII)
        if pronoun:
            nodes.append(("time_bar", FactualInterpretation("time_bar"), False))
            previous = None
            continue
        clause = re.sub(r"^" + DENIAL + r" (?:because|as|since|due to) ", "", clause, flags=re.I | re.ASCII)
        clause = re.sub(r",? (?:so|therefore|and) " + DENIAL + r"$", "", clause, flags=re.I | re.ASCII)
        candidates = []
        if _availability(clause, scope_month):
            candidates.append(("availability", FactualInterpretation("availability"), False))
        if _full(PATTERNS["time_bar"], clause):
            candidates.append(("time_bar", FactualInterpretation("time_bar"), False))
        missing = re.fullmatch(r"(?P<target>.+) (?:is|was) missing", clause, re.I | re.ASCII)
        implied = False
        if not missing:
            missing = re.fullmatch(r"we (?:have not received|are missing|lack|cannot verify) (?P<target>.+)", clause, re.I | re.ASCII)
            implied = bool(missing and not clause.lower().startswith("we have not received "))
        if missing:
            target = _artifact_target(missing["target"])
            if target:
                candidates.append(("missing", target, implied))
        else:
            request = re.fullmatch(REQUEST + r"(?P<target>.+)", clause, re.I | re.ASCII)
            if request:
                target = _artifact_target(request["target"])
                if _full(r"that document|it", request["target"]):
                    target = previous[1] if previous and previous[0] == "missing" else None
                if target:
                    candidates.append(("request", target, False))
        node = _unique_interpretation(candidates)
        if node is None:
            return None
        nodes.append(node)
        previous = node
    substantive = [node for node in nodes if node[0] != "denial"]
    if len(substantive) == 1:
        kind, target, implied = substantive[0]
        if kind == "missing" and not implied:
            return None
        return target
    if len(substantive) == 2 and [node[0] for node in substantive] == ["missing", "request"]:
        return _merge_artifacts(substantive[0][1], substantive[1][1])
    return None


def complete_explanation(text, reason, field_names=()):
    """Unknown clauses and residual predicates require review, even beside a known cue.

    These are full-clause grammars. The caller's cue matcher may suggest a
    factual interpretation only when this check accounts for the whole message.
    """
    pattern = PATTERNS.get(reason)
    if reason in {"artifact", "component", "filing_fields"}:
        targets = [ARTIFACT]
        if field_names:
            targets.append(DETERMINER + r"(?:missing )?(?:" + "|".join(re.escape(n) for n in field_names) + r")")
        pattern = REQUEST + r"(?:" + "|".join(targets) + r")"
    if pattern is None:
        return False
    clauses = response_clauses(text)
    factual = False
    for raw in clauses:
        clause = raw.strip()
        if not clause:
            continue
        if re.fullmatch(r"(?i:thank you(?: for your (?:time|patience|cooperation))?|thanks|(?:kind |best )?regards|sincerely)", clause):
            continue
        if re.fullmatch(r"(?i:sent by) [A-Z][A-Za-z0-9'-]*(?: [A-Z][A-Za-z0-9'-]*){0,4}", clause):
            continue
        if re.fullmatch(DENIAL, clause, re.I):
            continue
        clause = re.sub(r"^" + DENIAL + r" (?:because|as|since|due to) ", "", clause, flags=re.I)
        clause = re.sub(r",? (?:so|therefore|and) " + DENIAL + r"$", "", clause, flags=re.I)
        if not re.fullmatch(pattern, clause, re.I):
            return False
        factual = True
    return factual
