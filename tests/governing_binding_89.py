"""Authored reviewed-binding fixture for finding F5 (Ronok, 2026-11-09: "require reviewed binding").

A source that names no agreement cannot bind an overlay agreement by itself. Authored test
overlays for such sources therefore carry an explicit governing-terms attestation tied to the
exact compiled document. This is fixture data for local tests, not evidence that any person
reviewed a real customer agreement.
"""
UNAMENDED = ["scope", "measurement", "exclusions", "tiers", "fee_basis", "rounding", "filing", "remedy"]


def reviewed_binding(manifest, overlay):
    if manifest.get("agreement") is not None:
        return dict(overlay)
    document = manifest["document"]["sha256"]
    return dict(overlay, governing_terms=dict(verified=True, agreement=overlay["agreement"], source_sha256=document,
                                              effective_from=manifest["effective"][0], source_ref="authored-local-terms-copy",
                                              evidence_sha256=document, unamended_terms=list(UNAMENDED)))
