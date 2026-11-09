# Test changes: `work/submission-ramp-20261109`

Every changed existing test is listed here by exact name and reason. New tests are listed separately. Failed first attempts are kept.

## Changed existing tests

**`tests/test_ramp_records_v4.py`, shared `Reader` fixture.** Two fixture values changed, and one test gained assertions:

- **Bill fixture:** `"vendor": {"id": VENDOR, "name": "PRIVATE"}` became `"name": "Example Hosting Co"`.
- **Vendor fixture:** `"name": "PRIVATE"` became `"name": "Example Hosting Co"`. Its `display_name`, contacts, memos, URLs, merchant names, comment text, user emails and tokens still carry `"PRIVATE"`.
- **`test_default_legacy_off_and_full_snapshot`:** gained three assertions. The bill's `vendor_name` is kept, `invoice_number` is `None` when Ramp sends none, and the vendor record's `name` is kept.

Reason: role 3 task 3 asks for vendor names and invoice references in the worklist. The records sanitizer now keeps two bounded, exact display fields: the bill's `vendor.name` as `vendor_name`, plus `invoice_number`. It also keeps the vendor record's `name`. Before this change, nine tests failed only because the fixture used `"PRIVATE"` as the vendor name:

- `test_default_legacy_off_and_full_snapshot`
- `test_agreement_query_and_documented_payee_uuid_and_linked_po`
- `test_unsafe_next_never_followed_or_saved` (6 parameters)
- `test_linked_vendor_duplicate_competing_payload_cannot_override_detail`

**No privacy assertion was removed.** Every `assert "PRIVATE" not in json.dumps(...)` still runs and still covers every other private field. In `test_linked_vendor_duplicate_competing_payload_cannot_override_detail`, the competing list entry's `'HOSTILE PRIVATE'` name must still never appear. That now also checks that the vendor detail record's name wins over the list entry's.

## New tests

- **`tests/test_ramp_context.py`, 13 cases:**
  - a partial capture is never a complete account;
  - per-bill comment coverage isn't counted as a list;
  - the packaged November 5 capture reports its real gaps, with names shown as not captured;
  - links come only from Ramp or an operator-observed URL, never a pattern;
  - a finding attaches only through a reviewed exact binding;
  - Northwind or hypothetical terms never attach to the demo bill;
  - the person-posted note stays attributed to the person, using the committed receipt's real IDs;
  - the note is unattributed without the verified business (2 cases);
  - a receipt alone never creates a Ramp comment or confirmation;
  - a changed comment time isn't the person-posted note;
  - Ramp credit status comes only from both-sided reads;
  - local-ledger activity never appears as a Ramp confirmation.
- **`web/ramp_ui.test.cjs`, 4 cases:** the partial-capture statement and the complete statement; vendor name, invoice and verified link, with a missing name stated and an unsafe link dropped; a finding amount withheld without an exact binding; the record page's Ramp identity, freshness, link basis and person attribution, with no local confirmation.

## Failed first attempts

- After the first workspace change, `tests/test_ramp_award_procedural.py` failed with `Invalid snapshot checksum or schema`. The workspace view adds a local `status` key, and the strict snapshot validator inside the credit read-back refused it. Fixed in `ramp_context` by passing the capture without that key. Not fixed by loosening the validator.
- A first combined run passed the extra test files as one argument and ran nothing (`no tests ran`). Rerun with explicit paths.

## Results

- `tests/test_ramp*.py`, `tests/test_credit_steps.py`, `tests/test_reconciliation.py`, `tests/test_film_ramp_v4.py`, `tests/test_operations_recovery_90.py` and `tests/test_workspace_ui_v4.py`: **1,144 passed, 1 warning in 46.82s**.
- `node --test web/*.test.cjs tests/helpers/*.test.cjs`: **108 passed, 0 failed**.
- The full suite is left to the coordinator after the integration merge.
