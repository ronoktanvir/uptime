# Decision65 existing-test change ledger

No existing assertion or expected financial answer was weakened. The following tests gained explicit current pricing authority at their existing approval calls after independent review established that publication must revalidate the recorded fee dependency:

- `tests/test_governing_fees.py::test_positive_registry_lifecycle_requires_current_context_and_preserves_identity`: supplies the already issued context tuple to `catalog.act`; all previous outcomes, money and identity assertions remain.
- `tests/test_northwind_financial.py::test_ordinary_registry_test_lifecycle_and_export_keep_step_variant`: supplies independently reconstructed authenticated-adapter test contexts to `registry.act`; existing lifecycle, amount and variant assertions remain.

These are fixture setup changes, not assertion changes. The new `tests/test_governing_fee_current_authority.py` adds direct controls for the reviewer's duplicate lookup, stale check/actions, stale current case/rollup, historical byte preservation, exact application ownership and current signed-record reread findings. It includes a valid-authority positive control. The earlier core, source, exact rounding, deadline, package integrity, expectation isolation and advance tests were added in this stream; they did not replace older repository tests.
