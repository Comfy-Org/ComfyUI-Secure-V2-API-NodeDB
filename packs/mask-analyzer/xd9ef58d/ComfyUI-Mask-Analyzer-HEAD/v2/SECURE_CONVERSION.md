# Mask Analyzer conversion ledger

Upstream: https://github.com/imk-design/ComfyUI-Mask-Analyzer
Pin: `d9ef58d14e9d016a8888cb3fae50d2cf1059ab8e` (`xd9ef58d`).

Census: 2 Python registrations (`MaskAnalyze`, `MaskStrategySwitch`) supported,
0 rejected, 0 pending. No frontend extensions, JS-only nodes or routes. Exact
schemas, defaults/bounds/steps, categories, display names and all output names
remain. `algorithm.py` is byte-identical to pinned `mask_analyzer_router.py`.

Analyzer: public `SDK_REFS=False` raw-compute tier only. Switch: public value mode,
zero permissions. No private constructors or host model/files/network/storage/
graph services. Managed NumPy/Torch/OpenCV runtime dependencies are declared;
the original optional-OpenCV import and NumPy fallback remain in the algorithm.
Both native OpenCV and forced NumPy fallback are compared against pristine.

Preserved details: only the first frame of BHW masks is analyzed; threshold is
inclusive; connectivity is 8-way; bounding aspect uses every thresholded pixel
even if components are area-filtered away; small area comparison is inclusive;
score caps/ordering and overlay-before-direct strategy priority remain exact.
Empty masks produce the original seven-scalar direct result. Switch strips and
lowercases strings, and unknown strings select direct. No pixel normalization
or global RNG/warnings changes are introduced.

Resource boundary: strided HW or BHW MASK tensor, nonempty axes up to 8192,
batch 1..64, full input up to 16,777,216 elements, first frame up to 1,048,576
pixels. The conservative label/array projection is 12*(pixels+1) elements, capped
at 12,582,924; DFS work is 9*pixels, capped at 9,437,184. Bounds run before the
algorithm can copy to CPU, allocate binary/labels/stats/visited arrays or enter
DFS. Real NumPy-compatible Torch float, bool and integer dtypes are accepted;
bfloat16/complex/unsupported layouts are rejected rather than silently converted.
The MASK socket expects tensors; legacy list/NumPy convenience inputs outside
that contract are not accepted by this typed wrapper. NaN/Inf pixels retain the
original threshold arithmetic; schema controls must be finite. Switch strings
are at most 4096 UTF-8 bytes; integer values retain declared schema bounds.

Persistence disposition: no durable state. Only workflow input controls and
render MASK data are used; no editable files, caches, counters or endpoints.
Fresh pack filesystems and separate guests prove same-input continuity and
alternate-input isolation. No durable cloud KV claim is needed.

MIT license is copied exactly. CPU conversion/analysis is verified; GPU input
transfer/streams and unsupported dtype paths are not claimed as GPU-tested.
No shared API/runtime/docs/registry changes or API/dependency gaps. Verification
includes actual loader/schema census, native/fallback differentials, input/label/
DFS resource rejection before compute, real guest raw denial and zero-capability
switch, outer typed scalar outputs, fresh renders, canonical stubs, manifest,
cache hygiene and byte-exact pristine-to-V2 patch reconstruction.
