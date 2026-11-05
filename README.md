# Uptime for Ramp

Uptime adds contract evidence to the Ramp records an accounts-payable reviewer already uses. Open a bill to inspect its approval state, associated records, governing terms and any amount the evidence supports. Use the companion for evidence inspection, vendor onboarding, disputes and the audit trail. Ramp remains the financial system of record.

**Start the application** on macOS with `./Open\ Uptime.command`. The launcher opens a local reader account and prints the location of the private sign-in file. For a fresh sandbox sync, command-line setup or restarting an existing installation, follow the [operator guide](docs/v4/OPERATIONS.md).

**Open the engineering progress dashboard** by running `python3 scripts/serve_progress.py` from the repository, then visiting [localhost:8780](http://127.0.0.1:8780/). The Ramp-themed dependency graph shows completed work, current work, blockers, owners and evidence links. Select a task to see its prerequisites and downstream dependencies. Filters, search, a task list and an expanded graph support closer inspection. Its timestamped snapshot lives in `progress/data.json`. Refresh reloads that file. Maintainers update it after verifying changes.

**Watch the two-minute demonstration** from the [film](docs/demo/v4/walkthrough.mp4) or follow the [spoken script](docs/v4/DEMO.md). Its real sandbox capture contains six bills, twelve vendor records, twelve card transactions and twelve purchase orders. Eleven approval observations add context. Vendor, card, purchase-order and approval lists are sampled. The agreement and vendor-credit lists returned zero rows.

The demonstration follows the same open, approval-pending **$840 Ramp bill** into its evidence. There is no signed customer contract for that bill. A separately labeled constructed $800 cap produces a $40 hypothetical discrepancy. Nothing was stopped, paid or recovered in that example. Both the invoice and the amount remain traceable to their different sources.

## What you can verify

- **Read the finance records.** Refresh a tenant-bound sandbox installation using first-party OAuth, then inspect resource completeness, actual native references and case history. [Supported Ramp interfaces](docs/v4/RAMP-FEASIBILITY.md)
- **Evaluate a real bill when terms exist.** Install a signed, documented agreement-to-line binding. An unbound line returns missing evidence. The operator can revoke a package or verifier. [Price evidence procedure](docs/v4/RAMP-PRICE-EVIDENCE.md)
- **Review a finding in a native workflow.** Uptime prepares a redacted exact-object bill discussion, requires independent authorization and verifies delivery against the same thread. Current credentials lack the write grant. Blank Canvas requires a separately configured procurement trigger. [Native workflow](docs/v4/NATIVE-OPERATOR.md)
- **Follow a claim through credit application.** Estimated, filed, awarded, posted and applied amounts carry independent references. Completed sandbox reads found no native credits. [Credit synchronization](docs/v4/RAMP-CREDIT-SYNC.md) · [Award attribution](docs/v4/RAMP-ATTRIBUTION.md)
- **Inspect the acceptance evidence.** Before/after audit vectors, independent holdouts and the full regression suite answer different questions. The current release status records each individually. [Acceptance and remaining gaps](docs/v4/STATUS.md) · [Capability matrix](docs/v4/CAPABILITIES.md)

[Architecture](docs/v4/ARCHITECTURE.md) · [Decision records](docs/v4/decisions/INDEX.md) · [Original V3 specification](docs/uptime-v3/Uptime_V3_Product_Technical_Spec.md)
