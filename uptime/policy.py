from decimal import Decimal, InvalidOperation
from .storage import database, now

MODES = ("OBSERVE","ASSISTED","POLICY_AUTOMATED")


def setup(path):
    with database(path) as db, db:
        db.execute("""CREATE TABLE IF NOT EXISTS policy_revision (
            id INTEGER PRIMARY KEY, tenant TEXT NOT NULL, mode TEXT NOT NULL, cap TEXT NOT NULL,
            actor TEXT NOT NULL, at TEXT NOT NULL)""")


def policy(path, principal):
    with database(path) as db:
        rows=[dict(r) for r in db.execute("SELECT mode,cap,actor,at FROM policy_revision WHERE tenant=? ORDER BY id DESC",
                                           (principal.tenant,))]
    current=rows[0] if rows else {"mode":"ASSISTED","cap":"0.00"}
    return dict(mode=current["mode"],cap=current["cap"],role=principal.role,can_configure=principal.role=="reviewer",
                available_modes=list(MODES), history=rows, sources=["DETERMINISTIC_REPLAY"],
                scope="One separately approved, complete initial simulator claim only. No real outward communications.",
                reviewer_controls="Adapter promotion, rebuttals and simulated credit entries require explicit human action.")


def configure(path, principal, mode, cap):
    if principal.role != "reviewer":
        raise PermissionError("A reviewer session is required")
    if mode not in MODES or not isinstance(cap,str) or len(cap)>12:
        raise ValueError("Unknown mode or invalid USD cap")
    try:
        amount=Decimal(cap)
    except InvalidOperation as e:
        raise ValueError("USD cap must be decimal") from e
    if not amount.is_finite() or amount < 0 or amount > 10000 or amount.as_tuple().exponent < -2:
        raise ValueError("USD cap must be between 0 and 10,000 with cent precision")
    if mode=="POLICY_AUTOMATED" and not amount:
        raise ValueError("Automated simulation requires an explicit positive cap")
    with database(path) as db, db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT INTO policy_revision(tenant,mode,cap,actor,at) VALUES (?,?,?,?,?)",
                   (principal.tenant,mode,f"{amount:.2f}",principal.subject,now()))
    return policy(path,principal)


def dispatch_allowed(case, setting):
    if setting["mode"] != "POLICY_AUTOMATED" or case.get("policy_dispatchable") is not True:
        return False
    if "submit-claim" not in [a["id"] for a in case["actions"]]:
        return False
    amount=Decimal(case["ledger"]["estimated"])
    return amount.is_finite() and 0 < amount <= Decimal(setting["cap"])
