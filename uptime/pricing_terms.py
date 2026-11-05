"""Complete-source grammar for an explicit fixed, one-unit monthly rate schedule.

This is a bounded typed contractual operator, not a free-prose legal parser.
The entire schedule is consumed; unknown/conditional neighboring text refuses.
"""
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import re

from .contracts import Citation

FIXED = re.compile(r'For (?P<product>[A-Za-z0-9][A-Za-z0-9 &(),_.+/-]{0,99}), the fixed fee for exactly one subscription unit for each complete UTC calendar month is USD (?P<fee>(?:0|[1-9][0-9]{0,11})\.[0-9]{2})\. Invoice quantity must equal one; taxes are separate and excluded\.')


@dataclass(frozen=True)
class FixedMonthlyTerms:
    source_text: str
    source_sha256: str
    citation: Citation
    product: str
    monthly_fee: Decimal
    quantity: Decimal
    start: int
    end: int
    quote: str


def compile_fixed_monthly(source_text, citation):
    if (not isinstance(source_text,str) or len(source_text)>50000 or not isinstance(citation,Citation)
            or any(not isinstance(x,str) or not x.strip() for x in (citation.document,citation.version,citation.section,citation.uri))):
        raise ValueError('A complete fixed-month schedule and exact version citation are required.')
    quote=source_text.strip()
    match=FIXED.fullmatch(quote)
    if not match:
        raise ValueError('Unsupported fixed-month schedule; every source clause must be accounted for.')
    start=source_text.index(quote)
    return FixedMonthlyTerms(source_text,sha256(source_text.encode()).hexdigest(),citation,match['product'],
                             Decimal(match['fee']),Decimal(1),start,start+len(quote),quote)


def validate_fixed_monthly(terms, *, product, version, rate):
    if type(terms) is not FixedMonthlyTerms:
        raise ValueError('Source-backed fixed monthly quantity is required.')
    parsed=compile_fixed_monthly(terms.source_text,terms.citation)
    if parsed!=terms or (terms.product,terms.citation.version,terms.monthly_fee)!=(product,version,rate):
        raise ValueError('Fixed-month source, span, version or rate does not match typed terms.')
    return terms
