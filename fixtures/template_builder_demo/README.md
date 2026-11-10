# Template builder samples: Halcyon Grid Platform Availability Addendum

Authored samples for the template builder (`docs/demo/TEMPLATE-BUILDER.md`). Halcyon Grid Services, Inc. and every
customer here are invented; no real customer signed these documents, and the signature blocks are unsigned.

- `halcyon-a.txt` (customer Save Time Inc): the contract a build starts from. Claude readers and the template builder see it.
- `halcyon-b.txt` (Larkspur Analytics LLC): the second-document check. The builder may be shown its text and which
  rules failed on it during a repair round, never its expected values.
- `halcyon-c.txt` (Brightwater Freight Co.): read after reviewer approval, by the template alone (no model call).
- `expected.json`: the authored terms of all three, in Uptime's canonical forms (percent as a decimal string without
  `%`, integers as digit strings, choices as option ids).

All three are the same form with different numbers, parties, dates and addresses. The form deliberately carries other
numbers a position-based rule would pick up (payment within forty-five days, termination on thirty days' notice,
two hours' emergency maintenance notice, the second-tier threshold repeated in the termination clause), so a rule
has to anchor on wording.

What these show: that rules written from one document read other documents of the same form. What they do not show:
how the builder copes with a differently worded contract from the same vendor, scanned documents, amendments, or any
real customer's paper.
