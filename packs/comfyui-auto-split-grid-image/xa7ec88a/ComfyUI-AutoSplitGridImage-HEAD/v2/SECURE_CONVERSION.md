# Conversion evidence

- Upstream: https://github.com/stormcenter/ComfyUI-AutoSplitGridImage
- Pin: `a7ec88a33a7d861b998b87668f6e45046b172364`
- Actual loader census: 2 Python nodes, 0 frontend extensions, 0 routes
- Supported: GridImageSplitter, EvenImageResizer; rejected/pending: none
- Authority: `SDK_REFS=False`, `SDK_PERMISSIONS=("raw",)` only

Both algorithm files are byte-exact copies of the pinned implementation. Public
IDs, schemas, category, unnamed outputs, cell order, first-image-only grid
processing, full-batch preview, border detection, Canny split selection, Lanczos4
resampling and even-dimension cropping are preserved and tested differentially.

The wrapper bounds RGB tensor input (HWC or BHWC), finite floating-point dtype,
batch (64), dimensions (2..8192), total input pixels (16,777,216), grid controls
(1..10), split-method choices and conservative output pixels (67,108,864).
These resource/error boundaries deliberately reject excessive or invalid inputs.
No private ref constructor, host file operation, network, graph or model API is
used. Demonstration PNGs/workflow and release CI stay in the pristine snapshot.
