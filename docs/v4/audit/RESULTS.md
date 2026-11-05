# Durable independent audit results

Release remains blocked: the stable main integration passes all 116 executed observations, but both required real-browser observations are UNAVAILABLE. The baseline browser observations are also unavailable, so `baseline_verified` and `release_pass` remain false.

| Run | Source commit | PASS | FAIL | UNAVAILABLE | Exit |
|---|---|---:|---:|---:|---:|
| [baseline-v2](baseline-v2.json) | `18afaa6433284dc582d38c02b797dc4e688892f1` | 73 | 43 | 2 | 2 |
| [release-v2](release-v2.json) | `69809ff91033d3fba3853a8bf15a941af1700e61` | 110 | 6 | 2 | 1 |
| [main-release-v2](main-release-v2.json) | `dc0929957075d0f7392283a705b876c28cd343d8` | 116 | 0 | 2 | 1 |

Driver implementation commit: `69809ff91033d3fba3853a8bf15a941af1700e61`. [Driver verification](pytest-v2.log): **177 passed**, one Starlette/httpx deprecation warning, exit 0. No candidate application edits, oracle changes or merge occurred in this worktree. The repository-wide post-merge test remains the integration owner’s responsibility.

Main integration product SHA-256: `a6415ca4ab9e42ce1cb83c5d6a2a2925b56850827efd63992019bbf01fbfa5d4`. Its tracked tree was clean and its source/driver stability checks passed. Recorded at `2026-11-05T00:33:40.348489+00:00`. This is bounded coverage of the actual mounted app and audited vectors, not a claim to have tested every new feature or any live provider transport.

An earlier main run changed during execution. [That artifact](main-release-v2-raced.json) remains preserved with `source_stable: false` and `release_pass: false`; its passing observation count cannot certify a particular revision.

The durable assigned checkout retains six real product failures in its report. The same assertions pass on the later main integration except for browser observations that have not executed here:

- `A-prevention-paid-title`: observed `["price-000-audit", "$9,123.45"]`; required `["price-prepayment", "$7,500.00"]`.
- `A-billing-profile-intent`: observed `true`; required `false`.
- `A-guide-ui-api-limit`: observed `422`; required `200`.
- `A-provider-line-preserves-known-facts`: observed `true`; required `false`.
- `A-null-bill-status-resilience`: observed `false`; required `true`.
- `J-zero-fee-not-claimable`: observed `true`; required `false`.

Both `W-browser-sibling-origin` and `A-ui-financial-join-ids` stop at real `socket.bind` with `PermissionError`. System Chrome is installed, but it was not launched because listener creation failed. No skip, substitute browser or TestClient result counts as browser evidence.

Runtime: Python 3.13.12; system Chrome 156.0.8078.80. Package versions: fastapi 0.162.0, starlette 1.10.0, httpx 0.28.1, uvicorn 0.54.0, playwright 1.64.1, cryptography 46.0.7.

Root must run both browser-enabled phases outside the nested sandbox using the exact commands in [QA-design.md](../QA-design.md). Keep the driver unchanged between phases and use fresh report filenames. A release report must have `source_stable`, `driver_stable`, `baseline_verified` and `release_pass` all true before treating the gate as passed.

[execution-v2.json](execution-v2.json) records actual commands, exit codes and report hashes. Each JSON report independently embeds source, fixture, driver and runtime provenance. The original v1 reports are retained unchanged as prior evidence.

No blind holdout, live remote API, external model, customer file, private saved capture or existing credential was opened. All enrolled keys and operational state were disposable synthetic fixtures.
