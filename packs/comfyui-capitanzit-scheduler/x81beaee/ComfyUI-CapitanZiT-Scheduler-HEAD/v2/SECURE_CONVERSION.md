# Secure Nodes V2 conversion

Upstream is pinned at `81beaee4331df26ba040e0c6103766702651dfa0`.

## Census

- Python nodes: **4** (`CapitanZiTLinearSigma`, `FlowMatchSchedulerKleinEdit`,
  `FlowMatchSchedulerSmoothCosine`, `SamplerMinimalChangeFlow`)
- Frontend extensions: **1** (`Comfy.KleinEditSchedulerGraph`)
- HTTP routes: **0**
- Global scheduler registrations: **1** (`capitanZiT`)

All three sigma algorithms retain the pinned numeric behavior and bounds. The
Klein schedulers preserve model identity. The global `capitanZiT` mutation is
replaced by a declarative scalar-only scheduler provider. The Minimal Change
Flow sampler remains pack-owned but runs through the invocation-only retained
sampler broker, so model evaluation and progress callbacks stay host-owned.

The Klein graph is a per-node V2 canvas. It preserves parametric XY control,
draw mode, movable schedule points, edge control of `denoise`/`sigma_min`, and
workflow restoration through the original `draw_mode` and `custom_sigmas`
widgets. Pointer capture and teardown are scoped to that canvas. It uses no
ambient DOM, renderer globals, network access, routes, storage, or filesystem.

Capabilities are limited to `raw` tensor transfer for SIGMAS nodes and
`closures` for the custom sampler. The frontend needs no permission.
