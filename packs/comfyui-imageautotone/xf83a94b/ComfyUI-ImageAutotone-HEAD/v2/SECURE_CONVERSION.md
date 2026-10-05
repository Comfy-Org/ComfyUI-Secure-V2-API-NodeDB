# Secure Nodes V2 conversion

Upstream: <https://github.com/SparknightLLC/ComfyUI-ImageAutotone>

Pinned commit: `f83a94b5d696e53f20a3a9d853f8e594981e438b`

Release: `xf83a94b`

## Census

- Backend: 1 supported, 0 rejected, 0 pending.
- Frontend: 0 extensions.
- Routes and settings: none.

The conversion preserves the registered `ImageAutotone` ID, schema, independent
RGB histogram clipping, color remapping, batch behavior, alpha preservation,
and upstream uint8 quantization.

The upstream node advertises six-digit hex colors, but converts the parsed bytes
to a zero-dimensional NumPy string and crashes when it indexes the first color
channel. The conversion fixes that implementation defect: `#RRGGBB` now has the
same result as the equivalent comma-separated RGB value.

## Security boundary

The node declares `raw` because histogram calculation and per-channel color
mapping are pack-specific tensor computation. Input tensors, dimensions, batch,
colors, and clip percentages are bounded before processing. The guest returns a
new opaque `ImageRef`; it has no filesystem, network, subprocess, model, UI, or
ambient host authority.

The pinned upstream repository does not contain a license file. This conversion
records that provenance fact and does not invent a license.
