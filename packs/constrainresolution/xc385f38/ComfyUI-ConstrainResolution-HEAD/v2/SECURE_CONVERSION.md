# Secure Nodes V2 conversion

Upstream: <https://github.com/EnragedAntelope/ComfyUI-ConstrainResolution>

Pinned commit: `c385f389ee53cc15cd7f92edb76c1b35f45e0ba7`

Release: `xc385f38`

## Census

- Python nodes: 1 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- Backend routes and settings: 0.

The actual V3 entrypoint exports exactly `ConstrainResolution`. The secure
conversion preserves its schema, two constraint policies, five interpolation
methods, five crop anchors, aspect and dimension outputs, strict-mode errors,
pixel budget, and original-image passthrough.

## Security boundary

The node declares only `raw`. It materializes a bounded BHWC image tensor in
the isolated compute guest, performs the upstream resize/crop algorithm, and
returns a new opaque `ImageRef` plus the original ref. Lanczos is the same
Pillow algorithm used by ComfyUI's trusted `common_upscale`, copied into the
guest rather than importing host internals. The pack has no filesystem,
network, subprocess, model, UI, route, or ambient host authority.
