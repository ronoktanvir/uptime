# Phase83 vendor runtime session recovery

V4 now injects the application's existing account/sign-in callback. Every V4 API request is bound to its current mounted view; a401 from that view revokes all V4 controls before requesting sign-in. Detached responses cannot replace the new view. The application clears cached draft/write capability and invalidates pending page loads while presenting sign-in. Existing credentials, server session policy and signed requests are unchanged.

A401 does not trigger any POST retry. After signing in, an explicit exact-source access check recovers the server's existing job; candidate installation still needs an explicit reviewed overlay and confirmation. Ordinary network-unknown responses retain their existing reconciliation requirement. Failed or stale read requests cannot become successful records or approvals.

Polling now updates the live job banner when the displayed job state changes. Repeated terminal results preserve a later overlay-review message and its typed input. Older overlapping status reads cannot replace a newer terminal result, and source edits revoke previously detached candidate controls.

The original actual browser incident showed generic uncertainty and unavailable state, without a captured raw status. A separately authored regression expires a disposable server session, captures the resulting401, and exercises the real sign-in recovery against the durable queue. The same job remains succeeded, no candidate exists before the new confirmation, and generation/provider counts stay at one. That control is browser/runtime evidence with an explicit provider double; it does not rewrite the original incident or claim a new model extraction result.

This is routine parity with the existing account recovery design under decisions73/74, implemented natively as authorized by the lead. No new architecture/model review was run. Exact tests and retained intermediate failures are in [the phase83 ledger](TEST-CHANGES-83.md).
