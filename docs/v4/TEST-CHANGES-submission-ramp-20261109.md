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

### Rebuilt verified record (Ronok's 14:00 and 14:03 PST read-only captures)

The verified record changed from a whole packaged capture (schema `/1`) to a minimal excerpt (schema `uptime-ramp-verified-excerpt/2`), with vendor name and invoice number. These tests in `tests/test_ramp_context.py`, already integrated, changed for that reason:

- **`test_verified_record_is_the_exact_demo_bill_with_the_person_attributed_note`:** now asserts that the vendor name equals both the captured bill's `vendor_name` and the captured vendor record's `name`, instead of `None`. That was the coordinator's condition: a name only from captured records. It also asserts the invoice number, the new read time (22:00:38 UTC), `started_by: PERSON`, `excerpt: true` and the partial-list facts. The identity, link, binding, attribution and credit assertions are unchanged.
- **`test_verified_record_file_holds_no_credentials_hashes_or_query_strings` renamed to `test_verified_excerpt_holds_only_the_panel_records_and_no_private_fields`:** the same credential and association-field assertions still run. It now also requires:
  - only the bill, its vendor, its comment and linked credits;
  - no email, memo, contact, message or URL text in the records;
  - one vendor name committed;
  - no full capture.
- **`test_verified_record_refuses_anything_that_does_not_verify`:** grew from 7 cases to 12. The cases now act on the excerpt structure: excerpt checksum, vendor identity, comment parent, finding digest, `started_by` and `records_committed`. Each case except `checksum` recomputes the excerpt checksum, so the specific check is what refuses.
- **`test_northwind_terms_cannot_attach_to_the_verified_demo_bill`:** builds its view from the excerpt records and passes the verified credit read-back. Same two assertions (no attachment, no contract ID).

One more test changed in `web/ramp_ui.test.cjs`:

- **`the verified Ramp record panel is a dated saved record with its own business, beside an attributed worklist`:** the expected text is now "Saved record read from Ramp 2026-11-09 22:00 UTC, started by a person. Not a live read." plus the excerpt note. The coordinator's custody wording.

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

- **Verified record (coordinator option A):** 11 more cases in `tests/test_ramp_context.py`:
  - the record is the exact demo bill with the person-attributed note;
  - the file holds no credentials, hashes or query strings;
  - anything that doesn't verify is refused (7 cases: schema, URL, digest, bill, write flag, capture checksum, late association);
  - Northwind terms can't attach to the verified bill;
  - the panel appears only beside the packaged presentation worklist.

  One more case in `web/ramp_ui.test.cjs`: the panel is a dated saved record with its own business, beside a worklist attributed to the earlier installation.
- **Fixture names:** the test vendor name `"DocuSign"` was replaced with `"Example Vendor"` in this branch's new tests, so no vendor name looks inferred (coordinator condition 4).

- **Packaging tests in `tests/test_ramp_context.py`:** `test_packaging_keeps_only_the_bill_its_vendor_and_its_comment` and `test_packaging_refuses_an_association_that_does_not_verify` (which also covers the new `scripts/ramp_package_verified_record.py`, which never overwrites).

## Failed first attempts

- After the first workspace change, `tests/test_ramp_award_procedural.py` failed with `Invalid snapshot checksum or schema`. The workspace view adds a local `status` key, and the strict snapshot validator inside the credit read-back refused it. Fixed in `ramp_context` by passing the capture without that key. Not fixed by loosening the validator.
- A first combined run passed the extra test files as one argument and ran nothing (`no tests ran`). Rerun with explicit paths.
- The first packaging tests gave the second bill a vendor the test double doesn't serve, and raised `StopIteration`. They now use the double's second vendor.
- One packaging assertion checked that "PRIVATE" was absent from the excerpt. The double uses "PRIVATE" as its vendor *name*, which is meant to be kept. The assertion now checks what was intended: comment records carry only ID, parent and time, never text.
- The first `checksum` refusal case changed a bill that was already `PAID`, so nothing changed and the loader correctly accepted the file. The test now flips another bill's status; the loader is unchanged.

## Results

- `tests/test_ramp*.py`, `tests/test_credit_steps.py`, `tests/test_reconciliation.py`, `tests/test_film_ramp_v4.py`, `tests/test_operations_recovery_90.py` and `tests/test_workspace_ui_v4.py`: 1,144 passed, 1 warning in 46.82s at `318668b`. **1,155 passed, 1 warning in 27.71s** with the verified record.
- `node --test web/*.test.cjs tests/helpers/*.test.cjs`: 108 passed at `318668b`; **109 passed, 0 failed** with the verified record.
- Rebuilt record, on `7472ecb` plus this change: the focused Ramp set gave **1,162 passed, 1 warning in 25.51s**; `node --test web/*.test.cjs tests/helpers/*.test.cjs` gave **114 passed, 0 failed**; `scripts/check_repo.py` passed.
- The full suite is left to the coordinator after the integration merge.
