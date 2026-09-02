# Secure Nodes V2 conversion

Pinned upstream commit: `3617559bcb9d15ff60b24c6800701402eb2cd478`.

## Census

- Backend `InpaintCropImproved`: supported.
- Backend `InpaintStitchImproved`: supported.
- Frontend `inpaint-cropandstitch.showcontrol`: supported.
- Rejected: none.
- Pending: none.

## Security boundary

The crop, pre-resize, mask morphology, context selection, outpaint, blend, and
stitch algorithms remain pack-owned. Both nodes accept and return typed image
and mask refs and declare the permissioned `raw` compute tier. The custom
`STITCHER` socket is a bounded mapping of JSON metadata and typed `IMAGE`/
`MASK` refs; Stitch validates its exact keys, batch lengths, scalar types,
algorithms, device mode, and ref leaves before materializing any tensor.

The V2 backend imports no ambient ComfyUI modules and has no filesystem,
network, subprocess, model-loading, runtime-install, or host-mutation access.
CPU mode requests CPU placement through the typed image ref. GPU mode requests
the host's managed GPU placement for the image and moves the related raw mask
buffers to the same device inside the isolated compute realm.

The frontend extension uses `/comfy/api/v2.js` definition hooks, widget handles,
additive change subscriptions, and `setDisabled`. It does not reach a parent
window or DOM and does not replace widget descriptors or node methods.

SciPy is the only pack runtime dependency beyond the trusted runtime base; it
implements the pinned grayscale hole-fill, morphology, and Gaussian behavior.
No API, vendor, dependency, credential, or intended-behavior gap remains.
