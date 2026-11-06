# Decision 69 test changes

Changed existing test:

- `test_pinned_transport_refuses_changed_authority_or_execution_surface`: its fake successful stream now includes a matching exact model, session and successful terminal subtype. This makes the fixture a valid baseline for each existing authority failure; all original refusal assertions remain.

Added tests:

- `test_strict_model_json_rejects_ambiguous_or_nonfinite_values`: duplicate eligibility/amount keys, non-finite constants, numeric overflow and invalid UTF-8 are refused.
- `test_strict_model_json_preserves_exact_money_strings_and_utf8`: ordinary source text and exact decimal strings survive decoding.
- `test_public_transport_accepts_only_one_plain_matching_model_result`: preserves the valid plain profile and rejects model/session substitution, error/subtype/multiple results, the actually observed StructuredOutput surface, unexpected structured payload, non-object events and malformed JSON. Tool-surface failures prevent another call.

Focused run: `uv run --locked pytest tests/test_correspondence_model_transport.py tests/test_correspondence_interpretation.py -q --basetemp /Users/ronoktanvir/.local/share/uptime-engineering/tasks/pytest69-root` produced **98 passed, 1 warning in 2.11s**. No financial, source-authority or permission expectation was weakened.
