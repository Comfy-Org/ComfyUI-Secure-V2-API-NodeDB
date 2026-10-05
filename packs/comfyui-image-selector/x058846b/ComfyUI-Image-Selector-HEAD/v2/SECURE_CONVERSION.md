# Secure conversion record

Upstream is pinned at `058846b177626a226590d355a342ae8f364591ac`.

## Census

- Python nodes: 4 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- Backend routes: 0.

## Behavior

The conversion preserves the one-based comma/range syntax, including open
ranges, duplicate selections, the legacy zero/negative-index behavior,
malformed-segment skipping, empty-selection passthrough, and batch-major
duplication order. Inputs are bounded to 4,096 selected entries and a 64 KiB
selector expression.

IMAGE and LATENT resources remain opaque and require no permissions. Latent
selection/repetition deliberately preserves canonical `noise_mask`,
`batch_index`, and other metadata that the legacy implementation discarded.
This fixes metadata loss without changing the selected sample values or order.
