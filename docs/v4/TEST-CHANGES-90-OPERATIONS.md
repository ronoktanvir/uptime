# Workstream 90 operations test ledger

**No existing test function, fixture or assertion was changed.** All new controls are in `tests/test_operations_recovery_90.py`: 34 functions and 38 cases, two of them parametrized three ways.

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
| `test_restore_blocks_native_preparation_until_reconciled` | The restore epoch blocks native preparation; acknowledgement happens once and is immutable. Renamed within this branch from `..._and_new_mandates_...` when the mandate gate moved to its own commit. |
| `test_restored_workspace_refuses_new_mandates_until_acknowledged` | W0 gate: a restored workspace refuses new mandates until acknowledged; the original workspace is ungated |
| `test_never_restored_workspace_mandate_install_is_byte_identical` | W0 condition: with and without the gate, the same mandate leaves byte-identical database files and creates no restore table |
| `test_deleted_host_store_cannot_reopen_a_revoked_workspace` | The workspace event keeps a revocation after host-store deletion |
| `test_repository_paths_are_refused_through_symlinks_and_case_variants` | Symlinked and case-variant repository destinations are refused |
| `test_backup_during_concurrent_writes_is_a_consistent_snapshot` | Backups taken during writes verify, and each credit's event and award stay together |
| `test_restore_staging_collision_and_corrupt_database_fail_closed` | A staging collision refuses; a corrupt database makes the health command exit 1 |
| `test_bounded_read_retries_only_follow_transient_failures` | Retries only after 503, network and 429 failures; 401, 403, grant, revocation and binding refusals are never retried; attempts bounded 1..3 |
| `test_revocation_tenant_domain_is_pinned_to_the_workspace_id_domain` | W1 review note: the revocation tenant pattern equals the workspace `Id` domain, so D03 identity work cannot silently drift it; exact casing and length are enforced |
| `test_transport_failures_are_typed_without_leaking_provider_detail` | `RampNetworkError` is a `RampError` with the unchanged safe message and no chained cause |

| `test_deadline_alerts_exclude_filed_and_closed_claims_and_report_missed_cutoffs` | Only an unfiled open case is approaching; an awarded case and a case whose obligation has a real `reserve_claim` initial reservation are skipped; a cutoff 3 days past is reported as passed-unfiled and one 60 days past is not |
| `test_replay_workspace_does_not_raise_wall_clock_deadline_alerts` | Replay workspaces report deadlines as not evaluated and raise no wall-clock deadline findings |
| `test_clock_skew_and_capture_near_limit_are_reported` | A clock behind the capture is flagged instead of stale; the near-limit warning is INFO with an expiry and does not change status |
| `test_preflight_is_ready_for_a_safe_local_demo_machine` | A loopback-only, sandbox-configured machine with a fresh verified backup and protected configuration is READY, the database is unchanged and file contents are absent from the report |
| `test_preflight_flags_tunnels_exposed_ports_wrong_ramp_environment_and_low_disk` | Tunnelling clients, a wildcard listener, a non-sandbox Ramp environment, low disk and unavailable host probes all need attention; an idle port is INFO |
| `test_preflight_requires_a_recent_verified_backup_of_each_exact_workspace` | Backups are matched by exact binding, not filename; stale, tampered and missing backups and a missing workspace are each flagged |
| `test_preflight_reads_process_names_only_and_parses_listeners` | `ps` is invoked for the command-name column only; lsof field output parses IPv4, IPv6 and wildcard listeners |
| `test_preflight_command_prints_json_and_signals_attention` | The CLI prints the JSON report and exits 2 when attention is needed |
| `test_restored_reviewed_comment_delivered_after_backup_is_never_reposted` | W1 request (a): a REVIEWED comment delivered after the backup is restored as PREPARED, needs a fresh review, then records DELIVERED from the thread marker with zero new POSTs |
| `test_restored_dispatching_comment_can_only_be_reconciled` | W1 request (b): DISPATCHING becomes UNCERTAIN, execution refuses, read-back absence keeps it UNCERTAIN, and the health check shows the uncertain effect and the pending reconciliation |
| `test_restored_metadata_is_uncertain_and_unprepared_comments_are_unchanged` | W1 request (c): reviewed metadata becomes UNCERTAIN and execution refuses; a PREPARED comment is unchanged; stored plans are byte-identical |
| `test_outbox_restore_carries_quarantine_forward_and_refuses_mismatches` | Quarantine carries forward; a previous outbox without a target, a backup without an outbox, a non-outbox file, a foreign-tenant outbox, a byte-only rewrite and a content change are each refused |

Mutation checks: twenty-four targeted source mutations were each detected by their test, including the filed, closed-stage, replay, clock-skew, loopback, binding-match, tunnel, backup-age, backup-verification and all five outbox-fence checks. The outbox checksum mutant first survived because the table digests also caught the content change; a byte-only VACUUM case now pins the checksum on its own. Two first-run failures were test defects: an outbox created without opening W1's workflow had no tables, and a tamper `UPDATE` matched no rows. Both tests were corrected; no production code changed. See [ADR 96](decisions/ADR-0096-operations-recovery.md).

Retained intermediate failure: the first run of `test_backup_restore_restart_preserves_authority_and_financial_state` compared the whole Ramp overview and failed only on `data_provenance.evaluated_at`, which is the current evaluation clock and not stored state. The test now strips only `evaluated_at`/`as_of` keys; every other field is still compared. A full-suite attempt started at `c52a5a4` was stopped at 12% (exit 143) because the working tree changed during the run. Its log is kept as aborted and is not counted as a result. The first run of `test_revocation_tenant_domain_is_pinned_to_the_workspace_id_domain` failed because of a test defect: `BUSINESS.upper()` is unchanged when the UUID has no hex letters, so the case check tested nothing. It now uses a UUID with letters; the production code did not change.
