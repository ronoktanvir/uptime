"""D03-A residual on the legacy Twilio dispute route: the account is source-identity/1."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from uptime.disputes_claimant import ticket_for
from uptime.disputes_vendor import decide
from uptime.disputes_wire import FIXTURES, Ticket

DOSSIERS = json.loads((FIXTURES / "claimant" / "dossiers.json").read_text())
RECORDS = json.loads((FIXTURES / "simulator" / "records.json").read_text())
REFUSED = ["acct—east", " acct", "acct ", "acct  east", "acct​east", "éclair", "", "x" * 97, "!!!"]


def first_case():
    case_id = next(iter(DOSSIERS))
    return deepcopy(DOSSIERS[case_id])


def test_legacy_fixture_accounts_are_inside_the_domain_and_digests_unchanged():
    for dossier in DOSSIERS.values():
        ticket = ticket_for(dossier["tenant"], dossier, [])
        assert ticket.account == dossier["account"]
        assert Ticket(**{f: getattr(ticket, f) for f in ticket.__dataclass_fields__}).digest == ticket.digest


@pytest.mark.parametrize("account", REFUSED)
def test_out_of_domain_account_is_refused_not_rewritten(account):
    dossier = first_case()
    dossier["account"] = account
    with pytest.raises(ValueError):
        ticket_for(dossier["tenant"], dossier, [])
    ticket = ticket_for(first_case()["tenant"], first_case(), [])
    with pytest.raises(ValueError, match="never rewritten"):
        replace(ticket, account=account)


def test_counterparty_contests_an_identity_outside_the_domain():
    dossier = first_case()
    ticket = ticket_for(dossier["tenant"], dossier, [])
    record = dict(RECORDS[ticket.account])
    forged = object.__new__(Ticket)
    for name in ticket.__dataclass_fields__:
        object.__setattr__(forged, name, getattr(ticket, name))
    object.__setattr__(forged, "account", ticket.account + "—")
    record["account"] = forged.account
    from datetime import UTC, datetime
    assert decide(forged, record, datetime(2026, 11, 3, tzinfo=UTC)).code == "CONTESTED_SCOPE"


def test_spaces_and_punctuation_inside_the_domain_are_accepted_exactly():
    dossier = first_case()
    ticket = ticket_for(dossier["tenant"], dossier, [])
    assert replace(ticket, account="Cedar Orrery Studio").account == "Cedar Orrery Studio"


@pytest.mark.parametrize("field", ["vendor", "product"])
@pytest.mark.parametrize("value", ["Twilio\u2014Messaging", "Twilio  Messaging API", "Twilio\u200bMessaging", " Twilio"])
def test_vendor_and_service_names_follow_the_same_exact_source_rule(field, value):
    ticket = ticket_for(first_case()["tenant"], first_case(), [])
    with pytest.raises(ValueError, match="never rewritten"):
        replace(ticket, **{field: value})


def test_out_of_domain_service_name_is_unsupported_for_the_claimant():
    from datetime import UTC, datetime
    from uptime.contracts import Outcome
    from uptime.disputes_claimant import preflight
    dossier = first_case()
    dossier["product"] = "Twilio\u2014Messaging API"
    # The legacy profile already requires the exact covered service name.
    assert preflight(dossier, datetime(2026, 11, 3, tzinfo=UTC)).outcome == Outcome.UNSUPPORTED
