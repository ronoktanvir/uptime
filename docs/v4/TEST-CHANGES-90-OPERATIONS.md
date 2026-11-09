# Workstream 90 operations test ledger

**No existing test function, fixture or assertion was changed.** All new controls are in `tests/test_operations_recovery_90.py`: 19 functions and 23 cases, two of them parametrized three ways.

| New test | What it falsifies |
| --- | --- |
| `test_backup_restore_restart_preserves_authority_and_financial_state` | After restore and restart, financial tables, settlement reconciliation, case revisions, dashboard and Ramp views are identical (except the wall-clock evaluation instant), the enrolled key signs in, the old session is rejected, unused mandates are fenced, and another tenant or mode is refused |
| `test_restore_carries_forward_later_revocations_and_never_overwrites` | A revocation made after the backup is lost without `previous` and carried with it; no overwrite; wrong tenant or mode; foreign previous database; repository paths |
| `test_tampered_or_exposed_backup_is_refused` [database, manifest, permissions] | Altered database, altered manifest and group-readable copy are all refused, with no partial target left behind |
| `test_backup_contains_no_credentials_or_session_material` | No reviewer private scalar, bearer session token or credential field names in backup bytes |
| `test_installation_revocation_survives_restart_and_restore_and_stays_tenant_scoped` | Import and native preparation refuse after restart and after restoring a pre-revocation backup; history stays readable; another tenant is unaffected; the workspace event is immutable |
| `test_revoked_refresh_makes_no_provider_request` | Refresh refuses before any provider attribute is touched |
| `test_unsafe_revocation_store_fails_closed` [mode, foreign-record, malformed] | An unsafe store refuses access and the health check reports it |
| `test_health_report_separates_retryable_reads_from_uncertain_effects` | Read-only (byte-identical database), stale capture, interrupted import, uncertain model job, uncertain outbox delivery, missing outbox |
| `test_health_report_flags_quarantined_webhook_after_conflicting_replay` | Real inbox: verification, duplicate no-op, conflicting replay quarantines, secret absent from the report |
| `test_health_report_alerts_actionable_claim_cutoffs_only` | Eligible and missing-evidence cutoffs inside the window are alerted; ineligible and later ones are not |
| `test_configuration_custody_is_checked_without_reading_contents` | Protected, loose and missing files are classified, with file content absent from the report |
| `test_operator_commands_print_no_secrets_and_signal_attention` | CLI backup, verify, restore, acknowledge, revoke, status and health exit codes; no private key in output |
| `test_restore_blocks_native_preparation_and_new_mandates_until_reconciled` | The restore epoch blocks mandates and native preparation, acknowledgement happens once and is immutable, the original workspace is ungated |
| `test_deleted_host_store_cannot_reopen_a_revoked_workspace` | The workspace event keeps a revocation after host-store deletion |
| `test_repository_paths_are_refused_through_symlinks_and_case_variants` | Symlinked and case-variant repository destinations are refused |
| `test_backup_during_concurrent_writes_is_a_consistent_snapshot` | Backups taken during writes verify, and each credit's event and award stay together |
| `test_restore_staging_collision_and_corrupt_database_fail_closed` | A staging collision refuses; a corrupt database makes the health command exit 1 |
| `test_bounded_read_retries_only_follow_transient_failures` | Retries only after 503, network and 429 failures; 401, 403, grant, revocation and binding refusals are never retried; attempts bounded 1..3 |
| `test_transport_failures_are_typed_without_leaking_provider_detail` | `RampNetworkError` is a `RampError` with the unchanged safe message and no chained cause |

Mutation checks: eight targeted source mutations were each detected by their test. See [ADR 90](decisions/ADR-0090-operations-recovery.md).

Retained intermediate failure: the first run of `test_backup_restore_restart_preserves_authority_and_financial_state` compared the whole Ramp overview and failed only on `data_provenance.evaluated_at`, which is the current evaluation clock and not stored state. The test now strips only `evaluated_at`/`as_of` keys; every other field is still compared. A full-suite attempt started at `c52a5a4` was stopped at 12% (exit 143) because the working tree changed during the run. Its log is kept as aborted and is not counted as a result.
