"""Independent cent arithmetic, shared capacity, transactional and replay proofs."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, localcontext
from threading import Barrier
import sqlite3

from hypothesis import given, settings, strategies as st
import pytest

from uptime.allocations import (AllocationLedger, canonical, money, settlement_actions,
                                settlement_reconciliation, usd_cents)
from uptime.contracts import Principal
from uptime.storage import initialize, settlement_events, transition_settlement


SCOPE = dict(vendor_id="vendor", account_id="account", product_id="product",
             contract_id="contract", contract_version="2026-01", currency="USD")


def rows(suffix="1", amount=8000, **scope):
    base = dict(SCOPE, **scope)
    base.update(effective_date="2026-10-01", amount_cents=amount)
    award = dict(base, id="award-"+suffix, source_ref="award-source-"+suffix,
                 memo_ref="memo-"+suffix, confirmed=True, source="SIMULATED_VENDOR")
    credit = dict(base, id="credit-"+suffix, source_ref="credit-source-"+suffix,
                  memo_ref=award["memo_ref"], award_id=award["id"], source="DETERMINISTIC_REPLAY")
    return award, credit


def bill(amount=10000, eligible=None, **scope):
    return dict(SCOPE, **scope, id="shared-bill", source_ref="invoice-source-1",
                amount_cents=amount, eligible_cents=amount if eligible is None else eligible,
                effective_date="2026-11-01", source="SYNTHETIC_CUSTOMER")


def application(suffix="1", amount=8000, ident=None):
    ident = ident or "allocation-"+suffix
    return dict(id=ident, source_ref=ident, credit_id="credit-"+suffix, bill_id="shared-bill",
                amount_cents=amount, effective_date="2026-11-01", source="DETERMINISTIC_REPLAY")


def post(ledger, suffix="1", amount=8000, **scope):
    a, c = rows(suffix, amount, **scope)
    ledger.record_award("tenant", "case-"+suffix, a)
    ledger.record_credit("tenant", c)
    return a, c


def test_two_awards_cannot_allocate_160_dollars_to_one_100_dollar_bill(tmp_path):
    ledger = AllocationLedger(tmp_path / "allocation.db")
    post(ledger, "1")
    post(ledger, "2")
    ledger.record_bill("tenant", bill())
    ledger.apply("tenant", application("1"))
    history = ledger.history("tenant")
    with pytest.raises(ValueError, match="remaining eligible bill"):
        ledger.apply("tenant", application("2"))
    assert ledger.history("tenant") == history  # no failed-event residue
    ledger.apply("tenant", application("2", 2000))
    assert ledger.reconcile("tenant", "award-1")["applied"] == "80.00"
    assert ledger.reconcile("tenant", "award-2")["applied"] == "20.00"
    assert ledger.bill_balance("tenant", "shared-bill")["remaining_eligible_cents"] == 0
    assert ledger.reconcile("tenant", "award-1")["bill_balances"][0]["applied"] == "100.00"


def test_independent_connections_serialize_cross_award_capacity(tmp_path):
    path = tmp_path / "concurrent.db"
    ledger = AllocationLedger(path)
    post(ledger, "1")
    post(ledger, "2")
    ledger.record_bill("tenant", bill())
    workers = [AllocationLedger(path), AllocationLedger(path)]
    barrier = Barrier(2)

    def attempt(index):
        barrier.wait(timeout=10)
        try:
            workers[index].apply("tenant", application(str(index+1)))
            return "accepted"
        except ValueError as exc:
            assert "remaining eligible bill" in str(exc)
            return "refused"

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(attempt, range(2)))
    assert sorted(result) == ["accepted", "refused"]
    restarted = AllocationLedger(path)
    assert restarted.bill_balance("tenant", "shared-bill")["applied_cents"] == 8000
    assert sum(restarted.reconcile("tenant", "award-"+i)["applied_cents"] for i in ("1", "2")) == 8000


def test_concurrent_idempotent_delivery_has_one_application(tmp_path):
    path = tmp_path / "duplicates.db"
    ledger = AllocationLedger(path)
    post(ledger)
    ledger.record_bill("tenant", bill())
    workers = [AllocationLedger(path) for _ in range(8)]
    barrier = Barrier(8)

    def attempt(worker):
        barrier.wait(timeout=10)
        return worker.apply("tenant", application())

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(attempt, workers)) == ["allocation-1"]*8
    assert ledger.bill_balance("tenant", "shared-bill")["applied_cents"] == 8000
    assert len(ledger.reconcile("tenant", "award-1")["application_ids"]) == 1


@pytest.mark.parametrize("field,value", [
    ("account_id", "other-account"), ("product_id", "other-product"),
    ("contract_id", "other-contract"), ("contract_version", "older"),
    ("vendor_id", "other-vendor"), ("currency", "EUR"),
    ("effective_date", "2026-09-30"),
])
def test_foreign_or_predating_bill_cannot_consume_credit(tmp_path, field, value):
    ledger = AllocationLedger(tmp_path / "scoped.db")
    post(ledger)
    bad = {**bill(), field: value}
    with pytest.raises(ValueError):
        ledger.record_bill("tenant", bad)
        ledger.apply("tenant", application())
    assert ledger.reconcile("tenant", "award-1")["applied_cents"] == 0


def test_bill_total_and_eligible_outstanding_are_distinct(tmp_path):
    ledger = AllocationLedger(tmp_path / "eligible.db")
    post(ledger)
    ledger.record_bill("tenant", bill(amount=10000, eligible=1500))
    with pytest.raises(ValueError, match="remaining eligible bill"):
        ledger.apply("tenant", application(amount=1501))
    ledger.apply("tenant", application(amount=1500))
    assert ledger.bill_balance("tenant", "shared-bill")["total"] == "100.00"
    assert ledger.bill_balance("tenant", "shared-bill")["remaining_eligible"] == "0.00"


@pytest.mark.parametrize("mutation", [
    {"eligible_cents": 10001}, {"eligible_cents": -1}, {"eligible_cents": True},
    {"eligible_cents": 1.5}, {"eligible_cents": None}, {"amount_cents": 0},
    {"effective_date": "2026-02-30"}, {"account_id": None}, {"source_ref": None},
])
def test_unverified_bill_capacity_scope_and_date_fail_closed(tmp_path, mutation):
    ledger = AllocationLedger(tmp_path / "bad.db")
    with pytest.raises(ValueError):
        ledger.record_bill("tenant", {**bill(), **mutation})
    assert ledger.history("tenant") == []


def test_conflicting_duplicate_and_source_alias_cannot_double_count(tmp_path):
    ledger = AllocationLedger(tmp_path / "identity.db")
    award, credit = post(ledger)
    ledger.record_bill("tenant", bill())
    ledger.apply("tenant", application())
    # Equivalent normalized spellings replay exactly, including NFC scope IDs.
    ledger.record_award(" tenant ", " case-1 ", {**award, "id": " award-1 ", "currency": "usd"})
    ledger.apply("tenant", {**application(), "id": " allocation-1 "})
    for row in ({**application(), "amount_cents": 1}, {**application(), "id": "cloned"}):
        with pytest.raises(ValueError):
            ledger.apply("tenant", row)
    with pytest.raises(ValueError):
        ledger.record_credit("tenant", {**credit, "id": "cloned-credit"})
    with pytest.raises(ValueError):
        ledger.record_bill("tenant", {**bill(), "id": "cloned-bill"})
    with pytest.raises(ValueError):
        ledger.record_award("tenant", "other-case", {**award, "id": "cloned-award", "source_ref": "clone"})
    assert ledger.bill_balance("tenant", "shared-bill")["applied_cents"] == 8000


def test_memo_reuse_across_contract_or_product_is_not_a_new_award(tmp_path):
    ledger = AllocationLedger(tmp_path / "memo.db")
    a, _ = post(ledger)
    with pytest.raises(ValueError, match="memo identity"):
        ledger.record_award("tenant", "clone", dict(a, id="clone", source_ref="clone",
                                                    contract_id="other", product_id="other"))


def test_credit_cap_and_memo_match(tmp_path):
    ledger = AllocationLedger(tmp_path / "credit.db")
    a, c = rows(amount=100)
    ledger.record_award("tenant", "case-1", a)
    ledger.record_credit("tenant", {**c, "amount_cents": 80})
    with pytest.raises(ValueError, match="exceeds award"):
        ledger.record_credit("tenant", {**c, "id": "c2", "source_ref": "c2", "amount_cents": 21})
    with pytest.raises(ValueError, match="memo/scope/date"):
        ledger.record_credit("tenant", {**c, "id": "c2", "source_ref": "c2", "memo_ref": "wrong", "amount_cents": 20})
    ledger.record_credit("tenant", {**c, "id": "c2", "source_ref": "c2", "amount_cents": 20})
    assert ledger.reconcile("tenant", "award-1")["posted_cents"] == 100


def test_cross_tenant_and_application_scope_are_checked(tmp_path):
    ledger = AllocationLedger(tmp_path / "tenant.db")
    post(ledger)
    ledger.record_bill("tenant", bill())
    for tenant, patch in (("other", {}), ("tenant", {"tenant": "other"}),
                          ("tenant", {"account_id": "wrong"}), ("tenant", {"currency": "EUR"}),
                          ("tenant", {"effective_date": "2026-10-31"})):
        with pytest.raises(ValueError):
            ledger.apply(tenant, {**application(), **patch})
    with pytest.raises(KeyError):
        ledger.reconcile("other", "award-1")
    assert ledger.history("other") == []


def test_batch_rollback_leaves_no_partial_award_or_bill(tmp_path):
    ledger = AllocationLedger(tmp_path / "batch.db")
    a, c = rows()
    with pytest.raises(ValueError):
        ledger.ingest("tenant", "case-1", a, [c], [application(amount=8001)], [bill()])
    assert ledger.history("tenant") == []
    with pytest.raises(KeyError):
        ledger.bill_balance("tenant", "shared-bill")


def test_replay_at_sequence_and_restart_preserve_historical_totals(tmp_path):
    path = tmp_path / "history.db"
    ledger = AllocationLedger(path)
    post(ledger)
    ledger.record_bill("tenant", bill())
    ledger.apply("tenant", application(amount=3000))
    old = ledger.reconcile("tenant", "award-1")
    ledger.apply("tenant", application(amount=5000, ident="second"))
    restarted = AllocationLedger(path)
    assert restarted.reconcile("tenant", "award-1", as_of=old["as_of_sequence"]) == old
    assert restarted.reconcile("tenant", "award-1")["applied_cents"] == 8000
    assert restarted.bill_balance("tenant", "shared-bill", as_of=old["as_of_sequence"])["remaining_eligible_cents"] == 7000
    assert old["actual_recovery"] is None
    assert "LIVE_RAMP_SANDBOX" not in old["sources"]


@pytest.mark.parametrize("table", ["award", "credit", "bill", "application", "scope", "journal"])
def test_sql_history_is_immutable(tmp_path, table):
    path = tmp_path / "constraints.db"
    ledger = AllocationLedger(path)
    post(ledger)
    ledger.record_bill("tenant", bill())
    ledger.apply("tenant", application())
    with sqlite3.connect(path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute(f"DELETE FROM allocation_{table}")


def test_sql_direct_insert_cannot_bypass_aggregate_cap_or_zero_rule(tmp_path):
    path = tmp_path / "sql.db"
    ledger = AllocationLedger(path)
    post(ledger, "1")
    post(ledger, "2")
    ledger.record_bill("tenant", bill())
    ledger.apply("tenant", application("1"))
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        for amount in (8000, 0, -1):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute("""INSERT INTO allocation_application
                    SELECT tenant, 'direct', 'credit-2', bill_id, source, 'direct', ?, effective_date, sequence
                    FROM allocation_application LIMIT 1""", (amount,))
    assert ledger.bill_balance("tenant", "shared-bill")["applied_cents"] == 8000


def test_one_cent_goes_from_posted_to_full_apply_without_zero_partial(tmp_path):
    path = tmp_path / "cent.db"
    initialize(path)
    actor = Principal("tenant", "reviewer", "reviewer")
    transition_settlement(path, actor, "cent", "record-credit", "0.01")
    assert settlement_actions("POSTED", "0.01")[0]["id"] == "apply-balance"
    with pytest.raises(ValueError, match="positive cents"):
        transition_settlement(path, actor, "cent", "apply-partial", "0.01")
    transition_settlement(path, actor, "cent", "apply-balance", "0.01")
    transition_settlement(path, actor, "cent", "apply-balance", "0.01")
    result = settlement_reconciliation(path, "tenant", "cent", "0.01")
    assert result["applied_cents"] == 1
    assert result["stage"] == "APPLIED"
    assert len(result["application_ids"]) == 1
    assert len(settlement_events(path, "tenant", "cent")) == 2
    assert result["origins"] == ["INTAKE"]


def test_legacy_migration_keeps_original_history_and_explicit_simulation_origin(tmp_path):
    path = tmp_path / "legacy.db"
    # Independently construct the old schema, without V4 initializer behavior.
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE settlement_event (sequence INTEGER PRIMARY KEY, tenant TEXT,
            case_id TEXT, action TEXT, stage TEXT, actor TEXT, awarded TEXT, at TEXT,
            UNIQUE(tenant,case_id,action))""")
        for i, (action, stage) in enumerate((("record-credit", "POSTED"), ("apply-partial", "PARTIALLY_APPLIED"), ("apply-balance", "APPLIED")), 1):
            db.execute("INSERT INTO settlement_event VALUES(?,?,?,?,?,?,?,?)",
                       (i, "tenant", "cent", action, stage, "legacy-reviewer", "0.01", "2026-10-01T00:00:00+00:00"))
        original = db.execute("SELECT * FROM settlement_event").fetchall()
    ledger = AllocationLedger(path)
    result = ledger.reconcile("tenant", "sim:cent:award")
    assert result["applied_cents"] == 1
    assert result["origins"] == ["LEGACY_STAGE_PROJECTION"]
    assert len(result["application_ids"]) == 1
    assert result["actual_recovery"] is None
    assert "LIVE_RAMP_SANDBOX" not in result["sources"]
    AllocationLedger(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT * FROM settlement_event").fetchall() == original
        assert db.execute("SELECT COUNT(*) FROM allocation_legacy").fetchone()[0] == 3
    assert ledger.history("tenant") == AllocationLedger(path).history("tenant")


def native_records():
    vendor = "ada00000-0000-4000-8000-000000000001"
    credit_id = "ada00000-0000-4000-8000-000000000002"
    bill_id = "ada00000-0000-4000-8000-000000000003"
    a, c = rows(amount=10000, vendor_id=vendor)
    c.update(id=credit_id, source_ref=credit_id, source="LIVE_RAMP_SANDBOX")
    b = bill(vendor_id=vendor)
    b.update(id=bill_id, source_ref=bill_id, source="LIVE_RAMP_SANDBOX")
    obs = dict(id="receipt-1", credit_id=credit_id, bill_id=bill_id, source_ref=f"ramp:{credit_id}:{bill_id}",
               source="LIVE_RAMP_SANDBOX", amount_cents=4000, observed_at="2026-11-01T10:00:00Z", effective_date="2026-11-01")
    return a, c, b, obs


def test_provider_pair_cumulative_observations_are_not_incremental_events(tmp_path):
    ledger = AllocationLedger(tmp_path / "cumulative.db")
    a, c, b, obs = native_records()
    ledger.ingest("tenant", "case", a, [c], bills=[b])
    with pytest.raises(ValueError, match="cumulative"):
        ledger.apply("tenant", obs)
    ledger.observe_application("tenant", obs)
    first = ledger.reconcile("tenant", a["id"])
    # The credit GET and bill GET observe the same cumulative use; never add twice.
    ledger.observe_application("tenant", obs)
    ledger.observe_application("tenant", {**obs, "id": "bill-get"})
    ledger.observe_application("tenant", {**obs, "id": "offset-alias", "observed_at": "2026-11-01T02:00:00-08:00"})
    assert ledger.reconcile("tenant", a["id"])["applied_cents"] == 4000
    ledger.observe_application("tenant", {**obs, "id": "later", "amount_cents": 6000, "observed_at": "2026-11-01T11:00:00Z"})
    ledger.observe_application("tenant", {**obs, "id": "stale", "amount_cents": 2000, "observed_at": "2026-11-01T09:00:00Z"})
    result = ledger.reconcile("tenant", a["id"])
    assert result["applied_cents"] == 6000
    assert len(result["application_ids"]) == 2
    assert result["stage_sources"]["applied"] == ["LIVE_RAMP_SANDBOX"]
    assert result["actual_recovery"] is None
    assert ledger.reconcile("tenant", a["id"], as_of=first["as_of_sequence"]) == first
    for change in ({"amount_cents": 5000}, {"id": "conflict", "amount_cents": 1},
                   {"id": "decrease", "amount_cents": 5000, "observed_at": "2026-11-01T12:00:00Z"},
                   {"id": "future-over", "amount_cents": 10001, "observed_at": "2026-11-01T12:00:00Z"}):
        with pytest.raises(ValueError):
            ledger.observe_application("tenant", {**obs, **change})


@given(st.integers(min_value=0, max_value=10**15))
def test_usd_cents_is_exact_under_arbitrary_decimal_context(amount):
    with localcontext() as ctx:
        ctx.prec = 2
        assert usd_cents(money(amount)) == amount
        assert usd_cents(Decimal(money(amount))) == amount


@given(st.lists(st.integers(min_value=1, max_value=10000), min_size=1, max_size=20),
       st.integers(min_value=1, max_value=20000))
@settings(max_examples=50, deadline=None)
def test_generated_shared_bill_sequences_obey_independent_integer_oracle(amounts, capacity):
    # Each example gets a real independent SQLite database. No fake DB or mocks.
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as directory:
        ledger = AllocationLedger(Path(directory) / "property.db")
        ledger.record_bill("tenant", bill(capacity))
        expected = 0
        for index, amount in enumerate(amounts):
            suffix = str(index)
            post(ledger, suffix, amount)
            app = application(suffix, amount)
            if expected + amount <= capacity:
                ledger.apply("tenant", app)
                ledger.apply("tenant", app)  # replay must be exactly idempotent
                expected += amount
            else:
                with pytest.raises(ValueError):
                    ledger.apply("tenant", app)
            state = ledger.bill_balance("tenant", "shared-bill")
            assert state["applied_cents"] == expected
            assert state["remaining_eligible_cents"] == capacity - expected
        restarted = AllocationLedger(ledger.path)
        assert sum(restarted.reconcile("tenant", "award-"+str(i))["applied_cents"] for i in range(len(amounts))) == expected


def test_bill_cannot_predate_posted_credit_even_after_award(tmp_path):
    ledger = AllocationLedger(tmp_path / "credit-date.db")
    a, c = rows()
    ledger.record_award("tenant", "case-1", a)
    ledger.record_credit("tenant", {**c, "effective_date": "2026-11-02"})
    ledger.record_bill("tenant", bill())
    with pytest.raises(ValueError, match="predating bill"):
        ledger.apply("tenant", {**application(), "effective_date": "2026-11-03"})


def test_zero_and_stale_observations_do_not_bypass_scope_or_date_validation(tmp_path):
    ledger = AllocationLedger(tmp_path / "observation.db")
    a, c, b, obs = native_records()
    ledger.ingest("tenant", "case", a, [c], bills=[b])
    ledger.observe_application("tenant", obs)
    for patch in ({"amount_cents": 0, "effective_date": "2026-10-31"},
                  {"account_id": "wrong"}, {"effective_date": "2026-11-02"}):
        with pytest.raises(ValueError):
            ledger.observe_application("tenant", {**obs, "id": "new", **patch})
    assert ledger.bill_balance("tenant", b["id"])["applied_cents"] == 4000


def test_malformed_legacy_stage_history_rolls_back_additive_migration(tmp_path):
    path = tmp_path / "corrupt-legacy.db"
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE settlement_event (sequence INTEGER PRIMARY KEY, tenant TEXT,
            case_id TEXT, action TEXT, stage TEXT, actor TEXT, awarded TEXT, at TEXT)""")
        db.execute("INSERT INTO settlement_event VALUES(1,'tenant','bad','apply-balance','APPLIED','reviewer','1','2026-11-01T00:00:00Z')")
    with pytest.raises(ValueError, match="Inconsistent legacy"):
        AllocationLedger(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM settlement_event").fetchone()[0] == 1
        assert db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'allocation_%'").fetchall() == []


def test_legacy_projection_uses_recorded_dates_and_preserves_stage_checkpoint(tmp_path):
    path = tmp_path / "legacy-partial.db"
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE settlement_event (sequence INTEGER PRIMARY KEY, tenant TEXT,
            case_id TEXT, action TEXT, stage TEXT, actor TEXT, awarded TEXT, at TEXT)""")
        db.executemany("INSERT INTO settlement_event VALUES(?,?,?,?,?,?,?,?)", [
            (1, "tenant", "demo", "record-credit", "POSTED", "reviewer", "10.09", "2026-10-30T23:00:00-07:00"),
            (2, "tenant", "demo", "apply-partial", "PARTIALLY_APPLIED", "reviewer", "10.09", "2026-11-01T00:00:00Z"),
        ])
    ledger = AllocationLedger(path)
    result = ledger.reconcile("tenant", "sim:demo:award")
    assert result["applied"] == "5.04"
    with sqlite3.connect(path) as db:
        checkpoint = db.execute("SELECT journal_sequence FROM allocation_legacy WHERE settlement_sequence=1").fetchone()[0]
        assert db.execute("SELECT effective_date FROM allocation_credit").fetchone()[0] == "2026-10-31"
        assert db.execute("SELECT effective_date FROM allocation_bill").fetchone()[0] == "2026-11-01"
    assert ledger.reconcile("tenant", "sim:demo:award", as_of=checkpoint)["applied"] == "0.00"


def test_positive_application_and_exact_compatibility_reconciliation():
    from uptime.reconciliation import demo_reconciliation, reconcile
    from test_reconciliation import records
    a, c, x, b = records()
    with pytest.raises(ValueError, match="positive"):
        reconcile("one", a, [c], [{**x, "amount": "0.00"}], [b])
    with pytest.raises(ValueError, match="positive"):
        demo_reconciliation("0.01", "PARTIALLY_APPLIED")
    assert demo_reconciliation("0.01", "APPLIED")["applied"] == "0.01"
    with localcontext() as context:
        context.prec = 2
        assert reconcile("one", a, [c], [x], [b])["applied"] == "10.25"
        assert demo_reconciliation("10.09", "PARTIALLY_APPLIED")["applied"] == "5.04"


@given(st.integers(min_value=1, max_value=100000), st.integers(min_value=1, max_value=99))
def test_fractional_cent_amounts_are_never_rounded_into_settlement(whole_cents, fraction):
    with pytest.raises(ValueError, match="whole cents"):
        usd_cents(f"{whole_cents // 100}.{whole_cents % 100:02d}{fraction:02d}")


def test_bill_source_label_alias_cannot_create_a_second_fixture_balance(tmp_path):
    ledger = AllocationLedger(tmp_path / "source-alias.db")
    ledger.record_bill("tenant", bill())
    with pytest.raises(ValueError):
        ledger.record_bill("tenant", {**bill(), "id": "replay-alias", "source": "DETERMINISTIC_REPLAY"})


def test_normal_workbench_actions_write_persistent_allocations(tmp_path):
    from uptime.workbench import Workbench
    path = tmp_path / "workbench.db"
    bench = Workbench(path, "replay")
    principal = Principal("bears", "reviewer", "reviewer")
    for action in ("approve-claim", "submit-claim", "record-credit", "apply-partial", "apply-balance"):
        case = bench.act(principal, "dispute-partial", action)
    ledger = AllocationLedger(path)
    result = ledger.reconcile("bears", "sim:dispute-partial:award")
    assert result["applied"] == case["ledger"]["applied"] == "80.00"
    assert len(result["application_ids"]) == 2
    assert result["bill_balances"][0]["remaining_eligible_cents"] == 0
    Workbench(path, "replay")
    assert ledger.reconcile("bears", "sim:dispute-partial:award") == result


@given(st.lists(st.integers(min_value=1, max_value=1000), min_size=2, max_size=5),
       st.integers(min_value=1, max_value=3000))
@settings(max_examples=20, deadline=None)
def test_generated_concurrent_independent_writers_never_overallocate(amounts, capacity):
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "concurrent-property.db"
        ledger = AllocationLedger(path)
        ledger.record_bill("tenant", bill(capacity))
        workers = []
        for index, amount in enumerate(amounts):
            post(ledger, str(index), amount)
            workers.append(AllocationLedger(path))
        barrier = Barrier(len(workers))

        def attempt(index):
            barrier.wait(timeout=10)
            try:
                workers[index].apply("tenant", application(str(index), amounts[index]))
                return amounts[index]
            except ValueError as exc:
                assert "remaining eligible bill" in str(exc)
                return 0

        with ThreadPoolExecutor(max_workers=len(workers)) as pool:
            accepted = list(pool.map(attempt, range(len(workers))))
        used = sum(accepted)
        assert 0 <= used <= capacity
        assert ledger.bill_balance("tenant", "shared-bill")["applied_cents"] == used
        assert [ledger.reconcile("tenant", "award-"+str(i))["applied_cents"] for i in range(len(workers))] == accepted
        for amount, applied in zip(amounts, accepted):
            if not applied:
                assert amount > capacity-used


def test_first_class_bill_intake_exposes_shared_scope_and_balances(tmp_path):
    ledger = AllocationLedger(tmp_path / "intake.db")
    ledger.record_bill("tenant", bill())
    assert ledger.list_bills("other") == []
    assert ledger.list_bills("tenant")[0]["scope"]["account_id"] == "account"
    assert ledger.list_bills("tenant")[0]["remaining_eligible_cents"] == 10000
    post(ledger, "1")
    post(ledger, "2")
    ledger.apply("tenant", application("1", 8000))
    ledger.apply("tenant", application("2", 2000))
    assert len(ledger.list_awards("tenant")) == 2
    assert [row["award_id"] for row in ledger.list_awards("tenant", case_id="case-2")] == ["award-2"]
    assert ledger.list_bills("tenant")[0]["remaining_eligible_cents"] == 0


def test_compatibility_reconciliation_respects_supplied_eligible_capacity():
    from uptime.reconciliation import reconcile
    from test_reconciliation import records
    a, c, x, b = records()
    with pytest.raises(ValueError, match="exceeds"):
        reconcile("one", a, [c], [x], [{**b, "eligible_cents": 1000}])
