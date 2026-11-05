# Northwind integration checkpoint

Development source `dccfd1d` passes **2,819 locked Python tests**, but is **not accepted for release**. The independent review found stale fee authority surviving in approval/current financial projections, plus order-dependent lookup under ambiguous configuration. Three new failing probes remain preserved; the owner is repairing them. Main's prior accepted checkpoint is `c47094a`. This development checkpoint is published on `work/northwind-fee-authority` so collaborators can inspect actual progress and unresolved findings.

[Independent findings](evidence/governing-fee-65a-independent/review.json) · [Full regression receipt](evidence/verification-dccfd1d.json)

Implemented here: exact completed-step arithmetic, source-bound contractual fixed quantity, governing-fee contexts, authored Northwind order/amendment/invoices/usage and catalog monetary joins. January computes USD2,400 from the USD12,000 governing fee. The independent reviewer checked 500 Fraction-based arithmetic vectors. Those arithmetic checks do not establish current authority across every consumer; that is precisely what the new failures expose.

Parallel branches contain the bounded advance-billing increment, signed claim/denial/cure/award/local-post composition and clean UI. They are not yet accepted by this checkpoint. April application and the complete socket/browser rehearsal still need final integration. No fictional approval, signature, credit or receipt closes an actual-human or native Ramp proof gate.

The future-invoice chronology is now [ADR68](decisions/ADR-0068-future-invoice-application.md): March's USD1,000 price finding stays open; January's USD2,400 credit applies to the regular USD11,000 April invoice, leaving USD8,600. Do not substitute a later observation date for the original March invoice date.
