"""Bounded proposals from untrusted text. Only the desk can authorize or book anything."""
import re
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class Proposal:
    reason: str
    span: tuple[int, int] | None = None
    amount: str | None = None


# Each cue needs both a subject and a predicate. Ambiguous compound replies,
# imperatives about system behavior, conditional offers and unsupported units
# cannot authorize a follow-up or a financial entry.
def propose(text: str) -> Proposal:
    text = text.casefold()
    if re.search(r"\b(ignore|override|execute|credentials?|password|secret|token|system prompt|wire transfer|instructions?|disregard|hypothetical|hypothetically)\b|[<>{}]|https?://", text):
        return Proposal("unknown")
    reasons = {
        "maintenance": r"\b(maintenance|planned (?:work|downtime)|scheduled (?:work|downtime))\b",
        "time_bar": r"\b(too late|out of time|time.barred|untimely|late (?:submission|filing|claim)|missed (?:the |our )?(?:deadline|window)|(?:deadline|window|period) (?:has |had |was )?(?:closed|elapsed|expired|passed)|(?:after|outside|beyond) (?:the |our )?(?:filing |submission |claim |30.day )?(?:deadline|window|period)|(?:submitted|received|filed) late)\b",
    }
    found = [(reason, m.span()) for reason, pattern in reasons.items() if (m := re.search(pattern, text))]
    component = re.search(r"\b(component|endpoint|service identifier|affected api|service id)\b", text)
    request = re.search(r"\b(need(?:ed)?|missing|lack(?:s|ing)?|provide|send|supply|attach|require(?:s|d)?|identify|confirm|cannot verify|unable to verify|which|without|does not (?:identify|show)|did not (?:identify|include))\b", text)
    if component and request:
        found.append(("component", (min(component.start(), request.start()), max(component.end(), request.end()))))
    award = re.search(r"\b(award(?:ed|ing)?|grant(?:ed|ing)?|approve(?:d)?|issued?|applied|credit(?:ed)?|allow(?:ed)?)\b", text)
    values = list(re.finditer(r"(?:\busd\s*|\$\s*)([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)(?!\w|[.,][0-9])|\b([0-9]+(?:\.[0-9]+)?)\s*usd\b", text))
    # 'We deny the credit' is not an award. A request to send a credit is not
    # an assertion of issuance. A monetary assertion needs one explicit USD amount.
    if award and values:
        if (len(values) != 1 or re.search(r"\b(if|could|may|would|might|pending|propos\w*|offer\w*|request\w*|deny|denied|not|cannot|unable|no|never|up to|unless|instead|eur|cad|gbp)\b", text)
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
    return Proposal(reason, span)
