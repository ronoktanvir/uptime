"""Bounded proposals from untrusted text. Only the desk can authorize or book anything."""
import re
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class Proposal:
    reason: str
    span: tuple[int, int] | None = None
    amount: str | None = None
    artifact_type: str | None = None
    reference: str | None = None
    scope_field: str | None = None


# Each cue needs both a subject and a predicate. Ambiguous compound replies,
# imperatives about system behavior, conditional offers and unsupported units
# cannot authorize a follow-up or a financial entry.
def propose(text: str) -> Proposal:
    source = text
    text = text.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"))
    if re.search(r"\b(ignore|override|execute|credentials?|password|secret|token|system prompt|wire transfer|instructions?|disregard|hypothetical|hypothetically|quoted|forwarded)\b|[<>{}\"“”]|https?://", text):
        return Proposal("unknown")
    reasons = {
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
    alleged = re.search(r"\b(?:belongs? to|filed (?:for|under)|registered (?:to|under)|associated with)\s+(?:the\s+)?(account|resource|component|invoice)(?:\s+(?:id|identifier))?\s+[#:]?([a-z0-9][a-z0-9._-]{1,75})",text)
    if denial and alleged and re.search(r"[0-9_-]",alleged[2]) and not re.search(r"\b(if|may|might|could|uncertain)\b",text):
        scope_field = "component" if alleged[1]=="resource" else alleged[1]
        reference = source[alleged.start(2):alleged.end(2)].rstrip(".")
        found.append(("scope_error",(min(denial.start(),alleged.start()),max(denial.end(),alleged.end()))))
    if component and request and not (artifact_type or reference) and not re.search(r"\b(no|not|never)\b.{0,50}\b(component|endpoint|needed|required)\b", text):
        found.append(("component", (min(component.start(), request.start()), max(component.end(), request.end()))))
    award = re.search(r"\b(award(?:ed|ing)?|grant(?:ed|ing)?|approve(?:d)?|issued?|applied|credit(?:ed)?|allow(?:ed)?)\b", text)
    values = list(re.finditer(r"(?:\busd\s*|\$\s*)([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)(?!\w|[.,][0-9])|\b([0-9]+(?:\.[0-9]+)?)\s*usd\b", text))
    # 'We deny the credit' is not an award. A request to send a credit is not
    # an assertion of issuance. A monetary assertion needs one explicit USD amount.
    if award and values:
        if not re.search(r"\b(service credit|credit|credit memo)\b", text) or re.search(r"[-−]\s*(?:usd|\$)|\b(?:usd|\$)\s*[-−]", text):
            return Proposal("unknown")
        if len(values) > 1:
            # A partial award may restate the requested amount. Recognize it only
            # when exactly one amount follows an affirmative grant, and every
            # other amount is explicitly labeled as the prior claim/fee basis.
            grant_values = []
            for value in values:
                preceding = text[max(0, value.start() - 90):value.start()]
                labels = list(re.finditer(r"\b(approved|awarded|granted|issued|credited|requested|claimed|invoice|charges|fees)\b", preceding))
                if not labels:
                    return Proposal("unknown")
                if labels[-1].group() in {"approved", "awarded", "granted", "issued", "credited"}:
                    grant_values.append(value)
            if len(grant_values) != 1:
                return Proposal("unknown")
            values = grant_values
        if (re.search(r"\b(if|could|may|would|might|pending|reversed|rescinded|withdrawn|cancell?ed|void|rejected|refused|disputed|limit|propos\w*|offer\w*|request|requesting|deny|denied|not|cannot|unable|no|never|up to|unless|instead|eur|cad|gbp)\b", text)
                or not re.search(r"\b(awarded|granted|approved|issued|credited|we (?:award|grant|approve|confirm)|(?:credit|award) (?:of|is|has been|for))\b", text)):
            return Proposal("unknown")
        value = values[0]
        amount = Decimal((value.group(1) or value.group(2)).replace(",", ""))
        if amount <= 0 or amount.as_tuple().exponent < -2 or amount >= Decimal("1e12"):
            return Proposal("unknown")
        found.append(("award", (min(award.start(), value.start()), max(award.end(), value.end()))))
        if len(found) == 1:
            return Proposal("award", found[0][1], format(amount, ".2f"))
    if len(found) != 1 or len(found) == 1 and found[0][0] == "award":
        return Proposal("unknown")
    reason, span = found[0]
    if reason == "maintenance" and re.search(r"\b(no|not|never|possibly|potential|unclear|unknown|unconfirmed)\b.{0,40}\bmaintenance\b", text):
        return Proposal("unknown")
    return Proposal(reason, span, artifact_type=artifact_type, reference=reference, scope_field=scope_field)
