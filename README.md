# Uptime for Ramp

Uptime checks unpaid invoices against negotiated terms, tests SLA credit eligibility, prepares and disputes simulated claims, and reconciles awards through bill application. It runs locally as a finance workbench with a persistent case ledger.

**The live sandbox evidence is read-only.** Ramp returned six bills. Uptime read a pending USD 840.00 bill and a paid USD 481.28 bill back by their actual IDs. The token lacked `bills:write`. Neither verified line had a quantity, rate, SKU or service date. Uptime displays the bill and the missing evidence instead of assigning it a discrepancy.

**The demonstration has two distinct financial results.** A synthetic invoice shows a USD 7,500 prepayment discrepancy. A separate simulated Twilio case earns a USD 100 service credit and can apply USD 50 to a fixture bill. There is no verified customer recovery, actual prevented payment, or live credit application.

## Run the workbench

From this checkout, with Python 3.11+ and `uv` installed:

```sh
uv sync --locked
uv run --locked python scripts/serve.py --mode sandbox --open
```

On macOS, double-click **Open Uptime.command** instead. Sandbox mode displays the last verified observations, with their collection time. Use `--mode replay` for an entirely offline synthetic workspace. Use a separate database for a fresh rehearsal, for example `--db runtime/rehearsal-01.sqlite`. The server binds to loopback and the launcher opens an authenticated local reviewer session. Close with Ctrl-C.

## Demonstrate it

1. Open **Case ledger → price-prepayment**. The amendment prices 1,500 units at USD 20,000. The covered line billed USD 27,500. Review the separate paid-invoice comparison and missing-evidence examples.
2. Compare **sla-eligible** with **sla-ineligible**. The eligible basis excludes tax, carrier and unrelated charges. Public status observations alone cannot fill missing fee lines.
3. In **dispute-cure**, approve and submit to the simulator. Prepare the requested supplement, approve it and advance the replay cooldown if prompted. The simulator adjudicates the new evidence. Record the simulated credit and apply part of it. The award, posting, application and remainder have distinct IDs and amounts.
4. Inspect **dispute-denial**, **dispute-review** and **dispute-partial**. The workbench stops on corroborated maintenance, escalates uncertain notice timing and retains the contested remainder of a partial award.
5. Open **Onboarding lab**. The generated Atlassian candidate begins in shadow. Review its source clauses, tenant overlay, generated tests and independent gold results. A reviewer can approve and activate it locally, then roll it back. The delivered workspace contains no preapproved version.
6. In **Integrations**, inspect the exact sandbox observation and its readback IDs. The canonical provider UI requires a separate Ramp login. The public incident feed, model extraction and simulated transport each have their own source labels.

The two-minute captioned film and stills are under `docs/demo/film/`. All approvals in the film belong to a disposable scripted test reviewer. Use the [runbook](docs/orchestration/RUNBOOK.md) for the release gate, capture and deployment commands.

## Engineering record

- [Architecture and boundaries](docs/ARCHITECTURE.md)
- [Live, synthetic, replay and unavailable capability matrix](docs/orchestration/CAPABILITY_MATRIX.md)
- [Checkpoint evidence](docs/orchestration/STATUS.md) and [workstream ownership](docs/orchestration/TASKS.md)
- [Decision records and actual Opus review responses](docs/orchestration/DECISIONS_INDEX.md)
- [Open blockers and production limits](docs/orchestration/BLOCKERS.md)
- [Original V3 specification and handoff](docs/uptime-v3/)
