"""Require every substantive clause to fit the factual explanation being proposed."""
import re


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
    clauses = re.split(r"[!?;\n]+|\.(?=\s|$)", text)
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
