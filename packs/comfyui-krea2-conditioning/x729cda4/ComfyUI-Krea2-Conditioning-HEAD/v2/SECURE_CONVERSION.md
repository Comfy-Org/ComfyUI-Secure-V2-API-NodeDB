# Secure conversion record

Upstream is pinned at `729cda4fade982988a375b01928f515458407a5c`.

## Census

- Python nodes: 1 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- Backend routes: 0.

## Behavior and authority

The conversion preserves all four named profiles, custom comma/semicolon
weights, per-tap tensor scaling, optional RMS renormalization, global gain,
fallback scaling for non-divisible feature widths, recursive structures, and
conditioning metadata.

The node declares only `raw`, required to transform conditioning tensors inside
the isolated guest. Tensor sizes, structure depth, collection sizes, custom
weight text, and numeric ranges are bounded. It has no file, network, model,
UI, subprocess, or host-process authority.
