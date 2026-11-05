"""Bounded proposals from untrusted text. Only the desk can authorize or book anything."""
import re
from dataclasses import dataclass
from decimal import Decimal, localcontext

from .correspondence_language import complete_explanation

@dataclass(frozen=True)
class Proposal:
    reason: str
    span: tuple[int, int] | None = None
    amount: str | None = None
    artifact_type: str | None = None
    reference: str | None = None
    scope_field: str | None = None
    downtime_us: int | None = None


_USD = re.compile(r"(?:\busd\s*|\$\s*)([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)(?!\w|[.,][0-9])"
                  r"|\b([0-9]+(?:\.[0-9]+)?)\s*usd\b")
_CREDIT = r"(?:a |the |your )?(?:partial |full )?(?:future[- ]invoice |service |sla |account )?credit(?: memo)?"
_GRANT = r"(?:approved|awarded|granted|issued|authorized|credited|applied)"
_AMOUNT = r"(?P<award>v[0-9]+)"
_AWARD = re.compile(
    rf"(?:we (?:have )?(?:{_GRANT}|approve|award|grant|authorize) (?:you )?(?:"
    rf"{_CREDIT} (?:of |for |in the amount of )?{_AMOUNT}|(?P<first>v[0-9]+) (?:as |in )?{_CREDIT})"
    rf"|{_CREDIT} (?:of |for )?(?P<passive>v[0-9]+) (?:has been |is |was ){_GRANT}"
    rf"|we (?:have )?credited your account (?:with |for )?(?P<direct>v[0-9]+))"
    r"(?: (?:to your account|on your (?:next|future) invoice))?"
    r"(?: (?:against|of|from) (?:the |your )?(?:requested|claimed) (?P<requested>v[0-9]+))?"
)
_REQUESTED = re.compile(r"(?:(?:you (?:requested|claimed))|(?:(?:your|the) (?:original )?(?:claim|request) (?:was|totaled|totalled|is for))) (v[0-9]+)")
_REMAINDER = re.compile(r"(?:we (?:denied|decline|declined) the remaining (v[0-9]+)"
                        r"|the remaining (v[0-9]+) (?:is|was) (?:denied|declined|disputed))")


def award_proposal(text, values, claimed):
    """Interpret each monetary assertion and reconcile any other figure to the filed amount."""
    amounts = {}
    chunks = []
    last = 0
    if re.search(r"\bv[0-9]+\b", text):
        return Proposal("unknown")
    for i, value in enumerate(values):
        amount = Decimal((value.group(1) or value.group(2)).replace(",", ""))
        if amount < 0 or amount.as_tuple().exponent < -2 or amount >= Decimal("1e12"):
            return Proposal("unknown")
        marker = f"v{i}"
        amounts[marker] = amount
        chunks.extend((text[last:value.start()], marker))
        last = value.end()
    chunks.append(text[last:])
    clauses = re.split(r"\s*[.;!\n]+\s*", "".join(chunks).strip())
    awarded = requested = remainder = None
    for clause in filter(None, clauses):
        if grant := _AWARD.fullmatch(clause):
            if awarded is not None:
                return Proposal("unknown")
            awarded = next(amounts[k] for k in (grant["award"], grant["first"], grant["passive"], grant["direct"]) if k)
            if grant["requested"]:
                if requested is not None:
                    return Proposal("unknown")
                requested = amounts[grant["requested"]]
        elif req := _REQUESTED.fullmatch(clause):
            if requested is not None:
                return Proposal("unknown")
            requested = amounts[req[1]]
        elif rem := _REMAINDER.fullmatch(clause):
            if remainder is not None:
                return Proposal("unknown")
            remainder = amounts[rem[1] or rem[2]]
        else:
            return Proposal("unknown")
    if awarded is None or awarded <= 0 or requested is not None and claimed != requested:
        return Proposal("unknown")
    with localcontext() as context:
        context.prec = 50
        if remainder is not None and (claimed is None or awarded + remainder != claimed):
            return Proposal("unknown")
    return Proposal("award", (0, len(text)), format(awarded, ".2f"))


# Each cue needs both a subject and a predicate. Ambiguous compound replies,
# imperatives about system behavior, conditional offers and unsupported units
# cannot authorize a follow-up or a financial entry.
def propose(text: str, *, claimed: Decimal | None = None) -> Proposal:
    source = text
    text = text.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"))
    if re.search(r"\b(ignore|override|execute|credentials?|password|secret|token|system prompt|wire transfer|instructions?|disregard|hypothetical|hypothetically|quoted|forwarded)\b|[<>{}\"“”]|https?://", text):
        return Proposal("unknown")
    reasons = {
        "availability": (r"\b(?:availability|uptime|service levels?|service records?)\b[^.!?]{0,60}"
                         r"\b(?:meets?|met|satisf(?:ies|ied)|exceeds?|exceeded|at or above|above)\b[^.!?]{0,40}"
                         r"\b(?:commitment|threshold|target|guarantee|guaranteed level|minimum)\b"),
        "maintenance": r"\b(maintenance|planned (?:work|downtime)|scheduled (?:work|downtime))\b",
        "time_bar": r"\b(too late|out of time|time.barred|untimely|late (?:submission|filing|claim)|missed (?:the |our )?(?:deadline|window)|(?:deadline|window|period) (?:has |had |was )?(?:closed|elapsed|expired|passed)|(?:after|outside|beyond) (?:the |our )?(?:filing |submission |claim |30.day )?(?:deadline|window|period)|(?:submitted|received|filed) late)\b",
    }
    found = [(reason, m.span()) for reason, pattern in reasons.items() if (m := re.search(pattern, text))]
    component = re.search(r"\b(component|endpoint|service identifier|affected api|service id)\b", text)
    request = re.search(r"\b(need(?:ed)?|missing|lack(?:s|ing)?|provide|send|supply|attach|furnish|share|forward|submit|awaiting|require(?:s|d)?|identify|confirm|cannot verify|unable to verify|which|without|does not (?:identify|show)|did not (?:identify|include))\b", text)
    # Observable artifact classes and explicit references can be resolved by a
    # signed source. Natural language only proposes which proof to look up.
    artifact_type = reference = scope_field = None
    if request:
        classes = {"resource_log":r"\b(?:logs?|logbook|incident journal|telemetry extract|network trace)\b",
                   "invoice_detail":r"\b(?:itemi[sz]ed (?:invoice|charges|fees|statement)|invoice (?:detail|line|breakdown)|fee breakdown|charge breakdown)\b",
                   "scope_mapping":r"\b(?:account mapping|resource mapping|ownership record|account linkage)\b"}
        labels = r"\b(?:document|record|attachment|artifact|log|invoice)(?:\s+(?:reference|id|number))?\s+[#:]?([a-z0-9][a-z0-9._-]{1,75})"
        refs = [m for m in re.finditer(labels,text) if re.search(r"[a-z]",m[1]) and re.search(r"[0-9_-]",m[1])]
        if len({m[1].rstrip(".") for m in refs}) > 1:
            return Proposal("unknown")
        named = refs[0] if refs else None
        if named:
            reference = source[named.start(1):named.end(1)].rstrip(".")
        hits = [(kind, match) for kind, pattern in classes.items() if (match := re.search(pattern,text))]
        if len(hits)>1:
            return Proposal("unknown")
        if hits or reference:
            artifact_type, target = hits[0] if hits else (None,named)
            found.append(("artifact",(min(target.start(),request.start()),max(target.end(),request.end()))))
    denial = re.search(r"\b(?:deny|denied|declin(?:e|ed)|reject(?:ed)?|refused|ineligible)\b",text)
    downtime_us = None
    if denial and not re.search(r"\b(?:if|maybe|uncertain|approximately|at least|more than|over|possibly|could|might|your logs|you claimed|you reported|not)\b", text):
        # Match a definite quantity attributed to the counterparty itself. The
        # claimant checks whether its own signed, reconciled interval data exceed
        # that amount; a vendor-supplied number can never become a ledger operand.
        near = r"[^.!?;]{0,70}?"
        duration = r"(?P<quantity>[0-9]{1,8}(?:\.[0-9]{1,6})?)\s*(?P<unit>hours?|minutes?|seconds?)\b"
        measure = re.compile(
            r"\b(?:we (?:measured|logged|recorded|counted|observed)|our (?:monitors?|telemetry|records?|logs?|measurements?))\b"
            + near + duration + near + r"\b(?:downtime|unavailability|outage|interruption)\b")
        matches = list(measure.finditer(text))
        if len(matches) == 1 and len(re.findall(r"\b[0-9]+(?:\.[0-9]+)?\s*(?:hours?|minutes?|seconds?)\b",text)) == 1:
            match = matches[0]
            scale = {"hour":3_600_000_000,"minute":60_000_000,"second":1_000_000}
            with localcontext() as ctx:
                ctx.prec = 50
                downtime_us = int(Decimal(match["quantity"]) * scale[match["unit"].rstrip("s")])
            found.append(("downtime",match.span()))

    alleged = re.search(r"\b(?:belongs? to|filed (?:for|under)|registered (?:to|under)|associated with)\s+(?:the\s+)?(account|resource|component|invoice)(?:\s+(?:id|identifier))?\s+[#:]?([a-z0-9][a-z0-9._-]{1,75})",text)
    if denial and alleged and re.search(r"[0-9_-]",alleged[2]) and not re.search(r"\b(if|may|might|could|uncertain)\b",text):
        scope_field = "component" if alleged[1]=="resource" else alleged[1]
        reference = source[alleged.start(2):alleged.end(2)].rstrip(".")
        found.append(("scope_error",(min(denial.start(),alleged.start()),max(denial.end(),alleged.end()))))
    if component and request and not (artifact_type or reference) and not re.search(r"\b(no|not|never)\b.{0,50}\b(component|endpoint|needed|required)\b", text):
        found.append(("component", (min(component.start(), request.start()), max(component.end(), request.end()))))
    values = list(_USD.finditer(text))
    if values:
        return Proposal("unknown") if found else award_proposal(text, values, claimed)
    if len(found) != 1:
        return Proposal("unknown")
    reason, span = found[0]
    if reason in {"availability", "time_bar", "maintenance"} and re.search(
            r"\b(?:whether|unless|possibly|uncertain|unsure|could|might|hypothetical|perhaps|investigating|"
            r"not|never|didn't|wasn't|isn't|haven't)\b", text):
        return Proposal("unknown")
    if reason in {"artifact", "component"} and re.search(r"\b(?:no longer|do not send|don't send|unnecessary|already have)\b", text):
        return Proposal("unknown")
    if reason == "maintenance" and re.search(r"\b(no|not|never|possibly|potential|unclear|unknown|unconfirmed)\b.{0,40}\bmaintenance\b", text):
        return Proposal("unknown")
    if not complete_explanation(source, reason):
        return Proposal("unknown")
    return Proposal(reason, span, artifact_type=artifact_type, reference=reference, scope_field=scope_field, downtime_us=downtime_us)


def requested_filing_fields(text, names):
    """Match an explicit request to corroborated public field labels, never arbitrary vendor instructions."""
    lowered = text.casefold()
    if not complete_explanation(text, "filing_fields", names):
        return []
    if (not re.search(r"\b(?:need|missing|lack|provide|document|prove|send|supply|attach|furnish|require|show|demonstrate|without)\w*\b", lowered)
            or re.search(r"\b(?:ignore|override|execute|credentials?|password|secret|token|instructions?|disregard|quoted|hypothetical|already|unnecessary)\b|[<>{}\"“”]|https?://", lowered)):
        return []
    classes = ({"month","period"}, {"resource","station","endpoint","component"}, {"interval","intervals","timestamps","log","logs","journal"},
               {"controller","attribution","cause"}, {"valid","validation"}, {"bill","billing","invoice","charge","fees"})
    words = set(re.findall(r"[a-z]+", lowered))
    result = []
    for name in names:
        terms = set(re.findall(r"[a-z]+", name.casefold()))
        if name.casefold() in lowered or any(words & group and terms & group for group in classes):
            result.append(name)
    return sorted(result)
