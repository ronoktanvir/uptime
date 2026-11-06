# Test changes: public proposal operator configuration

No existing test was changed. `tests/test_public_proposal_config.py` adds 20 cases covering full readable request retention, exact reviewed hashes, explicit public authorization, expiry bounds, atomic preservation of an existing catalog on invalid updates, malformed/client-flag refusal, narrow draft signing paths, private configuration and refusal of arbitrary processing flags or unknown kinds.

The configuration and shared queue tests passed **55 tests in 1.98s**. The broader configuration, queue, draft-authority, vendor-catalog and signed journey suite passed **165 tests, 1 warning in 48.61s**. The warning is the existing Starlette/httpx deprecation. These checks used local test providers, with no model or Ramp calls. Application worker integrations and the root merge suite supply the subsequent composed proof.
