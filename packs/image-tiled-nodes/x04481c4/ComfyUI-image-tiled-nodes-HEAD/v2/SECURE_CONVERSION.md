# Image Tiled Nodes conversion ledger

Upstream: https://github.com/tuki0918/comfyui-image-tiled-nodes
Pin: `04481c4ca008dfd394d9b5b9b705218351670b9c` (`x04481c4`).

Census: 2 Python nodes supported (`TiledImageSplitter`, `TiledImageMerger`),
0 rejected, 0 pending. No frontend extensions, JS-only nodes or routes.
IDs, display names, categories, input order/defaults/bounds/steps and output
types/names remain exact, including the custom `TILE_INFO` socket.

`algorithm.py` is byte-identical to the pinned `nodes.py`. Wrapper validation
checks schema controls, projected loop counts/allocations and untrusted metadata
before entering the original algorithm. `SDK_REFS=False`, permissions `raw` only.
IMAGE/MASK tensors use declared outer-executor wrapping; TILE_INFO is bounded
JSON data, not a filesystem path, host object or arbitrary executable type.

Preserved semantics: batch/row/column tile ordering, edge backshift, overlap-based
feather widths (not full-tile-based), multiplying corner gradients, float32 masks,
bilinear resizing of processed tiles, float32 merging/weights, missing-tile partial
merge, ignoring extra image tiles, black uncovered pixels and final [0,1] clamp.
When overlap makes either grid axis nonpositive, the legacy fallback returns the
original image batch, a 2D float32 CPU zero mask, and empty positions. The merger
with zero images still uses three output channels, irrespective of input shape.
These quirks are tested, not silently normalized. No promise of exact identity
across the guest wire is made; pack-local algorithms do not mutate their inputs.

Resource boundary: strided floating BHWC with 1..4 channels; input tensor at most
16,777,216 elements; axes at most 8192; split input batch 1..64; at most 512 tiles
and positions, and at most 512 batch/row iterations even for empty-column grids.
Projected tile/mask storage or merger accumulator-plus-slot work
is limited to 33,554,432 elements. All checks precede tensor algorithms and loops.
The merger accepts a closed JSON shape with finite bounded feathering, valid
batch indices and nonnegative in-canvas positions. Optional `batch_size` defaults
to 1; unused row/col metadata is optional but bounded. Hostile metadata or requests
outside these bounds fail without allocating an invented output. NaN/Inf image
pixels retain legacy arithmetic; control numbers must be finite. CPU dtype/device
behavior is tested; GPU-specific allocation/stream behavior remains unproven.

Persistence disposition: no durable state. Inputs and TILE_INFO describe only
workflow/render data; there are no editable files, caches, endpoints or process
counters. Fresh pack filesystems and fresh guests reproduce computations and
isolate alternate inputs. No durable KV backing-store claim is needed.

MIT license is copied byte-for-byte. No shared API/runtime/docs/registry changes
or dependency/API gaps. Evidence includes actual loader/schema census, exact
differential split/merge/resize/feather/fallback cases, hostile metadata and bounds
rejection-before-compute, real guest split-to-merge, raw denial, outer declared
types, fresh renders, canonical stubs, manifest and pristine-to-V2 patch roundtrip.
