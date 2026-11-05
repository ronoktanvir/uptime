# ADR 0053 — Local engineering dependency dashboard

## Decision

Serve a dependency-free HTML, CSS and JavaScript progress dashboard on loopback port8780. Store a sanitized, manually maintained snapshot of tasks, dependencies and evidence in `progress/data.json`. Compute status counts and graph depth from that snapshot. Show its update time, current age and a warning after six hours. A user-triggered refresh rereads the file.

## Alternatives and costs

The user requested a quick localhost HTML view and GitHub delivery. An authenticated route inside the finance application would couple engineering metadata to financial authorization. A frontend build system adds installation and maintenance costs for this small read-only artifact. A self-contained file URL avoids a server but complicates separate snapshot updates. The selected stdlib server requires only Python and serves the dedicated progress directory. Maintaining the snapshot remains an explicit operational cost.

## Independent review and disposition

The actual `claude-opus-5-5` review is session `2db2c33f-9f97-4c04-af61-b9d889fc6c72`, packet SHA-256 `bb73a50e4a3299c8b869c8f6264aeae1d12e9f2106bf96c4bf674130599c4597`. The complete [packet](packets/53-read-only-progress-dashboard.md) and [response](reviews/53-read-only-progress-dashboard.json) are preserved.

Accept the staleness objection and the symlink, directory-listing and DNS-rebinding findings. The server validates the exact loopback Host and port, confines resolved paths to the progress directory, rejects traversal and disables directory listing. Links accept HTTP and HTTPS protocols only. Graph loading rejects duplicate IDs, cycles and missing dependencies. Snapshot entries contain project status and public or synthetic evidence references. Credentials, customer records, private fixtures and runtime databases are outside the served directory.

The user already authorized this private repository and the requested Ramp-themed dashboard. Additional blanket confirmation would repeat that authorization. The visual treatment uses an Uptime wordmark and a restrained graphite/lime palette. Repository privacy is independently checked before pushing. Publication safety depends on inspecting content before publication because a later removal commit preserves history.

## Verification and falsifiers

Root executed eleven real HTTP tests covering GET and HEAD, loopback binding, foreign Host rejection, encoded traversal, an out-of-directory symlink and directory-listing refusal. JavaScript tests check graph ordering, cycle and dangling-edge refusal, URL schemes and the actual committed snapshot. CI runs these graph checks. Root also inspected the normal browser at desktop and mobile dimensions, filtered blocked tasks, searched the list, opened task dependencies and exercised expanded view and Escape. Browser warnings and errors were empty.

The displayed regression and audit counts name their tested source commit. They do not certify later changes. Any fabricated completion state, stale-data concealment, exposed file or unexplained evidence link invalidates the dashboard's reporting claim. The dated snapshot remains reviewable in Git history.

## Rollback

Stop the loopback process and revert the dashboard commits if the view is unsuitable. Preserve source history and the separate finance application. If private information is discovered, stop serving and pushing immediately, then assess the actual exposed data and authorized remediation.
