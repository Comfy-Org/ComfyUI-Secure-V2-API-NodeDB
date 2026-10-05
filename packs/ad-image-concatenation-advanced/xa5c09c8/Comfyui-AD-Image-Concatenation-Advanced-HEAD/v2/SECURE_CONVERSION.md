# Secure Nodes V2 conversion

Upstream: <https://github.com/BigStationW/Comfyui-AD-Image-Concatenation-Advanced>

Pinned commit: `a5c09c8a893032dc4a3a3d5ff32fbd195883fbda`

Release: `xa5c09c8`

## Census

- Backend: 1 supported, 0 rejected, 0 pending.
- Frontend: 0 extensions.
- Routes and settings: none.

The conversion preserves the registered node ID and schema, optional inputs,
first-frame behavior, centered horizontal and vertical composition, cumulative
list output, four resampling modes, resize order, quantization, and fallback to
the original first image when composition fails.

## Security boundary

The node declares `raw` for its pack-specific Pillow composition algorithm.
Inputs and generated canvases are bounded before allocation. The guest returns
opaque `ImageRef` values and has no filesystem, network, subprocess, model, UI,
or ambient host authority.

The pinned upstream project metadata names a `LICENSE` file that is absent from
the repository. The conversion records that provenance fact and does not invent
a license.
