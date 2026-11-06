# Decision80: ground aggregate filing deadlines in complete source assertions

Status: implementation under verification. Base `c5dd4e4`. Inputs are authored public sources and local source/test code.

The aggregate fixed-filing validator must bind its exact timestamp and endpoint comparator to the claim obligation. A recipient phrase such as “by the vendor” cannot establish an inclusive deadline, and a source stating that no deadline applies cannot be compiled into one.

## Confirmed defect and reach

At unchanged base `c5dd4e4`, the exact Decision77 finding quote is accepted by `vendor_service_month.validate`. A manually authored full aggregate April source containing that clause also compiles. With existing authored verified observations, direct evaluation returns `ELIGIBLE`, `$10.00`, `TIMELY` using the invented inclusive cutoff. A second execution through the existing scripted meaning-review helper returns the same. The aggregate control has no source/evidence literal roles requiring semantic bindings, so direct evaluation does not require a binding context.

This establishes local compiler/evaluator reach. It does not establish that a model extracted the incorrect proposition, a registry promoted it, an actual person approved it, a claim was sent, or a credit was awarded. [The preserved before evidence](reviews/80-before.json) records these distinctions. The safe result is compilation refusal before producing an eligibility preview from an unsupported filing condition.

## Chosen correction and criticism

Use one finite full-block filing parser inside the existing fixed_filing validation path. Bind the mandatory claim obligation, exact UTC timestamp, comparator and optional relative days in one supported assertion. Permit only enumerated compatible companion assertions. Explicitly distinguish a recipient phrase from a comparator followed by the timestamp. Refuse negative, conditional, contradictory and unconsumed material. Preserve source citations and existing full-compiler arithmetic that compares relative days to the fixed period end.

The single actual tool-free Opus criticism identified recipient/comparator confusion, negated “exactly permitted” matching, “non-inclusive” substring matching, relative days borrowed from another obligation and mutation before conflict validation. The decision accepts explicit comparator rules, same-obligation clocks, finite companions and atomic updates, including repeated-identical idempotence and conflicting stored-day refusal.

The criticism proposed ignoring arbitrary non-filing sentences. That recommendation is rejected: it could erase unsupported material, and the known CalyxQuay filing block consists entirely of supported filing assertions. Full-block finite matching can preserve its exact bytes. The proposed extra whitespace restriction is also unnecessary here: the compiler already applies its documented normalization before calling this validator. No global normalization or source capture behavior changes.

## Ownership, compatibility and authority

Only fixed_filing helpers/constants/branch in `vendor_service_month.py` and new tests/docs are in scope. Decision77 period handling, resource scoped deadlines, arithmetic, evidence custody, model runtime, UI and action authority are unchanged. No fixtures, staged proposals or preexisting tests are rewritten.

The three known valid blocks are the original Heliograph relative-plus-absolute deadline, the April receipt deadline and the full CalyxQuay filing/explicit-equality/late-no-credit block. Their compiled manifests were frozen before implementation for exact canonical JSON comparison afterward. Final checks include unchanged public intake and Northwind setup to avoid repeating the earlier period compatibility regression.

The [packet](packets/80-aggregate-filing-grounding.md) records alternatives and falsification controls. The [public model receipt](reviews/80-aggregate-filing-model-receipt.json) retains exact model/session/tool inventories, final criticism, edit counts and stream hashes; full startup-spooled process streams remain protected outside Git. The lead runs tests/Git and freezes source before final verification. Root owns integration and its full suite.

Rollback: revert the bounded implementation commit. No stored source, receipt or evidence migration is needed.

## Implementation boundary

The delegated patch adds one filing assertion helper and three finite grammar tables, and replaces only the fixed_filing branch. The lead retained optional-article/singular/plural claim wording with explicit obligations and comparator binding. Relative counts are limited to 1–999 decimal days with no leading zero; unsupported origins, companion wording and other material remain refused. This is finite source support, not general contractual interpretation. Existing interpreter-dependency review checks remain in force; no stored approvals are migrated or manufactured.

[The exact test ledger](../TEST-CHANGES-80.md) distinguishes new controls from unchanged compatibility checks.
