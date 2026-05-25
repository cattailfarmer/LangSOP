# LangSOP Agent Instructions

LangSOP uses SOP files as its specification and authority layer. Treat `docs/canonical/*.sop` as processed authority only when the file contains a valid satisfaction signature using protocol UUID `ad10f10f-d506-48ef-a805-f8b0a133766c`.

Preserve source documents under `docs/source/` unchanged. Derived specifications belong under `docs/exploded/` or `docs/canonical/`.

When implementing runtime code later, keep LangGraph checkpoints as execution state and keep truth-bearing authority in SOP artifacts and the typed authority kernel records.

Use work packets only as generated execution views; do not let a packet replace the whole capability field.
