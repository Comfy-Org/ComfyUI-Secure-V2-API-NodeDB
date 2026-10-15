# Conversion evidence

- Upstream: https://github.com/fexploit/ComfyUI-AutoTrimBG
- Pin: `e11ea12bcd88d090520c68b494635abb970f1776`
- Actual loader census: 1 Python node, 0 frontend extensions, 0 routes
- Supported: RonLayers/TrimBg: RonLayersTrimBgUltraV2; rejected/pending: none
- Authority: `SDK_REFS=False`, `SDK_PERMISSIONS=("raw",)` only

The crop algorithm and image helpers are byte-exact pinned copies. Differential
tests cover padding/clamping, mask intensity, RGB/RGBA, crop/preview bytes,
float32/64, first-mask selection, empty masks, and helper behavior. The typed
BOX output remains a four-coordinate tuple or None. The public
`await sdk.ValueRef.from_value(box)` carries nonempty tuples through the bounded
structured-value codec, preserving their type across the plain JSON wire. It
does not add authority or a new API; the raw permission already covers it.
Real isolated guest and outer executor tests prove IMAGE/MASK/BOX outputs and
raw denial. CPU paths are tested; GPU-specific device execution is not exercised.

The wrapper bounds resources and validates published padding, finite tensor
values, layouts and matching dimensions before calling the pinned algorithm.
The original multi-image squeeze/PIL path is invalid; it is rejected explicitly
rather than inventing batched crop semantics. No successful output behavior is
otherwise altered. Demonstration PNG and release CI stay pristine-only.
