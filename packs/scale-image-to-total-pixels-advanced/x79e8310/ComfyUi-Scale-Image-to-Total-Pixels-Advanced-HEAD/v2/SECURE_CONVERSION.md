# Secure Nodes V2 conversion

Pinned upstream commit: `79e831097bb7a76ade3a28359300e62332086c42`.

## Census

- Backend: `ImageScaleToTotalPixelsX` — supported.
- Frontend: `scale_image_to_total_pixels_adv.resolution_label` — supported.

## Security boundary

The resize, crop, pad, clamping, and Lanczos algorithms remain pack-owned and
run in the isolated raw-compute tier. The node receives and returns typed image
refs and declares the `raw` permission; it imports no ComfyUI host modules and
has no filesystem, network, subprocess, model-loading, or package-installing
authority.

The frontend extension uses only `/comfy/api/v2.js`. Its cached-resolution
readout is rendered as a host-owned badge through definition lifecycle hooks,
replacing legacy access to `window.LiteGraph`, node method replacement, shared
canvas drawing, and timing-based layout mutation.

No API, vendor, dependency, hardware, or credential gap remains for this pack.
