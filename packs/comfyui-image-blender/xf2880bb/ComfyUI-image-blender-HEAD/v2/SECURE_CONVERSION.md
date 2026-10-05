# Secure conversion record

Upstream is pinned at `f2880bb8db5ed007823eccc43b8918728c4890dc`.

## Census

- Python nodes: 1 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- JavaScript-only nodes: 0.
- Backend routes: 0.

The actual package loader registers only `ImageBlender`. All 88 choices in its
ordered blend-mode enum resolve to pack-owned Torch functions. The repository
has no frontend, routes, models, downloads, or executable assets.

## Behavior and authority

The conversion preserves node and display IDs, category, schema order, all 88
ordered mode names, opacity composition, matched-mask blending, mismatched-mask
fallback, RGB assertions, batches, and output clamping. The upstream blend
modules, enum, and helpers are copied byte-for-byte into V2.

The algorithm remains in the pack and uses the permissioned raw-compute tier.
It has no file, network, model, storage, graph, backend, frontend, subprocess,
or other host authority. Execution adds batch, dimension, and total-pixel
bounds around valid BHWC input without changing valid results.
