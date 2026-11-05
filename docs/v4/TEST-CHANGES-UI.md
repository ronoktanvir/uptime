# UI test changes

- `web/ramp_ui.test.cjs`, `pagination bounds 1000 records while all types are selectable; source and money stay exact`: removed the assertion for a repeated row disclaimer. Native amount, finding amount, exact source, freshness, incomplete coverage, pagination and permission assertions remain.
- `web/ramp_ui.test.cjs`, `detail and plan are encoded GETs, never POST; receipt is scoped and unsafe link stays absent`: checks the actual unchanged `SYNTHETIC_INVOICE_CAP` finding kind and ordinary Contract finding heading instead of the removed repetitive scenario banner. GET-only, scoped receipt, secret and unsafe-link protections remain.
- `tests/test_ramp_ui_v4.py`, `test_ramp_browser_navigation_and_read_only_plan`: changed only the provider link’s accessible name from “Open record in Ramp sandbox” to “Open record in Ramp”; its exact sandbox URL and all read-only/navigation assertions remain.
