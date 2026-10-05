# Secure conversion report

- Upstream: `https://github.com/okgo4/ComfyUI-Mosaic-Mask`
- Pinned commit: `7871eb8cc512c63e6c6afaf465483b08f062ef52`
- Python census: **1 supported, 0 rejected, 0 pending**
- Frontend census: **0 extensions, 0 JS-only nodes**
- Routes: **0**

`MosaicMask` preserves the node/display IDs, schema, bundled templates,
OpenCV preprocessing and matching, grid-size filtering, dilation, top-N
connected-component retention, batch behavior, and float32 mask output.

The node has only the standard `raw` tensor capability. Image batches,
dimensions, channels, and total pixels are bounded before transfer to CPU.
Its pinned upstream repository does not contain a license file.
