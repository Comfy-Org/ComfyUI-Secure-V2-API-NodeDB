# Conversion evidence

Upstream https://github.com/ShmuelRonen/ComfyUI-SVDResizer
Pin 6ea6b21455afc4f4c86506e2ea674cdb46fbcb4b (x6ea6b21).
Actual-loader census: 1 Python registration SVDRsizer supported, 0 rejected or
pending; 0 frontend/JS-only nodes/routes. Catalog's two-node count was stale.
The upstream orphan display-map key SVDResizer is retained; it does not match
SVDRsizer, so the visible fallback name remains SVDRsizer. License is copied.

Preserves all six ordered interpolation choices: nearest (NOT nearest-exact),
bilinear, bicubic, area, nearest-exact, lanczos. Keeps original proportional
min-ratio/Python round sizing, actual output width/height, Torch default
interpolation semantics, BHWC batch ordering, dtype and device. Lanczos performs
the same canonical ComfyUI clip/uint8/Pillow LANCZOS/float32 conversion followed
by restoration of original dtype/device. This small helper is migrated as
pack-owned code; no ambient comfy.utils import or private ref constructor.
Unused host imports, unused AST operator table and global warning suppression
are removed. No global state or canonical API is changed.

Security: SDK_REFS=False, SDK_PERMISSIONS=('raw',), no other authority. Finite
floating BHWC RGB/RGBA tensors, 1..64 frames, input H/W 1..8192; input and output
at most 16,777,216 elements. Width/height retain schema bounds 576..1024; step64
is UI metadata, not a backend divisibility constraint. Collapsed aspect-fit
dimensions and malformed/excessive inputs fail before compute/allocation;
no nearest substitution or approximate Lanczos. Legacy programmatic width0
fallback is outside its declared schema and is deliberately not accepted.

Persistence disposition: no durable state. Controls/linked image belong in
normal workflow serialization; the algorithm uses only execution arguments.
No endpoints, pack-local writes, counters, editable defaults, caches or browser
storage. Fresh pack-filesystem/fresh guest tests demonstrate no state carryover;
no cloud KV continuity claim is made or needed.

Evidence: actual-loader/schema/manifest census, all-mode pixel differentials,
nearest distinction, Lanczos quantization, proportional output sizing, batch and
dtype/noncontiguous behavior, malformed/resource rejection before compute,
input/RNG/warning-policy isolation; real guest raw denial and actual outer
IMAGE+INT outputs; fresh-render reset; canonical stubs/license; exact pristine
to V2 patch reconstruction and cache hygiene. CPU paths are proven; GPU-specific
device behavior is untested and not claimed.
